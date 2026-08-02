"""Resolve every shot owned by a workflow, including scene-split storyboards."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Shot, Storyboard, Workflow


def _scene_index(board: Storyboard) -> int:
    content = board.content if isinstance(board.content, dict) else {}
    try:
        return max(1, int(content.get("scene_index") or 1))
    except (TypeError, ValueError):
        return 1


def _series_owned(board: Storyboard, metadata: dict[str, Any]) -> bool:
    content = board.content if isinstance(board.content, dict) else {}
    return (
        content.get("series_run_id") == metadata.get("series_run_id")
        and content.get("episode_number") == metadata.get("episode_number")
    )


async def workflow_shots(
    db: AsyncSession,
    *,
    workflow: Workflow,
    user_id: str,
    shot_ids: list[str] | None = None,
) -> list[Shot]:
    if not workflow.storyboard_id:
        return []
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    boards: list[Storyboard] = []
    if metadata.get("series_run_id") and workflow.script_id:
        candidates = list((await db.scalars(select(Storyboard).where(
            Storyboard.user_id == user_id,
            Storyboard.script_id == workflow.script_id,
            Storyboard.novel_id == workflow.novel_id,
        ))).all())
        boards = [board for board in candidates if _series_owned(board, metadata)]
    if not boards:
        board = await db.scalar(select(Storyboard).where(
            Storyboard.id == workflow.storyboard_id, Storyboard.user_id == user_id,
        ))
        boards = [board] if board else []
    boards.sort(key=lambda board: (_scene_index(board), board.created_at, board.id))
    board_order = {board.id: index for index, board in enumerate(boards)}
    query = select(Shot).where(Shot.user_id == user_id, Shot.storyboard_id.in_(board_order))
    if shot_ids:
        query = query.where(Shot.id.in_(shot_ids))
    shots = list((await db.scalars(query)).all())
    return sorted(shots, key=lambda shot: (board_order[shot.storyboard_id], int(shot.shot_number or 0), shot.id))


async def workflow_owns_storyboard(
    db: AsyncSession,
    *,
    workflow: Workflow,
    user_id: str,
    storyboard_id: str,
) -> bool:
    if storyboard_id == workflow.storyboard_id:
        return True
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    if not metadata.get("series_run_id") or metadata.get("episode_number") is None:
        return False
    board = await db.scalar(select(Storyboard).where(
        Storyboard.id == storyboard_id,
        Storyboard.user_id == user_id,
        Storyboard.script_id == workflow.script_id,
        Storyboard.novel_id == workflow.novel_id,
    ))
    return bool(board and _series_owned(board, metadata))


__all__ = ["workflow_owns_storyboard", "workflow_shots"]
