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


def test_studio_action_applies_asset_locks_and_records_audit(client: TestClient) -> None:
    user_id = f"studio-action-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)
    workflow_id = fixture["workflow_id"]

    response = client.post(
        f"/api/v1/studio/workflows/{workflow_id}/actions",
        json={"code": "apply_asset_locks"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "apply_asset_locks"
    assert payload["status"] == "succeeded"
    assert payload["risk"] == "safe"
    assert payload["result"]["applied_shot_count"] == 3

    snapshot_response = client.get(
        f"/api/v1/studio/workflows/{workflow_id}/snapshot",
        headers=_auth_headers(user_id),
    )
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["production"]["asset_lock_coverage"] == 1

    history_response = client.get(
        f"/api/v1/studio/workflows/{workflow_id}/actions",
        headers=_auth_headers(user_id),
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["items"][0]["code"] == "apply_asset_locks"
    assert history["items"][0]["status"] == "succeeded"


def test_studio_action_rejects_unknown_action_code(client: TestClient) -> None:
    user_id = f"studio-action-unknown-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    response = client.post(
        f"/api/v1/studio/workflows/{fixture['workflow_id']}/actions",
        json={"code": "delete_everything"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    assert "不支持的工作台修复动作" in response.json()["detail"]


def test_studio_review_creates_and_lists_review_runs(client: TestClient) -> None:
    user_id = f"studio-review-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)
    workflow_id = fixture["workflow_id"]

    response = client.post(
        f"/api/v1/studio/workflows/{workflow_id}/review",
        json={"mode": "production"},
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_id"] == workflow_id
    assert payload["mode"] == "production"
    assert payload["status"] == "blocked"
    assert payload["summary"]["blocking_issue_count"] >= 1
    assert any(issue["code"] == "missing_asset_locks" for issue in payload["issues"])
    assert any(action["code"] == "apply_asset_locks" for action in payload["actions"])

    history_response = client.get(
        f"/api/v1/studio/workflows/{workflow_id}/review-runs",
        headers=_auth_headers(user_id),
    )

    assert history_response.status_code == 200
    history = history_response.json()
    assert history["count"] >= 1
    assert history["items"][0]["id"] == payload["id"]
    assert history["items"][0]["summary"]["blocking_issue_count"] >= 1


def test_studio_review_records_test_bypass_audit(client: TestClient) -> None:
    user_id = f"studio-review-bypass-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)
    workflow_id = fixture["workflow_id"]

    response = client.post(
        f"/api/v1/studio/workflows/{workflow_id}/review",
        json={
            "mode": "test",
            "allow_test_bypass": True,
            "bypass_reason": "本地验证全流程先跳过",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "test"
    assert payload["status"] in {"ready", "confirmable"}
    assert payload["bypass_audit"]["reason"] == "本地验证全流程先跳过"
    assert payload["summary"]["bypassed_issue_count"] >= 1


def test_studio_action_execute_compat_route_and_safe_audit_action(client: TestClient) -> None:
    user_id = f"studio-action-compat-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)
    workflow_id = fixture["workflow_id"]

    lock_response = client.post(
        f"/api/v1/studio/workflows/{workflow_id}/actions/apply_asset_locks/execute",
        json={"mode": "production"},
        headers=_auth_headers(user_id),
    )
    assert lock_response.status_code == 200
    assert lock_response.json()["code"] == "apply_asset_locks"
    assert lock_response.json()["status"] == "succeeded"

    quality_response = client.post(
        f"/api/v1/studio/workflows/{workflow_id}/actions/quality_check/execute",
        json={"mode": "production"},
        headers=_auth_headers(user_id),
    )
    assert quality_response.status_code == 200
    payload = quality_response.json()
    assert payload["code"] == "quality_check"
    assert payload["status"] == "succeeded"
    assert payload["result"]["message"] == "已记录质量检查请求，请根据工作台问题列表继续处理。"


def test_studio_test_mode_skip_persists_bypass_audit(client: TestClient) -> None:
    user_id = f"studio-skip-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)
    workflow_id = fixture["workflow_id"]

    response = client.post(
        f"/api/v1/studio/workflows/{workflow_id}/actions",
        json={
            "code": "skip_issue",
            "source_issue_code": "missing_asset_locks",
            "mode": "test",
            "allow_test_bypass": True,
            "bypass_reason": "本地验证全流程先跳过",
        },
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "skip_issue"
    assert payload["status"] == "skipped"
    assert payload["source_issue_code"] == "missing_asset_locks"
    assert payload["result"]["bypass_audit"]["reason"] == "本地验证全流程先跳过"

    production_response = client.post(
        f"/api/v1/studio/workflows/{workflow_id}/actions",
        json={
            "code": "skip_issue",
            "source_issue_code": "missing_asset_locks",
            "mode": "production",
            "allow_test_bypass": True,
            "bypass_reason": "生产不能跳过",
        },
        headers=_auth_headers(user_id),
    )

    assert production_response.status_code == 422
    assert "生产出片模式不能跳过阻断项" in production_response.json()["detail"]
