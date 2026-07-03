from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models.video_job import VideoJob
from init_db import init_db
from main import app
from test_workflow_routes import (
    _auth_headers,
    _create_chapter,
    _create_final_quality_workflow,
    _create_novel,
    _insert_model_config,
)


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _patch_video_client(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.append(kwargs)

            class _CreateResult:
                id = f"strategy-video-task-{len(captured)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())
    return captured


def _create_video_workflow(client: TestClient, user_id: str) -> str:
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 策略路由")
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201, storyboard_resp.text
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "策略路由工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201, workflow_resp.text
    return workflow_resp.json()["workflow_id"]


def _get_video_job_data(job_id: str) -> dict:
    async def _get() -> dict:
        async with AsyncSessionLocal() as session:
            job = await session.get(VideoJob, job_id)
            assert job is not None
            return {"model_id": job.model_id, "extra_data": job.extra_data or {}}

    return asyncio.run(_get())


def test_draft_fast_routes_to_seedance_fast_config(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video = _patch_video_client(monkeypatch)
    user_id = uuid4().hex
    fast_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"seedance-fast-{uuid4()}",
        api_model_id="doubao-seedance-2-0-fast-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-fast",
    )
    workflow_id = _create_video_workflow(client, user_id)

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert captured_video[0]["model"] == "doubao-seedance-2-0-fast-260128"
    job_data = _get_video_job_data(payload["video_job_ids"][0])
    extra = job_data["extra_data"]
    assert job_data["model_id"] == "doubao-seedance-2-0-fast-260128"
    assert extra["model_config_id"] == fast_config_id
    assert extra["prompt_parameters"]["model_config_id"] == fast_config_id
    assert extra["strategy_routing"] == "strategy"
    assert extra["strategy_matched_api_model_id"] == "doubao-seedance-2-0-fast-260128"


def test_draft_fast_routes_to_agent_plan_seedance_fast_config(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video = _patch_video_client(monkeypatch)
    user_id = uuid4().hex
    fast_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano_agent_plan",
        model_id=f"agent-plan-seedance-fast-{uuid4()}",
        api_model_id="doubao-seedance-2.0-fast",
        model_type="video-generation",
        capabilities=["text-to-video", "image-to-video", "agent_plan"],
        api_key="sk-agent-fast",
    )
    workflow_id = _create_video_workflow(client, user_id)

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert captured_video[0]["model"] == "doubao-seedance-2.0-fast"
    job_data = _get_video_job_data(payload["video_job_ids"][0])
    extra = job_data["extra_data"]
    assert job_data["model_id"] == "doubao-seedance-2.0-fast"
    assert extra["model_config_id"] == fast_config_id
    assert extra["prompt_parameters"]["model_config_id"] == fast_config_id
    assert extra["strategy_routing"] == "strategy"
    assert extra["strategy_matched_api_model_id"] == "doubao-seedance-2.0-fast"


def test_final_quality_routes_to_seedance_20_before_fast(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video = _patch_video_client(monkeypatch)
    user_id = uuid4().hex
    quality_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"seedance-quality-{uuid4()}",
        api_model_id="doubao-seedance-2-0-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-quality",
    )
    _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"seedance-fast-{uuid4()}",
        api_model_id="doubao-seedance-2-0-fast-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-fast",
    )
    asset_locks = [
        {
            "asset_id": "asset-final-route-v1",
            "asset_version_id": "asset-final-route-version-1",
            "entity_name": "孙剑",
            "category": "character",
        }
    ]
    workflow_id, story_bible_id = _create_final_quality_workflow(
        client,
        user_id,
        asset_locks=asset_locks,
        character_rules=[{"name": "孙剑", "voice": "story-bible-sunjian"}],
    )

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "final_quality",
            "audio_mode": "none",
            "story_bible_id": story_bible_id,
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert captured_video[0]["model"] == "doubao-seedance-2-0-260128"
    extra = _get_video_job_data(payload["video_job_ids"][0])["extra_data"]
    assert extra["model_config_id"] == quality_config_id
    assert extra["strategy_routing"] == "strategy"
    assert extra["strategy_matched_api_model_id"] == "doubao-seedance-2-0-260128"
    assert extra["asset_version_locks"] == asset_locks
    assert extra["voice_lock_snapshot"] == {
        "character_name": "孙剑",
        "story_bible_id": story_bible_id,
        "voice": "story-bible-sunjian",
        "voice_source": "story_bible",
    }


def test_explicit_config_overrides_strategy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video = _patch_video_client(monkeypatch)
    user_id = uuid4().hex
    _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"seedance-fast-{uuid4()}",
        api_model_id="doubao-seedance-2-0-fast-260128",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-fast",
    )
    custom_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"custom-video-{uuid4()}",
        api_model_id="doubao-custom-video-route",
        model_type="video",
        capabilities=["text-to-video"],
        api_key="sk-custom",
    )
    workflow_id = _create_video_workflow(client, user_id)

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "model_config_id": custom_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert captured_video[0]["model"] == "doubao-custom-video-route"
    extra = _get_video_job_data(payload["video_job_ids"][0])["extra_data"]
    assert extra["model_config_id"] == custom_config_id
    assert extra["strategy_routing"] == "explicit"
    assert extra["strategy_matched_api_model_id"] is None


def test_no_strategy_config_falls_back(
    client: TestClient,
) -> None:
    user_id = uuid4().hex
    workflow_id = _create_video_workflow(client, user_id)

    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "production_strategy": "draft_fast",
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    extra = _get_video_job_data(payload["video_job_ids"][0])["extra_data"]
    assert extra["model_config_id"] is None
    assert extra["strategy_routing"] == "fallback"
    assert extra["strategy_matched_api_model_id"] is None
