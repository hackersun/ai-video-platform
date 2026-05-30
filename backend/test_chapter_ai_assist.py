"""
Tests for chapter AI-assisted editing and persistence.
"""

from __future__ import annotations

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


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_generate_chapter_uses_story_context_and_persists_entities(client: TestClient) -> None:
    user_id = "chapter-ai-generate-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "玄都续章",
            "genre": "仙侠",
            "description": "角色：林舟\n场景：玄都城\n道具：玉佩\n事件：灵潮爆发",
        },
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    first_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 灵潮",
            "chapter_number": 1,
            "content": "林舟握着玉佩抵达玄都城，发现城门爆发灵潮。",
        },
        headers=auth_headers(user_id),
    )
    assert first_resp.status_code == 201

    bible_resp = client.post(
        "/api/v1/story-bibles/generate-from-novel",
        json={"novel_id": novel_id, "style": "赛璐璐动画"},
        headers=auth_headers(user_id),
    )
    assert bible_resp.status_code == 201
    story_bible_id = bible_resp.json()["id"]

    generate_resp = client.post(
        "/api/v1/chapters/generate",
        json={
            "novel_id": novel_id,
            "chapter_title": "第二章 城门余波",
            "target_word_count": 600,
            "instruction": "角色：沈眠\n场景：寒鸦谷\n道具：黑铁剑\n事件：沈眠遭遇伏击",
        },
        headers=auth_headers(user_id),
    )
    assert generate_resp.status_code == 201
    generated = generate_resp.json()
    assert generated["chapter_number"] == 2
    assert "玄都续章" in generated["content"]
    assert generated["word_count"] == len(generated["content"])

    detail_resp = client.get(f"/api/v1/chapters/{generated['id']}", headers=auth_headers(user_id))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["content"] == generated["content"]

    entities_resp = client.post(
        "/api/v1/story-bibles/entities/extract",
        json={"chapter_id": generated["id"], "persist": False},
        headers=auth_headers(user_id),
    )
    assert entities_resp.status_code == 200
    assert len(entities_resp.json()["entities"]) >= 1

    bible_after = client.get(f"/api/v1/story-bibles/{story_bible_id}", headers=auth_headers(user_id))
    assert bible_after.status_code == 200
    extra_data = bible_after.json()["extra_data"]
    assert extra_data["last_synced_chapter_id"] == generated["id"]


def test_ai_assist_rewrite_extend_polish_are_persisted(client: TestClient) -> None:
    user_id = "chapter-ai-assist-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={
            "title": "星港追踪",
            "genre": "科幻",
            "description": "角色：林澈\n场景：星港\n道具：星门钥匙\n事件：星门开启",
        },
        headers=auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第一章 启航",
            "chapter_number": 1,
            "content": "林澈带着星门钥匙进入星港。",
        },
        headers=auth_headers(user_id),
    )
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": "第二章 暗巷",
            "chapter_number": 2,
            "content": "林澈在暗巷发现星门钥匙发光。",
        },
        headers=auth_headers(user_id),
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    rewrite_resp = client.post(
        f"/api/v1/chapters/{chapter_id}/ai-assist",
        json={"mode": "rewrite", "target_word_count": 600, "instruction": "保持星港场景"},
        headers=auth_headers(user_id),
    )
    assert rewrite_resp.status_code == 200
    rewritten = rewrite_resp.json()
    assert rewritten["status"] == "completed"
    assert "星港追踪" in rewritten["content"]

    extend_resp = client.post(
        f"/api/v1/chapters/{chapter_id}/ai-assist",
        json={"mode": "extend", "target_word_count": 600, "instruction": "追加追击事件"},
        headers=auth_headers(user_id),
    )
    assert extend_resp.status_code == 200
    extended = extend_resp.json()
    assert len(extended["content"]) > len(rewritten["content"])

    polish_resp = client.post(
        f"/api/v1/chapters/{chapter_id}/ai-assist",
        json={"mode": "polish", "target_word_count": 600, "instruction": "强化画面感"},
        headers=auth_headers(user_id),
    )
    assert polish_resp.status_code == 200
    polished = polish_resp.json()
    assert polished["content"]
    assert polished["word_count"] == len(polished["content"])

    persisted = client.get(f"/api/v1/chapters/{chapter_id}", headers=auth_headers(user_id))
    assert persisted.status_code == 200
    assert persisted.json()["content"] == polished["content"]


def test_ai_assist_rejects_unknown_mode(client: TestClient) -> None:
    user_id = "chapter-ai-invalid-user"
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "无效模式", "description": "测试"},
        headers=auth_headers(user_id),
    )
    chapter_resp = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_resp.json()["id"],
            "title": "第一章",
            "chapter_number": 1,
            "content": "测试内容",
        },
        headers=auth_headers(user_id),
    )

    response = client.post(
        f"/api/v1/chapters/{chapter_resp.json()['id']}/ai-assist",
        json={"mode": "unknown"},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
