"""
Batch route mounting tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.minimax_config import DEFAULT_TTS_VOICE
from app.models import Asset, BatchJob, BatchJobItem, Chapter, LLMConfig, LLMModel, LLMProvider, Novel, Script, Shot, StoryBible, Storyboard, TTSJob, VideoJob, Workflow
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_batch_queue_list_route_matches_frontend_path(client: TestClient) -> None:
    response = client.get("/api/v1/batch/list", headers=_auth_headers("batch-route-user"))

    assert response.status_code == 200
    assert response.json() == {"total": 0, "jobs": []}


def test_update_batch_item_accepts_json_body(client: TestClient, tmp_path) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    user_id = "batch-json-user"
    db_path = tmp_path / "batch-json.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    async def seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            session.add(BatchJob(
                id="batch-json-001",
                user_id=user_id,
                job_type="image",
                status="pending",
                total_count=1,
                pending_count=1,
                shot_ids=["shot-001"],
            ))
            session.add(BatchJobItem(
                id="item-json-001",
                batch_job_id="batch-json-001",
                user_id=user_id,
                shot_id="shot-001",
                status="pending",
            ))
            await session.commit()

    import asyncio
    asyncio.run(seed())
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.put(
            "/api/v1/batch/batch-json-001/items/item-json-001",
            headers=_auth_headers(user_id),
            json={
                "status": "succeeded",
                "image_url": "/static/generated/images/shot-001.jpg",
                "image_job_id": "image-task-001",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["image_url"] == "/static/generated/images/shot-001.jpg"
    assert payload["image_job_id"] == "image-task-001"


def test_start_tts_batch_generates_audio_for_items(client: TestClient, tmp_path) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    user_id = "batch-tts-user"
    db_path = tmp_path / "batch-tts.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    async def seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            session.add(Storyboard(
                id="storyboard-tts-001",
                user_id=user_id,
                script_id="script-tts-001",
                title="TTS batch storyboard",
                content={"chapter_id": "chapter-tts-001"},
            ))
            session.add(Shot(
                id="shot-tts-001",
                user_id=user_id,
                storyboard_id="storyboard-tts-001",
                shot_number=1,
                dialogue="孙剑：我来确认出口。",
                duration=4,
            ))
            session.add(BatchJob(
                id="batch-tts-001",
                user_id=user_id,
                job_type="tts",
                status="pending",
                total_count=1,
                pending_count=1,
                shot_ids=["shot-tts-001"],
                storyboard_id="storyboard-tts-001",
                workflow_id="workflow-tts-001",
            ))
            session.add(BatchJobItem(
                id="item-tts-001",
                batch_job_id="batch-tts-001",
                user_id=user_id,
                shot_id="shot-tts-001",
                status="pending",
            ))
            await session.commit()

    async def load_tts_job_voice() -> str | None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(TTSJob).where(TTSJob.shot_id == "shot-tts-001", TTSJob.user_id == user_id)
            )
            job = result.scalar_one_or_none()
            return job.voice if job else None

    import asyncio
    asyncio.run(seed())
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/api/v1/batch/batch-tts-001/start",
            headers=_auth_headers(user_id),
        )
        items_response = client.get(
            "/api/v1/batch/batch-tts-001/items",
            headers=_auth_headers(user_id),
        )
        tts_voice = asyncio.run(load_tts_job_voice())
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert response.json()["succeeded_count"] == 1
    assert items_response.status_code == 200, items_response.text
    item = items_response.json()["items"][0]
    assert item["status"] == "succeeded"
    assert item["audio_url"].startswith("/static/dev/tts-")
    assert item["tts_job_id"]
    assert tts_voice == DEFAULT_TTS_VOICE


def test_start_tts_batch_uses_user_default_clone_for_main_character(client: TestClient, tmp_path) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    user_id = "batch-tts-main-voice-user"
    db_path = tmp_path / "batch-tts-main-voice.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    async def seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            session.add(StoryBible(
                id="story-bible-main-001",
                user_id=user_id,
                novel_id="novel-main-001",
                title="主角声线测试 Story Bible",
                character_rules=[
                    {"name": "孙剑", "description": "第一主角"},
                    {"name": "沈岚", "description": "配角"},
                ],
            ))
            session.add(Storyboard(
                id="storyboard-main-001",
                user_id=user_id,
                script_id="script-main-001",
                novel_id="novel-main-001",
                title="TTS main voice storyboard",
                content={"chapter_id": "chapter-main-001", "story_bible_id": "story-bible-main-001"},
            ))
            session.add(Workflow(
                id="workflow-main-001",
                user_id=user_id,
                title="主角声线工作流",
                novel_id="novel-main-001",
                chapter_id="chapter-main-001",
                script_id="script-main-001",
                storyboard_id="storyboard-main-001",
                status="active",
            ))
            session.add(Asset(
                id="voice-asset-main-001",
                user_id=user_id,
                category="voice",
                name="孙秦岳默认声线",
                asset_type="audio",
                url="/static/generated/voice-clones/sunqinyue-default.mp3",
                tags=["voice_clone"],
                style_tags=["custom_voice"],
                generation_params={
                    "provider": "minimax",
                    "voice_id": "sunqinyue-default",
                    "clone_status": "provider_ready",
                    "provider_tts_model": "speech-2.8-hd",
                    "is_default": True,
                },
            ))
            session.add(Shot(
                id="shot-main-001",
                user_id=user_id,
                storyboard_id="storyboard-main-001",
                shot_number=1,
                dialogue="孙剑：我来确认出口。",
                duration=4,
            ))
            session.add(BatchJob(
                id="batch-main-001",
                user_id=user_id,
                job_type="tts",
                status="pending",
                total_count=1,
                pending_count=1,
                shot_ids=["shot-main-001"],
                storyboard_id="storyboard-main-001",
                workflow_id="workflow-main-001",
            ))
            session.add(BatchJobItem(
                id="item-main-001",
                batch_job_id="batch-main-001",
                user_id=user_id,
                shot_id="shot-main-001",
                status="pending",
            ))
            await session.commit()

    async def load_tts_job_voice() -> str | None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(TTSJob).where(TTSJob.shot_id == "shot-main-001", TTSJob.user_id == user_id)
            )
            job = result.scalar_one_or_none()
            return job.voice if job else None

    import asyncio
    asyncio.run(seed())
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/api/v1/batch/batch-main-001/start",
            headers=_auth_headers(user_id),
        )
        tts_voice = asyncio.run(load_tts_job_voice())
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert response.json()["succeeded_count"] == 1
    assert tts_voice == "sunqinyue-default"


def test_start_video_batch_generates_video_jobs_for_items(client: TestClient, tmp_path) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    user_id = "batch-video-user"
    db_path = tmp_path / "batch-video.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    async def seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            session.add(Novel(
                id="novel-video-001",
                user_id=user_id,
                title="Video batch novel",
            ))
            session.add(Chapter(
                id="chapter-video-001",
                user_id=user_id,
                novel_id="novel-video-001",
                title="Video batch chapter",
                chapter_number=1,
                content="雨巷霓虹中，沈岚抬头看向铜铃。",
            ))
            session.add(Script(
                id="script-video-001",
                user_id=user_id,
                novel_id="novel-video-001",
                chapter_id="chapter-video-001",
                title="Video batch script",
                content="雨巷霓虹中，沈岚抬头看向铜铃。",
                extra_data={"chapter_id": "chapter-video-001"},
            ))
            session.add(Storyboard(
                id="storyboard-video-001",
                user_id=user_id,
                script_id="script-video-001",
                novel_id="novel-video-001",
                title="Video batch storyboard",
                content={"chapter_id": "chapter-video-001"},
            ))
            session.add(Workflow(
                id="workflow-video-001",
                user_id=user_id,
                title="Video batch workflow",
                novel_id="novel-video-001",
                chapter_id="chapter-video-001",
                script_id="script-video-001",
                storyboard_id="storyboard-video-001",
                status="active",
            ))
            session.add(Shot(
                id="shot-video-001",
                user_id=user_id,
                storyboard_id="storyboard-video-001",
                shot_number=1,
                prompt="雨巷霓虹中，沈岚抬头看向铜铃。",
                visual_description="雨巷霓虹中，沈岚抬头看向铜铃。",
                duration=4,
            ))
            session.add(BatchJob(
                id="batch-video-001",
                user_id=user_id,
                job_type="video",
                status="pending",
                total_count=1,
                pending_count=1,
                shot_ids=["shot-video-001"],
                storyboard_id="storyboard-video-001",
                workflow_id="workflow-video-001",
            ))
            session.add(BatchJobItem(
                id="item-video-001",
                batch_job_id="batch-video-001",
                user_id=user_id,
                shot_id="shot-video-001",
                status="pending",
            ))
            await session.commit()

    async def load_video_job_count() -> int:
        async with SessionLocal() as session:
            result = await session.execute(
                select(VideoJob).where(VideoJob.user_id == user_id)
            )
            return len(result.scalars().all())

    import asyncio
    asyncio.run(seed())
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/api/v1/batch/batch-video-001/start",
            headers=_auth_headers(user_id),
        )
        items_response = client.get(
            "/api/v1/batch/batch-video-001/items",
            headers=_auth_headers(user_id),
        )
        video_job_count = asyncio.run(load_video_job_count())
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())

    assert response.status_code == 200, response.text
    assert response.json()["status"] in {"running", "completed"}
    item = items_response.json()["items"][0]
    assert item["status"] in {"running", "succeeded"}
    assert item["video_job_id"]
    assert video_job_count == 1


def test_start_video_batch_normalizes_duration_to_selected_model_limits(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    user_id = "batch-video-duration-user"
    db_path = tmp_path / "batch-video-duration.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    captured: dict[str, int] = {}

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    async def fake_generate_video(request, db, user_id: str):
        captured["duration"] = request.duration
        job = VideoJob(
            id="video-duration-job-001",
            user_id=user_id,
            task_id="video-duration-task-001",
            prompt=request.prompt,
            model_id=request.model,
            model_name="Seedance 1.5 test",
            duration=request.duration,
            resolution=request.resolution,
            image_url=request.image_url,
            status="pending",
            progress=10,
            extra_data={"model_config_id": request.model_config_id},
        )
        db.add(job)
        await db.commit()

        class Response:
            job_id = "video-duration-job-001"
            status = "pending"
            message = "submitted"

        return Response()

    async def seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            session.add(LLMProvider(
                id="provider-volcano-duration",
                name="volcano",
                name_cn="火山引擎",
                is_active=True,
            ))
            session.add(LLMModel(
                id="volcano.seedance.1_5_pro",
                provider_id="provider-volcano-duration",
                model_id="doubao-seedance-1-5-pro-251215",
                model_name="Doubao Seedance 1.5 Pro",
                model_name_cn="豆包Seedance-1.5-pro",
                model_type="video",
                capabilities=["image_to_video", "shot_video"],
                is_active=True,
            ))
            session.add(LLMConfig(
                id="seedance15-config-001",
                user_id=user_id,
                model_id="volcano.seedance.1_5_pro",
                name="默认 Seedance 1.5",
                api_key="test-key",
                is_active=True,
                is_default=True,
                test_status="success",
            ))
            session.add(Storyboard(
                id="storyboard-duration-001",
                user_id=user_id,
                script_id="script-duration-001",
                title="Video duration storyboard",
                content={"chapter_id": "chapter-duration-001"},
            ))
            session.add(Shot(
                id="shot-duration-001",
                user_id=user_id,
                storyboard_id="storyboard-duration-001",
                shot_number=1,
                prompt="雨巷中沈岚抬头看向铜铃。",
                duration=3,
                image_url="https://example.com/reference.png",
            ))
            session.add(BatchJob(
                id="batch-duration-001",
                user_id=user_id,
                job_type="video",
                status="pending",
                total_count=1,
                pending_count=1,
                shot_ids=["shot-duration-001"],
                storyboard_id="storyboard-duration-001",
                workflow_id="workflow-duration-001",
                extra_data={"model_config_id": "seedance15-config-001"},
            ))
            session.add(BatchJobItem(
                id="item-duration-001",
                batch_job_id="batch-duration-001",
                user_id=user_id,
                shot_id="shot-duration-001",
                status="pending",
            ))
            await session.commit()

    import asyncio
    asyncio.run(seed())
    monkeypatch.setattr("app.api.v1.endpoints.video.generate_video", fake_generate_video)
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/api/v1/batch/batch-duration-001/start",
            headers=_auth_headers(user_id),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())

    assert response.status_code == 200, response.text
    assert captured["duration"] == 4


def test_batch_progress_syncs_completed_video_items(client: TestClient, tmp_path) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    user_id = "batch-video-sync-user"
    db_path = tmp_path / "batch-video-sync.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    async def seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            session.add(BatchJob(
                id="batch-sync-001",
                user_id=user_id,
                job_type="video",
                status="running",
                total_count=1,
                running_count=1,
                shot_ids=["shot-sync-001"],
            ))
            session.add(BatchJobItem(
                id="item-sync-001",
                batch_job_id="batch-sync-001",
                user_id=user_id,
                shot_id="shot-sync-001",
                status="running",
                video_job_id="video-sync-001",
            ))
            session.add(VideoJob(
                id="video-sync-001",
                user_id=user_id,
                task_id="task-sync-001",
                prompt="同步完成的视频",
                model_id="doubao-seedance-1-5-pro-251215",
                model_name="豆包Seedance-1.5-pro",
                duration=4,
                resolution="720p",
                status="succeeded",
                progress=100,
                video_url="/static/generated/videos/video-sync-001.mp4",
            ))
            await session.commit()

    import asyncio
    asyncio.run(seed())
    app.dependency_overrides[get_db] = override_get_db
    try:
        progress_response = client.get(
            "/api/v1/batch/batch-sync-001/progress",
            headers=_auth_headers(user_id),
        )
        items_response = client.get(
            "/api/v1/batch/batch-sync-001/items",
            headers=_auth_headers(user_id),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())

    assert progress_response.status_code == 200, progress_response.text
    assert progress_response.json()["status"] == "completed"
    assert progress_response.json()["succeeded_count"] == 1
    item = items_response.json()["items"][0]
    assert item["status"] == "succeeded"
    assert item["video_url"] == "/static/generated/videos/video-sync-001.mp4"
