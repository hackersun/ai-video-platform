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


def _shot(user_id: str, entity_id: str) -> Shot:
    return Shot(
        id=f"shot-{uuid4()}",
        user_id=user_id,
        storyboard_id=f"storyboard-{uuid4()}",
        shot_number=1,
        duration=4,
        prompt="孙剑抬头确认自己的倒影",
        character_refs=[{"entity_id": entity_id, "name": "孙剑"}],
        extra_data={"quality_report": {"status": "warning", "warnings": ["原有提示"]}},
    )


def _front_asset(user_id: str, entity_id: str) -> Asset:
    return Asset(
        id=f"asset-{uuid4()}",
        user_id=user_id,
        category="character",
        asset_type="image",
        entity_id=entity_id,
        entity_type="character",
        name="孙剑正面定稿",
        url="https://cdn.example.com/sunjian-front.png",
        is_active=True,
        is_locked=True,
        is_final=True,
        generation_params={"view_key": "front"},
    )


def _video_job(user_id: str, shot: Shot) -> VideoJob:
    return VideoJob(
        id=f"video-{uuid4()}",
        user_id=user_id,
        workflow_id=f"workflow-{uuid4()}",
        task_id=f"task-{uuid4()}",
        title="镜头视频",
        prompt="shot video",
        model_id="test-video",
        model_name="Test Video",
        duration=4,
        status="succeeded",
        progress=100,
        video_url="https://cdn.example.com/shot.mp4",
        extra_data={"shot_id": shot.id},
    )


@pytest.mark.asyncio
async def test_record_completed_shot_visual_consistency_updates_shot_job_and_asset(
    db_session: AsyncSession,
) -> None:
    from app.services.visual_consistency_service import record_completed_shot_visual_consistency

    user_id = f"user-{uuid4()}"
    entity_id = "char-main"
    shot = _shot(user_id, entity_id)
    asset = _front_asset(user_id, entity_id)
    job = _video_job(user_id, shot)
    db_session.add_all([shot, asset, job])
    await db_session.flush()

    record = await record_completed_shot_visual_consistency(
        db_session,
        user_id=user_id,
        shot=shot,
        video_job=job,
        frame_urls=["/static/generated/frames/shot-001.png"],
        score=74,
    )

    assert record is not None
    assert record["score"] == 74
    assert record["status"] == "needs_review"
    assert record["reference_asset_id"] == asset.id
    assert record["frame_count"] == 1
    assert record["blocking"] is False

    quality_report = shot.extra_data["quality_report"]
    assert quality_report["status"] == "warning"
    assert quality_report["visual_consistency_score"] == 74
    assert quality_report["visual_consistency"] == record
    assert job.extra_data["visual_consistency"] == record

    asset_params = asset.generation_params
    assert asset_params["visual_consistency"] == record
    assert asset_params["visual_consistency_history"][0] == record


@pytest.mark.asyncio
async def test_record_completed_shot_visual_consistency_skips_without_front_reference(
    db_session: AsyncSession,
) -> None:
    from app.services.visual_consistency_service import record_completed_shot_visual_consistency

    user_id = f"user-{uuid4()}"
    shot = _shot(user_id, "missing-char")
    job = _video_job(user_id, shot)
    db_session.add_all([shot, job])
    await db_session.flush()

    record = await record_completed_shot_visual_consistency(
        db_session,
        user_id=user_id,
        shot=shot,
        video_job=job,
        frame_urls=[],
        score=74,
    )

    assert record is None
    assert "visual_consistency" not in job.extra_data
    assert "visual_consistency_score" not in shot.extra_data["quality_report"]


@pytest.mark.asyncio
async def test_record_completed_shot_visual_consistency_can_extract_frames(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.visual_consistency_service as service

    user_id = f"user-{uuid4()}"
    entity_id = "char-main"
    shot = _shot(user_id, entity_id)
    asset = _front_asset(user_id, entity_id)
    job = _video_job(user_id, shot)
    db_session.add_all([shot, asset, job])
    await db_session.flush()

    monkeypatch.setattr(
        service,
        "extract_video_frames",
        lambda video_url: {
            "source_video_url": video_url,
            "frame_count": 2,
            "frame_urls": ["/static/generated/frames/run/frame-001.jpg", "/static/generated/frames/run/frame-002.jpg"],
        },
    )

    record = await service.record_completed_shot_visual_consistency(
        db_session,
        user_id=user_id,
        shot=shot,
        video_job=job,
        extract_frames=True,
    )

    assert record is not None
    assert record["score"] == 86
    assert record["frame_count"] == 2
    assert record["frames"] == ["/static/generated/frames/run/frame-001.jpg", "/static/generated/frames/run/frame-002.jpg"]
