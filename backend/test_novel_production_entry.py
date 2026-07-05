from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from init_db import init_db
from main import app
from test_short_video_production import _auth_headers, _create_short_video_fixture


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _create_novel(client: TestClient, user_id: str, title: str = "入口测试小说") -> str:
    response = client.post(
        "/api/v1/novels",
        json={"title": title, "description": "入口测试", "genre": "悬疑"},
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_chapter(client: TestClient, user_id: str, novel_id: str, title: str = "入口测试章节") -> str:
    response = client.post(
        "/api/v1/chapters",
        json={
            "novel_id": novel_id,
            "title": title,
            "chapter_number": 1,
            "content": "沈砚在雨夜发现吊坠裂纹，故事由此开始。",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_novel_production_entry_no_chapters_points_to_content_prepare(client: TestClient) -> None:
    user_id = f"novel-entry-no-chapters-{uuid4()}"
    novel_id = _create_novel(client, user_id)

    response = client.get(f"/api/v1/novels/{novel_id}/production-entry", headers=_auth_headers(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["novel_id"] == novel_id
    assert payload["stage"] == "content_prepare"
    assert payload["primary_action"]["code"] == "open_chapters"
    assert payload["primary_action"]["href"] == f"/novels/{novel_id}?tab=chapters"
    assert payload["metrics"]["chapter_count"] == 0


def test_novel_production_entry_with_chapter_points_to_series_plan(client: TestClient) -> None:
    user_id = f"novel-entry-series-plan-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    _create_chapter(client, user_id, novel_id)

    response = client.get(f"/api/v1/novels/{novel_id}/production-entry", headers=_auth_headers(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "series_plan"
    assert payload["primary_action"]["code"] == "open_series_plan"
    assert payload["primary_action"]["href"] == f"/novels/{novel_id}?tab=series-plan"
    assert payload["metrics"]["chapter_count"] == 1
    assert payload["metrics"]["episode_count"] == 0


def test_novel_production_entry_with_series_plan_points_to_workflow_create(client: TestClient) -> None:
    user_id = f"novel-entry-workflow-create-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    _create_chapter(client, user_id, novel_id)

    plan_response = client.post(
        f"/api/v1/novels/{novel_id}/series-plan",
        json={"target_episode_count": 1, "target_duration_seconds": 60},
        headers=_auth_headers(user_id),
    )
    assert plan_response.status_code == 200

    response = client.get(f"/api/v1/novels/{novel_id}/production-entry", headers=_auth_headers(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "workflow_create"
    assert payload["primary_action"]["code"] == "open_series_plan"
    assert payload["metrics"]["chapter_count"] == 1
    assert payload["metrics"]["episode_count"] >= 1
    assert payload["metrics"]["workflow_count"] == 0


def test_novel_production_entry_with_fixture_points_to_studio(client: TestClient) -> None:
    user_id = f"novel-entry-studio-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/novels/{fixture['novel_id']}/production-entry",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] in {"studio_fix", "studio_ready"}
    assert payload["primary_action"]["code"] == "open_studio"
    assert f"workflow_id={fixture['workflow_id']}" in payload["primary_action"]["href"]
    assert payload["metrics"]["workflow_count"] >= 1


def test_novel_production_entries_batch_reports_series_plan_metrics_with_workflow(client: TestClient) -> None:
    user_id = f"novel-entry-batch-plan-workflow-{uuid4()}"
    novel_id = _create_novel(client, user_id)
    chapter_id = _create_chapter(client, user_id, novel_id)

    plan_response = client.post(
        f"/api/v1/novels/{novel_id}/series-plan",
        json={"target_episode_count": 1, "target_duration_seconds": 60},
        headers=_auth_headers(user_id),
    )
    assert plan_response.status_code == 200

    workflow_response = client.post(
        "/api/v1/workflow/start",
        json={"title": "入口批量指标工作流", "novel_id": novel_id, "chapter_id": chapter_id},
        headers=_auth_headers(user_id),
    )
    assert workflow_response.status_code == 201

    response = client.get(
        "/api/v1/novels/production-entries",
        params={"novel_ids": novel_id},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    entry = response.json()["entries"][novel_id]
    assert entry["stage"] == "studio_fix"
    assert entry["metrics"]["episode_count"] >= 1
    assert entry["metrics"]["workflow_count"] == 1
    assert f"workflow_id={workflow_response.json()['workflow_id']}" in entry["primary_action"]["href"]


def test_novel_production_entries_batch_returns_map(client: TestClient) -> None:
    user_id = f"novel-entry-batch-{uuid4()}"
    first_id = _create_novel(client, user_id, "批量入口 A")
    second_id = _create_novel(client, user_id, "批量入口 B")

    response = client.get(
        "/api/v1/novels/production-entries",
        params={"novel_ids": f"{first_id},{second_id}"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["entries"][first_id]["stage"] == "content_prepare"
    assert payload["entries"][second_id]["stage"] == "content_prepare"


def test_novel_production_entries_batch_caps_unique_ids(client: TestClient) -> None:
    user_id = f"novel-entry-batch-cap-{uuid4()}"
    novel_ids = [str(uuid4()) for _ in range(101)]

    response = client.get(
        "/api/v1/novels/production-entries",
        params={"novel_ids": ",".join(novel_ids)},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 100
    assert novel_ids[99] in payload["entries"]
    assert novel_ids[100] not in payload["entries"]
