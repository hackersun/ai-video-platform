from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.features.video_generation.application.lineage import resolve_video_lineage
from app.features.video_generation.errors import VideoGenerationError
from app.features.video_generation.schemas import VideoGenerateRequest
from app.models import Novel, Script, Shot, Storyboard, Workflow


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


async def _scene_lineage_fixture(db: AsyncSession):
    user_id, novel_id, script_id, run_id = (str(uuid4()) for _ in range(4))
    primary = Storyboard(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script_id,
        title="第一场", content={"series_run_id": run_id, "episode_number": 1, "scene_index": 1},
    )
    later = Storyboard(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script_id,
        title="第二场", content={"series_run_id": run_id, "episode_number": 1, "scene_index": 2},
    )
    foreign = Storyboard(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script_id,
        title="下一集", content={"series_run_id": run_id, "episode_number": 2, "scene_index": 1},
    )
    workflow = Workflow(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script_id,
        storyboard_id=primary.id, title="第一集", status="pending",
        metadata_={"series_run_id": run_id, "episode_number": 1},
    )
    later_shot = Shot(
        id=str(uuid4()), user_id=user_id, storyboard_id=later.id, shot_number=1,
        visual_description="第二场动作镜头",
    )
    db.add_all([
        Novel(id=novel_id, user_id=user_id, title="玄烬天门"),
        Script(id=script_id, user_id=user_id, novel_id=novel_id, title="第一集"),
        primary, later, foreign, workflow, later_shot,
    ])
    await db.flush()
    return user_id, workflow, later, foreign, later_shot


@pytest.mark.asyncio
async def test_lineage_accepts_later_scene_storyboard_owned_by_same_episode(db_session: AsyncSession) -> None:
    user_id, workflow, later, _, shot = await _scene_lineage_fixture(db_session)

    result = await resolve_video_lineage(
        db_session,
        user_id,
        VideoGenerateRequest(
            prompt="第二场动作镜头", workflow_id=workflow.id,
            storyboard_id=later.id, shot_id=shot.id,
        ),
    )

    assert result["storyboard_id"] == later.id
    assert result["shot_id"] == shot.id
    assert workflow.storyboard_id != later.id


@pytest.mark.asyncio
async def test_lineage_rejects_storyboard_from_different_episode(db_session: AsyncSession) -> None:
    user_id, workflow, _, foreign, _ = await _scene_lineage_fixture(db_session)

    with pytest.raises(VideoGenerationError) as caught:
        await resolve_video_lineage(
            db_session,
            user_id,
            VideoGenerateRequest(
                prompt="错误跨集镜头", workflow_id=workflow.id, storyboard_id=foreign.id,
            ),
        )

    assert caught.value.status_code == 422
    assert caught.value.detail == "workflow_id 与 storyboard_id 不匹配"
