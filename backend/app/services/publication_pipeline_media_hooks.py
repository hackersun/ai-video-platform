"""Production media hooks for the publication pipeline worker.

Wires ``run_media_quality_for_pipeline`` to the same ``generate_selected`` path
used by POST /series-runs/{id}/generate-selected, so the one-click pipeline can
actually generate media instead of blocking with ``media_generate_fn_missing``.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_pipeline_media import PipelineMediaBlocked, run_media_quality_for_pipeline


async def list_run_shots(db: AsyncSession, run: SeriesProductionRun):
    from app.api.v1.endpoints.series_runs import _run_shots

    return await _run_shots(db, run)


async def generate_selected_for_pipeline(
    db: AsyncSession, *, run: SeriesProductionRun, user_id: str, shots: list,
    workflow_for_shot: Dict[str, str], requested: list, mode: str, native_audio: bool = False,
) -> Dict[str, Any]:
    from app.api.v1.endpoints.series_runs import AcceptAnchorQualityRequest, accept_series_anchor_quality
    from app.api.v1.workflow_media_transport import workflow_media_result
    from app.features.series_anchor_generation import SeriesAnchorError
    from app.features.series_anchor_generation import generate_selected_anchors as generate_selected
    from app.features.workflow_media import public as workflow_media
    from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled

    run_id = run.id

    async def generate_batch(workflow_id, shot_ids, video_config_id, audio_config_id):
        result = await workflow_media_result(
            workflow_media.generate_workflow_media_batch(workflow_media.WorkflowMediaCommand(
                db, user_id, workflow_id, workflow_media.WorkflowMediaBatchRequest(
                    shot_ids=shot_ids, production_strategy="final_quality",
                    strategy=("direct_av_first" if deterministic_provider_fake_enabled() else "separate_video_tts"),
                    model_config_id=video_config_id, audio_model_config_id=audio_config_id,
                    native_audio=native_audio,
                    require_real_video=True,
                    require_provider_reference_image=not native_audio,
                ),
            ))
        )
        return result.model_dump()

    async def accept_quality(shot, job, evaluation_ids):
        return await accept_series_anchor_quality(
            run_id,
            AcceptAnchorQualityRequest(shot_id=shot.id, job_id=job.id, evaluation_ids=evaluation_ids),
            db, user_id,
        )

    try:
        return await generate_selected(
            db, run=run, user_id=user_id, shots=shots, workflow_for_shot=workflow_for_shot,
            requested=requested, mode=mode, generate_batch=generate_batch,
            native_audio=native_audio, accept_quality=accept_quality,
        )
    except SeriesAnchorError as error:
        detail = error.detail if isinstance(error.detail, dict) else {"code": str(error.detail)}
        raise PipelineMediaBlocked(
            str(detail.get("code") or "media_generation_failed"),
            str(detail.get("message") or detail),
        ) from error


async def run_media_quality_with_default_hooks(
    db: AsyncSession, run: SeriesProductionRun, pipeline: NovelPublicationPipeline, **kwargs,
) -> SeriesProductionRun:
    kwargs.setdefault("list_shots_fn", list_run_shots)
    kwargs.setdefault("generate_fn", generate_selected_for_pipeline)
    from app.services.publication_pipeline_prepare import prepare_run_for_media

    kwargs.setdefault("prepare_fn", prepare_run_for_media)
    return await run_media_quality_for_pipeline(db, run, pipeline, **kwargs)
