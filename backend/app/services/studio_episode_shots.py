"""Resolve every scene storyboard and shot owned by one Studio episode."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Shot, Storyboard, Workflow


def _content(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _matches_episode(board: Storyboard, metadata: dict[str, Any]) -> bool:
    content = _content(board.content)
    return (
        bool(metadata.get("series_run_id"))
        and content.get("series_run_id") == metadata.get("series_run_id")
        and int(content.get("episode_number") or 0) == int(metadata.get("episode_number") or 0)
        and content.get("input_hash") == metadata.get("input_hash")
    )


async def load_studio_episode_storyboards(
    db: AsyncSession,
    *,
    user_id: str,
    workflow: Workflow,
    primary: Storyboard | None,
) -> list[Storyboard]:
    if primary is None:
        return []
    metadata = _content(workflow.metadata_)
    rows = list((await db.scalars(select(Storyboard).where(
        Storyboard.user_id == user_id,
        Storyboard.novel_id == workflow.novel_id,
        Storyboard.script_id == workflow.script_id,
    ))).all())
    tagged = [board for board in rows if _matches_episode(board, metadata)]
    scene_boards = [
        board for board in tagged
        if int(_content(board.content).get("scene_index") or 0) > 0
        and bool(str(_content(board.content).get("source_text") or "").strip())
    ]
    boards = scene_boards or ([primary] if primary else [])
    return sorted(boards, key=lambda board: (
        int(_content(board.content).get("scene_index") or 1), str(board.id),
    ))


async def load_studio_episode_shots(
    db: AsyncSession,
    *,
    user_id: str,
    storyboards: list[Storyboard],
    limit: int,
) -> list[Shot]:
    board_ids = [board.id for board in storyboards]
    if not board_ids:
        return []
    rows = list((await db.scalars(select(Shot).where(
        Shot.user_id == user_id,
        Shot.storyboard_id.in_(board_ids),
    ).limit(limit))).all())
    board_order = {board_id: index for index, board_id in enumerate(board_ids)}
    return sorted(rows, key=lambda shot: (
        int(_content(shot.extra_data).get("episode_shot_number") or 0)
        or board_order.get(shot.storyboard_id, 0) * 1000 + int(shot.shot_number or 0),
        str(shot.id),
    ))


__all__ = ["load_studio_episode_shots", "load_studio_episode_storyboards"]
