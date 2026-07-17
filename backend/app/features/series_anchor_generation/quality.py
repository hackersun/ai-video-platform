"""Acceptance and repair application rules for immutable anchor evidence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.time_utils import utc_now
from app.models.media_generation_job import MediaGenerationJob
from app.models.quality_evaluation import QualityEvaluation
from app.models.series_production_run import SeriesProductionRun
from app.models.workflow import Workflow
from app.services.quality_evaluation_service import ArtifactBindingError, validate_persisted_anchor_evaluations
from app.services.repair_planner import plan_bound_repair

from .errors import SeriesAnchorError


def run_workflow_ids(run: SeriesProductionRun) -> set[str]:
    return {str((episode.get("canonical_ids") or {}).get("workflow_id")) for episode in run.episodes or []
            if (episode.get("canonical_ids") or {}).get("workflow_id")}


async def _latest_job(
    db: AsyncSession, *, run: SeriesProductionRun, user_id: str, shot_id: str,
) -> tuple[MediaGenerationJob, dict[str, Any]]:
    job = await db.scalar(select(MediaGenerationJob).where(
        MediaGenerationJob.user_id == user_id,
        MediaGenerationJob.workflow_id.in_(run_workflow_ids(run)),
        MediaGenerationJob.shot_id == shot_id, MediaGenerationJob.is_active.is_(True),
        MediaGenerationJob.status.in_(("succeeded", "completed")),
    ).order_by(MediaGenerationJob.created_at.desc()).limit(1))
    if job is None:
        raise SeriesAnchorError(409, "evaluations do not match the latest completed generation job")
    episode = next((item for item in run.episodes or []
                    if str((item.get("canonical_ids") or {}).get("workflow_id")) == str(job.workflow_id)), None)
    if episode is None:
        raise SeriesAnchorError(409, "generation job is not bound to a run episode")
    return job, episode


def _preceding_report(reports: dict[str, Any], episode_number: int) -> dict[str, Any] | None:
    candidates = [item for item in reports.values() if isinstance(item, dict) and item.get("ready") is True
                  and int(item.get("episode_number") or 0) < episode_number]
    return max(candidates, key=lambda item: (int(item.get("episode_number") or 0),
                                              str(item.get("evaluated_at") or "")), default=None)


def _validate_artifact(report: dict[str, Any], job: MediaGenerationJob, extra: dict[str, Any]) -> None:
    artifact_id = extra.get("artifact_id") or job.output_manifest_url or job.output_video_url or job.output_audio_url
    checks = (
        report["job_id"] == job.id,
        bool(artifact_id) and report["artifact_id"] == artifact_id,
        report["episode_contract_version"] == extra.get("episode_contract_version"),
    )
    if not all(checks):
        raise SeriesAnchorError(409, "evaluations do not match the latest generated artifact")


async def accept_quality(
    db: AsyncSession, *, run: SeriesProductionRun, user_id: str, shot_id: str,
    job_id: str, evaluation_ids: list[str],
) -> dict[str, Any]:
    if len(set(evaluation_ids)) != 6:
        raise SeriesAnchorError(422, "six unique evaluation IDs are required")
    rows = list((await db.scalars(select(QualityEvaluation).join(
        Workflow, Workflow.id == QualityEvaluation.workflow_id,
    ).where(QualityEvaluation.id.in_(evaluation_ids), Workflow.user_id == user_id))).all())
    job, episode = await _latest_job(db, run=run, user_id=user_id, shot_id=shot_id)
    if job.id != job_id:
        raise SeriesAnchorError(409, "evaluations do not match the latest completed generation job")
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    canonical_reference_id = extra.get("canonical_reference_id")
    if not canonical_reference_id or canonical_reference_id != ((run.run_metadata or {}).get("reference_preparation") or {}).get("asset_id"):
        raise SeriesAnchorError(409, "locked canonical reference is missing")
    metadata, reports = dict(run.run_metadata or {}), dict((run.run_metadata or {}).get("anchor_quality_reports") or {})
    episode_number = int(episode.get("episode_number") or 0)
    preceding = _preceding_report(reports, episode_number) if episode_number > 1 else None
    try:
        report = validate_persisted_anchor_evaluations(
            rows, allowed_workflow_ids=run_workflow_ids(run), expected_shot_id=shot_id,
            expected_episode_number=episode_number, expected_canonical_reference_id=str(canonical_reference_id),
            expected_preceding_artifact_id=preceding.get("artifact_id") if preceding else None,
            expected_evaluator_version="anchor-evaluator-v2", artifact_completed_at=job.updated_at or job.created_at,
            accepted_at=utc_now(),
        )
    except ArtifactBindingError as error:
        raise SeriesAnchorError(409, str(error)) from error
    _validate_artifact(report, job, extra)
    previous = reports.get(report["artifact_id"])
    if previous and previous.get("evaluation_ids") != report["evaluation_ids"]:
        raise SeriesAnchorError(409, "artifact already has a different accepted evaluation generation")
    reports[report["artifact_id"]], metadata["anchor_quality_reports"] = report, reports
    run.run_metadata = metadata
    try:
        await db.commit()
    except StaleDataError as error:
        await db.rollback()
        raise SeriesAnchorError(409, "series run version conflict") from error
    return report


def _repair_payload(
    run: SeriesProductionRun, user_id: str, request: dict[str, str], report: dict[str, Any],
    repairs: dict[str, Any], candidate_artifact_ids: object,
) -> dict[str, Any]:
    fingerprint = {"run_id": run.id, "user_id": user_id, "artifact_id": request["artifact_id"],
                   "issue_code": request["issue_code"], "parent_job_id": str(report["job_id"]),
                   "parent_evaluation_ids": sorted(str(value) for value in report["evaluation_ids"])}
    existing = repairs.get(request["repair_key"])
    if existing:
        if existing.get("fingerprint") == fingerprint:
            return existing
        raise SeriesAnchorError(409, "repair idempotency key scope conflict")
    prior = sum(1 for item in repairs.values() if item.get("artifact_id") == request["artifact_id"] and item.get("auto_retry_allowed"))
    plan = plan_bound_repair(issue=request["issue_code"], artifact_id=request["artifact_id"],
        candidate_artifact_ids=candidate_artifact_ids, parent_job_id=str(report["job_id"]),
        parent_evaluation_ids=report["evaluation_ids"], repair_key=request["repair_key"], prior_auto_retry_count=prior)
    return {"repair_id": plan.repair_id, "repair_key": plan.repair_key, "artifact_id": request["artifact_id"],
            "issue_code": plan.issue_code, "actions": list(plan.actions), "parent_job_id": plan.parent_job_id,
            "parent_evaluation_ids": list(plan.parent_evaluation_ids), "auto_retry_allowed": plan.auto_retry_allowed,
            "requires_review": plan.requires_review, "fingerprint": fingerprint}


async def plan_repair(db: AsyncSession, *, run: SeriesProductionRun, user_id: str, request: dict[str, str]) -> dict[str, Any]:
    metadata, reports = dict(run.run_metadata or {}), dict((run.run_metadata or {}).get("anchor_quality_reports") or {})
    report = reports.get(request["artifact_id"])
    if not isinstance(report, dict):
        raise SeriesAnchorError(404, "accepted anchor quality report not found")
    failed = [finding.get("code") for dimension in (report.get("dimensions") or {}).values()
              if dimension.get("blocking") for finding in dimension.get("findings") or []]
    if request["issue_code"] not in failed:
        raise SeriesAnchorError(409, "repair issue is not an accepted blocking finding")
    repairs = dict(metadata.get("anchor_repair_plans") or {})
    payload = _repair_payload(run, user_id, request, report, repairs, reports.keys())
    if repairs.get(request["repair_key"]) is payload:
        return payload
    repairs[request["repair_key"]], metadata["anchor_repair_plans"] = payload, repairs
    run.run_metadata = metadata
    try:
        await db.commit()
    except StaleDataError as error:
        await db.rollback()
        raise SeriesAnchorError(409, "series run repair authorization conflict") from error
    return payload


__all__ = ["accept_quality", "plan_repair", "run_workflow_ids"]
