from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.prompt_composer import compose_generation_prompt
from init_db import init_db
from main import app
from test_short_video_production import _auth_headers


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def test_compose_generation_prompt_injects_skill_blocks_before_video_constraints() -> None:
    prompt = compose_generation_prompt(
        task="shot_video",
        skill_blocks=["技能约束: 使用冷蓝光影，保持角色服装连续。"],
    )

    assert "技能约束: 使用冷蓝光影，保持角色服装连续。" in prompt
    assert prompt.index("技能约束: 使用冷蓝光影") < prompt.index("视频一致性约束:")


def test_prompt_skill_create_list_and_preview(client: TestClient) -> None:
    user_id = f"prompt-skill-user-{uuid4()}"

    create_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "冷蓝短剧一致性",
            "description": "约束竖屏短剧的色彩和漂移风险",
            "task": "shot_video",
            "stage": "consistency",
            "content": "技能约束: 使用{tone}，避免{bad_case}。",
            "variables": {"tone": "冷蓝光影", "bad_case": "角色服装漂移"},
            "priority": 20,
            "inject_position": "before_constraints",
            "is_active": True,
            "tags": ["短剧", "一致性"],
        },
        headers=_auth_headers(user_id),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "冷蓝短剧一致性"
    assert created["version"] == 1

    list_response = client.get(
        "/api/v1/prompt-skills",
        params={"task": "shot_video"},
        headers=_auth_headers(user_id),
    )
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert [item["id"] for item in items] == [created["id"]]

    preview_response = client.post(
        "/api/v1/prompt-skills/preview",
        json={
            "task": "shot_video",
            "skill_ids": [created["id"]],
            "context": {"tone": "冷蓝月光", "bad_case": "脸型变化"},
        },
        headers=_auth_headers(user_id),
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["skill_count"] == 1
    assert "技能约束: 使用冷蓝月光，避免脸型变化。" in preview["prompt"]
    assert "视频一致性约束:" in preview["prompt"]


def test_story_bible_compose_prompt_uses_active_prompt_skills(client: TestClient) -> None:
    user_id = f"prompt-skill-compose-user-{uuid4()}"
    create_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "自动注入技能",
            "task": "shot_video",
            "stage": "consistency",
            "content": "技能约束: 使用{tone}，避免{bad_case}。",
            "variables": {"tone": "冷蓝光影", "bad_case": "角色服装漂移"},
            "priority": 10,
            "inject_position": "before_constraints",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert create_response.status_code == 201

    compose_response = client.post(
        "/api/v1/story-bibles/compose-prompt",
        json={
            "task": "shot_video",
            "extra_context": {"tone": "冷蓝月光", "bad_case": "脸型变化"},
        },
        headers=_auth_headers(user_id),
    )

    assert compose_response.status_code == 200
    prompt = compose_response.json()["prompt"]
    assert "技能约束: 使用冷蓝月光，避免脸型变化。" in prompt
    assert prompt.index("技能约束: 使用冷蓝月光") < prompt.index("视频一致性约束:")
