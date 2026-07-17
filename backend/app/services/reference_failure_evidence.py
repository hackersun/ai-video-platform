"""Persist allowlisted reference failures without provider or artifact content."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models.series_production_run import SeriesProductionRun


def sanitize_reference_failure_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {"failure_stage": str(evidence.get("failure_stage") or "unknown")[:80]}
    for field in ("layout_score", "threshold"):
        try:
            value = float(evidence.get(field))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            safe[field] = value
    version = str(evidence.get("evaluator_version") or "")[:80]
    if version:
        safe["evaluator_version"] = version
    schema_version = str(evidence.get("schema_version") or "")[:80]
    if schema_version:
        safe["schema_version"] = schema_version
    for field in ("provider_task_id_present", "provider_completed", "safe_retry"):
        if isinstance(evidence.get(field), bool):
            safe[field] = evidence[field]
    return safe


async def record_reference_failure_evidence(
    db: AsyncSession, run: SeriesProductionRun, operation_id: str, evidence: dict[str, Any],
) -> dict[str, Any]:
    safe = {**sanitize_reference_failure_evidence(evidence), "recorded_at": utc_now().isoformat()}
    metadata = dict(run.run_metadata or {})
    failures = dict(metadata.get("reference_failure_evidence") or {})
    failures[str(operation_id)] = safe
    metadata["reference_failure_evidence"] = failures
    run.run_metadata = metadata
    flag_modified(run, "run_metadata")
    await db.commit()
    return safe


__all__ = ["record_reference_failure_evidence", "sanitize_reference_failure_evidence"]
