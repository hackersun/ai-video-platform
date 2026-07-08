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


def _create_story_state_fixture(client: TestClient, user_id: str) -> dict:
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": f"状态机漫剧 {uuid4()}",
            "genre": "都市异能",
            "description": "角色：沈砚。角色：林晚。场景：雨夜天桥。道具：青铜吊坠。事件：吊坠裂纹显现。",
        },
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_ids = []
    for number, title, content in [
        (
            1,
            "第一章 裂纹月光",
            "角色：沈砚。角色：林晚。场景：雨夜天桥。道具：青铜吊坠。事件：吊坠裂纹显现。沈砚握住青铜吊坠，裂纹亮起。",
        ),
        (
            2,
            "第二章 暗巷回声",
            "角色：沈砚。角色：林晚。场景：雾港暗巷。道具：青铜吊坠。事件：暗巷遭遇。林晚提醒沈砚黑影逼近。",
        ),
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

    entities = [
        (
            "character",
            "沈砚",
            chapter_ids[0],
            {
                "state": "警觉",
                "costume": "深色校服",
                "goal": "保护青铜吊坠",
                "visual_dna": {"hair": "黑色短发", "costume": "深色校服"},
                "relationships": [{"target": "林晚", "relation": "同伴", "status": "共同逃离"}],
            },
        ),
        (
            "character",
            "林晚",
            chapter_ids[1],
            {
                "state": "紧张",
                "costume": "浅色风衣",
                "visual_dna": {"hair": "长发", "costume": "浅色风衣"},
            },
        ),
        (
            "scene",
            "雨夜天桥",
            chapter_ids[0],
            {"scene_tags": ["室外", "夜晚"], "scene_dna": {"weather": "雨后", "lighting": "冷蓝月光"}},
        ),
        (
            "scene",
            "雾港暗巷",
            chapter_ids[1],
            {"scene_tags": ["室外", "追逐"], "scene_dna": {"weather": "浓雾", "lighting": "路灯闪烁"}},
        ),
        (
            "prop",
            "青铜吊坠",
            chapter_ids[0],
            {"state": "出现裂纹", "owner": "沈砚", "prop_dna": {"material": "青铜", "shape": "六边形"}},
        ),
        (
            "event",
            "吊坠裂纹显现",
            chapter_ids[0],
            {
                "sequence": 1,
                "participants": ["沈砚", "林晚"],
                "location": "雨夜天桥",
                "prop_state_changes": [{"prop": "青铜吊坠", "from": "完好", "to": "出现裂纹", "owner": "沈砚"}],
            },
        ),
        (
            "event",
            "暗巷遭遇",
            chapter_ids[1],
            {
                "sequence": 2,
                "participants": ["沈砚", "林晚"],
                "location": "雾港暗巷",
                "prop_state_changes": [{"prop": "青铜吊坠", "from": "出现裂纹", "to": "发出回声", "owner": "沈砚"}],
            },
        ),
    ]
    for entity_type, name, chapter_id, attributes in entities:
        response = client.post(
            "/api/v1/story-bibles/entities",
            json={
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "entity_type": entity_type,
                "name": name,
                "description": f"{name} 的状态机设定",
                "attributes": attributes,
                "source": "manual",
            },
            headers=_auth_headers(user_id),
        )
        assert response.status_code == 201

    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "状态机 Story Bible",
            "style": "竖屏动漫短剧，冷蓝光影",
            "worldview": "青铜吊坠会响应裂纹月光，吸引黑影追击。",
            "character_rules": [{"name": "沈砚", "appearance": "黑色短发，深色校服"}],
            "scene_rules": [{"name": "雨夜天桥", "description": "雨后冷蓝月光"}],
            "prop_rules": [{"name": "青铜吊坠", "state": "出现裂纹"}],
            "event_timeline": [{"name": "吊坠裂纹显现", "sequence": 1}],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    return {"novel_id": novel_id, "chapter_ids": chapter_ids, "story_bible_id": bible_resp.json()["id"]}


def test_story_state_machine_generates_persists_and_checks(client: TestClient) -> None:
    user_id = f"state-machine-user-{uuid4()}"
    fixture = _create_story_state_fixture(client, user_id)

    response = client.post(
        f"/api/v1/story-bibles/{fixture['story_bible_id']}/state-machine",
        json={"novel_id": fixture["novel_id"], "persist": True},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    state_machine = response.json()["state_machine"]
    assert state_machine["novel_id"] == fixture["novel_id"]
    assert state_machine["summary"]["characters"] >= 2
    assert state_machine["summary"]["props"] >= 1
    assert state_machine["current_state"]["characters"]["沈砚"]["costume"] == "深色校服"
    assert state_machine["current_state"]["props"]["青铜吊坠"]["state"] == "发出回声"
    assert len(state_machine["chapter_snapshots"]) == 2
    assert state_machine["prop_flows"]["青铜吊坠"][-1]["to"] == "发出回声"

    saved = client.get(
        f"/api/v1/story-bibles/{fixture['story_bible_id']}/state-machine",
        headers=_auth_headers(user_id),
    )
    assert saved.status_code == 200
    assert saved.json()["state_machine"]["current_state"]["props"]["青铜吊坠"]["owner"] == "沈砚"

    check = client.post(
        f"/api/v1/story-bibles/{fixture['story_bible_id']}/state-machine/check",
        json={"novel_id": fixture["novel_id"]},
        headers=_auth_headers(user_id),
    )
    assert check.status_code == 200
    assert check.json()["generated_transient"] is False
    assert check.json()["summary"]["events"] >= 2


def test_story_state_machine_filters_stale_noise_entities(client: TestClient) -> None:
    user_id = f"state-machine-noise-user-{uuid4()}"
    fixture = _create_story_state_fixture(client, user_id)

    for entity_type, name in [
        ("character", "霓虹"),
        ("character", "无人列车"),
        ("character", "追来的不"),
        ("prop", "紧铜铃"),
        ("prop", "对孙剑"),
        ("prop", "铃舌上刻着孙剑"),
    ]:
        response = client.post(
            "/api/v1/story-bibles/entities",
            json={
                "novel_id": fixture["novel_id"],
                "entity_type": entity_type,
                "name": name,
                "description": "旧版本误抽取噪声",
                "source": "deterministic",
            },
            headers=_auth_headers(user_id),
        )
        assert response.status_code == 201

    response = client.post(
        f"/api/v1/story-bibles/{fixture['story_bible_id']}/state-machine",
        json={"novel_id": fixture["novel_id"], "persist": False},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    state_machine = response.json()["state_machine"]
    assert {"霓虹", "无人列车", "追来的不"}.isdisjoint(state_machine["current_state"]["characters"])
    assert {"紧铜铃", "对孙剑", "铃舌上刻着孙剑"}.isdisjoint(state_machine["current_state"]["props"])


def test_story_state_machine_is_injected_into_prompt_context(client: TestClient) -> None:
    user_id = f"state-machine-prompt-user-{uuid4()}"
    fixture = _create_story_state_fixture(client, user_id)

    machine_resp = client.post(
        f"/api/v1/story-bibles/{fixture['story_bible_id']}/state-machine",
        json={"novel_id": fixture["novel_id"], "persist": True},
        headers=_auth_headers(user_id),
    )
    assert machine_resp.status_code == 200

    prompt_resp = client.post(
        "/api/v1/story-bibles/compose-prompt",
        json={
            "task": "shot_video",
            "story_bible_id": fixture["story_bible_id"],
            "extra_context": {"镜头目标": "沈砚握紧吊坠准备逃离暗巷"},
        },
        headers=_auth_headers(user_id),
    )

    assert prompt_resp.status_code == 200
    prompt = prompt_resp.json()["prompt"]
    assert "Story Bible状态机" in prompt
    assert "沈砚" in prompt
    assert "青铜吊坠" in prompt
    assert "后续生成必须继承当前状态" in prompt
