"""Persistent whole-book production run API."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.time_utils import utc_now
from app.models.novel import Novel
from app.models.chapter import Chapter
from app.models.shot import Shot
from app.models.workflow import Workflow
from app.models.storyboard import Storyboard
from app.models.media_generation_job import MediaGenerationJob
from app.models.series_production_run import SeriesProductionRun
from app.models.series_anchor_generation_submission import SeriesAnchorGenerationSubmission
from app.models.story_entity import StoryEntity
from app.services.story_entity_lifecycle import ARCHIVED, CANDIDATE, set_entity_review_status
from app.services.anchor_shot_service import anchor_coverage_blocker, anchor_shot_input, recommend_anchor_shots, validate_anchor_selection
from app.models.quality_evaluation import QualityEvaluation
from app.models.quality_evaluation import QUALITY_DIMENSIONS
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled
from app.services.deterministic_acceptance_lineage import sync_deterministic_episode_input_hash
from app.services.quality_evaluation_service import (
    AUTHORITATIVE_DIMENSION_POLICY,
    ArtifactBindingError,
    USER_FACING_DIMENSIONS,
    evaluate_bound_anchor,
    validate_persisted_anchor_evaluations,
)
from app.services.repair_planner import plan_bound_repair
from app.services.series_run_orchestrator import (
    InvalidRunTransition,
    SeriesRunOrchestrator,
    SeriesRunPreflightBlocked,
    transition_run,
)
from app.services.series_run_execution_queue import (
    queue_series_run_execution,
)
from app.features.series_run_media_preflight.public import evaluate_media_preflight
from app.features.series_run_acceptance import setup_acceptance_fixture
from app.features.series_anchor_generation import (
    SeriesAnchorError, accept_quality, create_run as create_series_run_record,
    generate_selected_anchors,
    plan_repair as plan_anchor_repair_record,
)
from app.features.series_anchor_generation.schemas import (
    AcceptAnchorQualityRequest, AnchorSelectionRequest, CreateSeriesRunRequest,
    DeterministicAcceptanceSetupRequest, GenerateSelectedRequest, PlanAnchorRepairRequest,
    PrepareReferenceResponse, ValidateLiveBindingsRequest, VoiceSelectionRequest,
)
from app.features.series_anchor_generation.quality_status import unevaluated_quality_results
from app.features.workflow_media import public as workflow_media
from app.api.v1.workflow_media_transport import workflow_media_result
from app.services.live_canary_budget import (
    BindingValidationError,
    InvalidAccountingInput,
    required_tested_at_for_run,
    trusted_live_canary_policy,
    validate_model_bindings,
)
from app.features.series_run_story_locks.public import (
    StoryLockPreparationBlocked,
    apply_deterministic_voice_binding, deterministic_anchor_entity_refs, deterministic_evidence_contract,
    seed_deterministic_local_mentions,
    prepare_story_locks,
    safe_story_lock_error_detail,
)
from app.services.series_run_live_preflight import build_live_preflight_plan, persist_voice_selection
from app.services.series_run_reference_preparation import (
    ReferencePreparationBlocked,
    default_reference_adapter,
    prepare_series_reference,
)
router = APIRouter()




async def _run_shots(db: AsyncSession, run: SeriesProductionRun) -> tuple[list, dict[str, str]]:
    shot_ids: list[str] = []
    workflow_for_shot: dict[str, str] = {}
    episode_for_shot: dict[str, int] = {}
    for episode in run.episodes or []:
        canonical = episode.get("canonical_ids") or {}
        workflow_id = canonical.get("workflow_id")
        for shot_id in canonical.get("shot_ids") or []:
            shot_ids.append(str(shot_id))
            workflow_for_shot[str(shot_id)] = str(workflow_id or "")
            episode_for_shot[str(shot_id)] = int(episode.get("episode_number") or 0)
    if not shot_ids:
        return [], {}
    rows = list((await db.scalars(select(Shot).where(Shot.id.in_(shot_ids), Shot.user_id == run.user_id))).all())
    shots = [anchor_shot_input(shot, episode_number=episode_for_shot.get(shot.id, 0)) for shot in rows]
    return shots, workflow_for_shot


def _payload(run: SeriesProductionRun) -> dict:
    return {
        "id": run.id,
        "user_id": run.user_id,
        "novel_id": run.novel_id,
        "series_plan_version": run.series_plan_version,
        "status": run.status,
        "current_episode_number": run.current_episode_number,
        "requested_stages": run.requested_stages or [],
        "model_bindings": run.model_bindings or {},
        "budget_policy": run.budget_policy or {},
        "cost_summary": run.cost_summary or {},
        "gate_summary": run.gate_summary or {},
        "run_metadata": run.run_metadata or {},
        "episodes": run.episodes or [],
        "version": run.version,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


async def _owned_run(db: AsyncSession, user_id: str, run_id: str) -> SeriesProductionRun:
    run = await db.scalar(
        select(SeriesProductionRun).where(
            SeriesProductionRun.id == run_id,
            SeriesProductionRun.user_id == user_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="series run not found")
    return run


@router.get("/series-runs/{run_id}/live-preflight-plan")
async def get_series_run_live_preflight_plan(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    native_audio: bool = False,
):
    run = await _owned_run(db, user_id, run_id)
    return await build_live_preflight_plan(db, run, native_audio=native_audio)


@router.post("/series-runs/{run_id}/voice-selection")
async def post_series_run_voice_selection(
    run_id: str,
    request: VoiceSelectionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    try:
        return await persist_voice_selection(
            db, run, config_id=request.config_id, model_id=request.model_id,
            voice_id=request.voice_id, version=request.version,
        )
    except BindingValidationError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "voice_selection_blocked", "message": str(error),
        }) from error


@router.post("/series-runs/{run_id}/prepare-story-locks")
async def post_series_run_prepare_story_locks(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    native_audio: bool = False,
):
    run = await _owned_run(db, user_id, run_id)
    try:
        return await prepare_story_locks(db, run, native_audio=native_audio)
    except StoryLockPreparationBlocked as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=safe_story_lock_error_detail(error),
        ) from error

@router.post("/series-runs/{run_id}/prepare-reference", response_model=PrepareReferenceResponse)
async def post_series_run_prepare_reference(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    native_audio: bool = False,
):
    run = await _owned_run(db, user_id, run_id)
    try:
        return await prepare_series_reference(
            db,
            run,
            adapter=default_reference_adapter(),
            native_audio=native_audio,
        )
    except ReferencePreparationBlocked as error:
        detail = {"code": "reference_preparation_blocked", "message": str(error)}
        if error.operation is not None:
            detail["operation"] = error.operation
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from error


@router.post("/series-runs")
async def create_series_run(
    request: CreateSeriesRunRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        run, created = await create_series_run_record(
            db, user_id=user_id, novel_id=request.novel_id,
            plan_version=request.series_plan_version, idempotency_key=request.idempotency_key,
            requested_stages=list(request.requested_stages), model_bindings=dict(request.model_bindings),
            requested_budget_policy=dict(request.budget_policy), episodes=[episode.model_dump() for episode in request.episodes],
        )
    except SeriesAnchorError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return JSONResponse(_payload(run), status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@router.post("/series-runs/deterministic-acceptance/setup")
async def setup_deterministic_acceptance(
    request: DeterministicAcceptanceSetupRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Seed only non-secret adapter bindings for an isolated browser acceptance."""
    if not deterministic_provider_fake_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    try:
        return await setup_acceptance_fixture(db, user_id=user_id, novel_id=request.novel_id)
    except SeriesAnchorError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/series-runs/{run_id}")
