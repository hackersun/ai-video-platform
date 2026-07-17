"""Truthful post-generation status when no trusted media evaluator has run."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_generation_job import MediaGenerationJob


async def unevaluated_quality_results(
    db: AsyncSession, *, user_id: str, selected_shots: list[object],
    workflow_for_shot: dict[str, str], episode_by_workflow: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    """Bind generated artifacts without presenting metadata as content evidence."""
    results: list[dict[str, object]] = []
    for shot in selected_shots:
        shot_id = str(getattr(shot, "id"))
        workflow_id = str(workflow_for_shot[shot_id])
        job = await db.scalar(select(MediaGenerationJob).where(
            MediaGenerationJob.user_id == user_id,
            MediaGenerationJob.workflow_id == workflow_id,
            MediaGenerationJob.shot_id == shot_id,
            MediaGenerationJob.is_active.is_(True),
            MediaGenerationJob.status.in_(("succeeded", "completed")),
        ).order_by(MediaGenerationJob.created_at.desc()).limit(1))
        if job is None:
            raise ValueError("completed selected-anchor artifact is missing")
        extra = job.extra_data if isinstance(job.extra_data, dict) else {}
        artifact_id = extra.get("artifact_id") or job.output_manifest_url or job.output_video_url
        if not artifact_id:
            raise ValueError("selected-anchor artifact identity is missing")
        episode = episode_by_workflow.get(workflow_id) or {}
        results.append({
            "shot_id": shot_id,
            "artifact_id": str(artifact_id),
            "evaluation_ids": [],
            "ready": False,
            "overall_readiness": "trusted_multimodal_evaluation_required",
            "evidence_source": "not_evaluated",
            "episode_number": int(episode.get("episode_number") or 0),
            "preceding_artifact_id": None,
        })
    return results


__all__ = ["unevaluated_quality_results"]
