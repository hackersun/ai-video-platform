from __future__ import annotations

from uuid import uuid4

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


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _create_novel_chapter(client: TestClient, user_id: str) -> tuple[str, str]:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": f"轻量动漫生产包 {uuid4()}",
            "genre": "都市异能",
            "description": "沈砚和林晚在废弃天桥追查青铜吊坠裂纹。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 裂纹月光",
            "chapter_number": 1,
            "content": "沈砚和林晚在雨后的废弃天桥发现青铜吊坠出现裂纹。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    return novel_id, chapter_resp.json()["id"]


def _create_entity(
    client: TestClient,
    user_id: str,
    novel_id: str,
    entity_type: str,
    name: str,
    attributes: dict,
    chapter_id: str | None = None,
    script_id: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "entity_type": entity_type,
            "name": name,
            "description": f"{name} 的生产设定",
            "attributes": attributes,
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()


def test_story_entity_production_pack_consistency_versions_and_shot_bindings(client: TestClient) -> None:
    user_id = f"production-pack-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_chapter(client, user_id)

    character = _create_entity(
        client,
        user_id,
        novel_id,
        "character",
        "沈砚",
        {
            "asset_pack": {
                "front": "/static/refs/shenyan-front.png",
                "side": "/static/refs/shenyan-side.png",
                "full_body": "/static/refs/shenyan-full.png",
            },
            "relationships": [
                {"target": "林晚", "type": "守护", "status": "信任", "evidence": "第一章共同逃离"}
            ],
            "visual_dna": {"hair": "黑色短发", "eyes": "琥珀色", "costume": "深色校服"},
        },
        chapter_id,
    )
    scene = _create_entity(
        client,
        user_id,
        novel_id,
        "scene",
        "废弃天桥",
        {
            "scene_tags": ["室外", "夜晚", "战斗"],
            "scene_dna": {"lighting": "冷蓝月光", "layout": "断裂天桥", "weather": "雨后潮湿"},
        },
        chapter_id,
    )
    prop = _create_entity(
        client,
        user_id,
        novel_id,
        "prop",
        "青铜吊坠",
        {
            "prop_dna": {"material": "青铜", "shape": "六边形吊坠", "marking": "裂纹月纹"},
            "owner": "沈砚",
        },
        chapter_id,
    )
    _create_entity(
        client,
        user_id,
        novel_id,
        "event",
        "吊坠裂纹显现",
        {
            "sequence": 1,
            "participants": ["沈砚", "林晚"],
            "location": "废弃天桥",
            "prop_state_changes": [{"prop": "青铜吊坠", "from": "完好", "to": "出现裂纹"}],
        },
        chapter_id,
    )

    pack_resp = client.get(
        f"/api/v1/story-bibles/entities/production-pack/{novel_id}",
        headers=_auth_headers(user_id),
    )
    assert pack_resp.status_code == 200
    pack = pack_resp.json()
    assert pack["counts"]["characters"] == 1
    assert pack["counts"]["scenes"] == 1
    assert pack["counts"]["props"] == 1
    assert pack["counts"]["events"] == 1
    assert pack["relationships"][0]["source_entity_name"] == "沈砚"
    assert pack["event_timeline"][0]["name"] == "吊坠裂纹显现"
    assert "战斗" in pack["scene_tags"][0]["tags"]
    assert any(item["entity_name"] == "青铜吊坠" for item in pack["asset_requirements"])

    consistency_resp = client.post(
        "/api/v1/story-bibles/entities/check-consistency",
        json={"novel_id": novel_id},
        headers=_auth_headers(user_id),
    )
    assert consistency_resp.status_code == 200
    consistency = consistency_resp.json()
    assert consistency["summary"]["characters"] == 1
    assert any(issue["code"] == "unknown_event_participant" for issue in consistency["issues"])
    assert not any(issue["code"] == "missing_prop_dna" for issue in consistency["issues"])

    snapshot_resp = client.post(
        f"/api/v1/story-bibles/entities/{character['id']}/versions",
        json={"note": "定稿"},
        headers=_auth_headers(user_id),
    )
    assert snapshot_resp.status_code == 200
    snapshot_id = snapshot_resp.json()["snapshot"]["id"]

    update_resp = client.put(
        f"/api/v1/story-bibles/entities/{character['id']}",
        json={"name": "沈砚改名", "attributes": {"asset_pack": {"front": "/static/refs/new.png"}}},
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "沈砚改名"

    restore_resp = client.post(
        f"/api/v1/story-bibles/entities/{character['id']}/versions/restore",
        json={"snapshot_id": snapshot_id},
        headers=_auth_headers(user_id),
    )
    assert restore_resp.status_code == 200
    restored = restore_resp.json()
    assert restored["name"] == "沈砚"
    assert restored["attributes"]["asset_pack"]["front"].endswith("shenyan-front.png")
    assert len(restored["attributes"]["version_snapshots"]) >= 2

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": "第一集剧本",
            "content": "沈砚握住青铜吊坠，林晚看向天桥尽头。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_resp.json()["id"],
            "title": "天桥裂纹分镜",
            "content": {"chapter_id": chapter_id},
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
            "prompt": "沈砚站在废弃天桥，手中的青铜吊坠亮起冷蓝光。",
            "dialogue": "沈砚：裂纹又扩大了。",
            "visual_description": "雨后天桥、冷蓝月光、吊坠特写。",
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201
    shot_id = shot_resp.json()["id"]

    context_resp = client.put(
        f"/api/v1/shots/{shot_id}/production-context",
        json={
            "entity_reference_bindings": [
                {"entity_id": character["id"], "role": "character_primary", "usage": "character_reference"},
                {"entity_id": scene["id"], "role": "scene", "usage": "background_reference"},
                {"entity_id": prop["id"], "role": "prop_key", "usage": "continuity_check"},
            ],
            "review_state": "approved",
        },
        headers=_auth_headers(user_id),
    )
    assert context_resp.status_code == 200
    bindings = context_resp.json()["production_context"]["entity_reference_bindings"]
    assert [item["entity_type"] for item in bindings] == ["character", "scene", "prop"]
    assert bindings[0]["asset_pack"]["front"].endswith("shenyan-front.png")
    assert bindings[1]["visual_dna"]["lighting"] == "冷蓝月光"
    assert bindings[2]["visual_dna"]["material"] == "青铜"


def test_extract_script_entities_creates_scoped_assets_and_supports_scope_changes(client: TestClient) -> None:
    user_id = f"entity-asset-scope-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_chapter(client, user_id)

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "实体资产抽取剧本",
            "content": (
                "角色：沈砚。角色：林晚。场景：废弃天桥。"
                "道具：青铜吊坠。事件：沈砚发现吊坠裂纹。"
            ),
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    extract_resp = client.post(
        "/api/v1/story-bibles/entities/extract-assets",
        json={
            "script_id": script_id,
            "entity_types": ["character", "scene", "prop", "event"],
            "persist_entities": True,
            "create_assets": True,
            "asset_scope": "entity",
        },
        headers=_auth_headers(user_id),
    )
    assert extract_resp.status_code == 200
    payload = extract_resp.json()
    assert payload["novel_id"] == novel_id
    assert payload["chapter_id"] == chapter_id
    assert payload["script_id"] == script_id
    assert len(payload["entities"]) >= 4
    assert len(payload["assets"]) == len(payload["entities"])
    assert {item["script_id"] for item in payload["entities"]} == {script_id}
    assert all(asset["entity_id"] for asset in payload["assets"])
    assert {asset["script_id"] for asset in payload["assets"]} == {script_id}

    entity_id = payload["entities"][0]["id"]
    asset_id = payload["assets"][0]["id"]

    script_entities_resp = client.get(
        f"/api/v1/story-bibles/entities?script_id={script_id}&scope=script",
        headers=_auth_headers(user_id),
    )
    assert script_entities_resp.status_code == 200
    assert any(item["id"] == entity_id for item in script_entities_resp.json())

    global_entity_resp = client.post(
        f"/api/v1/story-bibles/entities/{entity_id}/scope",
        json={"scope": "global"},
        headers=_auth_headers(user_id),
    )
    assert global_entity_resp.status_code == 200
    assert global_entity_resp.json()["novel_id"] is None
    assert global_entity_resp.json()["chapter_id"] is None
    assert global_entity_resp.json()["script_id"] is None

    rebound_entity_resp = client.post(
        f"/api/v1/story-bibles/entities/{entity_id}/scope",
        json={"scope": "script", "script_id": script_id},
        headers=_auth_headers(user_id),
    )
    assert rebound_entity_resp.status_code == 200
    assert rebound_entity_resp.json()["novel_id"] == novel_id
    assert rebound_entity_resp.json()["chapter_id"] == chapter_id
    assert rebound_entity_resp.json()["script_id"] == script_id

    global_asset_resp = client.post(
        f"/api/v1/assets/{asset_id}/scope",
        json={"scope": "global"},
        headers=_auth_headers(user_id),
    )
    assert global_asset_resp.status_code == 200
    assert global_asset_resp.json()["novel_id"] is None
    assert global_asset_resp.json()["entity_id"] is None

    rebound_asset_resp = client.post(
        f"/api/v1/assets/{asset_id}/scope",
        json={"scope": "novel", "novel_id": novel_id},
        headers=_auth_headers(user_id),
    )
    assert rebound_asset_resp.status_code == 200
    assert rebound_asset_resp.json()["novel_id"] == novel_id
    assert rebound_asset_resp.json()["chapter_id"] is None
    assert rebound_asset_resp.json()["script_id"] is None
    assert rebound_asset_resp.json()["entity_id"] is None

    novel_assets_resp = client.get(
        f"/api/v1/assets?novel_id={novel_id}&scope=novel&include_public=false",
        headers=_auth_headers(user_id),
    )
    assert novel_assets_resp.status_code == 200
    assert any(item["id"] == asset_id for item in novel_assets_resp.json())


def test_default_anime_starter_entities_are_seeded_as_global_and_editable(client: TestClient) -> None:
    user_id = f"starter-entities-user-{uuid4()}"

    first_resp = client.get(
        "/api/v1/story-bibles/entities?scope=global&limit=200",
        headers=_auth_headers(user_id),
    )
    assert first_resp.status_code == 200
    entities = first_resp.json()
    names = {item["name"] for item in entities}
    assert "热血少年主角" in names
    assert "城市夜巷" in names
    assert "命运吊坠" in names
    assert "开场危机" in names
    assert "少年剑修" in names
    assert "宗门长老" in names
    assert "江湖剑客" in names
    assert "血脉继承者" in names
    assert "都市异能者" in names
    assert "仙门山门" in names
    assert "修炼洞府" in names
    assert "江湖客栈" in names
    assert "竹林山道" in names
    assert "古遗迹秘境" in names
    assert "城市地铁站台" in names
    assert "隐藏异能实验室" in names
    assert "本命灵剑" in names
    assert "宗门玉牌" in names
    assert "残页秘籍" in names
    assert "异兽灵核" in names
    assert "组织门禁卡" in names
    assert "境界突破" in names
    assert "江湖比武" in names
    assert "秘境开启" in names
    assert "都市异能觉醒" in names
    assert all(item["novel_id"] is None for item in entities)

    lead = next(item for item in entities if item["name"] == "热血少年主角")
    assert lead["source"] == "starter"
    assert lead["attributes"]["starter_library"] is True
    assert "visual_dna" in lead["attributes"]

    update_resp = client.put(
        f"/api/v1/story-bibles/entities/{lead['id']}",
        json={"description": "用户定制后的主角设定"},
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "用户定制后的主角设定"

    second_resp = client.get(
        "/api/v1/story-bibles/entities?scope=global&limit=200",
        headers=_auth_headers(user_id),
    )
    assert second_resp.status_code == 200
    assert sum(1 for item in second_resp.json() if item["name"] == "热血少年主角") == 1


def test_entity_filters_include_global_by_default_and_maintenance_stays_available(client: TestClient) -> None:
    user_id = f"entity-filter-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_chapter(client, user_id)

    global_entity = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "entity_type": "prop",
            "name": "通用视觉符号",
            "description": "所有小说可复用的视觉元素",
            "attributes": {"visual_dna": {"shape": "发光符号"}},
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert global_entity.status_code == 201
    global_entity_id = global_entity.json()["id"]

    novel_entity = _create_entity(
        client,
        user_id,
        novel_id,
        "prop",
        "小说专属令牌",
        {"prop_dna": {"material": "黑铁", "shape": "令牌"}},
    )
    chapter_entity = _create_entity(
        client,
        user_id,
        novel_id,
        "scene",
        "章节专属天桥",
        {"scene_tags": ["室外", "夜晚"]},
        chapter_id,
    )

    default_filtered = client.get(
        f"/api/v1/story-bibles/entities?novel_id={novel_id}&limit=200",
        headers=_auth_headers(user_id),
    )
    assert default_filtered.status_code == 200
    default_ids = {item["id"] for item in default_filtered.json()}
    assert global_entity_id in default_ids
    assert novel_entity["id"] in default_ids
    assert chapter_entity["id"] in default_ids

    only_novel = client.get(
        f"/api/v1/story-bibles/entities?novel_id={novel_id}&scope=novel&limit=200",
        headers=_auth_headers(user_id),
    )
    assert only_novel.status_code == 200
    only_novel_ids = {item["id"] for item in only_novel.json()}
    assert novel_entity["id"] in only_novel_ids
    assert global_entity_id not in only_novel_ids
    assert chapter_entity["id"] not in only_novel_ids

    only_chapter = client.get(
        f"/api/v1/story-bibles/entities?novel_id={novel_id}&chapter_id={chapter_id}&scope=chapter&limit=200",
        headers=_auth_headers(user_id),
    )
    assert only_chapter.status_code == 200
    only_chapter_ids = {item["id"] for item in only_chapter.json()}
    assert chapter_entity["id"] in only_chapter_ids
    assert global_entity_id not in only_chapter_ids

    update_resp = client.put(
        f"/api/v1/story-bibles/entities/{global_entity_id}",
        json={"description": "更新后的通用视觉符号"},
        headers=_auth_headers(user_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "更新后的通用视觉符号"

    snapshot_resp = client.post(
        f"/api/v1/story-bibles/entities/{global_entity_id}/versions",
        json={"note": "维护检查"},
        headers=_auth_headers(user_id),
    )
    assert snapshot_resp.status_code == 200
    assert snapshot_resp.json()["snapshot"]["note"] == "维护检查"

    delete_resp = client.delete(
        f"/api/v1/story-bibles/entities/{global_entity_id}",
        headers=_auth_headers(user_id),
    )
    assert delete_resp.status_code == 200
    after_delete = client.get(
        f"/api/v1/story-bibles/entities?novel_id={novel_id}&limit=200",
        headers=_auth_headers(user_id),
    )
    assert after_delete.status_code == 200
    assert all(item["id"] != global_entity_id for item in after_delete.json())


def test_entity_stats_match_scope_filters_and_ignore_list_type_filter(client: TestClient) -> None:
    user_id = f"entity-stats-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_chapter(client, user_id)

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "title": "统计测试剧本",
            "content": "沈砚带着通用徽记进入废弃天桥。",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    global_prop = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "entity_type": "prop",
            "name": "跨小说通用徽记",
            "description": "可复用的全局道具",
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert global_prop.status_code == 201
    novel_character = _create_entity(
        client,
        user_id,
        novel_id,
        "character",
        "统计专属角色",
        {"visual_dna": {"hair": "黑发"}},
    )
    chapter_scene = _create_entity(
        client,
        user_id,
        novel_id,
        "scene",
        "统计章节场景",
        {"scene_tags": ["室外"]},
        chapter_id=chapter_id,
    )
    script_event = _create_entity(
        client,
        user_id,
        novel_id,
        "event",
        "统计剧本事件",
        {"sequence": 1},
        chapter_id=chapter_id,
        script_id=script_id,
    )

    default_stats = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}&chapter_id={chapter_id}&script_id={script_id}",
        headers=_auth_headers(user_id),
    )
    assert default_stats.status_code == 200
    default_counts = default_stats.json()["counts"]
    assert default_counts["prop"] >= 1
    assert default_counts["character"] >= 1
    assert default_counts["scene"] >= 1
    assert default_counts["event"] >= 1

    character_list = client.get(
        f"/api/v1/story-bibles/entities?novel_id={novel_id}&chapter_id={chapter_id}&script_id={script_id}&entity_type=character",
        headers=_auth_headers(user_id),
    )
    assert character_list.status_code == 200
    assert all(item["entity_type"] == "character" for item in character_list.json())

    stats_after_type_filter = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}&chapter_id={chapter_id}&script_id={script_id}",
        headers=_auth_headers(user_id),
    )
    assert stats_after_type_filter.status_code == 200
    assert stats_after_type_filter.json()["counts"] == default_counts

    only_novel_stats = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}&scope=novel",
        headers=_auth_headers(user_id),
    )
    assert only_novel_stats.status_code == 200
    only_novel_counts = only_novel_stats.json()["counts"]
    assert only_novel_counts["character"] >= 1
    assert only_novel_counts["scene"] == 0
    assert only_novel_counts["event"] == 0

    only_chapter_stats = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}&chapter_id={chapter_id}&scope=chapter",
        headers=_auth_headers(user_id),
    )
    assert only_chapter_stats.status_code == 200
    only_chapter_counts = only_chapter_stats.json()["counts"]
    assert only_chapter_counts["scene"] >= 1
    assert only_chapter_counts["event"] == 0

    only_script_stats = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}&chapter_id={chapter_id}&script_id={script_id}&scope=script",
        headers=_auth_headers(user_id),
    )
    assert only_script_stats.status_code == 200
    only_script_counts = only_script_stats.json()["counts"]
    assert only_script_counts["event"] >= 1
    assert only_script_counts["character"] == 0
    assert only_script_counts["scene"] == 0

    assert novel_character["id"]
    assert chapter_scene["id"]
    assert script_event["id"]


