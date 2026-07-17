"""Live-canary accounting and canonical-shot lineage for workflow media."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workflow_media.errors import WorkflowMediaError
from app.models import Shot, Storyboard, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_budget import (
    BindingValidationError,
    BudgetExceeded,
    InvalidAccountingInput,
    prepare_provider_operation,
    required_tested_at_for_run,
    settle_confirmed_provider_rejection,
    validate_model_bindings,
)


def _live_canary_enabled(run: Optional[SeriesProductionRun]) -> bool:
    return bool(run and (run.budget_policy or {}).get("live_canary") is True)


def _live_required_at(run: SeriesProductionRun) -> datetime:
    return required_tested_at_for_run(run)


async def prepare_live_provider_attempt(
    db: AsyncSession,
    run: Optional[SeriesProductionRun],
    *,
    capability: str,
    reservation_id: str,
    job_type: str = "provider_job",
    job_id: Optional[str] = None,
) -> Optional[str]:
    if not _live_canary_enabled(run):
        return None
    assert run is not None
    try:
        capabilities = (run.model_bindings or {}).get("capabilities") or {}
        config_ids = {
            name: str((capabilities.get(name) or {}).get("config_id") or "")
            for name in ("text", "image", "tts", "video")
        }
        await validate_model_bindings(
            db, run, config_ids, required_tested_at=_live_required_at(run), freshness_seconds=900
        )
        policy = run.budget_policy or {}
        estimates = policy.get("estimates_rmb") if isinstance(policy.get("estimates_rmb"), dict) else {}
        estimate = estimates.get(capability, policy.get(f"{capability}_estimate_rmb"))
        if estimate is None:
            raise BudgetExceeded(f"live canary has no trusted {capability} estimate")
        await prepare_provider_operation(
            db, run, capability=capability, job_type=job_type,
            job_id=job_id or reservation_id, reservation_id=reservation_id,
            estimate_rmb=Decimal(str(estimate)),
        )
        return reservation_id
    except (BindingValidationError, BudgetExceeded, InvalidAccountingInput) as error:
        await db.rollback()
        raise WorkflowMediaError(409, {
            "code": "live_canary_provider_gate_failed", "message": str(error), "capability": capability,
        }) from error


async def resolve_live_series_run_for_shot(
    db: AsyncSession, *, user_id: str, shot: Shot
) -> Optional[SeriesProductionRun]:
    """Resolve live context only through persisted shot -> storyboard -> workflow -> run lineage."""
    runs = list((await db.scalars(select(SeriesProductionRun).where(
        SeriesProductionRun.user_id == user_id,
        SeriesProductionRun.status == "media_running",
    ))).all())
    live_runs = [run for run in runs if _live_canary_enabled(run)]
    shot_storyboard = await db.get(Storyboard, shot.storyboard_id) if shot.storyboard_id else None
    matches: list[SeriesProductionRun] = []
    same_novel_live = False
    for run in live_runs:
        if shot_storyboard and shot_storyboard.novel_id == run.novel_id:
            same_novel_live = True
        for episode in run.episodes or []:
            canonical = episode.get("canonical_ids") or {}
            workflow_id = str(canonical.get("workflow_id") or "")
            shot_ids = {str(value) for value in (canonical.get("shot_ids") or [])}
            workflow = await db.scalar(select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.user_id == user_id,
                Workflow.novel_id == run.novel_id,
            )) if workflow_id else None
            if workflow and workflow.storyboard_id == shot.storyboard_id:
                same_novel_live = True
                if shot.id in shot_ids:
                    matches.append(run)
    unique = {run.id: run for run in matches}
    if len(unique) == 1:
        return next(iter(unique.values()))
    if len(unique) > 1 or same_novel_live:
        raise WorkflowMediaError(409, {
            "code": "live_canary_canonical_lineage_invalid",
            "message": "shot is ambiguous or not a canonical member of the active live series run",
            "shot_id": shot.id,
        })
    return None


async def finish_live_provider_attempt(
    db: AsyncSession,
    run: Optional[SeriesProductionRun],
    reservation_id: Optional[str],
    *,
    submission_failed: bool = False,
) -> None:
    if run is None or reservation_id is None:
        return
    if not submission_failed:
        raise InvalidAccountingInput("provider terminal outcomes require operation settlement")
    await settle_confirmed_provider_rejection(db, run, reservation_id=reservation_id)
