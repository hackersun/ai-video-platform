"""Fail-closed lineage retagging for the deterministic acceptance setup."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Script, Shot, Storyboard, Workflow


def _retag(value: Any, run_id: str, episode_number: int, input_hash: str, label: str) -> dict[str, Any]:
    if (not isinstance(value, dict) or value.get("series_run_id") != run_id
            or int(value.get("episode_number") or 0) != episode_number):
        raise ValueError(f"deterministic {label} lineage conflict")
    return {**value, "input_hash": input_hash}


async def sync_deterministic_episode_input_hash(
    db: AsyncSession, *, run: Any, episode: dict[str, Any], input_hash: str,
) -> None:
    """Retag only the episode's already-canonical, same-owner production chain."""
    canonical = dict(episode.get("canonical_ids") or {})
    number = int(episode.get("episode_number") or 0)
    chapter_ids = {str(value) for value in episode.get("chapter_ids") or []}
    workflow_id = canonical.get("workflow_id")
    workflow = await db.get(Workflow, workflow_id) if workflow_id else None
    if workflow_id and (workflow is None or workflow.user_id != run.user_id
                        or workflow.novel_id != run.novel_id or workflow.chapter_id not in chapter_ids):
        raise ValueError("deterministic workflow owner chain conflict")
    if workflow is not None:
        workflow.metadata_ = _retag(workflow.metadata_, run.id, number, input_hash, "workflow")

    script_id = canonical.get("script_id")
    script = await db.get(Script, script_id) if script_id else None
    if script_id and (script is None or script.user_id != run.user_id or script.novel_id != run.novel_id
                      or workflow is None or workflow.script_id != script.id):
        raise ValueError("deterministic script owner chain conflict")
    if script is not None:
        script.extra_data = _retag(script.extra_data, run.id, number, input_hash, "script")

    storyboard_id = canonical.get("storyboard_id")
    storyboard = await db.get(Storyboard, storyboard_id) if storyboard_id else None
    if storyboard_id and (storyboard is None or storyboard.user_id != run.user_id
                          or storyboard.novel_id != run.novel_id or script is None
                          or storyboard.script_id != script.id or workflow is None
                          or workflow.storyboard_id != storyboard.id):
        raise ValueError("deterministic storyboard owner chain conflict")
    if storyboard is not None:
        storyboard.content = _retag(storyboard.content, run.id, number, input_hash, "storyboard")

    shot_ids = [str(value) for value in canonical.get("shot_ids") or []]
    if shot_ids and storyboard is None:
        raise ValueError("deterministic shot owner chain is incomplete")
    for shot_id in shot_ids:
        shot = await db.get(Shot, shot_id)
        if shot is None or shot.user_id != run.user_id or shot.storyboard_id != storyboard.id:
            raise ValueError("deterministic shot owner chain conflict")
        shot.extra_data = _retag(shot.extra_data, run.id, number, input_hash, "shot")
