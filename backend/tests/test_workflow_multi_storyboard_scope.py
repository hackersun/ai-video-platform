from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Novel, Script, Shot, Storyboard, Workflow
from app.services.workflow_shot_scope import workflow_shots
from app.features.workflow_media.application.prepare_separate_media import _shot_storyboard_id


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


@pytest.mark.asyncio
async def test_series_workflow_returns_shots_from_all_scene_storyboards(db_session: AsyncSession) -> None:
    user_id, novel_id, script_id, run_id = (str(uuid4()) for _ in range(4))
    boards = [
        Storyboard(
            id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script_id, title=f"场景{index}",
            content={"series_run_id": run_id, "episode_number": 1, "scene_index": index},
        )
        for index in (1, 2)
    ]
    workflow = Workflow(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script_id,
        storyboard_id=boards[0].id, title="第一集", status="pending",
        metadata_={"series_run_id": run_id, "episode_number": 1},
    )
    shots = [
        Shot(id=str(uuid4()), user_id=user_id, storyboard_id=board.id, shot_number=number)
        for board in reversed(boards) for number in (2, 1)
    ]
    db_session.add_all([
        Novel(id=novel_id, user_id=user_id, title="归墟"),
        Script(id=script_id, user_id=user_id, novel_id=novel_id, title="第一集"),
        *boards, workflow, *shots,
    ])
    await db_session.flush()

    result = await workflow_shots(db_session, workflow=workflow, user_id=user_id)

    assert [(shot.storyboard_id, shot.shot_number) for shot in result] == [
        (boards[0].id, 1), (boards[0].id, 2), (boards[1].id, 1), (boards[1].id, 2),
    ]


def test_media_lineage_prefers_each_shots_actual_storyboard() -> None:
    context = type("Context", (), {"workflow": type("Workflow", (), {"storyboard_id": "board-first"})()})()
    later_shot = type("Shot", (), {"storyboard_id": "board-later"})()

    assert _shot_storyboard_id(context, later_shot) == "board-later"
