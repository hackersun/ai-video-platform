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


def _create_entity(
    client: TestClient,
    user_id: str,
    novel_id: str,
    chapter_id: str,
    entity_type: str,
    name: str,
    attributes: dict,
) -> dict:
    response = client.post(
        "/api/v1/story-bibles/entities",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "entity_type": entity_type,
            "name": name,
            "description": f"{name} 的短视频生产设定",
            "attributes": attributes,
            "source": "manual",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()


def _create_short_video_fixture(client: TestClient, user_id: str) -> dict:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": f"短剧一致性小说 {uuid4()}",
            "genre": "都市异能",
            "description": "沈砚和林晚在雨夜天桥追查青铜吊坠的裂纹。",
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
            "content": "沈砚和林晚在雨夜废弃天桥发现青铜吊坠裂开，远处黑影逼近。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    _create_entity(
        client,
        user_id,
        novel_id,
        chapter_id,
        "character",
        "沈砚",
        {
            "asset_pack": {
                "front": "/static/refs/shenyan-front.png",
                "side": "/static/refs/shenyan-side.png",
                "full_body": "/static/refs/shenyan-full.png",
            },
            "visual_dna": {"hair": "黑色短发", "costume": "深色校服"},
        },
    )
    _create_entity(
        client,
        user_id,
        novel_id,
        chapter_id,
        "scene",
        "废弃天桥",
        {"scene_tags": ["室外", "夜晚", "悬疑"], "scene_dna": {"weather": "雨后", "lighting": "冷蓝月光"}},
    )
    _create_entity(
        client,
        user_id,
        novel_id,
        chapter_id,
        "prop",
        "青铜吊坠",
        {"prop_dna": {"material": "青铜", "shape": "六边形", "marking": "裂纹月纹"}, "owner": "沈砚"},
    )
    _create_entity(
        client,
        user_id,
        novel_id,
        chapter_id,
        "event",
        "吊坠裂纹显现",
        {
            "sequence": 1,
            "participants": ["沈砚", "林晚"],
            "location": "废弃天桥",
            "prop_state_changes": [{"prop": "青铜吊坠", "from": "完好", "to": "出现裂纹"}],
        },
    )

    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "短剧 Story Bible",
            "style": "竖屏动漫短剧，冷蓝雨夜，高对比光影",
            "worldview": "青铜吊坠会响应裂纹月光，引出城市异能事件。",
            "character_rules": [{"name": "沈砚", "state": "警觉", "costume": "深色校服"}],
            "scene_rules": [{"name": "废弃天桥", "weather": "雨后", "lighting": "冷蓝月光"}],
            "prop_rules": [{"name": "青铜吊坠", "state": "出现裂纹", "owner": "沈砚"}],
            "event_timeline": [{"name": "吊坠裂纹显现", "sequence": 1}],
            "extra_data": {
                "character_states": {"沈砚": {"costume": "深色校服", "emotion": "警觉"}},
                "prop_flows": {"青铜吊坠": ["完好", "出现裂纹"]},
                "scene_states": {"废弃天桥": {"weather": "雨后", "time": "夜晚"}},
            },
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": "第一集剧本",
            "content": "沈砚握紧青铜吊坠，林晚提醒黑影正在靠近。",
            "extra_data": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "裂纹月光分镜",
            "description": "竖屏短视频第一集",
            "style": "anime",
            "genre": "都市异能",
            "content": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shot_ids = []
    for number, prompt, dialogue in [
        (1, "废弃天桥雨水反光，沈砚手中的青铜吊坠突然裂开。", "它又裂开了。"),
        (2, "林晚回头看向天桥尽头，黑影穿过冷蓝月光。", "别回头，有人来了。"),
        (3, "沈砚把吊坠握紧，镜头推近裂纹中亮起的月纹。", "下一秒，我们跑。"),
    ]:
        shot_resp = client.post(
            "/api/v1/shots",
            json={
                "storyboard_id": storyboard_id,
                "shot_number": number,
                "duration": 10,
                "prompt": prompt,
                "dialogue": dialogue,
                "visual_description": prompt,
                "camera_movement": "zoom_in" if number in {1, 3} else "pan_right",
                "keyframes": [{"time": 0, "prompt": prompt}, {"time": 1, "prompt": f"{prompt} 结尾特写"}],
            },
            headers=_auth_headers(user_id),
        )
        assert shot_resp.status_code == 201
        shot_ids.append(shot_resp.json()["id"])

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "短剧一致性工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201

    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "script_id": script_id,
        "storyboard_id": storyboard_id,
        "shot_ids": shot_ids,
        "workflow_id": workflow_resp.json()["workflow_id"],
    }


