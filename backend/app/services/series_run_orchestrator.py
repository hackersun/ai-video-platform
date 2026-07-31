"""Durable finite-state orchestration for whole-book production runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Workflow
from app.features.series_run_media_preflight.public import evaluate_media_preflight
from app.models.series_production_run import SeriesProductionRun
from app.services.episode_contract_service import lock_episode_contract
from app.services.live_canary_budget import (
    reconcile_reservation,
    release_reservation,
    reserve_budget,
    recover_provider_operations,
)
from app.services.live_canary_bindings import (
    validate_persisted_model_bindings,
    validate_required_model_bindings,
)
from app.services.series_run_live_preflight import build_live_preflight_plan
from app.services.episode_production_service import (
    create_or_resolve_script_stage,
    create_or_resolve_shots_stage,
    create_or_resolve_storyboard_stage,
    create_or_resolve_workflow_stage,
)


ACTIVE_STATES = (
    "created", "preflight", "planning", "facts_ready", "assets_ready",
    "episodes_building", "shots_ready", "anchor_ready", "media_running",
    "evaluating", "completed",
)
RECOVERY_STATES = {"failed", "blocked"}
EPISODE_STAGES = ("created", "workflow_ready", "script_ready", "storyboard_ready", "shots_ready")


class InvalidRunTransition(ValueError):
    pass


class SeriesRunPreflightBlocked(RuntimeError):
    def __init__(self, detail: dict[str, Any]) -> None:
        super().__init__(detail.get("message") or "series run media preflight failed")
        self.detail = detail


def transition_run(run: SeriesProductionRun, target: str) -> None:
    current = run.status
    if current == target:
        return
    metadata = dict(run.run_metadata or {})
    if target == "paused":
        if current not in ACTIVE_STATES[:-1]:
            raise InvalidRunTransition(f"cannot pause run in {current}")
        metadata["resume_status"] = current
    elif current == "paused":
        expected = metadata.get("resume_status")
        if not expected:
            raise InvalidRunTransition("paused run has no resume target")
        if expected not in ACTIVE_STATES or target != expected:
            raise InvalidRunTransition(f"paused run must resume to {expected}")
        metadata.pop("resume_status", None)
    elif current in RECOVERY_STATES:
        if target != "episodes_building":
            raise InvalidRunTransition(f"{current} run can only recover to episodes_building")
    elif target in RECOVERY_STATES:
        if current in {"completed", "paused"}:
            raise InvalidRunTransition(f"cannot move {current} run to {target}")
    else:
        try:
            legal_target = ACTIVE_STATES[ACTIVE_STATES.index(current) + 1]
        except (ValueError, IndexError) as error:
            raise InvalidRunTransition(f"no forward transition from {current}") from error
        if target != legal_target:
            raise InvalidRunTransition(f"illegal transition {current} -> {target}")
        if target == "media_running" and not (metadata.get("media_preflight") or {}).get("ready"):
            raise InvalidRunTransition("media_running requires a successful media preflight")
    run.status = target
    run.run_metadata = metadata



async def build_production_stage(
    db: AsyncSession, run: SeriesProductionRun, episode: dict[str, Any], stage: str
) -> dict[str, Any]:
    operations = {
        "workflow_ready": create_or_resolve_workflow_stage,
        "script_ready": create_or_resolve_script_stage,
        "storyboard_ready": create_or_resolve_storyboard_stage,
        "shots_ready": create_or_resolve_shots_stage,
    }
    try:
        operation = operations[stage]
    except KeyError as error:
        raise ValueError(f"unknown episode stage {stage}") from error
    return await operation(db, run=run, episode=episode)


StageBuilder = Callable[[AsyncSession, SeriesProductionRun, dict[str, Any], str], Awaitable[dict[str, Any]]]


class SeriesRunOrchestrator:
    def __init__(self, stage_builder: StageBuilder = build_production_stage) -> None:
        self._stage_builder = stage_builder

    async def validate_live_model_bindings(self, db: AsyncSession, run: SeriesProductionRun, bindings, **constraints):
        constraints.setdefault("persist", True)
        return await validate_required_model_bindings(db, run, bindings, **constraints)

    async def reserve_live_budget(self, db: AsyncSession, run: SeriesProductionRun, **reservation):
        return await reserve_budget(db, run, **reservation)

    async def reconcile_live_budget(self, db: AsyncSession, run: SeriesProductionRun, **reconciliation):
        return await reconcile_reservation(db, run, **reconciliation)

    async def release_live_budget(self, db: AsyncSession, run: SeriesProductionRun, **release):
        return await release_reservation(db, run, **release)

    async def execute(self, db: AsyncSession, run: SeriesProductionRun) -> SeriesProductionRun:
        if run.status in RECOVERY_STATES:
            transition_run(run, "episodes_building")
            await db.commit()
        elif run.status in ACTIVE_STATES[:5]:
            while run.status != "episodes_building":
                transition_run(run, ACTIVE_STATES[ACTIVE_STATES.index(run.status) + 1])
                await db.commit()
        if run.status == "shots_ready":
            return run
        return await self.build_episodes(db, run)

    async def enter_media_running(
        self, db: AsyncSession, run: SeriesProductionRun, *, native_audio: bool = False,
    ) -> SeriesProductionRun:
        if run.status not in {"shots_ready", "anchor_ready"}:
            raise InvalidRunTransition(f"cannot start media from {run.status}")
        if (run.budget_policy or {}).get("live_canary") is True:
            from datetime import timedelta
            from app.core.time_utils import utc_now
            await recover_provider_operations(
                db, adapters={}, user_id=run.user_id,
                stale_before=utc_now() - timedelta(minutes=15),
            )
            live_plan = await build_live_preflight_plan(
                db, run, native_audio=native_audio,
            )
            required_capabilities = set(live_plan["required_capabilities"])
            await validate_persisted_model_bindings(
                db, run, required_capabilities=required_capabilities,
            )
        preflight = await evaluate_media_preflight(db, run, native_audio=native_audio)
        run.gate_summary = {**(run.gate_summary or {}), "media_preflight": preflight}
        if not preflight["ready"]:
            await db.commit()
            raise SeriesRunPreflightBlocked({
                "code": "series_run_media_preflight_failed",
                "message": "真实媒体生成前置条件未满足",
                **preflight,
            })
        savepoint = await db.begin_nested()
        try:
            for episode in run.episodes or []:
                workflow_id = (episode.get("canonical_ids") or {}).get("workflow_id")
                if workflow_id:
                    await lock_episode_contract(
                        db,
                        run.user_id,
                        workflow_id,
                        commit=False,
                        exact_preflight_snapshot={**preflight["input_snapshot"], "snapshot_hash": preflight["snapshot_hash"]},
                    )
            metadata = dict(run.run_metadata or {})
            metadata["media_preflight"] = preflight
            run.run_metadata = metadata
            if run.status == "shots_ready":
                transition_run(run, "anchor_ready")
            transition_run(run, "media_running")
            await savepoint.commit()
            await db.commit()
        except Exception:
            await savepoint.rollback()
            await db.rollback()
            raise
        return run

    async def build_episodes(self, db: AsyncSession, run: SeriesProductionRun) -> SeriesProductionRun:
        if run.status != "episodes_building":
            raise InvalidRunTransition(f"cannot build episodes from {run.status}")
        for index, stored in enumerate(list(run.episodes or [])):
            if stored.get("stage") == "shots_ready":
                continue
            episode = dict(stored)
            episode["attempt_count"] = int(episode.get("attempt_count") or 0) + 1
            episode["blocker"] = None
            self._replace_episode(run, index, episode)
            run.current_episode_number = int(episode["episode_number"])
            await db.commit()
            current_stage = episode.get("stage") or "created"
            for stage in EPISODE_STAGES[EPISODE_STAGES.index(current_stage) + 1:]:
                try:
                    async with db.begin_nested():
                        additions = await self._stage_builder(db, run, dict(episode), stage)
                        await db.flush()
                except Exception as error:
                    await db.refresh(run)
                    failed = dict(run.episodes[index])
                    failed["blocker"] = str(error)
                    self._replace_episode(run, index, failed)
                    transition_run(run, "failed")
                    await db.commit()
                    raise
                episode = dict(episode)
                canonical = dict(episode.get("canonical_ids") or {})
                canonical.update(additions)
                episode.update(stage=stage, canonical_ids=canonical, blocker=None)
                self._replace_episode(run, index, episode)
                await db.commit()
        transition_run(run, "shots_ready")
        run.current_episode_number = int((run.episodes or [])[-1]["episode_number"])
        await db.commit()
        return run

    @staticmethod
    def _replace_episode(run: SeriesProductionRun, index: int, episode: dict[str, Any]) -> None:
        episodes = list(run.episodes or [])
        episodes[index] = episode
        run.episodes = episodes


async def mark_run_episode_contracts_superseded(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    reason: str,
    fresh_snapshot_hash: str,
) -> list[str]:
    workflow_ids = [
        str((episode.get("canonical_ids") or {}).get("workflow_id"))
        for episode in run.episodes or []
        if (episode.get("canonical_ids") or {}).get("workflow_id")
    ]
    workflows = list((await db.scalars(select(Workflow).where(
        Workflow.id.in_(workflow_ids),
        Workflow.user_id == run.user_id,
        Workflow.novel_id == run.novel_id,
    ))).all()) if workflow_ids else []
    affected: list[str] = []
    for workflow in workflows:
        metadata = dict(workflow.metadata_ or {})
        if metadata.get("series_run_id") != run.id:
            continue
        contract = dict(metadata.get("episode_contract") or {})
        if not contract:
            continue
        contract.update({
            "status": "superseded_review_required",
            "superseded_reason": reason,
            "fresh_snapshot_hash": fresh_snapshot_hash,
        })
        metadata["episode_contract"] = contract
        workflow.metadata_ = metadata
        flag_modified(workflow, "metadata_")
        affected.append(workflow.id)
    return affected