async def get_series_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return _payload(await _owned_run(db, user_id, run_id))


async def _change_state(db: AsyncSession, run: SeriesProductionRun, target: str) -> dict:
    try:
        transition_run(run, target)
    except InvalidRunTransition as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    try:
        await db.commit()
    except StaleDataError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="series run version conflict") from error
    await db.refresh(run)
    return _payload(run)


@router.post("/series-runs/{run_id}/pause")
async def pause_series_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await _change_state(db, await _owned_run(db, user_id, run_id), "paused")


@router.post("/series-runs/{run_id}/resume")
async def resume_series_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    if run.status == "paused":
        target = (run.run_metadata or {}).get("resume_status")
        if not target:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="paused run has no resume target")
        return await _change_state(db, run, target)
    if run.status in {"failed", "blocked"}:
        return await _change_state(db, run, "episodes_building")
    return _payload(run)


@router.post("/series-runs/{run_id}/execute")
async def execute_series_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    try:
        await SeriesRunOrchestrator().execute(db, run)
    except InvalidRunTransition as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except StaleDataError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="series run version conflict") from error
    await db.refresh(run)
    return _payload(run)


@router.post("/series-runs/{run_id}/execute-async")
async def execute_series_run_async(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Queue resumable episode work and return without holding the browser request."""
    run = await _owned_run(db, user_id, run_id)
    if run.status in {"shots_ready", "anchor_ready", "completed", "paused"}:
        execution, queued = None, False
    else:
        execution, queued = await queue_series_run_execution(db, run)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            **_payload(run),
            "execution_status": "queued" if queued else "already_running" if execution else "not_required",
            "execution_id": execution.id if execution else None,
        },
    )


@router.get("/series-runs/{run_id}/media-preflight")
async def get_series_run_media_preflight(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await evaluate_media_preflight(db, await _owned_run(db, user_id, run_id))


@router.post("/series-runs/{run_id}/anchors/quality")
async def accept_series_anchor_quality(
    run_id: str,
    request: AcceptAnchorQualityRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    try:
        return await accept_quality(db, run=run, user_id=user_id, shot_id=request.shot_id,
                                    job_id=request.job_id, evaluation_ids=request.evaluation_ids)
    except SeriesAnchorError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/series-runs/{run_id}/anchors/repair")
async def plan_series_anchor_repair(
    run_id: str,
    request: PlanAnchorRepairRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    try:
        return await plan_anchor_repair_record(db, run=run, user_id=user_id, request=request.model_dump())
    except SeriesAnchorError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/series-runs/{run_id}/media/start")
async def start_series_run_media(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    try:
        await SeriesRunOrchestrator().enter_media_running(db, run)
    except SeriesRunPreflightBlocked as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.detail) from error
    except BindingValidationError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InvalidRunTransition as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    await db.refresh(run)
    return _payload(run)


@router.post("/series-runs/{run_id}/live-bindings/validate")
async def validate_series_run_live_bindings(
    run_id: str,
    request: ValidateLiveBindingsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    try:
        snapshot = await SeriesRunOrchestrator().validate_live_model_bindings(
            db,
            run,
            request.required_bindings(),
            required_tested_at=required_tested_at_for_run(run),
            freshness_seconds=900,
        )
    except BindingValidationError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except StaleDataError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="series run version conflict") from error
    return {"model_bindings": snapshot, "version": run.version}


@router.post("/series-runs/{run_id}/live-canary/enable")
async def enable_series_run_live_canary(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Explicitly opt a run into the server-owned isolated live budget profile."""
    run = await _owned_run(db, user_id, run_id)
    try:
        run.budget_policy = trusted_live_canary_policy({"profile": "isolated_live_canary"})
    except InvalidAccountingInput as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "live_canary_unavailable", "message": str(error),
        }) from error
    await db.commit()
    await db.refresh(run)
    return _payload(run)


