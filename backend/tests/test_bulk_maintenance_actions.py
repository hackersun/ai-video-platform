from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from app.core.security import get_current_user_id
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


def _create_novel_and_chapter(client: TestClient, user_id: str, content: str) -> tuple[str, str]:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": f"批量维护测试小说 {uuid4()}",
            "genre": "玄幻",
            "description": "用于批量维护和重抽测试。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章",
            "chapter_number": 1,
            "content": content,
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    return novel_id, chapter_resp.json()["id"]


def _create_asset(client: TestClient, user_id: str, name: str, **overrides) -> dict:
    payload = {
        "category": "prop",
        "asset_type": "text",
        "name": name,
        "description": f"{name} 描述",
        "tags": ["批量测试"],
    }
    payload.update(overrides)
    response = client.post("/api/v1/assets", json=payload, headers=_auth_headers(user_id))
    assert response.status_code == 201
    return response.json()


def _create_story_entity(
    client: TestClient,
    user_id: str,
    *,
    novel_id: str,
    chapter_id: str | None = None,
    script_id: str | None = None,
    entity_type: str = "character",
    name: str = "测试实体",
) -> dict:
    response = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "entity_type": entity_type,
            "name": name,
            "description": f"{name} 的视觉设定",
            "appearance": f"{name} 外观明确，便于生成参考图",
            "visual_prompt": f"{name} 动漫设定稿",
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()


def test_asset_bulk_archive_skips_locked_assets_and_test_override_warns(client: TestClient) -> None:
    user_id = f"bulk-asset-user-{uuid4()}"
    free_asset = _create_asset(client, user_id, "可归档资产")
    locked_asset = _create_asset(client, user_id, "锁定资产")

    lock_resp = client.post(f"/api/v1/assets/{locked_asset['id']}/lock", headers=_auth_headers(user_id))
    assert lock_resp.status_code == 200

    blocked_resp = client.post(
        "/api/v1/assets/bulk-action",
        json={"asset_ids": [free_asset["id"], locked_asset["id"]], "action": "archive"},
        headers=_auth_headers(user_id),
    )
    assert blocked_resp.status_code == 200
    blocked = blocked_resp.json()
    assert blocked["updated_count"] == 1
    assert any(item["id"] == locked_asset["id"] and "锁定" in item["reason"] for item in blocked["skipped"])

    override_resp = client.post(
        "/api/v1/assets/bulk-action",
        json={"asset_ids": [locked_asset["id"]], "action": "archive", "allow_test_override": True},
        headers=_auth_headers(user_id),
    )
    assert override_resp.status_code == 200
    override = override_resp.json()
    assert override["updated_count"] == 1
    assert any("测试模式" in warning for warning in override["warnings"])


def test_asset_bulk_test_override_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    user_id = f"prod-{uuid4().hex[:12]}"
    locked_asset = _create_asset(client, user_id, "生产锁定资产")
    assert client.post(f"/api/v1/assets/{locked_asset['id']}/lock", headers=_auth_headers(user_id)).status_code == 200
    monkeypatch.setenv("DEV_MODE", "false")

    async def override_user_id() -> str:
        return user_id

    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        response = client.post(
            "/api/v1/assets/bulk-action",
            json={"asset_ids": [locked_asset["id"]], "action": "archive", "allow_test_override": True},
        )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_count"] == 0
    assert any(item["id"] == locked_asset["id"] and "锁定" in item["reason"] for item in payload["skipped"])
    assert any("生产模式" in warning for warning in payload["warnings"])


def test_bulk_set_scope_requires_scope_identifier(client: TestClient) -> None:
    user_id = f"bulk-scope-user-{uuid4()}"
    asset = _create_asset(client, user_id, "缺少作用域资产")
    novel_id, chapter_id = _create_novel_and_chapter(client, user_id, "顾青在云桥拾起银钥。")
    entity_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "prop",
            "name": "银钥",
            "description": "带云纹的银钥",
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert entity_resp.status_code == 201
    entity = entity_resp.json()

    asset_resp = client.post(
        "/api/v1/assets/bulk-action",
        json={"asset_ids": [asset["id"]], "action": "set_scope", "scope": "novel"},
        headers=_auth_headers(user_id),
    )
    assert asset_resp.status_code == 422
    assert "novel_id" in asset_resp.json()["detail"]

    entity_resp = client.post(
        "/api/v1/story-bibles/entities/bulk-action",
        json={"entity_ids": [entity["id"]], "action": "set_scope", "scope": "chapter"},
        headers=_auth_headers(user_id),
    )
    assert entity_resp.status_code == 422
    assert "chapter_id" in entity_resp.json()["detail"]


