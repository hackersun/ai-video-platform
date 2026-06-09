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


def test_studio_snapshot_reports_workflow_context_and_blockers(client: TestClient) -> None:
    user_id = f"studio-snapshot-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"]["id"] == fixture["workflow_id"]
    assert payload["story_context"]["novel"]["id"] == fixture["novel_id"]
    assert payload["story_context"]["chapter"]["id"] == fixture["chapter_id"]
    assert payload["story_bible"]["title"] == "短剧 Story Bible"
    assert payload["production"]["shot_count"] == 3
    assert payload["production"]["asset_lock_coverage"] == 0
    assert any(issue["code"] == "missing_asset_locks" for issue in payload["issues"])
    assert any(action["code"] == "apply_asset_locks" for action in payload["actions"])
    assert payload["mode_policy"]["mode"] == "production"
    assert payload["mode_policy"]["ready"] is False


def test_studio_snapshot_allows_confirmable_test_mode_bypass(client: TestClient) -> None:
    user_id = f"studio-bypass-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        params={
            "mode": "test",
            "allow_test_bypass": "true",
            "bypass_reason": "本地验证完整流程",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    missing_locks = [issue for issue in payload["issues"] if issue["code"] == "missing_asset_locks"]
    assert missing_locks
    assert missing_locks[0]["severity"] == "confirmable"
    assert payload["mode_policy"]["mode"] == "test"
    assert payload["mode_policy"]["bypassed_issue_count"] >= 1
    assert payload["mode_policy"]["bypass_audit"]["reason"] == "本地验证完整流程"


def test_studio_snapshot_updates_asset_lock_coverage_after_existing_action(client: TestClient) -> None:
    user_id = f"studio-locks-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    lock_response = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/asset-locks",
        json={"create_missing_assets": True, "persist": True},
        headers=_auth_headers(user_id),
    )
    assert lock_response.status_code == 200

    response = client.get(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/snapshot",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["production"]["asset_lock_coverage"] == 1
    assert not [issue for issue in payload["issues"] if issue["code"] == "missing_asset_locks"]
    assert payload["assets"]["total_count"] >= 3
