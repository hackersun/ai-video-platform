"""Decision metrics for series production readiness."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.workflow import Workflow


MAIN_CHARACTER_FAILURES = {"main_character_identity_mismatch"}
STATE_CONTINUITY_FAILURES = {"wrong_prop_owner", "wrong_prop_state", "future_episode_leakage"}
VOICE_LIPSYNC_FAILURES = {"wrong_speaker", "wrong_voice", "voice_lipsync_failure"}


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _per_minute(value: float, accepted_minutes: float) -> float | None:
    return round(value / accepted_minutes, 4) if accepted_minutes > 0 else None


def aggregate_production_metrics(attempts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate every attempt while using accepted finals only for efficiency denominators."""
    records = [dict(item) for item in attempts]
    shot_ids = {str(item.get("shot_id")) for item in records if item.get("shot_id")}
    accepted_records = [item for item in records if item.get("accepted_final") is True]
    accepted_shot_ids = {str(item.get("shot_id")) for item in accepted_records if item.get("shot_id")}
    failed_records = [item for item in records if item.get("status") == "failed"]
    abandoned_records = [item for item in records if item.get("status") == "abandoned"]
    regenerated = [
        item for item in records
        if item.get("shot_id") and int(item.get("attempt") or 1) > 1
    ]
    first_pass_accepted = {
        str(item.get("shot_id"))
        for item in accepted_records
        if int(item.get("attempt") or 1) == 1 and item.get("shot_id")
    }

    def shots_with_issue(codes: set[str]) -> set[str]:
        return {
            str(item.get("shot_id"))
            for item in records
            if item.get("shot_id") and codes.intersection(set(item.get("issue_codes") or []))
        }

    total_cost = sum(_number(item.get("cost_rmb")) for item in records)
    missing_cost_count = sum(item.get("cost_rmb") is None for item in records)
    total_wall = sum(_number(item.get("wall_clock_minutes")) for item in records)
    total_human = sum(
        _number(item.get("human_review_minutes")) + _number(item.get("human_repair_minutes"))
        for item in records
    )
    accepted_minutes = sum(_number(item.get("final_duration_seconds")) for item in accepted_records) / 60
    failed_abandoned = [*failed_records, *abandoned_records]

    attribution_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        key = (
            str(item.get("provider_id") or "unknown"),
            str(item.get("model_id") or "unknown"),
            str(item.get("prompt_version") or "unknown"),
            str(item.get("contract_version") or "unknown"),
        )
        attribution_groups[key].append(item)
    attribution = []
    for key, group in sorted(attribution_groups.items()):
        attribution.append({
            "provider_id": key[0],
            "model_id": key[1],
            "prompt_version": key[2],
            "contract_version": key[3],
            "attempts": len(group),
            "accepted_final_shots": len({str(item.get("shot_id")) for item in group if item.get("accepted_final") is True}),
            "failed_attempts": sum(item.get("status") == "failed" for item in group),
            "abandoned_attempts": sum(item.get("status") == "abandoned" for item in group),
            "cost_rmb": round(sum(_number(item.get("cost_rmb")) for item in group), 4),
        })

    evidence_fields = ("provider_id", "model_id", "prompt_version", "contract_version")
    evidence_missing = {
        field: sum(item.get(field) == "evidence_missing" for item in records)
        for field in evidence_fields
    }
    return {
        "counts": {
            "planned_shots": len(shot_ids),
            "attempts": len(records),
            "accepted_final_shots": len(accepted_shot_ids),
            "failed_attempts": len(failed_records),
            "abandoned_attempts": len(abandoned_records),
            "regenerated_attempts": len(regenerated),
        },
        "first_pass_shot_acceptance_rate": _rate(len(first_pass_accepted), len(shot_ids)),
        "main_character_hard_failure_rate": _rate(len(shots_with_issue(MAIN_CHARACTER_FAILURES)), len(shot_ids)),
        "state_continuity_conflict_rate": _rate(len(shots_with_issue(STATE_CONTINUITY_FAILURES)), len(shot_ids)),
        "voice_lipsync_hard_failure_rate": _rate(len(shots_with_issue(VOICE_LIPSYNC_FAILURES)), len(shot_ids)),
        "regenerated_shots_per_accepted_shot": (
            round(len(regenerated) / len(accepted_shot_ids), 4) if accepted_shot_ids else None
        ),
        "rmb_per_accepted_final_minute": (
            None if missing_cost_count else _per_minute(total_cost, accepted_minutes)
        ),
        "wall_clock_minutes_per_accepted_final_minute": _per_minute(total_wall, accepted_minutes),
        "human_review_repair_minutes_per_accepted_final_minute": _per_minute(total_human, accepted_minutes),
        "accepted_final_minutes": round(accepted_minutes, 4),
        "failed_abandoned": {
            "attempt_count": len(failed_abandoned),
            "cost_rmb": round(sum(_number(item.get("cost_rmb")) for item in failed_abandoned), 4),
            "wall_clock_minutes": round(sum(_number(item.get("wall_clock_minutes")) for item in failed_abandoned), 4),
        },
        "attribution": attribution,
        "evidence_missing": {**evidence_missing, "cost_rmb": missing_cost_count},
    }