def test_short_episode_plan_contains_vertical_short_drama_controls(client: TestClient) -> None:
    user_id = "short-plan-user"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.post(
        "/api/v1/short-video/episode-plan",
        json={
            "novel_id": fixture["novel_id"],
            "chapter_id": fixture["chapter_id"],
            "target_duration_seconds": 60,
            "aspect_ratio": "9:16",
            "style": "anime",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["format"]["aspect_ratio"] == "9:16"
    assert plan["format"]["target_duration_seconds"] == 60
    assert plan["narrative_control"]["hook"]
    assert plan["narrative_control"]["conflict"]
    assert plan["narrative_control"]["cliffhanger"]
    assert any(beat["code"] == "opening_hook" for beat in plan["shot_rhythm"])
    assert plan["model_route"]["shot_video"]["default_model_id"]
    assert "沈砚" in plan["story_context"]["characters"]


def test_shot_production_contract_persists_story_entities_and_model_route(client: TestClient) -> None:
    user_id = "short-contract-user"
    fixture = _create_short_video_fixture(client, user_id)
    shot_id = fixture["shot_ids"][0]

    response = client.post(
        f"/api/v1/short-video/shots/{shot_id}/production-contract?persist=true",
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is True
    contract = payload["contract"]
    assert contract["lineage"]["novel_id"] == fixture["novel_id"]
    assert contract["lineage"]["chapter_id"] == fixture["chapter_id"]
    assert contract["short_video_role"]["code"] == "opening_hook"
    assert any(item["name"] == "沈砚" for item in contract["characters"])
    assert any(item["name"] == "废弃天桥" for item in contract["scenes"])
    assert any(item["name"] == "青铜吊坠" for item in contract["props"])
    assert contract["dialogue_subtitle"]["subtitle_text"] == "它又裂开了。"
    assert contract["model_route"]["shot_audio_video"]["default_model_id"]
    assert contract["story_bible_state"]["status"] == "available"
    assert contract["seed"]

    shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=_auth_headers(user_id))
    assert shot_resp.status_code == 200
    production_context = shot_resp.json()["extra_data"]["production_context"]
    assert production_context["production_contract"]["seed"] == contract["seed"]
    assert production_context["production_contract"]["lineage"]["shot_id"] == shot_id


def test_workflow_short_video_readiness_and_refresh_contracts(client: TestClient) -> None:
    user_id = "short-readiness-user"
    fixture = _create_short_video_fixture(client, user_id)

    readiness_resp = client.get(
        f"/api/v1/short-video/workflow/{fixture['workflow_id']}/readiness?target_duration_seconds=60&aspect_ratio=9:16",
        headers=_auth_headers(user_id),
    )
    assert readiness_resp.status_code == 200
    readiness = readiness_resp.json()
    assert readiness["summary"]["shot_count"] == 3
    assert readiness["summary"]["estimated_duration_seconds"] == 30
    assert readiness["episode_plan"]["format"]["aspect_ratio"] == "9:16"
    assert len(readiness["contracts"]) == 3
    assert readiness["contracts"][0]["role"]["code"] == "opening_hook"
    assert readiness["contracts"][-1]["role"]["code"] == "cliffhanger"
    assert readiness["model_route"]["subtitle_generation"]["default_model_id"]
    presets = readiness["production_presets"]
    assert presets["selected"]["aspect_ratio"] == "9:16"
    assert any(item["ratio"] == "9:16" and item["selected"] for item in presets["aspect_ratios"])
    assert len({item["ratio"] for item in presets["aspect_ratios"]}) == len(presets["aspect_ratios"])
    style_names = {item["name"] for item in presets["style_references"]}
    assert "2D 动画风格图实例" in style_names
    assert "3D 玄幻风格图实例" in style_names
    assert presets["consistency_templates"]["character_three_view"]["prompt_template"]
    assert presets["consistency_templates"]["scene_multi_view"]["view_count"] == 4
    assert presets["consistency_templates"]["prop_multi_view"]["view_count"] == 4
    selected_style_id = presets["style_references"][0]["id"]

    selected_resp = client.get(
        f"/api/v1/short-video/workflow/{fixture['workflow_id']}/readiness?target_duration_seconds=60&aspect_ratio=16:9&style_asset_id={selected_style_id}",
        headers=_auth_headers(user_id),
    )
    assert selected_resp.status_code == 200
    selected_presets = selected_resp.json()["production_presets"]
    assert selected_presets["selected"]["aspect_ratio"] == "16:9"
    assert selected_presets["selected"]["style_asset_id"] == selected_style_id
    assert any(item["id"] == selected_style_id and item["selected"] for item in selected_presets["style_references"])

    refresh_resp = client.post(
        f"/api/v1/short-video/workflow/{fixture['workflow_id']}/refresh-contracts",
        json={},
        headers=_auth_headers(user_id),
    )
    assert refresh_resp.status_code == 200
    refreshed = refresh_resp.json()
    assert refreshed["refreshed_count"] == 3

    first_shot = client.get(f"/api/v1/shots/{fixture['shot_ids'][0]}", headers=_auth_headers(user_id))
    assert first_shot.status_code == 200
    assert first_shot.json()["extra_data"]["production_context"]["production_contract"]["contract_version"] == "short-video-v1"


def test_workflow_short_video_readiness_blocks_empty_storyboard(client: TestClient) -> None:
    user_id = "short-empty-storyboard-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": f"空分镜短视频小说 {uuid4()}",
            "genre": "修仙",
            "description": "少年在宗门山门前准备突破。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 山门雷声",
            "chapter_number": 1,
            "content": "少年站在宗门山门前，雷声逼近。",
        },
        headers=_auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": "第一集剧本",
            "content": "少年抬头看向雷云。",
            "extra_data": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "空分镜",
            "description": "尚未创建镜头",
            "style": "anime",
            "genre": "修仙",
            "content": {"chapter_id": chapter_id},
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "空分镜工作流",
            "novel_id": novel_id,
            "chapter_id": chapter_id,
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    workflow_id = workflow_resp.json()["workflow_id"]

    response = client.get(
        f"/api/v1/short-video/workflow/{workflow_id}/readiness",
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 200
    readiness = response.json()
    assert readiness["summary"]["ready"] is False
    assert readiness["summary"]["blocking_issue_count"] == 1
    assert readiness["blocking_issues"][0]["code"] == "missing_shots"
    assert "先生成或创建镜头" in readiness["recommendations"][0]
