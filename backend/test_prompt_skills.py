from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import PromptSkill
from app.services.prompt_composer import compose_generation_prompt
from init_db import init_db
from main import app
from test_short_video_production import _auth_headers


EXPECTED_STANDARD_TASKS = {
    "novel_generation",
    "chapter_writing",
    "script_generation",
    "storyboard_generation",
    "entity_extraction",
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


def test_prompt_skill_variable_guides_cover_storyboard_dialogue_context(client: TestClient) -> None:
    user_id = f"prompt-skill-variable-user-{uuid4()}"

    guide_response = client.get(
        "/api/v1/prompt-skills/variables",
        params={"task": "storyboard_generation"},
        headers=_auth_headers(user_id),
    )

    assert guide_response.status_code == 200
    guide = guide_response.json()
    assert guide["task"] == "storyboard_generation"
    assert guide["task_label"] == "分镜创建"
    variable_by_name = {item["name"]: item for item in guide["items"]}

    for name in ("shot_count", "style", "source_content", "dialogue", "subtitle_text"):
        assert name in variable_by_name
        assert variable_by_name[name]["example"]

    assert variable_by_name["dialogue"]["system_fill"] is True
    assert "角色名：台词" in variable_by_name["dialogue"]["description"]
    assert variable_by_name["subtitle_text"]["system_fill"] is True
    assert guide["sample_context"]["dialogue"]
    assert guide["sample_context"]["subtitle_text"]

    preview_response = client.post(
        "/api/v1/prompt-skills/preview",
        json={
            "task": "storyboard_generation",
            "draft_name": "分镜变量预览",
            "draft_content": "生成{shot_count}个镜头，对白为{dialogue}，字幕为{subtitle_text}。",
            "context": guide["sample_context"],
        },
        headers=_auth_headers(user_id),
    )

    assert preview_response.status_code == 200
    prompt = preview_response.json()["prompt"]
    assert "生成8个镜头" in prompt
    assert "沈砚：铜铃又响了。" in prompt
    assert "字幕为沈砚：铜铃又响了。" in prompt
    assert "{dialogue}" not in prompt


def test_prompt_skill_variable_guides_cover_entity_asset_extraction(client: TestClient) -> None:
    user_id = f"prompt-skill-entity-variable-user-{uuid4()}"

    guide_response = client.get(
        "/api/v1/prompt-skills/variables",
        params={"task": "entity_extraction"},
        headers=_auth_headers(user_id),
    )

    assert guide_response.status_code == 200
    guide = guide_response.json()
    assert guide["task"] == "entity_extraction"
    assert guide["task_label"] == "实体/资产抽取"
    variable_by_name = {item["name"]: item for item in guide["items"]}

    for name in ("source_content", "entity_types", "allowed_entity_types", "output_format"):
        assert name in variable_by_name
        assert variable_by_name[name]["example"]

    preview_response = client.post(
        "/api/v1/prompt-skills/preview",
        json={
            "task": "entity_extraction",
            "context": guide["sample_context"],
        },
        headers=_auth_headers(user_id),
    )

    assert preview_response.status_code == 200
    prompt = preview_response.json()["prompt"]
    assert "实体/资产抽取" in prompt or "实体" in prompt
    assert "JSON 数组" in prompt


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
    assert by_id["builtin-shot_video-standard"]["is_active"] is False
    assert [item["id"] for item in items if item["is_active"]] == [created["id"]]

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


def test_published_prompt_skill_edit_projects_draft_until_activate(client: TestClient) -> None:
    user_id = f"prompt-skill-version-user-{uuid4()}"
    created = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "模型提示词", "task": "script_generation", "stage": "analysis",
            "content": "published body", "variables": {
                "routing": {"model_filter": ["MiniMax-M3"]},
            }, "is_active": True,
        },
        headers=_auth_headers(user_id),
    ).json()

    updated_response = client.put(
        f"/api/v1/prompt-skills/{created['id']}",
        json={
            "name": "模型提示词（已编辑）", "description": "新的展示说明",
            "task": "script_generation", "stage": "analysis",
            "content": "draft body", "variables": {
                "routing": {"model_filter": ["MiniMax-M3"]},
            }, "priority": 23, "inject_position": "after_constraints",
            "tags": ["已编辑"], "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["version"] == 2
    assert updated_response.json()["content"] == "draft body"
    assert updated_response.json()["name"] == "模型提示词（已编辑）"
    assert updated_response.json()["description"] == "新的展示说明"
    assert updated_response.json()["priority"] == 23
    assert updated_response.json()["inject_position"] == "after_constraints"
    assert updated_response.json()["tags"] == ["已编辑"]

    item_response = client.get(
        "/api/v1/prompt-skills", params={"task": "script_generation"},
        headers=_auth_headers(user_id),
    )
    assert item_response.status_code == 200
    item = next(row for row in item_response.json()["items"] if row["id"] == created["id"])
    assert item["content"] == "draft body"
    assert item["name"] == "模型提示词（已编辑）"
    assert item["description"] == "新的展示说明"
    assert item["priority"] == 23
    assert item["inject_position"] == "after_constraints"
    assert item["tags"] == ["已编辑"]

    preview_response = client.post(
        "/api/v1/prompt-skills/preview",
        json={"task": "script_generation", "skill_ids": [created["id"]], "context": {}},
        headers=_auth_headers(user_id),
    )
    assert preview_response.status_code == 200
    assert "draft body" in preview_response.json()["prompt"]
    assert preview_response.json()["skills"][0]["name"] == "模型提示词（已编辑）"

    clone_response = client.post(
        f"/api/v1/prompt-skills/{created['id']}/clone", headers=_auth_headers(user_id),
    )
    assert clone_response.status_code == 201
    assert clone_response.json()["content"] == "draft body"
    assert clone_response.json()["is_active"] is False
    assert clone_response.json()["name"] == "模型提示词（已编辑） 副本"
    assert clone_response.json()["description"] == "新的展示说明"
    assert clone_response.json()["priority"] == 23
    assert clone_response.json()["inject_position"] == "after_constraints"
    assert clone_response.json()["tags"] == ["已编辑"]

    async def stored_state():
        from app.models import PromptProfileVersion

        async with AsyncSessionLocal() as db:
            skill = await db.get(PromptSkill, created["id"])
            versions = list((await db.execute(
                select(PromptProfileVersion)
                .where(PromptProfileVersion.profile_id == created["id"])
                .order_by(PromptProfileVersion.version)
            )).scalars())
            return skill.content, [(item.version, item.status, item.content) for item in versions]

    skill_content, versions = asyncio.run(stored_state())
    assert skill_content == "published body"
    assert versions == [(1, "published", "published body"), (2, "draft", "draft body")]

    activated = client.post(
        f"/api/v1/prompt-skills/{created['id']}/activate",
        headers=_auth_headers(user_id),
    )
    assert activated.status_code == 200
    assert activated.json()["version"] == 2
    assert activated.json()["content"] == "draft body"
    assert activated.json()["name"] == "模型提示词（已编辑）"
    assert activated.json()["description"] == "新的展示说明"


def test_active_prompt_skill_task_change_requires_clone(client: TestClient) -> None:
    user_id = f"prompt-skill-task-user-{uuid4()}"
    created = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "不可改任务", "task": "script_generation", "stage": "analysis",
            "content": "published body", "is_active": True,
        },
        headers=_auth_headers(user_id),
    ).json()

    response = client.put(
        f"/api/v1/prompt-skills/{created['id']}",
        json={
            "name": "不可改任务", "task": "shot_video", "stage": "analysis",
            "content": "published body", "is_active": True,
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    assert "克隆" in response.json()["detail"]


def test_replaced_and_deleted_legacy_skill_cannot_remain_canonical_candidate(
    client: TestClient,
) -> None:
    user_id = f"prompt-skill-retire-user-{uuid4()}"
    first = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "旧精确模板", "task": "script_generation", "stage": "analysis",
            "content": "old exact", "variables": {
                "routing": {"model_filter": ["MiniMax-M3"]},
            }, "is_active": True,
        },
        headers=_auth_headers(user_id),
    ).json()
    second = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "新通用模板", "task": "script_generation", "stage": "analysis",
            "content": "new generic", "variables": {}, "is_active": True,
        },
        headers=_auth_headers(user_id),
    ).json()

    async def route_and_state():
        from app.models import PromptProfileVersion
        from app.services.prompt_template_router import select_prompt_skill_for_model

        async with AsyncSessionLocal() as db:
            route = await select_prompt_skill_for_model(
                db, user_id=user_id, task="script_generation", provider_name="minimax",
                model_id="MiniMax-M3", model_capabilities=["text_generation"],
            )
            first_skill = await db.get(PromptSkill, first["id"])
            versions = list((await db.execute(
                select(PromptProfileVersion)
                .where(PromptProfileVersion.profile_id == first["id"])
                .order_by(PromptProfileVersion.version)
            )).scalars())
            return route, getattr(first_skill, "prompt_profile_version_id", None), versions[-1]

    route, linked_version_id, latest = asyncio.run(route_and_state())
    assert route["prompt_skill_name"] == second["name"]
    assert latest.status == "disabled"
    assert linked_version_id == latest.id

    reactivated = client.post(
        f"/api/v1/prompt-skills/{first['id']}/activate", headers=_auth_headers(user_id),
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["id"] == first["id"]
    assert reactivated.json()["is_active"] is True
    route, linked_version_id, latest = asyncio.run(route_and_state())
    assert route["prompt_skill_name"] == first["name"]
    assert route["prompt_profile_version_id"] == linked_version_id == latest.id
    assert latest.status == "published"

    replaced_again = client.post(
        f"/api/v1/prompt-skills/{second['id']}/activate", headers=_auth_headers(user_id),
    )
    assert replaced_again.status_code == 200

    deleted = client.delete(
        f"/api/v1/prompt-skills/{first['id']}", headers=_auth_headers(user_id),
    )
    assert deleted.status_code == 200
    route_after, _, _ = asyncio.run(route_and_state())
    assert route_after["prompt_skill_name"] == second["name"]


def test_put_is_active_true_reactivates_canonical_profile(client: TestClient) -> None:
    user_id = f"prompt-skill-put-reactivate-user-{uuid4()}"
    first = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "PUT 重新激活", "task": "script_generation", "stage": "analysis",
            "content": "reactivated exact", "variables": {
                "routing": {"model_filter": ["MiniMax-M3"]},
            }, "is_active": True,
        },
        headers=_auth_headers(user_id),
    ).json()
    client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "当前通用模板", "task": "script_generation", "stage": "analysis",
            "content": "current generic", "is_active": True,
        },
        headers=_auth_headers(user_id),
    )

    updated = client.put(
        f"/api/v1/prompt-skills/{first['id']}",
        json={
            "name": "PUT 重新激活", "task": "script_generation", "stage": "analysis",
            "content": "reactivated exact", "variables": {
                "routing": {"model_filter": ["MiniMax-M3"]},
            }, "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is True

    async def route_and_version():
        from app.models import PromptProfileVersion
        from app.services.prompt_template_router import select_prompt_skill_for_model

        async with AsyncSessionLocal() as db:
            route = await select_prompt_skill_for_model(
                db, user_id=user_id, task="script_generation", provider_name="minimax",
                model_id="MiniMax-M3", model_capabilities=["text_generation"],
            )
            skill = await db.get(PromptSkill, first["id"])
            version = await db.get(PromptProfileVersion, skill.prompt_profile_version_id)
            return route, version

    route, version = asyncio.run(route_and_version())
    assert version.status == "published"
    assert route["prompt_skill_id"] == first["id"]
    assert route["prompt_profile_version_id"] == version.id


def test_activate_translates_canonical_validation_error(client: TestClient) -> None:
    user_id = f"prompt-skill-validation-user-{uuid4()}"
    skill = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "校验失败草稿", "task": "script_generation", "stage": "analysis",
            "content": "draft body", "is_active": False,
        },
        headers=_auth_headers(user_id),
    ).json()

    async def corrupt_checksum():
        from app.models import PromptProfileVersion

        async with AsyncSessionLocal() as db:
            version = await db.get(PromptProfileVersion, skill["prompt_profile_version_id"])
            version.checksum = "0" * 64
            await db.commit()

    asyncio.run(corrupt_checksum())
    response = client.post(
        f"/api/v1/prompt-skills/{skill['id']}/activate", headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    assert "checksum" in response.json()["detail"]


def test_prompt_skill_delete_only_allows_inactive_user_skill(client: TestClient) -> None:
    user_id = f"prompt-skill-delete-user-{uuid4()}"

    inactive_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "未发布草稿技能",
            "task": "shot_video",
            "stage": "consistency",
            "content": "草稿技能: {tone}",
            "is_active": False,
        },
        headers=_auth_headers(user_id),
    )
    assert inactive_response.status_code == 201
    inactive = inactive_response.json()

    active_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "已发布在用技能",
            "task": "shot_video",
            "stage": "consistency",
            "content": "在用技能: {tone}",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert active_response.status_code == 201
    active = active_response.json()

    active_delete_response = client.delete(
        f"/api/v1/prompt-skills/{active['id']}",
        headers=_auth_headers(user_id),
    )
    assert active_delete_response.status_code == 422
    assert "正在使用" in active_delete_response.json()["detail"]

    builtin_delete_response = client.delete(
        "/api/v1/prompt-skills/builtin-shot_video-standard",
        headers=_auth_headers(user_id),
    )
    assert builtin_delete_response.status_code == 422
    assert "内置" in builtin_delete_response.json()["detail"]

    delete_response = client.delete(
        f"/api/v1/prompt-skills/{inactive['id']}",
        headers=_auth_headers(user_id),
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
    assert delete_response.json()["id"] == inactive["id"]

    list_response = client.get(
        "/api/v1/prompt-skills",
        params={"task": "shot_video"},
        headers=_auth_headers(user_id),
    )
    ids = {item["id"] for item in list_response.json()["items"]}
    assert inactive["id"] not in ids
    assert active["id"] in ids


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


def test_prompt_skill_optimize_returns_polished_content_and_warnings(client: TestClient) -> None:
    user_id = f"prompt-skill-optimize-user-{uuid4()}"

    response = client.post(
        "/api/v1/prompt-skills/optimize",
        json={
            "task": "shot_video",
            "name": "镜头漂移控制",
            "description": "控制镜头生成时的角色漂移",
            "content": "保持角色一致，不要乱变。",
            "mode": "polish",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["task"] == "shot_video"
    assert result["source"] in {"local_rules", "ai_model"}
    assert "优化目标" in result["optimized_content"]
    assert "保持角色一致" in result["optimized_content"]
    assert result["warnings"]
    assert "original_content" in result


def test_prompt_skill_optimize_requires_content(client: TestClient) -> None:
    user_id = f"prompt-skill-optimize-empty-user-{uuid4()}"

    response = client.post(
        "/api/v1/prompt-skills/optimize",
        json={
            "task": "shot_video",
            "name": "空内容",
            "content": "   ",
            "mode": "polish",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 400
    assert "请先填写" in response.json()["detail"]


def test_prompt_skill_preview_can_use_unsaved_draft_content(client: TestClient) -> None:
    user_id = f"prompt-skill-draft-preview-user-{uuid4()}"

    response = client.post(
        "/api/v1/prompt-skills/preview",
        json={
            "task": "shot_video",
            "draft_name": "草稿镜头技能",
            "draft_content": "草稿技能约束: 使用{tone}，避免{bad_case}。",
            "context": {"tone": "青绿色边缘光", "bad_case": "表情漂移"},
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["skill_count"] == 1
    assert result["skills"][0]["id"] == "draft"
    assert "草稿技能约束: 使用青绿色边缘光，避免表情漂移。" in result["prompt"]
