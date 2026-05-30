"""
Tests for fill-entity-refs endpoint.
"""

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


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_fill_entity_refs_storyboard_not_found(client: TestClient) -> None:
    """404 when storyboard does not exist."""
    response = client.post(
        "/api/v1/storyboards/nonexistent-id/fill-entity-refs",
        headers=auth_headers("test-user"),
    )
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


def test_fill_entity_refs_unauthorized(client: TestClient) -> None:
    """Without auth header, should return 401 or 403 or 404."""
    response = client.post("/api/v1/storyboards/some-id/fill-entity-refs")
    # Auth failures can be 401, 403, or 404 depending on implementation
    assert response.status_code in (401, 403, 404)


def test_fill_entity_refs_success_with_empty_shots(client: TestClient) -> None:
    """Returns success even when storyboard has no shots."""
    user_id = f"fill-refs-user-{uuid4()}"

    # Create a novel first
    novel_resp = client.post(
        "/api/v1/novels",
        headers=auth_headers(user_id),
        json={"title": f"Test Novel for Fill {user_id}", "description": "test novel"},
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    # Create a script
    script_resp = client.post(
        "/api/v1/scripts",
        headers=auth_headers(user_id),
        json={
            "novel_id": novel_id,
            "title": f"Test Script for Fill {user_id}",
            "content": "test script content",
        },
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    # Create an empty storyboard
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        headers=auth_headers(user_id),
        json={"script_id": script_id, "title": f"Empty Storyboard {user_id}"},
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    # Fill entity refs on empty storyboard
    fill_resp = client.post(
        f"/api/v1/storyboards/{storyboard_id}/fill-entity-refs",
        headers=auth_headers(user_id),
    )
    assert fill_resp.status_code == 200
    data = fill_resp.json()
    assert data["status"] == "success"
    assert data["count"] == 0
    assert "message" in data


def test_fill_entity_refs_success_with_shots(client: TestClient) -> None:
    """Fill entity refs on storyboard with shots updates them correctly."""
    user_id = f"fill-refs-user-{uuid4()}"

    # Create a novel with entities
    novel_resp = client.post(
        "/api/v1/novels",
        headers=auth_headers(user_id),
        json={"title": f"Novel with Entities {user_id}", "description": "test novel for entity refs"},
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    # Create story entities individually via story_bible endpoint
    for entity_data in [
        {"entity_type": "character", "name": "张三", "description": "主角", "novel_id": novel_id},
        {"entity_type": "scene", "name": "山洞", "description": "神秘山洞", "novel_id": novel_id},
    ]:
        entity_resp = client.post(
            "/api/v1/story-bibles/entities",
            headers=auth_headers(user_id),
            json=entity_data,
        )
        assert entity_resp.status_code == 201, f"Story entity creation failed: {entity_resp.json()}"

    # Create a script
    script_resp = client.post(
        "/api/v1/scripts",
        headers=auth_headers(user_id),
        json={
            "novel_id": novel_id,
            "title": f"Script with Entities {user_id}",
            "content": "张三在山洞里修炼",
        },
    )
    assert script_resp.status_code == 201
    script_id = script_resp.json()["id"]

    # Create a storyboard
    storyboard_resp = client.post(
        "/api/v1/storyboards",
        headers=auth_headers(user_id),
        json={
            "script_id": script_id,
            "title": f"Storyboard with Shots {user_id}",
            "content": {"novel_id": novel_id},
        },
    )
    assert storyboard_resp.status_code == 201
    storyboard_id = storyboard_resp.json()["id"]

    # Create shots
    shots_resp = client.post(
        "/api/v1/shots/batch?storyboard_id=" + storyboard_id,
        headers=auth_headers(user_id),
        json=[
            {
                "storyboard_id": storyboard_id,
                "shot_number": 1,
                "duration": 4,
                "prompt": "张三在山洞里打坐修炼",
                "dialogue": "修炼中...",
            },
            {
                "storyboard_id": storyboard_id,
                "shot_number": 2,
                "duration": 5,
                "prompt": "山洞里光芒闪烁",
                "dialogue": None,
            },
        ],
    )
    assert shots_resp.status_code == 201
    assert len(shots_resp.json()) == 2

    # Fill entity refs
    fill_resp = client.post(
        f"/api/v1/storyboards/{storyboard_id}/fill-entity-refs",
        headers=auth_headers(user_id),
    )
    assert fill_resp.status_code == 200
    data = fill_resp.json()
    assert data["status"] == "success"
    assert data["count"] == 2

    # Verify shots were updated
    shots_get_resp = client.get(
        f"/api/v1/shots/storyboard/{storyboard_id}",
        headers=auth_headers(user_id),
    )
    assert shots_get_resp.status_code == 200
    shots = shots_get_resp.json()
    assert len(shots) == 2

    # At least one shot should have entity_refs populated
    for shot in shots:
        extra = shot.get("extra_data") or {}
        entity_refs = extra.get("entity_refs") or {}
        # Check that entity_refs structure exists
        assert "characters" in entity_refs or "scenes" in entity_refs