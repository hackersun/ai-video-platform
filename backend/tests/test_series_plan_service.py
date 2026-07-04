from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.models import Chapter, Novel
from app.services.series_production import SERIES_PLAN_KEY, build_series_plan, get_series_plan


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_novel_with_chapters(db_session: AsyncSession) -> Novel:
    user_id = f"user-{uuid4()}"
    novel = Novel(
        id=f"novel-{uuid4()}",
        user_id=user_id,
        title="整书拆集测试",
        description="少年在旧城中追查星光密信。",
        genre="fantasy",
        status="writing",
        extra_data={"existing": "preserved"},
    )
    chapters = [
        Chapter(
            id=f"chapter-{index}",
            novel_id=novel.id,
            user_id=user_id,
            title=f"第{index}章",
            content=f"第{index}章正文",
            chapter_number=index,
            word_count=1000 + index,
            status="completed",
        )
        for index in range(1, 6)
    ]
    db_session.add(novel)
    db_session.add_all(chapters)
    await db_session.flush()
    return novel


@pytest.mark.asyncio
async def test_build_series_plan_groups_chapters_into_episodes(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    plan = await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        target_episode_count=3,
    )

    assert len(plan["episodes"]) == 3
    assert plan["episodes"][0]["episode_number"] == 1
    assert plan["episodes"][0]["chapter_ids"] == ["chapter-1", "chapter-2"]
    assert plan["episodes"][0]["status"] == "planned"
    assert plan["episodes"][0]["workflow_id"] is None
    assert "continuity_summary" in plan["episodes"][0]
    assert plan["episodes"][0]["production_readiness"]["next_action"]["code"] == "generate_script"


@pytest.mark.asyncio
async def test_build_series_plan_persists_on_novel_extra_data(
    db_session: AsyncSession,
    seeded_novel_with_chapters: Novel,
) -> None:
    plan = await build_series_plan(
        db_session,
        seeded_novel_with_chapters.user_id,
        novel_id=seeded_novel_with_chapters.id,
        target_episode_count=3,
    )

    await db_session.refresh(seeded_novel_with_chapters)
    extra_data = seeded_novel_with_chapters.extra_data
    assert extra_data["existing"] == "preserved"
    assert extra_data[SERIES_PLAN_KEY]["novel_id"] == seeded_novel_with_chapters.id
    assert extra_data[SERIES_PLAN_KEY]["episodes"][0]["chapter_ids"] == plan["episodes"][0]["chapter_ids"]

    saved_plan = await get_series_plan(db_session, seeded_novel_with_chapters.user_id, seeded_novel_with_chapters.id)
    assert saved_plan["episodes"][0]["chapter_ids"] == ["chapter-1", "chapter-2"]
