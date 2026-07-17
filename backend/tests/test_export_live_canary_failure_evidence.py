import json
import sqlite3
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "export_live_canary_failure_evidence.py"


def test_exporter_preserves_recovery_ids_without_secrets(tmp_path: Path) -> None:
    database = tmp_path / "canary.db"
    output = tmp_path / "failure-evidence.json"
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE series_production_runs (id TEXT PRIMARY KEY, user_id TEXT, status TEXT, cost_summary JSON, run_metadata JSON)"
        )
        db.execute(
            """CREATE TABLE live_canary_provider_operations (
            id TEXT PRIMARY KEY, run_id TEXT, user_id TEXT, reservation_id TEXT,
            capability TEXT, job_type TEXT, job_id TEXT, artifact_id TEXT,
            provider_task_id TEXT, status TEXT, actual_rmb TEXT, cost_source TEXT,
            recovery_reason TEXT, created_at TEXT, updated_at TEXT)"""
        )
        cost = {
            "spent_rmb": "1.00", "reserved_rmb": "3.50",
            "reservations": {"video-reservation": {
                "state": "reserved", "estimate_rmb": "3.50", "capability": "video",
                "job_type": "video_job", "job_id": "video-job-1",
                "operation_id": "video-operation-1", "provider_task_id": "provider-video-1",
                "api_key": "must-not-export", "prompt": "must-not-export",
            }},
        }
        metadata = {"reference_failure_evidence": {"video-operation-1": {
            "failure_stage": "layout_scoring", "layout_score": 0.412345, "threshold": 0.75,
            "evaluator_version": "reference-layout-pixels-v1", "recorded_at": "2026-07-14T14:18:21+00:00",
            "schema_version": "reference-adapter-stage-v1", "provider_task_id_present": True,
            "provider_completed": True, "safe_retry": False,
            "prompt": "must-not-export", "public_url": "https://must-not-export.example/image.png",
            "provider_message": "must-not-export",
        }}, "provider_response_evidence": {"video-operation-1": {
            "schema_version": "image-provider-response-shape-v1", "provider": "minimax",
            "response_kind": "object", "data_kind": "object",
            "provider_task_id_present": True, "artifact_returned": True,
            "payload_counts": {"base64": 1, "url": 0, "raw": "must-not-export"},
            "metadata_counts": {"failed": 0, "success": 1, "raw": "must-not-export"}, "base_status_code": "0",
            "base_status_message_sha256": "abc123", "prompt": "must-not-export",
        }}}
        db.execute(
            "INSERT INTO series_production_runs VALUES (?, ?, ?, ?, ?)",
            ("run-1", "canary-user", "media_running", json.dumps(cost), json.dumps(metadata)),
        )
        db.executemany(
            "INSERT INTO live_canary_provider_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("reference-operation", "run-1", "canary-user", "reference-reservation", "reference", "asset", "asset-1", "asset-1", "provider-reference-1", "reconciled", "1.00", "estimated_as_actual", None, "2026-07-14", "2026-07-14"),
                ("video-operation-1", "run-1", "canary-user", "video-reservation", "video", "video_job", "video-job-1", None, "provider-video-1", "accepted", None, None, None, "2026-07-14", "2026-07-14"),
                ("tts-operation", "run-1", "canary-user", "tts-reservation", "tts", "tts_job", "tts-job-1", None, None, "confirmed_rejected_before_acceptance", None, None, None, "2026-07-14", "2026-07-14"),
            ],
        )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--database", str(database), "--user-id", "canary-user", "--output", str(output)],
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    evidence = json.loads(output.read_text())
    assert evidence["schema"] == "live-canary-failure-evidence-v1"
    assert evidence["runs"][0]["operations"][1]["provider_task_id"] == "provider-video-1"
    assert evidence["runs"][0]["operations"][1]["failure_evidence"] == {
        "failure_stage": "layout_scoring", "layout_score": 0.412345, "threshold": 0.75,
        "evaluator_version": "reference-layout-pixels-v1", "recorded_at": "2026-07-14T14:18:21+00:00",
        "schema_version": "reference-adapter-stage-v1", "provider_task_id_present": True,
        "provider_completed": True, "safe_retry": False,
    }
    assert evidence["runs"][0]["operations"][1]["provider_response_evidence"] == {
        "schema_version": "image-provider-response-shape-v1", "provider": "minimax",
        "response_kind": "object", "data_kind": "object",
        "provider_task_id_present": True, "artifact_returned": True,
        "payload_counts": {"base64": 1, "url": 0},
        "metadata_counts": {"failed": 0, "success": 1}, "base_status_code": "0",
        "base_status_message_sha256": "abc123",
    }
    assert evidence["runs"][0]["reservations"][0]["state"] == "reserved"
    serialized = json.dumps(evidence)
    assert "must-not-export" not in serialized
    assert output.stat().st_mode & 0o777 == 0o600
