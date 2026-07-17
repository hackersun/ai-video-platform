#!/usr/bin/env python3
"""Export recovery identifiers from an isolated live-canary DB without secrets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any


RESERVATION_FIELDS = (
    "state", "estimate_rmb", "capability", "job_type", "job_id",
    "operation_id", "provider_task_id",
)
OPERATION_FIELDS = (
    "id", "reservation_id", "capability", "job_type", "job_id", "artifact_id",
    "provider_task_id", "status", "actual_rmb", "cost_source", "recovery_reason",
    "created_at", "updated_at",
)
FAILURE_FIELDS = (
    "failure_stage", "layout_score", "threshold", "evaluator_version", "recorded_at",
    "schema_version", "provider_task_id_present", "provider_completed", "safe_retry",
)
PROVIDER_RESPONSE_FIELDS = (
    "schema_version", "provider", "response_kind", "data_kind", "provider_task_id_present",
    "artifact_returned", "base_status_code", "base_status_message_sha256",
)


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _reservations(summary: dict[str, Any]) -> list[dict[str, Any]]:
    raw = summary.get("reservations") or {}
    if not isinstance(raw, dict):
        return []
    return [
        {"reservation_id": reservation_id, **{
            field: value.get(field) for field in RESERVATION_FIELDS if value.get(field) is not None
        }}
        for reservation_id, value in sorted(raw.items()) if isinstance(value, dict)
    ]


def _failure_evidence(metadata: dict[str, Any], operation_id: str) -> dict[str, Any] | None:
    raw = (metadata.get("reference_failure_evidence") or {}).get(operation_id)
    if not isinstance(raw, dict):
        return None
    safe = {field: raw[field] for field in FAILURE_FIELDS if raw.get(field) is not None}
    return safe or None


def _provider_response_evidence(metadata: dict[str, Any], operation_id: str) -> dict[str, Any] | None:
    raw = (metadata.get("provider_response_evidence") or {}).get(operation_id)
    if not isinstance(raw, dict):
        return None
    safe = {field: raw[field] for field in PROVIDER_RESPONSE_FIELDS if raw.get(field) is not None}
    for field, keys in (
        ("payload_counts", ("base64", "url")),
        ("metadata_counts", ("failed", "success")),
    ):
        values = raw.get(field)
        if isinstance(values, dict):
            counts = {
                key: values[key] for key in keys
                if isinstance(values.get(key), int) and not isinstance(values.get(key), bool)
            }
            if counts:
                safe[field] = counts
    return safe or None


def build_failure_evidence(database: Path, user_id: str) -> dict[str, Any]:
    with database.open("rb") if database.is_file() else open(os.devnull, "rb") as handle:
        signature = handle.read(16)
    if signature != b"SQLite format 3\x00":
        raise ValueError("database must be an existing SQLite file")
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        run_columns = {row[1] for row in connection.execute("PRAGMA table_info(series_production_runs)")}
        metadata_column = ", run_metadata" if "run_metadata" in run_columns else ""
        order_by = "created_at, id" if "created_at" in run_columns else "id"
        runs = connection.execute(
            f"SELECT id, status, cost_summary{metadata_column} FROM series_production_runs WHERE user_id = ? ORDER BY {order_by}",
            (user_id,),
        ).fetchall()
        payload_runs = []
        for run in runs:
            summary = _json_object(run["cost_summary"])
            metadata = _json_object(run["run_metadata"]) if "run_metadata" in run.keys() else {}
            operations = connection.execute(
                "SELECT * FROM live_canary_provider_operations WHERE run_id = ? AND user_id = ? ORDER BY rowid",
                (run["id"], user_id),
            ).fetchall()
            payload_runs.append({
                "id": run["id"], "status": run["status"],
                "spent_rmb": str(summary.get("spent_rmb") or "0.00"),
                "reserved_rmb": str(summary.get("reserved_rmb") or "0.00"),
                "reservations": _reservations(summary),
                "operations": [{
                    **{field: operation[field] for field in OPERATION_FIELDS if operation[field] is not None},
                    **({"failure_evidence": failure} if (
                        failure := _failure_evidence(metadata, operation["id"])
                    ) else {}),
                    **({"provider_response_evidence": response_evidence} if (
                        response_evidence := _provider_response_evidence(metadata, operation["id"])
                    ) else {}),
                } for operation in operations],
            })
    return {
        "schema": "live-canary-failure-evidence-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "runs": payload_runs,
    }


def write_failure_evidence(output: Path, evidence: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(evidence, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, output)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        evidence = build_failure_evidence(args.database, args.user_id)
        write_failure_evidence(args.output, evidence)
    except Exception as error:
        print(json.dumps({"status": "refused", "error_class": type(error).__name__}))
        return 2
    print(json.dumps({"status": "ok", "runs": len(evidence["runs"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