def test_entity_stats_follow_scope_filters_without_list_type_or_limit_distortion(client: TestClient) -> None:
    user_id = f"entity-stats-user-{uuid4()}"
    novel_id, chapter_id = _create_novel_chapter(client, user_id)

    global_character = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "entity_type": "character",
            "name": "通用角色模板",
            "description": "可复用角色",
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert global_character.status_code == 201
    novel_prop = _create_entity(
        client,
        user_id,
        novel_id,
        "prop",
        "小说专属护符",
        {"prop_dna": {"shape": "护符"}},
    )
    chapter_scene = _create_entity(
        client,
        user_id,
        novel_id,
        "scene",
        "章节专属街口",
        {"scene_tags": ["室外"]},
        chapter_id,
    )

    stats_resp = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}",
        headers=_auth_headers(user_id),
    )
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["counts"]["character"] >= 1
    assert stats["counts"]["prop"] >= 1
    assert stats["counts"]["scene"] >= 1
    assert stats["total"] == sum(stats["counts"].values())

    character_list_resp = client.get(
        f"/api/v1/story-bibles/entities?novel_id={novel_id}&entity_type=character&limit=1",
        headers=_auth_headers(user_id),
    )
    assert character_list_resp.status_code == 200
    assert len(character_list_resp.json()) == 1
    stats_after_type_filter_resp = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}",
        headers=_auth_headers(user_id),
    )
    assert stats_after_type_filter_resp.status_code == 200
    assert stats_after_type_filter_resp.json()["counts"] == stats["counts"]

    only_novel_stats_resp = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}&scope=novel",
        headers=_auth_headers(user_id),
    )
    assert only_novel_stats_resp.status_code == 200
    only_novel_counts = only_novel_stats_resp.json()["counts"]
    assert only_novel_counts["prop"] >= 1
    assert only_novel_counts["character"] == 0
    assert only_novel_counts["scene"] == 0

    only_chapter_stats_resp = client.get(
        f"/api/v1/story-bibles/entities/stats?novel_id={novel_id}&chapter_id={chapter_id}&scope=chapter",
        headers=_auth_headers(user_id),
    )
    assert only_chapter_stats_resp.status_code == 200
    only_chapter_counts = only_chapter_stats_resp.json()["counts"]
    assert only_chapter_counts["scene"] >= 1
    assert only_chapter_counts["character"] == 0
    assert only_chapter_counts["prop"] == 0
    assert novel_prop["id"]
    assert chapter_scene["id"]
