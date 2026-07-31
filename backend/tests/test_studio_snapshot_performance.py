from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.services.studio_snapshot as studio_snapshot
from app.core.database import Base
from app.models import Chapter, Novel, Workflow


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_snapshot_uses_persisted_series_plan_without_full_rebuild(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"studio-user-{uuid4()}"
    novel_id = f"studio-novel-{uuid4()}"
    chapter_ids = [f"studio-chapter-{uuid4()}" for _ in range(4)]
    workflow_id = f"studio-workflow-{uuid4()}"
    episodes = [
        {
            "episode_index": index,
            "title": f"第{index}集",
            "chapter_ids": [chapter_id],
            "production_bible_summary": {"version": 1},
            "production_graph": {"version": 3, "status": "consistent"},
        }
        for index, chapter_id in enumerate(chapter_ids, start=1)
    ]
    db_session.add(Novel(
        id=novel_id,
        user_id=user_id,
        title="四章工作室性能测试",
        extra_data={"series_plan": {"version": 1, "episodes": episodes}},
    ))
    db_session.add_all([
        Chapter(
            id=chapter_id,
            user_id=user_id,
            novel_id=novel_id,
            title=f"第{index}章",
            chapter_number=index,
        )
        for index, chapter_id in enumerate(chapter_ids, start=1)
    ])
    db_session.add(Workflow(
        id=workflow_id,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_ids[1],
        title="第二集工作流",
        status="running",
    ))
    await db_session.commit()

    async def reject_full_rebuild(*args, **kwargs):
        raise AssertionError("Studio snapshot must not rebuild the full series plan")

    monkeypatch.setattr(studio_snapshot, "get_series_plan", reject_full_rebuild, raising=False)

    snapshot = await studio_snapshot.build_studio_snapshot(db_session, user_id, workflow_id)

    assert len(snapshot["series_plan"]["episodes"]) == 4
    assert snapshot["series_plan"]["current_episode"]["episode_index"] == 2
    assert snapshot["series_plan"]["episodes"][0]["production_bible_summary"] == {"version": 1}
    assert snapshot["series_plan"]["episodes"][0]["production_graph"]["version"] == 3
