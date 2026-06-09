from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.prompt_composer import compose_generation_prompt
from init_db import init_db
from main import app
from test_short_video_production import _auth_headers


EXPECTED_STANDARD_TASKS = {
    "novel_generation",
    "chapter_writing",
    "script_generation",
    "storyboard_generation",
    "shot_prompt",
    "shot_video",
    "character_image",
    "scene_reference_image",
    "prop_image",
    "novel_cover",
    "tts_dialogue",
    "shot_audio_video",
    "consistency_review",
    "repair_suggestion",
}


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


def test_builtin_prompt_skills_cover_core_ai_flow(client: TestClient) -> None:
    user_id = f"prompt-skill-builtin-user-{uuid4()}"

    list_response = client.get(
        "/api/v1/prompt-skills",
        headers=_auth_headers(user_id),
    )

    assert list_response.status_code == 200
    items = list_response.json()["items"]
    builtin_items = [item for item in items if item["is_builtin"]]
    builtin_tasks = {item["task"] for item in builtin_items}

    assert EXPECTED_STANDARD_TASKS.issubset(builtin_tasks)
    for task in EXPECTED_STANDARD_TASKS:
        task_items = [item for item in builtin_items if item["task"] == task]
        assert len(task_items) == 1
        skill = task_items[0]
        assert skill["name"].strip()
        assert skill["content"].strip()
        assert skill["is_active"] is True
        assert "标准" in skill["tags"]

    preview_response = client.post(
        "/api/v1/prompt-skills/preview",
        json={
            "task": "novel_cover",
            "context": {"title": "星海试炼", "genre": "科幻冒险", "style": "电影感动漫"},
        },
        headers=_auth_headers(user_id),
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["skill_count"] == 1
    assert "封面" in preview["prompt"]
    assert "星海试炼" in preview["prompt"]


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
    by_id = {item["id"]: item for item in items}
    assert created["id"] in by_id
    assert "builtin-shot_video-standard" in by_id
    assert by_id["builtin-shot_video-standard"]["is_builtin"] is True

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


def test_prompt_skill_clone_edit_activate_keeps_one_active_per_task(client: TestClient) -> None:
    user_id = f"prompt-skill-activate-user-{uuid4()}"

    first_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "基础镜头技能",
            "task": "shot_video",
            "stage": "consistency",
            "content": "基础技能: {tone}",
            "variables": {"tone": "冷蓝光影"},
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert first_response.status_code == 201
    first = first_response.json()

    second_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "新版镜头技能",
            "task": "shot_video",
            "stage": "consistency",
            "content": "新版技能: {tone}",
            "variables": {"tone": "冷蓝月光"},
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert second_response.status_code == 201
    second = second_response.json()

    active_response = client.get(
        "/api/v1/prompt-skills",
        params={"task": "shot_video", "active": "true"},
        headers=_auth_headers(user_id),
    )
    assert active_response.status_code == 200
    active_items = active_response.json()["items"]
    assert [item["id"] for item in active_items] == [second["id"]]

    clone_response = client.post(
        f"/api/v1/prompt-skills/{second['id']}/clone",
        headers=_auth_headers(user_id),
    )
    assert clone_response.status_code == 201
    clone = clone_response.json()
    assert clone["is_active"] is False

    update_response = client.put(
        f"/api/v1/prompt-skills/{clone['id']}",
        json={
            "name": "回滚镜头技能",
            "task": "shot_video",
            "stage": "consistency",
            "content": "回滚技能: {tone}",
            "variables": {"tone": "冷蓝微光"},
            "priority": 30,
            "inject_position": "before_constraints",
            "is_active": False,
            "tags": ["回滚"],
        },
        headers=_auth_headers(user_id),
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["version"] == clone["version"] + 1

    activate_response = client.post(
        f"/api/v1/prompt-skills/{clone['id']}/activate",
        headers=_auth_headers(user_id),
    )
    assert activate_response.status_code == 200
    activated = activate_response.json()
    assert activated["id"] == clone["id"]
    assert activated["is_active"] is True

    active_after_response = client.get(
        "/api/v1/prompt-skills",
        params={"task": "shot_video", "active": "true"},
        headers=_auth_headers(user_id),
    )
    active_after = active_after_response.json()["items"]
    assert [item["id"] for item in active_after] == [clone["id"]]

    all_response = client.get(
        "/api/v1/prompt-skills",
        params={"task": "shot_video"},
        headers=_auth_headers(user_id),
    )
    by_id = {item["id"]: item for item in all_response.json()["items"]}
    assert by_id[first["id"]]["is_active"] is False
    assert by_id[second["id"]]["is_active"] is False
    assert by_id[clone["id"]]["is_active"] is True


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


def test_user_active_prompt_skill_overrides_builtin_prompt_skill(client: TestClient) -> None:
    user_id = f"prompt-skill-override-user-{uuid4()}"
    create_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "用户镜头视频标准",
            "task": "shot_video",
            "stage": "generation",
            "content": "用户覆盖技能: 使用{tone}，只保留当前项目自定义规则。",
            "variables": {"tone": "冷蓝光影"},
            "priority": 1,
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
            "extra_context": {"tone": "银蓝夜色"},
        },
        headers=_auth_headers(user_id),
    )

    assert compose_response.status_code == 200
    prompt = compose_response.json()["prompt"]
    assert "用户覆盖技能: 使用银蓝夜色" in prompt
    assert "标准镜头视频技能" not in prompt
