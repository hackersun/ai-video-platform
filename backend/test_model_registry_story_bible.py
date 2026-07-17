"""
Tests for model registry, Story Bible, prompt composition and workflow job binding.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_model_registry_exposes_task_defaults(client: TestClient) -> None:
    response = client.get("/api/v1/llm/registry", headers=auth_headers("registry-user"))

    assert response.status_code == 200
    payload = response.json()
    tasks = {item["task"]: item for item in payload["task_defaults"]}
    assert tasks["novel_generation"]["default_model"]["modality"] == "text"
    assert tasks["character_image"]["default_model"]["api_model_id"] == "doubao-seedream-5-0-260128"
    assert tasks["scene_reference_image"]["default_model"]["api_model_id"] == "doubao-seedream-5-0-260128"
    assert tasks["shot_video"]["default_model"]["modality"] == "video"
    assert tasks["shot_video"]["default_model"]["api_model_id"] == "doubao-seedance-2-0-260128"
    assert tasks["tts_dialogue"]["default_model"]["modality"] == "audio"

    shot_default = client.get("/api/v1/llm/task-defaults/shot_video", headers=auth_headers("registry-user"))
    assert shot_default.status_code == 200
    assert "image_to_video" in shot_default.json()["required_capabilities"]


def test_story_bible_crud_and_prompt_composition(client: TestClient) -> None:
    user_id = "story-bible-user"

    character_resp = client.post(
        "/api/v1/characters",
        json={
            "name": "林舟",
            "description": "少年剑修",
            "appearance": "银发，青色长袍，腰间玉佩",
            "personality": "冷静克制",
            "voice": "calm-young-male",
        },
        headers=auth_headers(user_id),
    )
    assert character_resp.status_code == 201
    character_id = character_resp.json()["id"]

    story_bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "title": "玄都纪元设定",
            "style": "日式赛璐璐动漫，冷色月光，线条清晰",
            "worldview": "灵气复苏后的山海城邦",
            "character_rules": [{"name": "林舟", "appearance": "玉佩必须始终挂在左腰"}],
            "scene_rules": [{"name": "玄都城", "description": "青瓦高墙，空中有灵舟航道"}],
            "prop_rules": [{"name": "玉佩", "state": "不能损坏"}],
            "event_timeline": [{"title": "第一章", "description": "林舟夜入玄都城"}],
            "negative_prompt": "写实摄影，现代车辆",
        },
        headers=auth_headers(user_id),
    )
    assert story_bible_resp.status_code == 201
    story_bible_id = story_bible_resp.json()["id"]

    prompt_resp = client.post(
        "/api/v1/story-bibles/compose-prompt",
        json={
            "task": "shot_video",
            "story_bible_id": story_bible_id,
            "character_ids": [character_id],
            "extra_context": {"镜头目标": "夜色中角色抬头看见灵舟"},
        },
        headers=auth_headers(user_id),
    )

    assert prompt_resp.status_code == 200
    prompt = prompt_resp.json()["prompt"]
    assert "shot_video" in prompt
    assert "日式赛璐璐动漫" in prompt
    assert "玉佩必须始终挂在左腰" in prompt
    assert "林舟" in prompt
    assert "夜色中角色抬头看见灵舟" in prompt


def test_workflow_status_returns_only_bound_jobs(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = "workflow-bound-user"

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={"title": "绑定测试工作流"},
        headers=auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    class _FakeTasks:
        @staticmethod
        def create(*args, **kwargs):
            class _CreateResult:
                id = "bound-video-task"

            return _CreateResult()

    class _FakeContentGeneration:
        tasks = _FakeTasks()

    class _FakeArkClient:
        content_generation = _FakeContentGeneration()

    monkeypatch.setattr("app.api.v1.endpoints.video.create_ark_client", lambda *_: _FakeArkClient())

    unbound_resp = client.post(
        "/api/v1/video/generate",
        json={"prompt": "不属于该工作流", "api_key": "test-key"},
        headers=auth_headers(user_id),
    )
    assert unbound_resp.status_code == 200

    bound_resp = client.post(
        "/api/v1/video/generate",
        json={
            "prompt": "属于该工作流",
            "api_key": "test-key",
            "project_id": "project-123",
            "workflow_id": workflow_id,
        },
        headers=auth_headers(user_id),
    )
    assert bound_resp.status_code == 200
    bound_job_id = bound_resp.json()["job_id"]

    status_resp = client.get(f"/api/v1/workflow/status/{workflow_id}", headers=auth_headers(user_id))
    assert status_resp.status_code == 200
    video_jobs = status_resp.json()["video_jobs"]
    assert [job["id"] for job in video_jobs] == [bound_job_id]
    assert video_jobs[0]["workflow_id"] == workflow_id
    assert video_jobs[0]["project_id"] == "project-123"