def evaluate_readiness_tiers(
    deterministic: Mapping[str, Any],
    internal_trial: Mapping[str, Any],
    live_runs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    deterministic_ready = all(
        deterministic.get(key) is True
        for key in ("contract_tests", "frontend_build", "browser_suite")
    )
    internal_trial_ready = deterministic_ready and all(
        internal_trial.get(key) is True for key in ("passed", "persisted_local_data")
    )
    qualifying = [
        dict(run)
        for run in live_runs
        if int(run.get("episodes") or 0) >= 3
        and run.get("passed") is True
        and run.get("thresholds_passed") is True
        and run.get("manual_db_repair") is False
    ]
    series_candidate = internal_trial_ready and bool(qualifying)
    distinct_dates = {str(run.get("date")) for run in qualifying if run.get("date")}
    commercial_ready = series_candidate and len(distinct_dates) >= 3
    tiers = {
        "deterministic_ready": deterministic_ready,
        "internal_trial_ready": internal_trial_ready,
        "series_production_candidate": series_candidate,
        "commercial_series_ready": commercial_ready,
    }
    current = "not_ready"
    for tier in tiers:
        if tiers[tier]:
            current = tier
    return {"current_tier": current, "tiers": tiers, "qualifying_live_run_count": len(qualifying)}


async def persist_production_readiness_evidence(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise ValueError("workflow not found for readiness evidence owner")
    metadata = dict(workflow.metadata_ or {})
    evidence = dict(metadata.get("production_readiness_evidence") or {})
    for key in ("deterministic", "internal_trial"):
        incoming = payload.get(key)
        if isinstance(incoming, Mapping):
            evidence[key] = {**dict(evidence.get(key) or {}), **dict(incoming)}
    live_run = payload.get("live_run")
    if isinstance(live_run, Mapping):
        run = dict(live_run)
        identity = str(run.get("run_id") or run.get("date") or "")
        if not identity:
            raise ValueError("live readiness evidence requires run_id or date")
        runs = [dict(item) for item in evidence.get("live_runs") or [] if isinstance(item, Mapping)]
        runs = [item for item in runs if str(item.get("run_id") or item.get("date") or "") != identity]
        runs.append(run)
        evidence["live_runs"] = sorted(runs, key=lambda item: (str(item.get("date") or ""), str(item.get("run_id") or "")))
    metadata["production_readiness_evidence"] = evidence
    workflow.metadata_ = metadata
    flag_modified(workflow, "metadata_")
    await db.commit()
    return evidence


__all__ = [
    "aggregate_production_metrics",
    "evaluate_readiness_tiers",
    "persist_production_readiness_evidence",
]
