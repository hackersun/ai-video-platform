from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
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


@pytest.fixture()
def user_id() -> str:
    return f"production-bible-review-{uuid4()}"


@pytest.fixture()
def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


@pytest.fixture()
def seeded_novel_with_story_bible(client: TestClient, auth_headers: dict[str, str]) -> SimpleNamespace:
    novel_response = client.post(
        "/api/v1/novels",
        headers=auth_headers,
        json={
            "title": f"Production Bible 审核测试 {uuid4()}",
            "genre": "科幻",
            "description": "用于审核 Production Bible 连续性事实。",
        },
    )
    assert novel_response.status_code == 201
    novel_id = novel_response.json()["id"]

    story_bible_response = client.post(
        "/api/v1/story-bibles",
        headers=auth_headers,
        json={
            "novel_id": novel_id,
            "title": "Production Bible 审核设定",
            "style": "赛博国风动画",
            "worldview": "星港城邦与旧神遗迹共存。",
            "extra_data": {
                "state_machine": {
                    "generated_at": "2026-07-04T00:00:00+00:00",
                    "current_state": {"characters": {}, "scenes": {}, "props": {}, "events": []},
                }
            },
        },
    )
    assert story_bible_response.status_code == 201

    character_name = f"林舟-{uuid4()}"
    entity_response = client.post(
        "/api/v1/story-bibles/entities",
        headers=auth_headers,
        json={
            "novel_id": novel_id,
            "entity_type": "character",
            "name": character_name,
            "description": "主角，星港调查员。",
            "attributes": {"voice": "calm-young-male"},
            "source": "manual",
        },
    )
    assert entity_response.status_code == 201
    entity_id = entity_response.json()["id"]

    asset_response = client.post(
        "/api/v1/assets",
        headers=auth_headers,
        json={
            "novel_id": novel_id,
            "entity_id": entity_id,
            "category": "character",
            "asset_type": "image",
            "name": f"{character_name} 定稿",
            "description": "角色定稿资产。",
            "url": "https://example.com/linzhou.png",
        },
    )
    assert asset_response.status_code == 201

    return SimpleNamespace(novel_id=novel_id, story_bible_id=story_bible_response.json()["id"])


@pytest.fixture()
def seeded_character_entity(client: TestClient, auth_headers: dict[str, str]) -> SimpleNamespace:
    response = client.post(
        "/api/v1/story-bibles/entities",
        headers=auth_headers,
        json={
            "entity_type": "character",
            "name": f"林舟-{uuid4()}",
            "description": "主角，星港调查员。",
            "attributes": {"voice": "calm-young-male"},
            "source": "manual",
        },
    )
    assert response.status_code == 201
    return SimpleNamespace(id=response.json()["id"])


def test_review_endpoint_returns_bible_sections(client, auth_headers, seeded_novel_with_story_bible):
    response = client.get(
        f"/api/v1/story-bibles/novel/{seeded_novel_with_story_bible.novel_id}/production-bible/review",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sections"] == ["style", "characters", "scenes", "props", "events", "voices"]
    assert payload["approval_state"] == "approved"
    assert payload["summary"]["readiness_score"] >= 80
    assert payload["summary"]["missing_requirements"] == []


def test_approve_character_updates_entity_attributes(client, auth_headers, seeded_character_entity):
    response = client.post(
        f"/api/v1/story-bibles/entities/{seeded_character_entity.id}/approve",
        headers=auth_headers,
        json={"approved": True, "approval_note": "主角设定确认"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["entity_id"] == seeded_character_entity.id
    assert payload["approved"] is True

    entity_response = client.get(
        f"/api/v1/story-bibles/entities/{seeded_character_entity.id}",
        headers=auth_headers,
    )
    assert entity_response.status_code == 200
    entity = entity_response.json()
    assert entity["is_approved"] is True
    assert entity["attributes"]["approval_note"] == "主角设定确认"
    assert datetime.fromisoformat(entity["attributes"]["approved_at"])
