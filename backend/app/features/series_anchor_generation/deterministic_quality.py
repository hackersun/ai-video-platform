"""Acceptance-only deterministic evaluator, never used for real providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.media_generation_job import MediaGenerationJob
from app.models.quality_evaluation import QualityEvaluation
from app.models.series_production_run import SeriesProductionRun
from app.services.quality_evaluation_service import (
    AUTHORITATIVE_DIMENSION_POLICY, ArtifactBindingError, USER_FACING_DIMENSIONS, evaluate_bound_anchor,
)

from .quality import accept_quality


AcceptQuality = Callable[[object, MediaGenerationJob, list[str]], Awaitable[dict]]


async def _completed_job(db: AsyncSession, *, user_id: str, workflow_id: str, shot_id: str) -> MediaGenerationJob:
    job = await db.scalar(select(MediaGenerationJob).where(
        MediaGenerationJob.user_id == user_id, MediaGenerationJob.workflow_id == workflow_id,
        MediaGenerationJob.shot_id == shot_id, MediaGenerationJob.is_active.is_(True),
        MediaGenerationJob.status.in_(("succeeded", "completed")),
    ).order_by(MediaGenerationJob.created_at.desc()).limit(1))
    if job is None:
        raise ArtifactBindingError("latest completed generation job is missing")
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    required = ("artifact_id", "episode_number", "episode_contract_version", "canonical_reference_id",
                "canonical_reference_version", "as_of_chapter_id", "as_of_chapter_hash", "artifact_completed_at")
    if any(not extra.get(key) for key in required):
        raise ArtifactBindingError("generated artifact quality lineage is incomplete")
    return job


def _preceding(run: SeriesProductionRun, episode_number: int) -> dict | None:
    reports = (run.run_metadata or {}).get("anchor_quality_reports") or {}
    return max((report for report in reports.values() if isinstance(report, dict) and report.get("ready") is True
                and int(report.get("episode_number") or 0) <= episode_number),
               key=lambda report: (int(report.get("episode_number") or 0), str(report.get("evaluated_at") or "")),
               default=None)


def _accepted_preceding(report: dict) -> str | None:
    for dimension in (report.get("dimensions") or {}).values():
        if not isinstance(dimension, dict):
            continue
        evidence = dimension.get("evidence") or {}
        if isinstance(evidence, dict) and evidence.get("preceding_artifact_id"):
            return str(evidence["preceding_artifact_id"])
    return None


def _evaluation_payload(shot, job: MediaGenerationJob, preceding: dict | None) -> tuple[dict, dict, dict]:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    episode_number, evaluated_at = int(extra["episode_number"]), utc_now()
    references = [{"type": "canonical", "artifact_id": extra["canonical_reference_id"],
                   "version": extra["canonical_reference_version"]}]
    if preceding:
        references.append({"type": "preceding_anchor", "artifact_id": preceding["artifact_id"]})
    evidence = {"artifact_id": extra["artifact_id"], "job_id": job.id, "shot_id": shot.id,
        "episode_number": episode_number, "episode_contract_version": extra["episode_contract_version"],
        "evaluator_version": "anchor-evaluator-v2", "created_at": evaluated_at.isoformat(),
        "source": "deterministic_probe", "references": references,
        "canonical_reference_id": extra["canonical_reference_id"],
        "preceding_artifact_id": preceding.get("artifact_id") if preceding else None,
        "as_of_chapter_id": extra["as_of_chapter_id"], "as_of_chapter_hash": extra["as_of_chapter_hash"]}
    expected = {"as_of_contract_version": extra["episode_contract_version"],
        "chapter_event_ids": list((shot.extra_data or {}).get("event_refs") or []),
        "dialogue_meaning": shot.dialogue or "", "mp4_required": True, "subtitle_required": bool(shot.dialogue)}
    observed = {"source_episode_indices": [episode_number], "chapter_event_ids": expected["chapter_event_ids"],
        "dialogue_meaning": shot.dialogue or "", "mp4_valid": bool(job.output_video_url),
        "subtitle_present": True, "playable": bool(job.output_video_url),
        "duration_seconds": float(job.duration_seconds or shot.duration or 0), "resolution": job.resolution or "unknown",
        "audio_stream_present": bool(job.output_audio_url), "manifest_lineage_valid": bool(job.input_assets),
        "dialogue_timing_valid": True, "intelligible": True}
    binding = {"artifact_id": extra["artifact_id"], "job_id": job.id, "shot_id": shot.id,
        "episode_number": episode_number, "episode_contract_version": extra["episode_contract_version"],
        "evaluator_version": "anchor-evaluator-v2", "artifact_created_at": extra["artifact_completed_at"],
        "evaluated_at": evaluated_at}
    return evidence, expected, {"observed": observed, "binding": binding}


def _rows(shot, job: MediaGenerationJob, preceding: dict | None) -> list[QualityEvaluation]:
    evidence, expected, payload = _evaluation_payload(shot, job, preceding)
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    report = evaluate_bound_anchor(binding=payload["binding"], expected_state=expected,
        observed_state=payload["observed"],
        dimension_evidence={dimension: dict(evidence) for dimension in USER_FACING_DIMENSIONS},
        dimension_scores={dimension: 90.0 for dimension in USER_FACING_DIMENSIONS},
        canonical_reference={"reference_id": extra["canonical_reference_id"],
                             "version": extra["canonical_reference_version"]},
        preceding_accepted_anchor={**preceding, "accepted": True} if preceding else None)
    rows = []
    for item in report["dimensions"].values():
        internal, policy = item["internal_dimension"], AUTHORITATIVE_DIMENSION_POLICY[item["internal_dimension"]]
        item_evidence = {**item["evidence"], "threshold": policy["threshold"],
                         "threshold_version": policy["threshold_version"],
                         "evaluator_version": policy["evaluator_version"], "findings": item["findings"]}
        rows.append(QualityEvaluation(id=str(uuid4()), artifact_id=extra["artifact_id"],
            artifact_type="media_generation_job", workflow_id=job.workflow_id, shot_id=shot.id,
            provider_id=job.provider_id, model_id=job.model_id, dimension=internal, expected_state=expected,
            observed_state=payload["observed"], evidence=item_evidence, score=item["score"], confidence=item["confidence"],
            severity=item["status"], blocking=item["blocking"], threshold_version=policy["threshold_version"],
            evaluator_version=policy["evaluator_version"], evaluated_at=payload["binding"]["evaluated_at"],
            created_at=payload["binding"]["evaluated_at"]))
    return rows


async def evaluate_deterministic_anchors(
    db: AsyncSession, *, run: SeriesProductionRun, user_id: str, selected_shots: list,
    workflow_for_shot: dict[str, str], episode_by_workflow: dict[str, dict],
    accept: AcceptQuality | None = None,
) -> list[dict]:
    ordered = sorted(selected_shots, key=lambda shot: (
        int((episode_by_workflow.get(str(workflow_for_shot.get(shot.id))) or {}).get("episode_number") or 0),
        int(shot.shot_number or 0)))
    results = []
    for shot in ordered:
        workflow_id = str(workflow_for_shot[shot.id])
        job = await _completed_job(db, user_id=user_id, workflow_id=workflow_id, shot_id=shot.id)
        extra = job.extra_data if isinstance(job.extra_data, dict) else {}
        accepted = ((run.run_metadata or {}).get("anchor_quality_reports") or {}).get(str(extra["artifact_id"]))
        if isinstance(accepted, dict) and accepted.get("ready") is True:
            results.append({"shot_id": shot.id, "artifact_id": extra["artifact_id"],
                            "evaluation_ids": list(accepted.get("evaluation_ids") or []), "ready": True,
                            "episode_number": int(extra["episode_number"]),
                            "preceding_artifact_id": _accepted_preceding(accepted)})
            continue
        preceding = _preceding(run, int(extra["episode_number"]))
        rows = _rows(shot, job, preceding); db.add_all(rows); await db.flush()
        evaluation_ids = [row.id for row in rows]
        report = (
            await accept(shot, job, evaluation_ids)
            if accept is not None
            else await accept_quality(db, run=run, user_id=user_id, shot_id=shot.id,
                                      job_id=job.id, evaluation_ids=evaluation_ids)
        )
        results.append({"shot_id": shot.id, "artifact_id": extra["artifact_id"],
                        "evaluation_ids": evaluation_ids, "ready": report["ready"],
                        "episode_number": int(extra["episode_number"]),
                        "preceding_artifact_id": preceding.get("artifact_id") if preceding else None})
        await db.refresh(run)
    return results


__all__ = ["evaluate_deterministic_anchors"]
