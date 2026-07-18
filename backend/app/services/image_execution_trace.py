"""Persist safe image execution trace identifiers on existing domain records."""

from __future__ import annotations

from typing import Any, Mapping


def image_submission_trace(shot_id: str, run: Any) -> dict[str, str | None]:
    return {"job_id": shot_id, "run_id": getattr(run, "id", None)}


def merge_image_execution_trace(
    metadata: Mapping[str, Any] | None, result: Mapping[str, Any],
) -> dict[str, Any]:
    trace_id = result.get("execution_snapshot_id")
    values = dict(metadata or {})
    if trace_id:
        values["image_execution_snapshot_id"] = trace_id
    return values


def image_asset_trace(result: Mapping[str, Any]) -> dict[str, str]:
    trace_id = result.get("execution_snapshot_id")
    return {"execution_snapshot_id": trace_id} if trace_id else {}
