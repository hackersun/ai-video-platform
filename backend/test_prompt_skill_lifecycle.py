from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import PromptSkill
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