def test_asset_reextract_by_novel_generates_entity_view_assets(client: TestClient) -> None:
    user_id = f"asset-reextract-novel-{uuid4()}"
    novel_id, chapter_id = _create_novel_and_chapter(client, user_id, "林澈握着玉符走进青石大殿。")
    entity = _create_story_entity(
        client,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="character",
        name="林澈",
    )

    response = client.post(
        "/api/v1/assets/reextract",
        json={"novel_id": novel_id, "entity_types": ["character"], "mode": "append", "style": "anime"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 3
    assert payload["deleted_count"] == 0
    assert payload["updated_count"] == 1
    assert {asset["entity_id"] for asset in payload["assets"]} == {entity["id"]}
    assert {asset["generation_params"]["view_key"] for asset in payload["assets"]} == {"front", "side", "back"}


def test_asset_reextract_delete_then_extract_archives_unlocked_and_skips_locked_assets(client: TestClient) -> None:
    user_id = f"asset-reextract-lock-{uuid4()}"
    novel_id, chapter_id = _create_novel_and_chapter(client, user_id, "银钥落在阵台上，符文亮起。")
    entity = _create_story_entity(
        client,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="prop",
        name="银钥",
    )
    unlocked = _create_asset(
        client,
        user_id,
        "银钥 · 主视图旧版",
        category="prop",
        asset_type="image",
        entity_id=entity["id"],
        entity_type="prop",
        novel_id=novel_id,
        chapter_id=chapter_id,
        generation_params={"source": "entity_multiview", "view_key": "main"},
    )
    locked = _create_asset(
        client,
        user_id,
        "银钥 · 细节定稿",
        category="prop",
        asset_type="image",
        entity_id=entity["id"],
        entity_type="prop",
        novel_id=novel_id,
        chapter_id=chapter_id,
        generation_params={"source": "entity_multiview", "view_key": "detail"},
    )
    assert client.post(f"/api/v1/assets/{locked['id']}/lock", headers=_auth_headers(user_id)).status_code == 200

    response = client.post(
        "/api/v1/assets/reextract",
        json={
            "entity_ids": [entity["id"]],
            "entity_types": ["prop"],
            "mode": "delete_then_extract",
            "style": "anime",
            "view_keys": ["main", "detail"],
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 1
    assert payload["deleted_count"] == 1
    assert any(item["id"] == locked["id"] and "锁定" in item["reason"] for item in payload["skipped"])
    assert {asset["generation_params"]["view_key"] for asset in payload["assets"]} == {"main"}

    old_unlocked = client.get(f"/api/v1/assets/{unlocked['id']}", headers=_auth_headers(user_id)).json()
    old_locked = client.get(f"/api/v1/assets/{locked['id']}", headers=_auth_headers(user_id)).json()
    assert old_unlocked["is_active"] is False
    assert old_locked["is_active"] is True


def test_asset_reextract_selected_entity_ids_only(client: TestClient) -> None:
    user_id = f"asset-reextract-selected-{uuid4()}"
    novel_id, chapter_id = _create_novel_and_chapter(client, user_id, "顾青在茶铺看见铜镜和灯笼。")
    selected = _create_story_entity(
        client,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="scene",
        name="茶铺",
    )
    ignored = _create_story_entity(
        client,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type="prop",
        name="铜镜",
    )

    response = client.post(
        "/api/v1/assets/reextract",
        json={"entity_ids": [selected["id"]], "entity_types": ["scene"], "mode": "append", "style": "anime"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 4
    assert {asset["entity_id"] for asset in payload["assets"]} == {selected["id"]}
    assert ignored["id"] not in {asset["entity_id"] for asset in payload["assets"]}


def test_entity_reextract_overwrite_preserves_entity_id_and_updates_content(client: TestClient) -> None:
    user_id = f"bulk-entity-reextract-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_and_chapter(
        client,
        user_id,
        "沈月璃在青阳宗外门石屋醒来，旧铜钩悬在门梁上。王执事提醒她别碰铜钩。",
    )

    entity_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "character",
            "name": "沈月璃",
            "description": "旧描述",
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert entity_resp.status_code == 201
    original = entity_resp.json()

    reextract_resp = client.post(
        "/api/v1/story-bibles/entities/reextract",
        json={
            "chapter_id": chapter_id,
            "entity_types": ["character", "scene", "prop"],
            "mode": "overwrite",
        },
        headers=_auth_headers(user_id),
    )
    assert reextract_resp.status_code == 200
    payload = reextract_resp.json()
    assert payload["updated_count"] >= 1

    list_resp = client.get(
        f"/api/v1/story-bibles/entities?chapter_id={chapter_id}&scope=chapter",
        headers=_auth_headers(user_id),
    )
    assert list_resp.status_code == 200
    entities = list_resp.json()
    updated = next(item for item in entities if item["name"] == "沈月璃")
    assert updated["id"] == original["id"]
    assert updated["description"] != "旧描述"
    assert any(item["name"] == "旧铜钩" and item["entity_type"] == "prop" for item in entities)


def test_entity_reextract_overwrite_refreshes_visual_fields(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    from app.api.v1.endpoints import story_bible

    async def fake_extract(*_args, **_kwargs):
        return [
            {
                "entity_type": "character",
                "name": "陆衡",
                "canonical_name": "陆衡",
                "description": "披青色斗篷、左眼下有银色小痣的青年。",
                "aliases": ["雾港青年"],
                "appearance": "青色斗篷，左眼下银色小痣，手持破损罗盘。",
                "visual_prompt": "anime character, cyan cloak, silver mole under left eye, broken compass",
                "attributes": {"appearance": "青色斗篷，银色小痣", "visual_prompt": "青色斗篷青年"},
                "relations": [{"target": "破损罗盘", "type": "持有"}],
                "state_changes": [{"state": "抵达雾港"}],
                "evidence": "陆衡披青色斗篷穿过雾港，左眼下有银色小痣。",
                "confidence": 96,
                "source": "ai",
            }
        ]

    monkeypatch.setattr(story_bible, "_extract_story_entities_with_optional_ai", fake_extract)
    user_id = f"bulk-entity-visual-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_and_chapter(
        client,
        user_id,
        "陆衡披青色斗篷穿过雾港，左眼下有银色小痣，手中握着破损罗盘。",
    )
    entity_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "character",
            "name": "陆衡",
            "description": "旧描述",
            "attributes": {"appearance": "旧外观", "visual_prompt": "旧提示"},
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert entity_resp.status_code == 201
    original = entity_resp.json()

    response = client.post(
        "/api/v1/story-bibles/entities/reextract",
        json={"chapter_id": chapter_id, "entity_types": ["character"], "mode": "overwrite"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    updated = next(item for item in payload["entities"] if item["name"] == "陆衡")
    assert updated["id"] == original["id"]
    assert updated["appearance"]
    assert updated["appearance"] != "旧外观"
    assert updated["visual_prompt"]
    assert updated["visual_prompt"] != "旧提示"


def test_entity_bulk_delete_archives_unlocked_assets_and_skips_locked_assets(client: TestClient) -> None:
    user_id = f"bulk-entity-delete-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_and_chapter(client, user_id, "林晚握着青铜吊坠站在废弃天桥。")
    entity_resp = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": "prop",
            "name": "青铜吊坠",
            "description": "裂纹吊坠",
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert entity_resp.status_code == 201
    entity = entity_resp.json()
    unlocked = _create_asset(client, user_id, "吊坠草稿", entity_id=entity["id"], entity_type="prop", novel_id=novel_id, chapter_id=chapter_id)
    locked = _create_asset(client, user_id, "吊坠定稿", entity_id=entity["id"], entity_type="prop", novel_id=novel_id, chapter_id=chapter_id)
    assert client.post(f"/api/v1/assets/{locked['id']}/lock", headers=_auth_headers(user_id)).status_code == 200

    delete_resp = client.post(
        "/api/v1/story-bibles/entities/bulk-action",
        json={"entity_ids": [entity["id"]], "action": "delete"},
        headers=_auth_headers(user_id),
    )
    assert delete_resp.status_code == 200
    payload = delete_resp.json()
    assert payload["deleted_count"] == 0
    assert any(item["id"] == locked["id"] and "锁定" in item["reason"] for item in payload["skipped"])

    assets_resp = client.get(f"/api/v1/assets?entity_id={entity['id']}", headers=_auth_headers(user_id))
    assert assets_resp.status_code == 200
    remaining_ids = {item["id"] for item in assets_resp.json()}
    assert unlocked["id"] in remaining_ids
    assert locked["id"] in remaining_ids


def test_template_bulk_clone_and_delete_respects_preset_rules(client: TestClient) -> None:
    user_id = f"bulk-template-user-{uuid4()}"
    custom_resp = client.post(
        "/api/v1/templates",
        json={
            "name": "用户镜头模板",
            "category": "shot",
            "tags": ["旧标签"],
            "content": {"shots": []},
        },
        headers=_auth_headers(user_id),
    )
    assert custom_resp.status_code == 201
    custom = custom_resp.json()

    clone_resp = client.post(
        "/api/v1/templates/bulk-action",
        json={"template_ids": ["preset_0"], "action": "clone"},
        headers=_auth_headers(user_id),
    )
    assert clone_resp.status_code == 200
    assert clone_resp.json()["created_count"] == 1

    delete_resp = client.post(
        "/api/v1/templates/bulk-action",
        json={"template_ids": [custom["id"], "preset_0"], "action": "delete"},
        headers=_auth_headers(user_id),
    )
    assert delete_resp.status_code == 200
    payload = delete_resp.json()
    assert payload["deleted_count"] == 1
    assert any(item["id"] == "preset_0" and "预置" in item["reason"] for item in payload["skipped"])


def test_prompt_skill_bulk_clone_delete_and_tag_rules(client: TestClient) -> None:
    user_id = f"bulk-prompt-skill-user-{uuid4()}"
    inactive_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "未激活批量技能",
            "task": "shot_video",
            "content": "保持镜头约束。",
            "is_active": False,
            "tags": ["旧"],
        },
        headers=_auth_headers(user_id),
    )
    assert inactive_resp.status_code == 201
    inactive = inactive_resp.json()

    active_resp = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "激活批量技能",
            "task": "shot_video",
            "content": "激活镜头约束。",
            "is_active": True,
        },
        headers=_auth_headers(user_id),
    )
    assert active_resp.status_code == 201
    active = active_resp.json()

    tag_resp = client.post(
        "/api/v1/prompt-skills/bulk-action",
        json={"skill_ids": [inactive["id"]], "action": "set_tags", "tags": ["批量", "可维护"]},
        headers=_auth_headers(user_id),
    )
    assert tag_resp.status_code == 200
    assert tag_resp.json()["updated_count"] == 1
    assert tag_resp.json()["skills"][0]["tags"] == ["批量", "可维护"]

    clone_resp = client.post(
        "/api/v1/prompt-skills/bulk-action",
        json={"skill_ids": ["builtin-shot_video-standard"], "action": "clone"},
        headers=_auth_headers(user_id),
    )
    assert clone_resp.status_code == 200
    assert clone_resp.json()["created_count"] == 1

    delete_resp = client.post(
        "/api/v1/prompt-skills/bulk-action",
        json={"skill_ids": [inactive["id"], active["id"], "builtin-shot_video-standard"], "action": "delete"},
        headers=_auth_headers(user_id),
    )
    assert delete_resp.status_code == 200
    payload = delete_resp.json()
    assert payload["deleted_count"] == 1
    assert any(item["id"] == active["id"] and "激活" in item["reason"] for item in payload["skipped"])
    assert any(item["id"] == "builtin-shot_video-standard" and "内置" in item["reason"] for item in payload["skipped"])
