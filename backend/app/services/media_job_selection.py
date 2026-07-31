"""Shared lineage rules for selecting the current media job for a shot."""

from __future__ import annotations

from typing import Any


def job_extra(job: Any) -> dict:
    return job.extra_data if isinstance(getattr(job, "extra_data", None), dict) else {}


def job_lineage_value(job: Any, key: str) -> str | None:
    extra = job_extra(job)
    value = getattr(job, key, None) or extra.get(key)
    if not value and isinstance(extra.get("lineage"), dict):
        value = extra["lineage"].get(key)
    return str(value) if value else None


def job_shot_id(job: Any) -> str | None:
    return job_lineage_value(job, "shot_id")


def job_created_key(job: Any) -> str:
    created_at = getattr(job, "created_at", None)
    return created_at.isoformat() if created_at else ""


def is_superseded(job: Any) -> bool:
    return job_extra(job).get("superseded_by_regeneration") is True


def latest_non_superseded_by_shot(jobs: list[Any]) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    fallback: dict[str, Any] = {}
    for job in jobs:
        shot_id = job_shot_id(job)
        if not shot_id:
            continue
        if shot_id not in fallback or job_created_key(job) > job_created_key(fallback[shot_id]):
            fallback[shot_id] = job
        if is_superseded(job):
            continue
        if shot_id not in latest or job_created_key(job) > job_created_key(latest[shot_id]):
            latest[shot_id] = job
    return {**fallback, **latest}


__all__ = [
    "is_superseded",
    "job_created_key",
    "job_lineage_value",
    "job_shot_id",
    "latest_non_superseded_by_shot",
]
