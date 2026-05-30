"""
Parent ownership validation tests for workflow resources.
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


def create_novel(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/novels",
        json={
            "title": f"Novel for {user_id}",
            "description": "test novel",
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_chapter(client: TestClient, user_id: str) -> str:
    novel_id = create_novel(client, user_id)
    response = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": f"Chapter for {user_id}",
            "content": "test content",
            "chapter_number": 1,
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_script(client: TestClient, user_id: str) -> str:
    novel_id = create_novel(client, user_id)
    response = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": f"Script for {user_id}",
            "description": "test script",
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_list_scripts_supports_pagination(client: TestClient) -> None:
    user_id = f"script-pagination-user-{uuid4()}"
    novel_id = create_novel(client, user_id)
    for idx in range(3):
        response = client.post(
            "/api/v1/scripts",
            json={
                "novel_id": novel_id,
                "title": f"Script {idx}",
                "description": "test script",
            },
            headers=auth_headers(user_id),
        )
        assert response.status_code == 201

    page1 = client.get(
        "/api/v1/scripts?page=1&page_size=2",
        headers=auth_headers(user_id),
    )
    assert page1.status_code == 200
    assert len(page1.json()) == 2

    page2 = client.get(
        "/api/v1/scripts?page=2&page_size=2",
        headers=auth_headers(user_id),
    )
    assert page2.status_code == 200
    assert len(page2.json()) == 1


def create_storyboard(client: TestClient, user_id: str) -> str:
    script_id = create_script(client, user_id)
    response = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": f"Storyboard for {user_id}",
            "description": "test storyboard",
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_shot(client: TestClient, user_id: str) -> str:
    storyboard_id = create_storyboard(client, user_id)
    response = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": f"Shot for {user_id}",
            "dialogue": "test dialogue",
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_script_rejects_blank_novel_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": "   ",
            "title": "Script should fail",
            "description": "test script",
        },
        headers=auth_headers("script-blank-novel-user"),
    )

    assert response.status_code == 422


def test_create_script_returns_novel_context(client: TestClient) -> None:
    user_id = "script-context-user"
    novel_id = create_novel(client, user_id)

    response = client.post(
        "/api/v1/scripts",
        json={
            "novel_id": novel_id,
            "title": "Script with context",
            "description": "test script",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["novel_id"] == novel_id
    assert payload.get("novel_title") == "Novel for script-context-user"


def test_create_storyboard_returns_script_context(client: TestClient) -> None:
    user_id = "storyboard-context-user"
    script_id = create_script(client, user_id)

    response = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": script_id,
            "title": "Storyboard with context",
            "description": "test storyboard",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["script_id"] == script_id
    assert payload.get("script_title") == "Script for storyboard-context-user"


def test_create_shot_returns_storyboard_context(client: TestClient) -> None:
    user_id = "shot-context-user"
    storyboard_id = create_storyboard(client, user_id)

    response = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "Shot with context",
            "dialogue": "test dialogue",
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["storyboard_id"] == storyboard_id
    assert payload.get("storyboard_title") == "Storyboard for shot-context-user"


def test_create_chapter_rejects_foreign_owned_novel(client: TestClient) -> None:
    owner_novel_id = create_novel(client, "novel-owner-user")

    response = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": owner_novel_id,
            "title": "Chapter should fail",
            "content": "test content",
            "chapter_number": 1,
        },
        headers=auth_headers("chapter-other-user"),
    )

    assert response.status_code == 404


def test_create_storyboard_rejects_foreign_owned_script(client: TestClient) -> None:
    owner_script_id = create_script(client, "storyboard-script-owner")

    response = client.post(
        "/api/v1/storyboards",
        json={
            "script_id": owner_script_id,
            "title": "Storyboard should fail",
            "description": "test storyboard",
        },
        headers=auth_headers("storyboard-other-user"),
    )

    assert response.status_code == 404


def test_list_storyboards_rejects_foreign_owned_script(client: TestClient) -> None:
    create_storyboard(client, "storyboard-list-owner")
    foreign_script_id = create_script(client, "storyboard-list-foreign-owner")

    response = client.get(
        f"/api/v1/storyboards/script/{foreign_script_id}",
        headers=auth_headers("storyboard-list-owner"),
    )

    assert response.status_code == 404


def test_create_shot_rejects_foreign_owned_storyboard(client: TestClient) -> None:
    owner_storyboard_id = create_storyboard(client, "shot-storyboard-owner")

    response = client.post(
        "/api/v1/shots",
        json={
            "storyboard_id": owner_storyboard_id,
            "shot_number": 1,
            "duration": 4,
            "prompt": "Shot should fail",
            "dialogue": "test dialogue",
        },
        headers=auth_headers("shot-other-user"),
    )

    assert response.status_code == 404


def test_list_shots_rejects_foreign_owned_storyboard(client: TestClient) -> None:
    create_shot(client, "shot-list-owner")
    foreign_storyboard_id = create_storyboard(client, "shot-list-foreign-owner")

    response = client.get(
        f"/api/v1/shots/storyboard/{foreign_storyboard_id}",
        headers=auth_headers("shot-list-owner"),
    )

    assert response.status_code == 404


def test_update_script_rejects_foreign_owned_novel(client: TestClient) -> None:
    script_id = create_script(client, "script-owner-user")
    foreign_novel_id = create_novel(client, "novel-owner-for-update")

    response = client.put(
        f"/api/v1/scripts/{script_id}",
        json={"novel_id": foreign_novel_id},
        headers=auth_headers("script-owner-user"),
    )

    assert response.status_code == 404


def test_create_shots_batch_rejects_foreign_owned_storyboard(client: TestClient) -> None:
    foreign_storyboard_id = create_storyboard(client, "batch-storyboard-owner")

    response = client.post(
        f"/api/v1/shots/batch?storyboard_id={foreign_storyboard_id}",
        json=[
            {
                "storyboard_id": foreign_storyboard_id,
                "shot_number": 1,
                "duration": 4,
                "prompt": "Batch shot should fail",
                "dialogue": "test dialogue",
            }
        ],
        headers=auth_headers("batch-other-user"),
    )

    assert response.status_code == 404


def test_create_shots_batch_rejects_mismatched_storyboard_id(client: TestClient) -> None:
    query_storyboard_id = create_storyboard(client, "batch-contract-owner")
    other_storyboard_id = create_storyboard(client, "batch-contract-owner")

    response = client.post(
        f"/api/v1/shots/batch?storyboard_id={query_storyboard_id}",
        json=[
            {
                "storyboard_id": other_storyboard_id,
                "shot_number": 1,
                "duration": 4,
                "prompt": "Batch contract mismatch",
                "dialogue": "test dialogue",
            }
        ],
        headers=auth_headers("batch-contract-owner"),
    )

    assert response.status_code == 422
