"""Load and validate the context shared by workflow-media strategies."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.series_run_media_preflight.public import evaluate_media_preflight
from app.features.workflow_media.domain.production_strategy import (
    validate_generation_strategy,
    validate_production_strategy,
)
from app.features.workflow_media.errors import WorkflowMediaError
from app.features.workflow_media.repositories import workflow_media_repository as repository
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest
from app.models import Shot, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.production_strategy_routing import resolve_strategy_video_config_id
from app.services.series_run_orchestrator import mark_run_episode_contracts_superseded


@dataclass(frozen=True)
class WorkflowMediaContext:
    db: AsyncSession
    user_id: str
    workflow: Workflow
    series_run: Optional[SeriesProductionRun]
    shots: list[Shot]
    strategy_video_routing: dict
    effective_video_config_id: Optional[str]


async def _validate_series_run(
    db: AsyncSession, user_id: str, workflow: Workflow, *, native_audio: bool = False,
) -> Optional[SeriesProductionRun]:
    series_run_id = str((workflow.metadata_ or {}).get("series_run_id") or "").strip()
    if not series_run_id:
        return None
    series_run = await repository.get_series_run(
        db, series_run_id, user_id, workflow.novel_id,
    )
    preflight = ((series_run.gate_summary or {}).get("media_preflight") if series_run else None) or {}
    fresh = await evaluate_media_preflight(
        db, series_run, native_audio=native_audio,
    ) if series_run is not None else {}
    snapshot_changed = bool(series_run and fresh.get("snapshot_hash") != preflight.get("snapshot_hash"))
    fresh_not_ready = bool(series_run and fresh.get("ready") is not True)
    if snapshot_changed or fresh_not_ready:
        await mark_run_episode_contracts_superseded(
            db, series_run, reason="input_snapshot_changed",
            fresh_snapshot_hash=str(fresh.get("snapshot_hash") or ""),
        )
        series_run.gate_summary = {**(series_run.gate_summary or {}), "media_preflight": fresh}
        await db.commit()
    if (
        series_run is None or series_run.status != "media_running"
        or preflight.get("ready") is not True or fresh.get("ready") is not True
        or snapshot_changed
    ):
        raise WorkflowMediaError(409, {
            "code": "series_run_media_preflight_required",
            "message": "整书工作流必须先通过 series run 媒体门禁",
            "series_run_id": series_run_id,
            "issues": fresh.get("issues") or preflight.get("issues") or [],
            "snapshot_changed": snapshot_changed,
        })
    return series_run


async def load_workflow_media_context(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    request: WorkflowMediaBatchRequest,
) -> WorkflowMediaContext:
    workflow = await repository.get_workflow(db, workflow_id, user_id)
    if workflow is None:
        raise WorkflowMediaError(404, "工作流不存在")
    series_run = await _validate_series_run(
        db, user_id, workflow, native_audio=request.native_audio,
    )
    validate_generation_strategy(request.strategy)
    validate_production_strategy(request.production_strategy)
    if not request.shot_ids and not workflow.storyboard_id:
        raise WorkflowMediaError(422, "工作流缺少分镜或指定镜头")
    shots = await repository.list_shots(
        db, user_id, workflow.storyboard_id, request.shot_ids,
    )
    if not shots:
        raise WorkflowMediaError(422, "没有可生成的镜头")
    routing = await resolve_strategy_video_config_id(
        db, user_id, request.production_strategy, request.model_config_id,
    )
    return WorkflowMediaContext(
        db=db,
        user_id=user_id,
        workflow=workflow,
        series_run=series_run,
        shots=shots,
        strategy_video_routing=routing,
        effective_video_config_id=routing["model_config_id"] or request.model_config_id,
    )
