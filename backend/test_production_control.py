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


def test_production_pack_asset_locks_media_audit_and_quality(client: TestClient) -> None:
    user_id = f"production-control-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    pack_resp = client.post(
        f"/api/v1/production-control/novels/{fixture['novel_id']}/production-pack",
        json={"create_missing_assets": True, "persist": True},
        headers=_auth_headers(user_id),
    )
    assert pack_resp.status_code == 200
    pack = pack_resp.json()
    assert pack["summary"]["lock_count"] >= 3
    assert pack["summary"]["created_asset_count"] >= 1

    locks_resp = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/asset-locks",
        json={"create_missing_assets": True, "persist": True},
        headers=_auth_headers(user_id),
    )
    assert locks_resp.status_code == 200
    locks_payload = locks_resp.json()
    assert locks_payload["applied_shots"]
    assert locks_payload["applied_shots"][0]["lock_count"] > 0

    shot_resp = client.get(f"/api/v1/shots/{fixture['shot_ids'][0]}", headers=_auth_headers(user_id))
    assert shot_resp.status_code == 200
    production_context = shot_resp.json()["extra_data"]["production_context"]
    assert production_context["asset_version_locks"]

    batch_resp = client.post(
        f"/api/v1/workflow/{fixture['workflow_id']}/generate-media-batch",
        json={"strategy": "direct_av_first", "subtitle_mode": "shot_dialogue", "audio_mode": "model_audio"},
        headers=_auth_headers(user_id),
    )
    assert batch_resp.status_code == 200
    media_job_id = batch_resp.json()["media_job_ids"][0]
    media_job = client.get(f"/api/v1/media/jobs/{media_job_id}", headers=_auth_headers(user_id))
    assert media_job.status_code == 200
    assert media_job.json()["extra_data"]["asset_version_locks"]

    audit_resp = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/media-audit",
        json={"persist_remote": True, "dry_run": False},
        headers=_auth_headers(user_id),
    )
    assert audit_resp.status_code == 200
    audit = audit_resp.json()
    assert audit["summary"]["item_count"] >= 1
    assert audit["summary"]["missing_count"] == 0

    quality_resp = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/quality-check",
        json={"persist": True},
        headers=_auth_headers(user_id),
    )
    assert quality_resp.status_code == 200
    quality = quality_resp.json()
    assert quality["summary"]["shot_count"] == 3
    assert quality["summary"]["average_score"] > 0


def test_ai_producer_assistant_reports_and_auto_fixes_safe_items(client: TestClient) -> None:
    user_id = f"producer-assistant-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    check_resp = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/producer-assistant",
        json={"auto_fix": False},
        headers=_auth_headers(user_id),
    )
    assert check_resp.status_code == 200
    payload = check_resp.json()
    assert payload["summary"]["action_count"] >= 1
    assert payload["summary"]["next_action"]["code"] in {
        "build_production_pack",
        "apply_asset_locks",
        "refresh_contracts",
        "fix_shot_blockers",
        "review_quality_warnings",
        "ready_for_generation",
    }

    fix_resp = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/producer-assistant",
        json={"auto_fix": True},
        headers=_auth_headers(user_id),
    )
    assert fix_resp.status_code == 200
    fixed = fix_resp.json()
    assert fixed["summary"]["executed_count"] >= 1

    first_shot = client.get(f"/api/v1/shots/{fixture['shot_ids'][0]}", headers=_auth_headers(user_id))
    assert first_shot.status_code == 200
    production_context = first_shot.json()["extra_data"]["production_context"]
    assert production_context["asset_version_locks"]
    assert production_context["production_contract"]["contract_version"] == "short-video-v1"


def test_ai_producer_assistant_executes_only_requested_safe_next_action(client: TestClient) -> None:
    user_id = f"producer-next-action-user-{uuid4()}"
    fixture = _create_short_video_fixture(client, user_id)

    fix_resp = client.post(
        f"/api/v1/production-control/workflow/{fixture['workflow_id']}/producer-assistant",
        json={"auto_fix": True, "action_code": "build_production_pack"},
        headers=_auth_headers(user_id),
    )
    assert fix_resp.status_code == 200
    payload = fix_resp.json()
    assert [item["code"] for item in payload["executed"]] == ["build_production_pack"]

    first_shot = client.get(f"/api/v1/shots/{fixture['shot_ids'][0]}", headers=_auth_headers(user_id))
    assert first_shot.status_code == 200
    production_context = first_shot.json()["extra_data"]["production_context"]
    assert production_context["asset_version_locks"]
    assert "production_contract" not in production_context
