"""
Workflow route tests for TTS and synthesis.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.synthesis_job import SynthesisJob
from app.models.video_job import VideoJob
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


@pytest.fixture()
def fake_tts_service(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_text_to_speech(self, *args, **kwargs):
        return {
            "task_id": "tts-task-123",
            "status": "succeeded",
            "audio_url": "https://example.com/audio.mp3",
            "duration": 3.5,
            "model": "test-tts-model",
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.text_to_speech",
        _fake_text_to_speech,
    )


@pytest.fixture()
def fake_synthesis_service(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_video_voice_synthesis(self, *args, **kwargs):
        return {
            "task_id": "synthesis-task-123",
            "status": "succeeded",
            "output_url": "https://example.com/video.mp4",
            "duration": 10.0,
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.video_voice_synthesis",
        _fake_video_voice_synthesis,
    )


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _create_novel(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": f"Novel for {user_id}", "description": "test novel"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_chapter(client: TestClient, user_id: str, novel_id: str, title: str = "Chapter") -> str:
    response = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": title,
            "chapter_number": 1,
            "content": "雨夜街道中，主角发现关键线索并推动剧情。",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_script(client: TestClient, user_id: str) -> str:
    novel_id = _create_novel(client, user_id)
    response = client.post(
        "/api/v1/scripts",
        json={"novel_id": novel_id, "title": f"Script for {user_id}", "description": "test script"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_storyboard(client: TestClient, user_id: str) -> str:
    script_id = _create_script(client, user_id)
    response = client.post(
        "/api/v1/storyboards",
        json={"script_id": script_id, "title": f"Storyboard for {user_id}", "description": "test storyboard"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_shot(client: TestClient, user_id: str) -> tuple[str, str, str]:
    script_id = _create_script(client, user_id)
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={"script_id": script_id, "title": f"Storyboard for {user_id}", "description": "test storyboard"},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": f"Shot for {user_id}",
            "dialogue": "test dialogue",
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    return shot_resp.json()["id"], storyboard_id, script_id


def _insert_video_job(job: VideoJob) -> None:
    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(job)
            await session.commit()

    asyncio.run(_insert())


def _insert_synthesis_job(job: SynthesisJob) -> None:
    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            session.add(job)
            await session.commit()

    asyncio.run(_insert())


def _insert_model_config(
    *,
    user_id: str,
    provider_id: str,
    model_id: str,
    api_model_id: str,
    model_type: str,
    capabilities: list[str],
    api_key: str,
) -> str:
    config_id = f"{model_id}-config-{uuid4()}"

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            provider = await session.get(LLMProvider, provider_id)
            if provider is None:
                provider = LLMProvider(
                    id=provider_id,
                    name=provider_id,
                    name_cn=provider_id,
                    base_url="https://example.com",
                    is_active=True,
                )
                session.add(provider)
            model = await session.get(LLMModel, model_id)
            if model is None:
                model = LLMModel(
                    id=model_id,
                    provider_id=provider_id,
                    model_id=api_model_id,
                    model_name=model_id,
                    model_name_cn=model_id,
                    model_type=model_type,
                    capabilities=capabilities,
                    is_active=True,
                )
                session.add(model)
            config = LLMConfig(
                id=config_id,
                user_id=user_id,
                model_id=model_id,
                name=f"{model_id} config",
                is_active=True,
                is_default=True,
                test_status="success",
            )
            config.set_api_key_encrypted(api_key)
            session.add(config)
            await session.commit()

    asyncio.run(_insert())
    return config_id


def _create_public_storage_config(client: TestClient, user_id: str, public_base_url: str = "https://cdn.example.com") -> str:
    create_resp = client.post(
        "/api/v1/external/configs",
        json={
            "provider_id": "object_storage",
            "name": "测试 CDN 参考图出口",
            "custom_base_url": public_base_url,
            "extra_config": {
                "public_base_url": public_base_url,
                "local_static_prefix": "/static/",
                "public_static_prefix": "/static/",
            },
            "is_default": True,
        },
        headers=_auth_headers(user_id),
    )
    assert create_resp.status_code == 201, create_resp.text
    config_id = create_resp.json()["id"]
    test_resp = client.post(f"/api/v1/external/configs/{config_id}/test", headers=_auth_headers(user_id))
    assert test_resp.status_code == 200, test_resp.text
    assert test_resp.json()["status"] == "success"
    return config_id


def test_video_job_includes_workflow_lineage_fields(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "video-task-123"

            return _CreateResult()

        @staticmethod
        def get(*args, **kwargs):
            class _GetResult:
                status = "succeeded"
                content = None

            return _GetResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    shot_id, storyboard_id, script_id = _create_shot(client, "video-lineage-user")

    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Generate from shot",
            "api_key": "test-key",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
        },
        headers=_auth_headers("video-lineage-user"),
    )

    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]

    jobs_resp = client.get("/api/v1/video/jobs", headers=_auth_headers("video-lineage-user"))
    assert jobs_resp.status_code == 200
    job = next(item for item in jobs_resp.json() if item["id"] == job_id)
    assert job["shot_id"] == shot_id
    assert job["storyboard_id"] == storyboard_id
    assert job["script_id"] == script_id


def test_video_generation_passes_seed_and_sdk_parameters(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-seeded"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-seed-user"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)

    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Seeded shot video",
            "api_key": "test-key",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "duration": 8,
            "resolution": "1080p",
            "seed": 4242,
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200
    assert captured["duration"] == 8
    assert captured["resolution"] == "1080p"
    assert captured["seed"] == 4242
    assert captured["camera_fixed"] is False
    assert captured["watermark"] is True
    assert "--resolution 1080p" in captured["content"][-1]["text"]

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    assert job_resp.json()["seed"] == 4242


def test_video_generation_uses_selected_video_model_config_metadata(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-selected-model"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-selected-model-user"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Selected configured video model",
            "api_key": "test-key",
            "model": "Doubao-Seedance-1.0-pro-fast",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "image_url": "https://example.com/ref.png",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200
    assert captured["model"] == "ep-20260322134751-fbglz"
    assert captured["content"][0]["type"] == "image_url"
    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["provider_id"] == "volcano"
    assert job["api_model_id"] == "Doubao-Seedance-1.0-pro-fast"
    assert job["model_endpoint_id"] == "ep-20260322134751-fbglz"
    assert job["prompt_parameters"]["image_url_sent"] is True
    assert job["prompt_parameters"]["duration"] == 5


def test_video_generation_skips_local_reference_image_for_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-local-image-skipped"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-local-image-user"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Local reference image should not be sent",
            "api_key": "test-key",
            "model": "Doubao-Seedance-1.0-pro-fast",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "image_url": "/static/generated/images/local-ref.png",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    assert captured["content"][0]["type"] == "text"
    assert all(item["type"] != "image_url" for item in captured["content"])

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["image_url"] == "/static/generated/images/local-ref.png"
    assert job["prompt_parameters"]["image_url_sent"] is False
    assert job["prompt_parameters"]["provider_image_url"] is None
    assert "公网" in job["prompt_parameters"]["image_url_omitted_reason"]
    assert "参考图接入说明" in job["prompt"]


def test_video_generation_maps_local_reference_image_through_public_storage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-public-storage-image"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-public-storage-user"
    storage_config_id = _create_public_storage_config(client, user_id)
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Local reference image should be delivered by CDN",
            "api_key": "test-key",
            "model": "Doubao-Seedance-1.0-pro-fast",
            "shot_id": shot_id,
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "image_url": "/static/generated/images/local-ref.png",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200, create_resp.text
    assert captured["content"][0]["type"] == "image_url"
    assert captured["content"][0]["image_url"]["url"] == "https://cdn.example.com/static/generated/images/local-ref.png"

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["image_url"] == "/static/generated/images/local-ref.png"
    assert job["prompt_parameters"]["image_url_sent"] is True
    assert job["prompt_parameters"]["provider_image_url"] == "https://cdn.example.com/static/generated/images/local-ref.png"
    assert job["prompt_parameters"]["image_delivery_method"] == "public_static_base_url"
    assert job["prompt_parameters"]["image_delivery_config_id"] == storage_config_id


def test_video_generation_accepts_seedance_20_fast_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-seedance-20-fast"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-seedance-20-fast-user"
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Seedance 2.0 fast video model",
            "api_key": "test-key",
            "model": "doubao-seedance-2-0-fast-260128",
            "duration": 4,
            "resolution": "720p",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200
    assert captured["model"] == "doubao-seedance-2-0-fast-260128"
    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["api_model_id"] == "doubao-seedance-2-0-fast-260128"
    assert job["model_endpoint_id"] == "doubao-seedance-2-0-fast-260128"


def test_video_generation_accepts_volcano_agent_plan_video_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    captured_client: dict = {}

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured.update(kwargs)

            class _CreateResult:
                id = "video-task-agent-plan"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    def _fake_create_ark_client(api_key: str, base_url: str | None = None):
        captured_client["api_key"] = api_key
        captured_client["base_url"] = base_url
        return _FakeArkClient()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", _fake_create_ark_client)

    user_id = "video-agent-plan-user"
    create_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Agent Plan Seedance video model",
            "api_key": "agent-plan-key",
            "model": "vplan-seedance-2-0-fast",
            "duration": 5,
            "resolution": "720p",
        },
        headers=_auth_headers(user_id),
    )

    assert create_resp.status_code == 200
    assert captured_client["api_key"] == "agent-plan-key"
    assert captured_client["base_url"] == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert captured["model"] == "doubao-seedance-2.0-fast"
    assert captured["duration"] == 5

    job_resp = client.get(f"/api/v1/video/jobs/{create_resp.json()['job_id']}", headers=_auth_headers(user_id))
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["provider_id"] == "volcano_agent_plan"
    assert job["api_model_id"] == "doubao-seedance-2.0-fast"
    assert job["model_endpoint_id"] == "doubao-seedance-2.0-fast"


def test_video_job_infers_full_lineage_from_chapter_shot(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "video-task-full-lineage"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = "video-full-lineage-user"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 雨巷")

    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 3,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    storyboard_id = storyboard_payload["id"]
    script_id = storyboard_payload["script_id"]
    shot_id = storyboard_payload["shots"][0]["id"]

    create_resp = client.post(
        "/api/v1/video/generate",
        json={"prompt": "Generate from inferred shot lineage", "api_key": "test-key", "shot_id": shot_id},
        headers=_auth_headers(user_id),
    )
    assert create_resp.status_code == 200
    create_payload = create_resp.json()
    job_id = create_payload["job_id"]
    assert create_payload["novel_id"] == novel_id
    assert create_payload["chapter_id"] == chapter_id
    assert create_payload["script_id"] == script_id
    assert create_payload["storyboard_id"] == storyboard_id
    assert create_payload["shot_id"] == shot_id

    jobs_resp = client.get(
        f"/api/v1/video/jobs?novel_id={novel_id}&chapter_id={chapter_id}&script_id={script_id}&storyboard_id={storyboard_id}&shot_id={shot_id}",
        headers=_auth_headers(user_id),
    )
    assert jobs_resp.status_code == 200
    job = next(item for item in jobs_resp.json() if item["id"] == job_id)
    assert job["novel_id"] == novel_id
    assert job["chapter_id"] == chapter_id
    assert job["script_id"] == script_id
    assert job["storyboard_id"] == storyboard_id
    assert job["shot_id"] == shot_id
    assert job["chapter_title"] == "第一章 雨巷"

    wrong_chapter_id = _create_chapter(client, user_id, novel_id, "第二章 错误来源")
    mismatch_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "Should reject mismatched chapter",
            "api_key": "test-key",
            "shot_id": shot_id,
            "chapter_id": wrong_chapter_id,
        },
        headers=_auth_headers(user_id),
    )
    assert mismatch_resp.status_code == 422


def test_chapter_generation_reuses_latest_script_when_multiple_scripts_exist(client: TestClient) -> None:
    user_id = f"chapter-production-duplicates-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 重复生成")

    first_script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_id, "style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert first_script_resp.status_code == 201, first_script_resp.text

    second_script_resp = client.post(
        "/api/v1/scripts/generate",
        json={"chapter_id": chapter_id, "style": "anime"},
        headers=_auth_headers(user_id),
    )
    assert second_script_resp.status_code == 201, second_script_resp.text
    latest_script_id = second_script_resp.json()["id"]
    assert latest_script_id != first_script_resp.json()["id"]

    status_resp = client.get(f"/api/v1/chapters/{chapter_id}/production-status", headers=_auth_headers(user_id))
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["script_id"] == latest_script_id

    generate_resp = client.post(
        f"/api/v1/chapters/{chapter_id}/generate-all",
        json={"style": "anime", "shot_count": 2},
        headers=_auth_headers(user_id),
    )
    assert generate_resp.status_code == 200, generate_resp.text
    payload = generate_resp.json()
    assert payload["script_id"] == latest_script_id
    assert payload["shot_count"] == 2

    storyboard_resp = client.get(f"/api/v1/storyboards/{payload['storyboard_id']}", headers=_auth_headers(user_id))
    assert storyboard_resp.status_code == 200, storyboard_resp.text
    assert storyboard_resp.json()["script_id"] == latest_script_id


def test_video_job_update_cancel_and_archive_management(client: TestClient) -> None:
    user_id = "video-job-manage-user"
    shot_id, storyboard_id, script_id = _create_shot(client, user_id)
    job_id = f"video-job-manage-{uuid4()}"
    _insert_video_job(
        VideoJob(
            id=job_id,
            user_id=user_id,
            task_id=f"video-task-manage-{uuid4()}",
            title="待管理视频任务",
            prompt="镜头管理测试",
            model_id="test-model",
            model_name="测试模型",
            status="pending",
            progress=10,
            duration=4,
            resolution="720p",
            extra_data={
                "shot_id": shot_id,
                "storyboard_id": storyboard_id,
                "script_id": script_id,
            },
        )
    )

    update_resp = client.put(
        f"/api/v1/video/jobs/{job_id}",
        json={"title": "更新后的视频任务", "progress": 35, "status": "running"},
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["title"] == "更新后的视频任务"
    assert updated["status"] == "running"
    assert updated["progress"] == 35
    assert updated["shot_id"] == shot_id

    cancel_resp = client.post(f"/api/v1/video/jobs/{job_id}/cancel", headers=_auth_headers(user_id))
    assert cancel_resp.status_code == 200
    cancelled = cancel_resp.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["error_message"] == "任务已由用户取消"

    jobs_before_delete = client.get("/api/v1/video/jobs", headers=_auth_headers(user_id)).json()
    assert any(item["id"] == job_id for item in jobs_before_delete)

    delete_resp = client.delete(f"/api/v1/video/jobs/{job_id}", headers=_auth_headers(user_id))
    assert delete_resp.status_code == 200

    jobs_after_delete = client.get("/api/v1/video/jobs", headers=_auth_headers(user_id)).json()
    assert all(item["id"] != job_id for item in jobs_after_delete)


def test_video_job_cannot_cancel_completed_job(client: TestClient) -> None:
    user_id = "video-job-complete-cancel-user"
    job_id = f"video-job-complete-cancel-{uuid4()}"
    _insert_video_job(
        VideoJob(
            id=job_id,
            user_id=user_id,
            task_id=f"video-task-complete-cancel-{uuid4()}",
            title="已完成视频任务",
            prompt="已完成不能取消",
            model_id="test-model",
            model_name="测试模型",
            status="succeeded",
            progress=100,
            video_url="https://example.com/video.mp4",
        )
    )

    cancel_resp = client.post(f"/api/v1/video/jobs/{job_id}/cancel", headers=_auth_headers(user_id))
    assert cancel_resp.status_code == 400


def test_workflow_concatenate_builds_multi_shot_sequence_manifest(client: TestClient) -> None:
    user_id = "sequence-manifest-user"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 连续成片")

    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "shot_count": 2,
            "style": "anime",
            "use_ai_refine": False,
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    storyboard_id = storyboard_payload["id"]
    script_id = storyboard_payload["script_id"]
    shots = storyboard_payload["shots"][:2]

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "连续成片工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    video_job_ids = []
    tts_job_ids = []
    for index, shot in enumerate(shots, start=1):
        video_resp = client.post(
            "/api/v1/video/generate",
                json={
                    "prompt": f"连续成片镜头 {index}",
                    "workflow_id": workflow_id,
                    "shot_id": shot["id"],
                    "duration": max(4, shot["duration"]),
                },
            headers=_auth_headers(user_id),
        )
        assert video_resp.status_code == 200
        video_job_ids.append(video_resp.json()["job_id"])

        tts_resp = client.post(
            "/api/v1/tts/generate",
            json={
                "text": f"第 {index} 个镜头台词",
                "title": f"镜头 {index} 配音",
                "workflow_id": workflow_id,
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "script_id": script_id,
                "storyboard_id": storyboard_id,
                "shot_id": shot["id"],
            },
            headers=_auth_headers(user_id),
        )
        assert tts_resp.status_code == 200
        tts_job_ids.append(tts_resp.json()["job_id"])

    concat_resp = client.post(
        f"/api/v1/workflow/concatenate/{workflow_id}",
        json={
            "video_job_ids": video_job_ids,
            "tts_job_ids": tts_job_ids,
            "title": "连续成片",
            "transition_style": "fade",
            "include_subtitles": True,
            "quality_profile": "review",
        },
        headers=_auth_headers(user_id),
    )
    assert concat_resp.status_code == 200
    concat_payload = concat_resp.json()
    assert concat_payload["job_id"]
    assert concat_payload["segment_count"] == 2
    assert concat_payload["manifest_url"].startswith("/static/exports/")
    assert concat_payload["output_url"].startswith("/static/dev/final-")
    assert concat_payload["duration_seconds"] >= 8

    synthesis_resp = client.get(
        f"/api/v1/synthesis/jobs/{concat_payload['job_id']}",
        headers=_auth_headers(user_id),
    )
    assert synthesis_resp.status_code == 200
    synthesis_payload = synthesis_resp.json()
    assert synthesis_payload["output_url"] != synthesis_payload["video_url"]
    extra = synthesis_payload["extra_data"]
    assert extra["manifest_url"] == concat_payload["manifest_url"]
    assert extra["segment_count"] == 2
    assert [segment["video"]["job_id"] for segment in extra["segments"]] == video_job_ids
    assert [segment["audio"]["job_id"] for segment in extra["segments"]] == tts_job_ids
    assert extra["segments"][0]["lineage"]["chapter_id"] == chapter_id
    assert extra["segments"][0]["subtitle"]["enabled"] is True
    assert extra["segments"][1]["transition"]["style"] == "fade"

    manifest_resp = client.get(concat_payload["manifest_url"])
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["segment_count"] == 2
    assert manifest["tracks"]["subtitle"][0]["text"] == "第 1 个镜头台词"

    workflow_status = client.get(
        f"/api/v1/workflow/status/{workflow_id}",
        headers=_auth_headers(user_id),
    )
    assert workflow_status.status_code == 200
    status_payload = workflow_status.json()
    assert status_payload["synthesis_jobs"][0]["manifest_url"] == concat_payload["manifest_url"]
    assert status_payload["synthesis_jobs"][0]["segment_count"] == 2

    preflight_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/render/preflight",
        headers=_auth_headers(user_id),
    )
    assert preflight_resp.status_code == 200
    preflight = preflight_resp.json()
    assert preflight["ready"] is True
    assert preflight["segment_count"] == 2
    assert preflight["manifest_url"] == concat_payload["manifest_url"]

    render_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={"quality_profile": "review"},
        headers=_auth_headers(user_id),
    )
    assert render_resp.status_code == 200
    render_payload = render_resp.json()
    assert render_payload["status"] == "rendered"
    assert render_payload["preview_url"].endswith("-preview.html")
    assert render_payload["srt_url"].endswith(".srt")
    assert render_payload["timeline_url"].endswith("-timeline.json")
    assert render_payload["render_manifest_url"].startswith("/static/exports/")

    srt_resp = client.get(render_payload["srt_url"])
    assert srt_resp.status_code == 200
    assert "第 1 个镜头台词" in srt_resp.text
    assert "00:00:00,000 -->" in srt_resp.text

    timeline_resp = client.get(render_payload["timeline_url"])
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert timeline["tracks"][0]["track_type"] == "video"
    assert len(timeline["tracks"][0]["clips"]) == 2

    sync_timeline_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/timeline/sync",
        json={"synthesis_job_id": concat_payload["job_id"], "name": "首集可编辑时间线"},
        headers=_auth_headers(user_id),
    )
    assert sync_timeline_resp.status_code == 200
    synced = sync_timeline_resp.json()
    assert synced["track_count"] == 3
    assert synced["clip_count"] == 6
    assert synced["duration_seconds"] == concat_payload["duration_seconds"]

    tracks_resp = client.get(f"/api/v1/timelines/{synced['timeline_id']}/tracks", headers=_auth_headers(user_id))
    assert tracks_resp.status_code == 200
    tracks = tracks_resp.json()
    assert [track["track_type"] for track in tracks] == ["video", "audio", "subtitle"]

    clips_resp = client.get(f"/api/v1/timelines/{synced['timeline_id']}/clips", headers=_auth_headers(user_id))
    assert clips_resp.status_code == 200
    clips = clips_resp.json()
    assert len(clips) == 6
    assert len([clip for clip in clips if clip["source_type"] in {"video_job", "direct_audio_video"}]) == 2
    assert len([clip for clip in clips if clip["source_type"] == "subtitle"]) == 2
    assert any(clip["text_content"] == "第 1 个镜头台词" for clip in clips)

    first_subtitle_clip = next(clip for clip in clips if clip["source_type"] == "subtitle")
    update_clip_resp = client.put(
        f"/api/v1/timelines/{synced['timeline_id']}/clips/{first_subtitle_clip['id']}",
        json={
            "text_content": "已编辑 Timeline 字幕",
            "position": 0.5,
            "duration": 3.0,
        },
        headers=_auth_headers(user_id),
    )
    assert update_clip_resp.status_code == 200

    timeline_preflight_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/render/preflight",
        params={"synthesis_job_id": concat_payload["job_id"], "use_editable_timeline": "true"},
        headers=_auth_headers(user_id),
    )
    assert timeline_preflight_resp.status_code == 200
    timeline_preflight = timeline_preflight_resp.json()
    assert timeline_preflight["render_source"] == "editable_timeline"
    assert timeline_preflight["timeline_id"] == synced["timeline_id"]

    timeline_render_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={
            "synthesis_job_id": concat_payload["job_id"],
            "force": True,
            "use_editable_timeline": True,
        },
        headers=_auth_headers(user_id),
    )
    assert timeline_render_resp.status_code == 200
    timeline_render = timeline_render_resp.json()
    assert timeline_render["render_source"] == "editable_timeline"
    assert timeline_render["timeline_id"] == synced["timeline_id"]

    edited_srt_resp = client.get(timeline_render["srt_url"])
    assert edited_srt_resp.status_code == 200
    assert "已编辑 Timeline 字幕" in edited_srt_resp.text
    assert "第 1 个镜头台词" not in edited_srt_resp.text
    assert "00:00:00,500 --> 00:00:03,500" in edited_srt_resp.text

    edited_timeline_resp = client.get(timeline_render["timeline_url"])
    assert edited_timeline_resp.status_code == 200
    edited_timeline = edited_timeline_resp.json()
    assert edited_timeline["source"] == "editable_timeline"
    assert edited_timeline["timeline_id"] == synced["timeline_id"]
    assert edited_timeline["tracks"][2]["clips"][0]["text_content"] == "已编辑 Timeline 字幕"

    rendered_job = client.get(
        f"/api/v1/synthesis/jobs/{concat_payload['job_id']}",
        headers=_auth_headers(user_id),
    ).json()
    assert rendered_job["output_url"] == timeline_render["preview_url"]
    assert rendered_job["extra_data"]["render_status"] == "rendered"
    assert rendered_job["extra_data"]["render_artifacts"]["srt_url"] == timeline_render["srt_url"]
    assert rendered_job["extra_data"]["render_source"] == "editable_timeline"

    rendered_status = client.get(
        f"/api/v1/workflow/status/{workflow_id}",
        headers=_auth_headers(user_id),
    ).json()
    assert 10 in rendered_status["completed_steps"]


def test_workflow_media_batch_separate_video_tts_uses_selected_models(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []
    captured_tts: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    def _fake_create_ark_client(api_key: str, base_url: str | None = None):
        assert api_key == "sk-video"
        return _FakeArkClient()

    async def _fake_tts(self, *args, **kwargs):
        captured_tts.append(kwargs)
        return {
            "task_id": f"tts-task-{len(captured_tts)}",
            "audio_url": f"https://example.com/audio-{len(captured_tts)}.mp3",
            "duration": 3.0,
            "status": "succeeded",
        }

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", _fake_create_ark_client)
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_tts)

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-model-{uuid4()}",
        api_model_id="doubao-seedance-test",
        model_type="video",
        capabilities=["text-to-video"],
        api_key="sk-video",
    )
    audio_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="minimax",
        model_id=f"test-audio-model-{uuid4()}",
        api_model_id="speech-test",
        model_type="tts",
        capabilities=["text-to-speech"],
        api_key="sk-audio",
    )

    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 分步模型")
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 2, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "分步模型工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_model_config_id": audio_config_id,
            "subtitle_mode": "shot_dialogue",
            "audio_mode": "model_audio",
            "voice_model": "female-shaonj",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert payload["ready_for_concatenate"] is False
    assert len(payload["video_job_ids"]) == 2
    assert len(payload["tts_job_ids"]) == 2
    assert len(captured_video) == 2
    assert len(captured_tts) == 2
    assert captured_video[0]["model"] == "doubao-seedance-test"
    assert captured_tts[0]["model"] == "speech-test"
    assert captured_tts[0]["voice_id"] == "female-shaonj"

    video_job = client.get(f"/api/v1/video/jobs/{payload['video_job_ids'][0]}", headers=_auth_headers(user_id)).json()
    assert video_job["model_config_id"] == video_config_id or video_job["prompt_parameters"]["model_config_id"] == video_config_id
    assert video_job["api_model_id"] == "doubao-seedance-test"

    tts_jobs = client.get(f"/api/v1/tts/jobs?workflow_id={workflow_id}", headers=_auth_headers(user_id)).json()
    selected_tts = next(item for item in tts_jobs if item["id"] == payload["tts_job_ids"][0])
    assert selected_tts["extra_data"]["model_config_id"] == audio_config_id
    assert selected_tts["extra_data"]["api_model_id"] == "speech-test"


def test_workflow_media_batch_tts_uses_story_bible_character_voice(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_tts: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "video-task-story-bible-voice"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    async def _fake_tts(self, *args, **kwargs):
        captured_tts.append(kwargs)
        return {
            "task_id": "tts-task-story-bible-voice",
            "audio_url": "https://example.com/story-bible-voice.mp3",
            "duration": 2.8,
            "status": "succeeded",
        }

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())
    monkeypatch.setattr("app.services.minimax_service.MiniMaxService.text_to_speech", _fake_tts)

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-story-bible-voice-{uuid4()}",
        api_model_id="doubao-seedance-story-bible-voice",
        model_type="video",
        capabilities=["text-to-video"],
        api_key="sk-video",
    )
    audio_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="minimax",
        model_id=f"test-audio-story-bible-voice-{uuid4()}",
        api_model_id="speech-story-bible-voice",
        model_type="tts",
        capabilities=["text-to-speech"],
        api_key="sk-audio",
    )

    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 音色一致性")
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "音色一致性 Story Bible",
            "style": "国风修仙赛璐璐动漫",
            "character_rules": [
                {
                    "name": "孙剑",
                    "appearance": "黑发束起，外门灰白短袍，眼神锐利沉稳",
                    "voice": "story-bible-sunjian",
                    "voice_speed": 1.25,
                }
            ],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第一章剧本",
            "content": "孙剑醒来，确认自己重生。",
            "genre": "修仙",
            "style": "国风修仙",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "醒来镜头",
            "content": {"chapter_id": chapter_id, "story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_resp.json()["id"],
            "shot_number": 1,
            "duration": 4,
            "prompt": "孙剑从木榻上惊醒",
            "dialogue": "孙剑：这一世，我不会再输。",
            "character_refs": [{"name": "孙剑"}],
            "extra_data": {"story_bible_id": story_bible_id},
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "Story Bible 音色工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_resp.json()["id"],
            "storyboard_id": storyboard_resp.json()["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_model_config_id": audio_config_id,
            "audio_mode": "model_audio",
            "voice_model": "fallback-voice",
            "speed": 1.0,
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert payload["tts_voice_lock_count"] == 1
    assert captured_tts[0]["voice_id"] == "story-bible-sunjian"
    assert captured_tts[0]["speed"] == 1.25

    tts_jobs = client.get(f"/api/v1/tts/jobs?workflow_id={workflow_id}", headers=_auth_headers(user_id)).json()
    selected_tts = next(item for item in tts_jobs if item["id"] == payload["tts_job_ids"][0])
    assert selected_tts["voice"] == "story-bible-sunjian"
    assert selected_tts["extra_data"]["voice_source"] == "story_bible"
    assert selected_tts["extra_data"]["voice_character_name"] == "孙剑"
    assert selected_tts["extra_data"]["story_bible_id"] == story_bible_id


def test_video_consistency_package_uses_real_novel_character_and_shared_style_seed(
    client: TestClient,
) -> None:
    user_id = f"video-consistency-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "逆天至尊",
            "genre": "修仙",
            "description": "外门弟子孙剑重生归来，承接前世逆天至尊的记忆。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 重生外门",
            "chapter_number": 1,
            "content": "角色：孙剑。场景：青阳宗外门木屋。道具：断剑。事件：孙剑重生。孙剑从剧烈疼痛中醒来，狂喜地确认自己还活着。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "孙剑",
            "description": "青阳宗外门弟子，前世为威震修真界的逆天至尊。",
            "appearance": "年轻瘦弱的身躯，双手带有修炼初期留下的茧子，眼神锐利而深沉。",
            "personality": "隐忍冷静，重生后目标明确。",
            "avatar": "/static/generated/images/sunjian-reference.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201

    bible_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "style": "统一国风修仙赛璐璐动漫，冷暖对比光影"},
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201

    polluted_character_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "character",
            "name": "疼痛",
            "description": "规则识别人物",
            "source": "deterministic",
        },
        headers=_auth_headers(user_id),
    )
    assert polluted_character_resp.status_code == 201
    polluted_prop_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "prop",
            "name": "逆天至尊孙剑",
            "description": "错误道具",
            "source": "deterministic",
        },
        headers=_auth_headers(user_id),
    )
    assert polluted_prop_resp.status_code == 201

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "第一章剧本",
            "content": "孙剑在外门木屋醒来，确认重生，握紧断剑。",
            "genre": "修仙",
            "style": "国风修仙赛璐璐",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "重生醒来",
            "description": "同一场景内连续两个镜头",
            "content": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shot_ids: list[str] = []
    for shot_number, prompt in (
        (1, "孙剑从木榻上惊醒，额头冷汗，窗外晨光落在青阳宗外门木屋。"),
        (2, "孙剑低头看见带茧的双手，握紧断剑，眼神从震惊转为锐利。"),
    ):
        shot_resp = client.post(
            "/api/v1/shots",
            json={
                "storyboard_id": storyboard_id,
                "shot_number": shot_number,
                "duration": 4,
                "prompt": prompt,
                "visual_description": prompt,
                "dialogue": "孙剑：这一世，我不会再输。",
                "character_refs": [{"name": "疼痛", "source": "deterministic"}],
            },
            headers=_auth_headers(user_id),
        )
        assert shot_resp.status_code == 201
        shot_ids.append(shot_resp.json()["id"])

    jobs = []
    for shot_id in shot_ids:
        video_resp = client.post(
            "/api/v1/video/generate",
            json={
                "prompt": "生成逆天至尊第一章连续镜头",
                "shot_id": shot_id,
                "duration": 4,
                "resolution": "720p",
            },
            headers=_auth_headers(user_id),
        )
        assert video_resp.status_code == 200
        job_resp = client.get(f"/api/v1/video/jobs/{video_resp.json()['job_id']}", headers=_auth_headers(user_id))
        assert job_resp.status_code == 200
        jobs.append(job_resp.json())

    assert jobs[0]["consistency"]["series_seed"] == jobs[1]["consistency"]["series_seed"]
    assert jobs[0]["consistency"]["style_lock"]["storyboard_id"] == storyboard_id
    assert jobs[0]["prompt_parameters"]["image_url_sent"] is False
    assert jobs[0]["prompt_parameters"]["reference_image_source"] == "character_avatar"
    assert "公网" in jobs[0]["prompt_parameters"]["image_url_omitted_reason"]
    assert jobs[0]["image_url"] == "/static/generated/images/sunjian-reference.png"
    assert "孙剑" in jobs[0]["prompt"]
    assert "年轻瘦弱" in jobs[0]["prompt"]
    assert "眼神锐利" in jobs[0]["prompt"]
    assert "疼痛: 规则识别人物" not in jobs[0]["prompt"]
    assert all(ref["name"] == "孙剑" for ref in jobs[0]["character_refs"])
    assert all("孙剑" not in ref.get("name", "") for ref in jobs[0]["prop_refs"])


def test_video_consistency_uses_same_novel_seed_across_chapters(
    client: TestClient,
) -> None:
    user_id = f"whole-novel-video-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "逆天至尊跨章",
            "genre": "修仙",
            "description": "角色：孙剑。场景：青阳宗。道具：断剑。事件：孙剑重生后继续修炼。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_ids = []
    for number, title, content in [
        (
            1,
            "第一章 重生外门",
            "角色：孙剑。场景：青阳宗外门木屋。道具：断剑。事件：孙剑重生。孙剑醒来握紧断剑，确认自己重生。",
        ),
        (
            2,
            "第二章 断剑试炼",
            "角色：孙剑。场景：青阳宗试炼台。道具：断剑。事件：试炼反击。孙剑带着断剑走上试炼台，承接重生后的决心。",
        ),
    ]:
        chapter_resp = client.post(
            "/api/v1/chapters",
            json={
                "novel_id": novel_id,
                "title": title,
                "chapter_number": number,
                "content": content,
            },
            headers=_auth_headers(user_id),
        )
        assert chapter_resp.status_code == 201
        chapter_ids.append(chapter_resp.json()["id"])

    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "孙剑",
            "description": "青阳宗外门弟子，重生后保留前世记忆。",
            "appearance": "黑发束起，外门灰白短袍，眼神锐利沉稳。",
            "avatar": "/static/generated/images/sunjian-series-ref.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201

    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "逆天至尊跨章 Story Bible",
            "style": "统一国风修仙赛璐璐动漫，角色线条干净，灵气光效稳定",
            "worldview": "青阳宗外门弟子通过试炼进入内门，断剑承载前世记忆。",
            "character_rules": [{"name": "孙剑", "appearance": "黑发束起，外门灰白短袍，眼神锐利沉稳"}],
            "scene_rules": [{"name": "青阳宗", "description": "山门青石、晨雾、冷暖对比光影"}],
            "prop_rules": [{"name": "断剑", "state": "由孙剑持有"}],
            "event_timeline": [{"name": "孙剑重生", "sequence": 1}],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    for entity_type, name, chapter_id, attributes in [
        ("character", "孙剑", chapter_ids[0], {"state": "刚重生", "costume": "外门灰白短袍"}),
        ("character", "孙剑", chapter_ids[1], {"state": "准备试炼", "costume": "外门灰白短袍"}),
        ("scene", "青阳宗外门木屋", chapter_ids[0], {"scene_dna": {"lighting": "清晨冷光"}}),
        ("scene", "青阳宗试炼台", chapter_ids[1], {"scene_dna": {"lighting": "正午强光"}}),
        ("prop", "断剑", chapter_ids[0], {"state": "被孙剑握紧", "owner": "孙剑"}),
        ("event", "孙剑重生", chapter_ids[0], {"sequence": 1}),
        ("event", "试炼反击", chapter_ids[1], {"sequence": 2}),
    ]:
        entity_resp = client.post(
            "/api/v1/story-bibles/entities",
            json={
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "entity_type": entity_type,
                "name": name,
                "description": f"{name} 跨章连续性设定",
                "attributes": attributes,
                "source": "manual",
            },
            headers=_auth_headers(user_id),
        )
        assert entity_resp.status_code == 201

    machine_resp = client.post(
        f"/api/v1/story-bibles/{story_bible_id}/state-machine",
        json={"novel_id": novel_id, "persist": True},
        headers=_auth_headers(user_id),
    )
    assert machine_resp.status_code == 200

    jobs = []
    storyboards = []
    for chapter_id in chapter_ids:
        storyboard_resp = client.post(
            "/api/v1/storyboards/generate-smart",
            json={
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "story_bible_id": story_bible_id,
                "shot_count": 1,
                "style": "anime",
                "use_ai_refine": False,
            },
            headers=_auth_headers(user_id),
        )
        assert storyboard_resp.status_code == 201
        storyboard_payload = storyboard_resp.json()
        storyboards.append(storyboard_payload)
        shot = storyboard_payload["shots"][0]
        assert shot["extra_data"]["novel_series_seed"]
        assert shot["extra_data"]["continuity_lock"]["scope"] == "novel_series"

        video_resp = client.post(
            "/api/v1/video/generate",
            json={
                "prompt": "生成整部小说一致的动漫镜头",
                "shot_id": shot["id"],
                "story_bible_id": story_bible_id,
                "duration": 4,
                "resolution": "720p",
            },
            headers=_auth_headers(user_id),
        )
        assert video_resp.status_code == 200
        job_resp = client.get(f"/api/v1/video/jobs/{video_resp.json()['job_id']}", headers=_auth_headers(user_id))
        assert job_resp.status_code == 200
        jobs.append(job_resp.json())

    assert storyboards[0]["content"]["novel_series_seed"] == storyboards[1]["content"]["novel_series_seed"]
    assert storyboards[0]["content"]["chapter_seed"] != storyboards[1]["content"]["chapter_seed"]
    assert jobs[0]["consistency"]["novel_series_seed"] == jobs[1]["consistency"]["novel_series_seed"]
    assert jobs[0]["consistency"]["chapter_seed"] != jobs[1]["consistency"]["chapter_seed"]
    assert jobs[0]["consistency"]["style_lock"]["scope"] == "novel_series"
    assert jobs[0]["consistency"]["style_lock"]["novel_series_seed"] == jobs[1]["consistency"]["style_lock"]["novel_series_seed"]
    assert jobs[1]["consistency"]["previous_chapter_context"]["title"] == "第一章 重生外门"
    assert jobs[1]["consistency"]["chapter_state_snapshot"]["title"] == "第二章 断剑试炼"
    assert "整部小说连续性锁" in jobs[1]["prompt"]
    assert "上一章承接" in jobs[1]["prompt"]
    assert "第一章 重生外门" in jobs[1]["prompt"]
    assert "孙剑" in jobs[1]["prompt"]
    assert "断剑" in jobs[1]["prompt"]
    assert jobs[1]["prompt_parameters"]["reference_image_source"] == "character_avatar"


def test_workflow_media_batch_uses_consistency_prompt_and_reference_image(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-consistency-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-consistency-model-{uuid4()}",
        api_model_id="doubao-seedance-consistency-test",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 批量一致性")
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "沈砚",
            "appearance": "青衣长发，神情冷静",
            "avatar": "https://example.com/shenyan.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 2, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "批量一致性工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 2
    first_prompt = captured_video[0]["content"][-1]["text"]
    assert "视频一致性约束" in first_prompt
    assert "角色视觉DNA锁" in first_prompt
    assert "沈砚" in first_prompt
    assert captured_video[0]["content"][0]["type"] == "image_url"
    assert captured_video[0]["seed"] != captured_video[1]["seed"]

    jobs = [
        client.get(f"/api/v1/video/jobs/{job_id}", headers=_auth_headers(user_id)).json()
        for job_id in payload["video_job_ids"]
    ]
    assert jobs[0]["consistency"]["series_seed"] == jobs[1]["consistency"]["series_seed"]
    assert jobs[0]["prompt_parameters"]["reference_image_source"] == "character_avatar"


def test_workflow_media_batch_skips_local_reference_image_for_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-local-ref-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-local-ref-model-{uuid4()}",
        api_model_id="doubao-seedance-local-ref-test",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 本地参考图")
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "林澈",
            "appearance": "黑发少年，灰色短袍，目光坚定",
            "avatar": "/static/generated/images/linche-reference.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "本地参考图批量工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 1
    assert captured_video[0]["content"][0]["type"] == "text"
    assert all(item["type"] != "image_url" for item in captured_video[0]["content"])

    job = client.get(f"/api/v1/video/jobs/{payload['video_job_ids'][0]}", headers=_auth_headers(user_id)).json()
    assert job["image_url"] == "/static/generated/images/linche-reference.png"
    assert job["prompt_parameters"]["image_url_sent"] is False
    assert job["prompt_parameters"]["reference_image_source"] == "character_avatar"
    assert "公网" in job["prompt_parameters"]["image_url_omitted_reason"]
    assert "参考图接入说明" in job["prompt"]


def test_workflow_media_batch_maps_local_reference_image_through_public_storage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_video: list[dict] = []

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            captured_video.append(kwargs)

            class _CreateResult:
                id = f"video-cdn-ref-task-{len(captured_video)}"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video._create_ark_client", lambda *_: _FakeArkClient())

    user_id = uuid4().hex
    storage_config_id = _create_public_storage_config(client, user_id)
    video_config_id = _insert_model_config(
        user_id=user_id,
        provider_id="volcano",
        model_id=f"test-video-cdn-ref-model-{uuid4()}",
        api_model_id="doubao-seedance-cdn-ref-test",
        model_type="video",
        capabilities=["text-to-video", "image-to-video"],
        api_key="sk-video",
    )
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id, "第一章 CDN参考图")
    character_resp = client.post(
        "/api/v1/characters",
        json={
            "novel_id": novel_id,
            "name": "林澈",
            "appearance": "黑发少年，灰色短袍，目光坚定",
            "avatar": "/static/generated/images/linche-reference.png",
        },
        headers=_auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards/generate-smart",
        json={"novel_id": novel_id, "chapter_id": chapter_id, "shot_count": 1, "style": "anime", "use_ai_refine": False},
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_payload = storyboard_resp.json()
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "CDN参考图批量工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": storyboard_payload["script_id"],
            "storyboard_id": storyboard_payload["id"],
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    batch_resp = client.post(
        f"/api/v1/workflow/{workflow_resp.json()['workflow_id']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts",
            "model_config_id": video_config_id,
            "audio_mode": "none",
        },
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    payload = batch_resp.json()
    assert len(captured_video) == 1
    assert captured_video[0]["content"][0]["type"] == "image_url"
    assert captured_video[0]["content"][0]["image_url"]["url"] == "https://cdn.example.com/static/generated/images/linche-reference.png"

    job = client.get(f"/api/v1/video/jobs/{payload['video_job_ids'][0]}", headers=_auth_headers(user_id)).json()
    assert job["image_url"] == "/static/generated/images/linche-reference.png"
    assert job["prompt_parameters"]["image_url_sent"] is True
    assert job["prompt_parameters"]["provider_image_url"] == "https://cdn.example.com/static/generated/images/linche-reference.png"
    assert job["prompt_parameters"]["image_delivery_method"] == "public_static_base_url"
    assert job["prompt_parameters"]["image_delivery_config_id"] == storage_config_id


def test_entity_extraction_does_not_treat_state_words_as_characters() -> None:
    from app.services.entity_extraction_service import extract_story_entities

    text = "剧烈疼痛之后，狂喜涌上心头，阳光照进木屋，年轻瘦弱的双手还在颤抖。角色：孙剑。孙剑说道：这一世我会改写命运。"
    entities = extract_story_entities(text, {"character"})
    names = {entity["name"] for entity in entities}
    assert "孙剑" in names
    assert "疼痛" not in names
    assert "狂喜" not in names
    assert "阳光" not in names
    assert "年轻" not in names
    assert "瘦弱" not in names


def test_workflow_render_preflight_reports_missing_manifest(client: TestClient) -> None:
    user_id = "render-preflight-missing-user"
    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={"title": "缺少清单工作流"},
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    preflight_resp = client.get(
        f"/api/v1/workflow/{workflow_id}/render/preflight",
        headers=_auth_headers(user_id),
    )
    assert preflight_resp.status_code == 200
    payload = preflight_resp.json()
    assert payload["ready"] is False
    assert payload["blocking_issue_count"] == 1
    assert payload["issues"][0]["code"] == "missing_synthesis_job"

    render_resp = client.post(
        f"/api/v1/workflow/{workflow_id}/render",
        json={},
        headers=_auth_headers(user_id),
    )
    assert render_resp.status_code == 404


def test_tts_job_includes_script_id_from_shot_context(client: TestClient, fake_tts_service: None) -> None:
    shot_id, _storyboard_id, script_id = _create_shot(client, "tts-lineage-user")

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
            "shot_id": shot_id,
        },
        headers=_auth_headers("tts-lineage-user"),
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    jobs_response = client.get("/api/v1/tts/jobs", headers=_auth_headers("tts-lineage-user"))
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == job_id)
    assert job["shot_id"] == shot_id
    assert job["script_id"] == script_id


def test_synthesis_job_includes_video_tts_sources(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
            "video_job_id": "video-job-123",
            "tts_job_id": "tts-job-456",
        },
        headers=_auth_headers("synthesis-lineage-user"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]

    jobs_response = client.get("/api/v1/synthesis/jobs", headers=_auth_headers("synthesis-lineage-user"))
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == payload["job_id"])
    assert job["video_job_id"] == "video-job-123"
    assert job["tts_job_id"] == "tts-job-456"


def test_synthesis_jobs_filter_lineage_and_expose_render_artifacts(client: TestClient) -> None:
    user_id = "synthesis-filter-user"
    matched_job_id = f"synthesis-filter-match-{uuid4()}"
    other_job_id = f"synthesis-filter-other-{uuid4()}"
    novel_id = f"novel-{uuid4()}"
    chapter_id = f"chapter-{uuid4()}"
    script_id = f"script-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    shot_id = f"shot-{uuid4()}"

    _insert_synthesis_job(
        SynthesisJob(
            id=matched_job_id,
            user_id=user_id,
            workflow_id="workflow-filter-1",
            title="第一章可播放渲染包",
            model_id="local-render",
            model_name="本地渲染包",
            video_url="/static/dev/source-a.mp4",
            audio_url="/static/dev/audio-a.mp3",
            status="succeeded",
            progress=100,
            output_url="/static/exports/render-a-preview.html",
            duration_seconds=8,
            extra_data={
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "script_id": script_id,
                "storyboard_id": storyboard_id,
                "shot_id": shot_id,
                "render_status": "rendered",
                "manifest_url": "/static/exports/sequence-a.json",
                "segment_count": 1,
                "render_artifacts": {
                    "preview_url": "/static/exports/render-a-preview.html",
                    "srt_url": "/static/exports/render-a.srt",
                    "timeline_url": "/static/exports/render-a-timeline.json",
                    "render_manifest_url": "/static/exports/render-a.json",
                },
                "segments": [
                    {
                        "lineage": {
                            "novel_id": novel_id,
                            "chapter_id": chapter_id,
                            "script_id": script_id,
                            "storyboard_id": storyboard_id,
                            "shot_id": shot_id,
                        }
                    }
                ],
            },
        )
    )
    _insert_synthesis_job(
        SynthesisJob(
            id=other_job_id,
            user_id=user_id,
            workflow_id="workflow-filter-2",
            title="第二章草稿",
            model_id="local-render",
            model_name="本地渲染包",
            video_url="/static/dev/source-b.mp4",
            status="succeeded",
            progress=100,
            output_url="/static/exports/render-b-preview.html",
            extra_data={
                "novel_id": novel_id,
                "chapter_id": f"chapter-other-{uuid4()}",
                "script_id": f"script-other-{uuid4()}",
                "storyboard_id": f"storyboard-other-{uuid4()}",
                "shot_id": f"shot-other-{uuid4()}",
                "render_status": "ready",
                "manifest_url": "/static/exports/sequence-b.json",
                "segment_count": 1,
            },
        )
    )

    jobs_response = client.get(
        "/api/v1/synthesis/jobs",
        params={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
            "shot_id": shot_id,
            "status": "succeeded",
            "render_status": "rendered",
        },
        headers=_auth_headers(user_id),
    )

    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert [job["id"] for job in jobs] == [matched_job_id]
    job = jobs[0]
    assert job["novel_id"] == novel_id
    assert job["chapter_id"] == chapter_id
    assert job["script_id"] == script_id
    assert job["storyboard_id"] == storyboard_id
    assert job["shot_id"] == shot_id
    assert job["render_status"] == "rendered"
    assert job["manifest_url"] == "/static/exports/sequence-a.json"
    assert job["segment_count"] == 1
    assert job["preview_url"] == "/static/exports/render-a-preview.html"
    assert job["srt_url"] == "/static/exports/render-a.srt"
    assert job["timeline_url"] == "/static/exports/render-a-timeline.json"
    assert job["render_manifest_url"] == "/static/exports/render-a.json"


def test_tts_requires_api_key_outside_dev_mode(
    client: TestClient,
    fake_tts_service: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_MODE", "false")
    suffix = uuid4().hex[:10]
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"tts-key-user-{suffix}",
            "email": f"tts-key-user-{suffix}@example.test",
            "password": "testPass123",
        },
    )
    assert register_resp.status_code == 200
    access_token = register_resp.json()["access_token"]
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 422


def test_tts_rejects_blank_api_key(client: TestClient, fake_tts_service: None) -> None:
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "   ",
        },
    )

    assert response.status_code == 422


def test_tts_rejects_unknown_shot_id(client: TestClient, fake_tts_service: None) -> None:
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "shot_id": "missing-shot",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 404


def test_synthesis_requires_api_key(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
        },
    )

    assert response.status_code == 422


def test_synthesis_requires_audio_url(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 422


def test_synthesis_rejects_blank_api_key(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "   ",
        },
    )

    assert response.status_code == 422


def test_synthesis_rejects_invalid_video_url(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "not-a-url",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 422


def test_tts_generate_returns_502_when_service_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_text_to_speech(self, *args, **kwargs):
        raise Exception("upstream failure")

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.text_to_speech",
        _failing_text_to_speech,
    )

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 502


def test_synthesis_generate_returns_502_when_service_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_video_voice_synthesis(self, *args, **kwargs):
        raise Exception("upstream failure")

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.video_voice_synthesis",
        _failing_video_voice_synthesis,
    )

    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 502


def test_tts_defaults_status_and_progress_when_service_omits_status(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _text_to_speech_without_status(self, *args, **kwargs):
        return {
            "task_id": "tts-task-no-status",
            "audio_url": "https://example.com/audio-no-status.mp3",
            "duration": 2.0,
            "model": "test-tts-model",
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.text_to_speech",
        _text_to_speech_without_status,
    )

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    jobs_response = client.get("/api/v1/tts/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == job_id)
    assert job["status"] == "succeeded"
    assert job["progress"] == 100


def test_synthesis_defaults_status_progress_and_model_metadata_when_service_omits_status(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _video_voice_synthesis_without_status(self, *args, **kwargs):
        return {
            "task_id": "synthesis-task-no-status",
            "output_url": "https://example.com/video-no-status.mp4",
            "duration": 6.0,
            "message": "done",
        }

    monkeypatch.setattr(
        "app.services.volcano_service.VolcanoService.video_voice_synthesis",
        _video_voice_synthesis_without_status,
    )

    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    jobs_response = client.get("/api/v1/synthesis/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    job = next(job for job in jobs if job["id"] == job_id)
    assert job["status"] == "succeeded"
    assert job["progress"] == 100
    assert job["model_name"] == "volcano-synthesis"


def test_video_download_supports_relative_static_url(client: TestClient) -> None:
    static_dev_dir = Path(__file__).resolve().parent / "static" / "dev"
    static_dev_dir.mkdir(parents=True, exist_ok=True)
    asset = static_dev_dir / f"download-{uuid4()}.mp4"
    asset.write_bytes(b"fake-video-bytes")
    try:
        response = client.post(
            "/api/v1/video/download",
            json={"video_url": f"/static/dev/{asset.name}", "filename": "clip.mp4"},
        )
    finally:
        asset.unlink(missing_ok=True)

    assert response.status_code == 200
    assert response.content == b"fake-video-bytes"
    assert "attachment" in response.headers.get("content-disposition", "")


def test_timeline_clip_create_uses_nested_clip_route(client: TestClient) -> None:
    user_id = f"timeline-clip-{uuid4()}"
    project_resp = client.post(
        "/api/v1/projects",
        json={"name": "Timeline Clip Project"},
        headers=_auth_headers(user_id),
    )
    assert project_resp.status_code == 201

    timeline_resp = client.post(
        "/api/v1/timelines",
        json={
            "project_id": project_resp.json()["id"],
            "name": "Editable Timeline",
            "video_track_count": 1,
            "audio_track_count": 1,
            "subtitle_track_count": 1,
        },
        headers=_auth_headers(user_id),
    )
    assert timeline_resp.status_code == 201
    timeline_id = timeline_resp.json()["id"]

    tracks_resp = client.get(f"/api/v1/timelines/{timeline_id}/tracks", headers=_auth_headers(user_id))
    assert tracks_resp.status_code == 200
    subtitle_track = next(track for track in tracks_resp.json() if track["track_type"] == "subtitle")

    clip_resp = client.post(
        f"/api/v1/timelines/{timeline_id}/clips",
        json={
            "timeline_id": timeline_id,
            "track_id": subtitle_track["id"],
            "source_type": "subtitle",
            "position": 0,
            "duration": 4,
            "name": "字幕片段",
            "text_content": "可编辑字幕",
        },
        headers=_auth_headers(user_id),
    )
    assert clip_resp.status_code == 201
    clip = clip_resp.json()
    assert clip["timeline_id"] == timeline_id
    assert clip["source_type"] == "subtitle"
    assert clip["text_content"] == "可编辑字幕"

    mismatch_resp = client.post(
        f"/api/v1/timelines/{timeline_id}/clips",
        json={
            "timeline_id": str(uuid4()),
            "track_id": subtitle_track["id"],
            "source_type": "subtitle",
        },
        headers=_auth_headers(user_id),
    )
    assert mismatch_resp.status_code == 422


def test_tts_generate_and_list_job(client: TestClient, fake_tts_service: None) -> None:
    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text": "你好，世界",
            "title": "测试配音任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "tts-task-123"
    assert payload["status"] == "succeeded"
    assert payload["job_id"]

    jobs_response = client.get("/api/v1/tts/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert any(job["id"] == payload["job_id"] for job in jobs)
    assert any(job["audio_url"] == "https://example.com/audio.mp3" for job in jobs)


def test_synthesis_generate_and_list_job(client: TestClient, fake_synthesis_service: None) -> None:
    response = client.post(
        "/api/v1/synthesis/generate",
        json={
            "video_url": "https://example.com/source.mp4",
            "audio_url": "https://example.com/audio.mp3",
            "title": "测试合成任务",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "synthesis-task-123"
    assert payload["status"] == "succeeded"
    assert payload["job_id"]

    jobs_response = client.get("/api/v1/synthesis/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert any(job["id"] == payload["job_id"] for job in jobs)
    assert any(job["output_url"] == "https://example.com/video.mp4" for job in jobs)