@router.get("/series-runs/{run_id}/anchor-shots")
async def get_series_run_anchor_shots(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    shots, _ = await _run_shots(db, run)
    metadata = run.run_metadata or {}
    smoke = recommend_anchor_shots(shots, mode="smoke")
    representative = recommend_anchor_shots(shots, mode="representative")
    full = recommend_anchor_shots(shots, mode="full")
    return {
        "selected_shot_ids": metadata.get("selected_anchor_shot_ids") or [],
        "selected_mode": metadata.get("selected_anchor_mode"),
        "smoke": smoke,
        "representative": representative,
        "full": full,
        "blockers": {
            "smoke": anchor_coverage_blocker(smoke, mode="smoke"),
            "representative": anchor_coverage_blocker(representative, mode="representative"),
            "full": anchor_coverage_blocker(full, mode="full"),
        },
    }


@router.put("/series-runs/{run_id}/anchor-shots")
async def put_series_run_anchor_shots(
    run_id: str,
    request: AnchorSelectionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    shots, _ = await _run_shots(db, run)
    try:
        selected = validate_anchor_selection(request.shot_ids, {shot.id for shot in shots})
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    recommendations = recommend_anchor_shots(shots, mode=request.mode)
    blocker = anchor_coverage_blocker(recommendations, mode=request.mode)
    if blocker:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocker)
    if set(selected) != {item["shot_id"] for item in recommendations}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="selection must match recommended mode anchors")
    run.run_metadata = {
        **(run.run_metadata or {}),
        "selected_anchor_shot_ids": selected,
        "selected_anchor_mode": request.mode,
        "anchor_selection_revision": int((run.run_metadata or {}).get("anchor_selection_revision") or 0) + int(selected != ((run.run_metadata or {}).get("selected_anchor_shot_ids") or []) or request.mode != (run.run_metadata or {}).get("selected_anchor_mode")),
    }
    await db.commit()
    await db.refresh(run)
    return {"selected_shot_ids": selected, "version": run.version}


@router.post("/series-runs/{run_id}/generate-selected")
async def generate_selected_series_run_anchors(
    run_id: str,
    request: GenerateSelectedRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await _owned_run(db, user_id, run_id)
    shots, workflow_for_shot = await _run_shots(db, run)

    async def generate_batch(workflow_id, shot_ids, video_config_id, audio_config_id):
        result = await workflow_media_result(
            workflow_media.generate_workflow_media_batch(workflow_media.WorkflowMediaCommand(
                db, user_id, workflow_id, workflow_media.WorkflowMediaBatchRequest(
                    shot_ids=shot_ids, production_strategy="final_quality",
                    strategy=("direct_av_first" if deterministic_provider_fake_enabled() else "separate_video_tts"),
                    model_config_id=video_config_id, audio_model_config_id=audio_config_id,
                    native_audio=request.native_audio,
                    require_real_video=True,
                    require_provider_reference_image=not request.native_audio,
                ),
            ))
        )
        return result.model_dump()

    async def accept_generated_quality(shot, job, evaluation_ids):
        return await accept_series_anchor_quality(
            run.id,
            AcceptAnchorQualityRequest(shot_id=shot.id, job_id=job.id, evaluation_ids=evaluation_ids),
            db, user_id,
        )

    try:
        return await generate_selected_anchors(
            db, run=run, user_id=user_id, shots=shots, workflow_for_shot=workflow_for_shot,
            requested=request.shot_ids, mode=request.mode, generate_batch=generate_batch,
            native_audio=request.native_audio,
            accept_quality=accept_generated_quality,
        )
    except SeriesAnchorError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
