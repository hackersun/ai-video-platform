"""Persist sanitized Prompt Skill evidence for selected-anchor video jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import VideoJob
from app.models.series_production_run import SeriesProductionRun


def job_skill_evidence(job: VideoJob | Any) -> dict[str, Any]:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    consistency = extra.get("consistency") if isinstance(extra.get("consistency"), dict) else {}
    entries = consistency.get("prompt_skills") if isinstance(consistency.get("prompt_skills"), list) else []
    entry = entries[0] if entries and isinstance(entries[0], dict) else {}
    task = str(consistency.get("task") or "")
    if task not in {"shot_video", "shot_audio_video"} or not entry.get("id"):
        return {}
    return {
        "id": entry["id"], "name": entry.get("name"), "version": entry.get("version"),
        "profile_version_id": entry.get("prompt_profile_version_id"), "task": task,
        "execution_mode": "provider_model", "artifact_type": "video_job", "artifact_id": job.id,
        "rendered_prompt_sha256": consistency.get("rendered_prompt_sha256"),
        "shot_id": str(extra.get("shot_id") or consistency.get("shot_id") or ""),
    }


async def record_anchor_skill_evidence(
    db: AsyncSession, run: SeriesProductionRun, batches: list[dict[str, Any]],
) -> None:
    job_ids = list(dict.fromkeys(
        str(job_id) for batch in batches for job_id in batch.get("video_job_ids") or []
    ))
    if not job_ids:
        return
    jobs = list((await db.scalars(select(VideoJob).where(
        VideoJob.id.in_(job_ids), VideoJob.user_id == run.user_id,
    ))).all())
    collected = [evidence for job in jobs if (evidence := job_skill_evidence(job))]
    if not collected:
        return
    metadata = dict(run.run_metadata or {})
    all_evidence = dict(metadata.get("skill_evidence") or {})
    for evidence in collected:
        task_evidence = dict(all_evidence.get(evidence["task"]) or {})
        task_evidence[evidence["shot_id"] or evidence["artifact_id"]] = evidence
        all_evidence[evidence["task"]] = task_evidence
    metadata["skill_evidence"] = all_evidence
    run.run_metadata = metadata
    flag_modified(run, "run_metadata")


__all__ = ["job_skill_evidence", "record_anchor_skill_evidence"]
