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


def _create_series_fixture(client: TestClient, user_id: str) -> dict:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": f"整书漫剧计划 {uuid4()}",
            "genre": "都市异能",
            "description": "角色：沈砚。角色：林晚。场景：雨夜天桥。道具：青铜吊坠。事件：吊坠裂纹显现。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_ids = []
    for number, title, content in [
        (1, "第一章 裂纹月光", "沈砚和林晚在雨夜天桥发现青铜吊坠出现裂纹。"),
        (2, "第二章 黑影逼近", "黑影逼近，林晚提醒沈砚不要回头。"),
        (3, "第三章 暗巷回声", "两人逃入暗巷，吊坠传出回声。"),
        (4, "第四章 灯塔信号", "沈砚在废弃灯塔发现吊坠信号。"),
    ]:
        chapter_resp = client.post(
            "/api/v1/chapters",
            json={
                "novel_id": novel_id,
                "title": title,
                "chapter_number": number,
                "content": content,
                "status": "completed",
            },
            headers=_auth_headers(user_id),
        )
        assert chapter_resp.status_code == 201
        chapter_ids.append(chapter_resp.json()["id"])

    entity_ids = {}
    for entity_type, name in [
        ("character", "沈砚"),
        ("character", "林晚"),
        ("scene", "雨夜天桥"),
        ("prop", "青铜吊坠"),
        ("event", "吊坠裂纹显现"),
    ]:
        entity_resp = client.post(
            "/api/v1/story-bibles/entities",
            json={
                "novel_id": novel_id,
                "chapter_id": chapter_ids[0],
                "entity_type": entity_type,
                "name": name,
                "description": f"{name} 的连续漫剧设定",
                "attributes": {},
                "source": "manual",
            },
            headers=_auth_headers(user_id),
        )
        assert entity_resp.status_code == 201
        entity_ids[name] = entity_resp.json()["id"]

    script_resp = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "chapter_id": chapter_ids[0],
            "title": "第一集剧本",
            "content": "沈砚握紧青铜吊坠，林晚看见黑影。",
            "status": "completed",
        },
        headers=_auth_headers(user_id),
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    storyboard_resp = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "novel_id": novel_id,
            "title": "第一集分镜",
            "description": "第一集竖屏分镜",
            "content": {"chapter_id": chapter_ids[0]},
            "style": "anime",
        },
        headers=_auth_headers(user_id),
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    shot_resp = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 8,
            "prompt": "雨夜天桥上，青铜吊坠裂纹发光。",
            "dialogue": "它又裂开了。",
            "visual_description": "雨夜天桥上，青铜吊坠裂纹发光。",
            "character_refs": [{"character_id": entity_ids["沈砚"], "name": "沈砚"}],
        },
        headers=_auth_headers(user_id),
    )
    assert shot_resp.status_code == 201

    workflow_resp = client.post(
        "/api/v1/workflow/start",
        json={
            "title": "第一集生产工程",
            "novel_id": novel_id,
            "chapter_id": chapter_ids[0],
            "script_id": script_id,
            "storyboard_id": storyboard_id,
        },
        headers=_auth_headers(user_id),
    )
    assert workflow_resp.status_code == 201
    return {"novel_id": novel_id, "chapter_ids": chapter_ids, "entity_ids": entity_ids}


def test_series_plan_generates_and_persists_episode_plan(client: TestClient) -> None:
    user_id = f"series-plan-user-{uuid4()}"
    fixture = _create_series_fixture(client, user_id)

    response = client.post(
        f"/api/v1/novels/{fixture['novel_id']}/series-plan",
        json={
            "target_episode_count": 2,
            "target_duration_seconds": 75,
            "aspect_ratio": "9:16",
            "style": "竖屏动漫短剧",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["novel_id"] == fixture["novel_id"]
    assert plan["target_episode_count"] == 2
    assert len(plan["episodes"]) == 2
    assert plan["episodes"][0]["chapter_ids"] == fixture["chapter_ids"][:2]
    assert plan["episodes"][1]["chapter_ids"] == fixture["chapter_ids"][2:]
    assert plan["episodes"][0]["status"] == "shots_ready"
    assert plan["episodes"][0]["workflow_id"]
    assert "沈砚" in plan["episodes"][0]["key_characters"]
    assert "雨夜天桥" in plan["episodes"][0]["key_scenes"]
    assert "青铜吊坠" in plan["episodes"][0]["key_props"]
    assert plan["episodes"][0]["narrative"]["hook"]
    assert plan["episodes"][0]["narrative"]["cliffhanger"]
    assert plan["episodes"][0]["next_action"]["code"] == "generate_media"
    assert "shot_video" in plan["model_route"]
    assert plan["production_bible_summary"]["novel_id"] == fixture["novel_id"]
    assert plan["production_bible_summary"]["asset_readiness"]["missing_asset_count"] >= 1
    assert plan["episodes"][0]["production_readiness"]["has_workflow"] is True
    assert plan["episodes"][0]["production_readiness"]["has_storyboard"] is True
    assert plan["episodes"][0]["production_readiness"]["shot_count"] == 1
    assert plan["episodes"][0]["production_readiness"]["missing_asset_count"] >= 1
    assert plan["episodes"][0]["production_readiness"]["voice_count"] >= 0
    assert plan["episodes"][0]["production_readiness"]["next_action"]["code"] == "generate_media"
    assert plan["episodes"][0]["continuity_summary"]["characters"]
    assert plan["episodes"][0]["missing_requirements"]

    saved = client.get(
        f"/api/v1/novels/{fixture['novel_id']}/series-plan",
        headers=_auth_headers(user_id),
    )
    assert saved.status_code == 200
    saved_plan = saved.json()
    assert saved_plan["generated_at"] == plan["generated_at"]
    assert saved_plan["episodes"][0]["chapter_ids"] == fixture["chapter_ids"][:2]
    assert saved_plan["production_bible_summary"]["novel_id"] == fixture["novel_id"]
    assert saved_plan["episodes"][0]["production_readiness"]["shot_count"] == 1


def test_series_plan_requires_chapters(client: TestClient) -> None:
    user_id = f"series-plan-empty-user-{uuid4()}"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "空小说", "genre": "悬疑", "description": "暂无章节"},
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201

    response = client.post(
        f"/api/v1/novels/{novel_resp.json()['id']}/series-plan",
        json={"target_episode_count": 3},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 400
    assert "章节" in response.json()["detail"]


def test_story_entity_impact_route_reports_affected_episode_range(client: TestClient) -> None:
    user_id = f"entity-impact-route-user-{uuid4()}"
    fixture = _create_series_fixture(client, user_id)
    plan_resp = client.post(
        f"/api/v1/novels/{fixture['novel_id']}/series-plan",
        json={"chapters_per_episode": 1},
        headers=_auth_headers(user_id),
    )
    assert plan_resp.status_code == 200

    response = client.get(
        f"/api/v1/story-bibles/entities/{fixture['entity_ids']['沈砚']}/impact",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["entity"]["name"] == "沈砚"
    assert payload["affected_episode_count"] == 4
    assert payload["affected_shot_count"] == 1
    assert payload["episodes"][0]["episode_index"] == 1
    assert payload["episodes"][0]["affected_shots"][0]["id"]
    assert payload["apply_options"][0]["label"] == "从第 1 集起应用新设定"
