"""
Asset-backed custom storyboard template tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.time_utils import utc_now
from app.core.database import AsyncSessionLocal
from app.models.asset import Asset
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


def _insert_duplicate_starter_assets(user_id: str) -> None:
    import asyncio

    async def _insert() -> None:
        async with AsyncSessionLocal() as session:
            now = utc_now()
            for index in range(2):
                session.add(
                    Asset(
                        id=str(uuid4()),
                        user_id=user_id,
                        category="prompt",
                        name=f"重复系统预置资产 {index}",
                        asset_type="text",
                        source_url="starter:asset-character-consistency-prompt",
                        tags=["系统预置"],
                        is_active=True,
                        is_public=False,
                        created_at=now,
                        updated_at=now,
                    )
                )
            await session.commit()

    asyncio.run(_insert())


def test_custom_template_asset_crud_exposes_shot_template(client: TestClient) -> None:
    user_id = "template-asset-user"
    shot_template = {
        "shot_count": 2,
        "shots": [
            {"camera_angle": "wide", "camera_movement": "static", "emotion": "tense"},
            {"camera_angle": "close-up", "camera_movement": "zoom_in", "emotion": "surprised"},
        ],
    }

    create_resp = client.post(
        "/api/v1/assets",
        json={
            "category": "template",
            "asset_type": "text",
            "name": "悬疑双镜头模板",
            "description": "用于快速生成悬疑揭示镜头",
            "tags": ["悬疑", "揭示"],
            "style_tags": ["anime"],
            "prompt_template": "{{character}}在{{scene}}发现{{prop}}",
            "variables": [{"name": "character", "type": "character_ref"}],
            "shot_template": shot_template,
            "is_public": True,
        },
        headers=auth_headers(user_id),
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    asset_id = created["id"]
    assert created["shot_template"]["shot_count"] == 2
    assert created["is_public"] is True

    list_resp = client.get("/api/v1/assets?category=template&include_public=false", headers=auth_headers(user_id))
    assert list_resp.status_code == 200
    assert any(item["id"] == asset_id and item["shot_template"]["shot_count"] == 2 for item in list_resp.json())

    update_resp = client.put(
        f"/api/v1/assets/{asset_id}",
        json={"name": "悬疑三镜头模板", "shot_template": {"shot_count": 3, "shots": shot_template["shots"]}},
        headers=auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "悬疑三镜头模板"
    assert update_resp.json()["shot_template"]["shot_count"] == 3

    delete_resp = client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers(user_id))
    assert delete_resp.status_code == 204

    after_delete = client.get("/api/v1/assets?category=template&include_public=false", headers=auth_headers(user_id))
    assert after_delete.status_code == 200
    assert all(item["id"] != asset_id for item in after_delete.json())


def test_default_anime_starter_assets_are_seeded_and_editable(client: TestClient) -> None:
    user_id = f"starter-assets-user-{uuid4()}"

    first_resp = client.get("/api/v1/assets?include_public=false&limit=200", headers=auth_headers(user_id))
    assert first_resp.status_code == 200
    assets = first_resp.json()
    names = {item["name"] for item in assets}
    assert "角色一致性提示词" in names
    assert "9:16 短剧三段式镜头模板" in names
    assert "命运吊坠道具 DNA" in names
    assert "修仙宗门场景包" in names
    assert "修仙突破提示词" in names
    assert "武侠江湖场景包" in names
    assert "武侠刀剑对决提示词" in names
    assert "玄幻秘境场景包" in names
    assert "玄幻血脉觉醒提示词" in names
    assert "都市异能场景包" in names
    assert "都市异能觉醒提示词" in names

    template = next(item for item in assets if item["name"] == "9:16 短剧三段式镜头模板")
    assert template["shot_template"]["shot_count"] == 5
    assert template["is_public"] is False

    update_resp = client.put(
        f"/api/v1/assets/{template['id']}",
        json={"name": "9:16 短剧三段式镜头模板-已定制"},
        headers=auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"].endswith("已定制")

    second_resp = client.get("/api/v1/assets?include_public=false&limit=200", headers=auth_headers(user_id))
    assert second_resp.status_code == 200
    seeded_keys = [
        item
        for item in second_resp.json()
        if item.get("tags") and "系统预置" in item["tags"]
    ]
    assert len(seeded_keys) >= 8
    assert sum(1 for item in second_resp.json() if item["id"] == template["id"]) == 1


def test_asset_library_tolerates_duplicate_default_seed_rows(client: TestClient) -> None:
    user_id = f"starter-duplicate-assets-user-{uuid4()}"
    _insert_duplicate_starter_assets(user_id)

    list_resp = client.get("/api/v1/assets?include_public=false&limit=200", headers=auth_headers(user_id))
    assert list_resp.status_code == 200, list_resp.text
    names = {item["name"] for item in list_resp.json()}
    assert "角色一致性提示词" in names

    category_resp = client.get("/api/v1/assets/categories?include_public=false", headers=auth_headers(user_id))
    assert category_resp.status_code == 200, category_resp.text


def test_asset_categories_count_visible_assets_and_novel_filter_includes_global(client: TestClient) -> None:
    user_id = f"asset-filter-user-{uuid4()}"
    other_user_id = f"asset-filter-other-{uuid4()}"

    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "资产筛选小说", "genre": "都市异能", "description": "测试资产筛选"},
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    global_resp = client.post(
        "/api/v1/assets",
        json={
            "category": "prop",
            "asset_type": "text",
            "name": "通用道具资产",
            "description": "所有小说都可复用",
            "tags": ["通用"],
        },
        headers=auth_headers(user_id),
    )
    assert global_resp.status_code == 201
    global_asset_id = global_resp.json()["id"]

    novel_asset_resp = client.post(
        "/api/v1/assets",
        json={
            "category": "prop",
            "asset_type": "text",
            "name": "小说专属道具资产",
            "description": "仅当前小说使用",
            "novel_id": novel_id,
            "tags": ["专属"],
        },
        headers=auth_headers(user_id),
    )
    assert novel_asset_resp.status_code == 201
    novel_asset_id = novel_asset_resp.json()["id"]

    other_resp = client.post(
        "/api/v1/assets",
        json={"category": "prop", "asset_type": "text", "name": "其他用户私有道具"},
        headers=auth_headers(other_user_id),
    )
    assert other_resp.status_code == 201

    category_resp = client.get("/api/v1/assets/categories?include_public=false", headers=auth_headers(user_id))
    assert category_resp.status_code == 200
    prop_category = next(item for item in category_resp.json() if item["name"] == "prop")
    assert prop_category["asset_count"] >= 3
    assert prop_category["asset_count"] < 20

    filtered_resp = client.get(
        f"/api/v1/assets?novel_id={novel_id}&category=prop&include_public=false&limit=200",
        headers=auth_headers(user_id),
    )
    assert filtered_resp.status_code == 200
    filtered_ids = {item["id"] for item in filtered_resp.json()}
    assert global_asset_id in filtered_ids
    assert novel_asset_id in filtered_ids
    assert other_resp.json()["id"] not in filtered_ids

    scoped_resp = client.get(
        f"/api/v1/assets?novel_id={novel_id}&category=prop&scope=novel&include_public=false&limit=200",
        headers=auth_headers(user_id),
    )
    assert scoped_resp.status_code == 200
    scoped_ids = {item["id"] for item in scoped_resp.json()}
    assert novel_asset_id in scoped_ids
    assert global_asset_id not in scoped_ids
