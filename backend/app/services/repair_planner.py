"""Smallest-scope repair plans for quality blockers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import NAMESPACE_URL, uuid5


_ACTIONS_BY_ISSUE = {
    "wrong_voice": ("regenerate_tts", "rerun_lipsync", "rerender_audio"),
    "wrong_speaker": ("regenerate_tts", "rerun_lipsync", "rerender_audio"),
    "wrong_prop_state": ("regenerate_shot_video", "rerun_visual_review"),
    "wrong_prop_owner": ("regenerate_shot_video", "rerun_visual_review"),
    "subtitle_timing": ("retime_subtitles", "rerender_subtitles"),
    "missing_subtitle": ("generate_subtitles", "rerender_subtitles"),
    "main_character_identity_mismatch": ("regenerate_shot_video", "rerun_visual_review"),
    "future_episode_leakage": (
        "revise_shot_prompt",
        "regenerate_shot_video",
        "rerun_narrative_review",
    ),
    "corrupt_mp4": ("rerender_video", "validate_mp4"),
}


@dataclass(frozen=True)
class RepairPlan:
    issue_code: str
    actions: tuple[str, ...]
    affected_artifact_ids: tuple[str, ...]
    unchanged_artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class BoundRepairPlan(RepairPlan):
    repair_id: str
    repair_key: str
    parent_job_id: str
    parent_evaluation_ids: tuple[str, ...]
    auto_retry_allowed: bool
    requires_review: bool


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def plan_minimal_repair(
    *,
    issue: str,
    affected_artifact_ids: Iterable[str],
    candidate_artifact_ids: Iterable[str],
) -> RepairPlan:
    """Return actions for only the affected artifacts in the caller-owned scope."""

    affected = _unique(affected_artifact_ids)
    candidates = _unique(candidate_artifact_ids)
    candidate_set = set(candidates)
    if not set(affected).issubset(candidate_set):
        raise ValueError("affected artifact IDs must belong to the candidate scope")

    affected_set = set(affected)
    return RepairPlan(
        issue_code=issue,
        actions=_ACTIONS_BY_ISSUE.get(issue, ("review_affected_artifact",)),
        affected_artifact_ids=affected,
        unchanged_artifact_ids=tuple(
            artifact_id for artifact_id in candidates if artifact_id not in affected_set
        ),
    )


def plan_bound_repair(
    *,
    issue: str,
    artifact_id: str,
    candidate_artifact_ids: Iterable[str],
    parent_job_id: str,
    parent_evaluation_ids: Iterable[str],
    repair_key: str,
    prior_auto_retry_count: int,
) -> BoundRepairPlan:
    """Create an idempotent, artifact-scoped repair plan with audit lineage."""

    if not repair_key or not parent_job_id:
        raise ValueError("repair_key and parent_job_id are required")
    if prior_auto_retry_count < 0:
        raise ValueError("prior_auto_retry_count cannot be negative")
    parent_ids = _unique(parent_evaluation_ids)
    if not parent_ids:
        raise ValueError("parent_evaluation_ids are required")
    base = plan_minimal_repair(
        issue=issue,
        affected_artifact_ids=(artifact_id,),
        candidate_artifact_ids=candidate_artifact_ids,
    )
    semantic_conflict = issue in {
        "future_episode_leakage", "chapter_event_ids_mismatch", "dialogue_meaning_mismatch",
    }
    prompt_local_or_transient = issue in {
        "wrong_voice", "wrong_speaker", "wrong_prop_state", "wrong_prop_owner",
        "main_character_identity_mismatch", "subtitle_timing", "missing_subtitle", "corrupt_mp4",
    }
    return BoundRepairPlan(
        issue_code=base.issue_code,
        actions=base.actions,
        affected_artifact_ids=base.affected_artifact_ids,
        unchanged_artifact_ids=base.unchanged_artifact_ids,
        repair_id=str(uuid5(NAMESPACE_URL, repair_key)),
        repair_key=repair_key,
        parent_job_id=parent_job_id,
        parent_evaluation_ids=parent_ids,
        auto_retry_allowed=prompt_local_or_transient and not semantic_conflict and prior_auto_retry_count < 1,
        requires_review=semantic_conflict or not prompt_local_or_transient,
    )


__all__ = ["BoundRepairPlan", "RepairPlan", "plan_bound_repair", "plan_minimal_repair"]
