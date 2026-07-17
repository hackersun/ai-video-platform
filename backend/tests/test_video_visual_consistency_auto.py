from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.models import Asset, Shot, VideoJob


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


def _shot(user_id: str) -> Shot:
    return Shot(
        id=f"shot-{uuid4()}",
        user_id=user_id,
        storyboard_id=f"storyboard-{uuid4()}",
        shot_number=1,
        duration=4,
        prompt="孙剑自动检查镜头",
        character_refs=[{"entity_id": "char-main", "name": "孙剑"}],
        extra_data={"quality_report": {"status": "ready"}},
    )


def _front_asset(user_id: str) -> Asset:
    return Asset(
        id=f"asset-{uuid4()}",
        user_id=user_id,
        category="character",
        asset_type="image",
        entity_id="char-main",
        entity_type="character",
        name="孙剑正面定稿",
        url="https://cdn.example.com/sunjian-front.png",
        is_active=True,
        is_locked=True,
        is_final=True,
        generation_params={"view_key": "front"},
    )


def _video_job(user_id: str, shot_id: str, *, auto_check: bool) -> VideoJob:
    extra_data = {"shot_id": shot_id}
    if auto_check:
        extra_data["visual_consistency_auto_check"] = True
    return VideoJob(
        id=f"video-{uuid4()}",
        user_id=user_id,
        task_id=f"task-{uuid4()}",
        title="自动视觉一致性视频",
        prompt="shot video",
        model_id="test-video",
        model_name="Test Video",
        status="pending",
        progress=10,
        extra_data=extra_data,
    )


@pytest.mark.asyncio
async def test_sync_video_job_auto_records_visual_consistency_when_enabled(
    db_session: AsyncSession,
) -> None:
    from app.features.video_generation.public import VideoJobSyncCommand, sync_video_job_and_shot

    user_id = f"user-{uuid4()}"
    shot = _shot(user_id)
    asset = _front_asset(user_id)
    job = _video_job(user_id, shot.id, auto_check=True)
    db_session.add_all([shot, asset, job])
    await db_session.flush()

    await sync_video_job_and_shot(
        db_session, job,
        VideoJobSyncCommand("succeeded", 100, "/static/generated/videos/shot.mp4", None),
    )

    assert job.extra_data["visual_consistency"]["score"] == 72
    assert job.extra_data["visual_consistency_auto_checked"] is True
    assert shot.extra_data["quality_report"]["visual_consistency_score"] == 72
    assert asset.generation_params["visual_consistency_history"][0]["reference_asset_id"] == asset.id


@pytest.mark.asyncio
async def test_sync_video_job_does_not_auto_record_visual_consistency_by_default(
    db_session: AsyncSession,
) -> None:
    from app.features.video_generation.public import VideoJobSyncCommand, sync_video_job_and_shot

    user_id = f"user-{uuid4()}"
    shot = _shot(user_id)
    asset = _front_asset(user_id)
    job = _video_job(user_id, shot.id, auto_check=False)
    db_session.add_all([shot, asset, job])
    await db_session.flush()

    await sync_video_job_and_shot(
        db_session, job,
        VideoJobSyncCommand("succeeded", 100, "/static/generated/videos/shot.mp4", None),
    )

    assert "visual_consistency" not in job.extra_data
    assert "visual_consistency_score" not in shot.extra_data["quality_report"]
    assert "visual_consistency_history" not in asset.generation_params
