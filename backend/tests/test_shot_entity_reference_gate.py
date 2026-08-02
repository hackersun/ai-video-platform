from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Chapter, Novel, StoryEntity
from app.services.owned_shot_entity_refs import resolve_owned_shot_entity_context


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


def _entity(user_id: str, novel_id: str, chapter_id: str, kind: str, name: str) -> StoryEntity:
    return StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
        entity_type=kind, name=name, canonical_name=name, is_approved=True,
        extra_data={"lifecycle": {"status": "approved"}},
    )


@pytest.mark.asyncio
async def test_unique_source_entities_fill_missing_model_refs_with_evidence(db_session: AsyncSession) -> None:
    user_id, novel_id, chapter_id = str(uuid4()), str(uuid4()), str(uuid4())
    source = "顾清霜在归墟塔举起青铜星盘，塔门随即开启。"
    db_session.add_all([
        Novel(id=novel_id, user_id=user_id, title="归墟"),
        Chapter(id=chapter_id, user_id=user_id, novel_id=novel_id, title="一", chapter_number=1, content=source),
        _entity(user_id, novel_id, chapter_id, "character", "顾清霜"),
        _entity(user_id, novel_id, chapter_id, "scene", "归墟塔"),
        _entity(user_id, novel_id, chapter_id, "prop", "青铜星盘"),
    ])
    await db_session.flush()

    result = await resolve_owned_shot_entity_context(
        db_session, user_id=user_id, novel_id=novel_id, chapter_ids=[chapter_id],
        as_of_chapter_id=chapter_id, source_text=source, shot_text="镜头推进，保持上一镜连续。",
    )

    assert [item["name"] for item in result["entity_refs"]["characters"]] == ["顾清霜"]
    assert [item["name"] for item in result["entity_refs"]["scenes"]] == ["归墟塔"]
    assert [item["name"] for item in result["entity_refs"]["props"]] == ["青铜星盘"]
    assert result["entity_reference_resolution"] == {
        "strategy": "exact_match_with_unique_source_fallback",
        "fallback_types": ["character", "scene", "prop"],
    }


@pytest.mark.asyncio
async def test_ambiguous_characters_are_not_silently_selected(db_session: AsyncSession) -> None:
    user_id, novel_id, chapter_id = str(uuid4()), str(uuid4()), str(uuid4())
    source = "顾清霜与沈砚一同进入归墟塔。"
    db_session.add_all([
        Novel(id=novel_id, user_id=user_id, title="归墟"),
        Chapter(id=chapter_id, user_id=user_id, novel_id=novel_id, title="一", chapter_number=1, content=source),
        _entity(user_id, novel_id, chapter_id, "character", "顾清霜"),
        _entity(user_id, novel_id, chapter_id, "character", "沈砚"),
    ])
    await db_session.flush()

    result = await resolve_owned_shot_entity_context(
        db_session, user_id=user_id, novel_id=novel_id, chapter_ids=[chapter_id],
        as_of_chapter_id=chapter_id, source_text=source, shot_text="镜头推进。",
    )

    assert result["entity_refs"]["characters"] == []
    assert result["entity_reference_resolution"]["fallback_types"] == []
