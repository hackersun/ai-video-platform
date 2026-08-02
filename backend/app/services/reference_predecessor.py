"""Resolve the nearest successful predecessor media inside one novel."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Script, Shot, Storyboard, VideoJob


def _scene_index(storyboard: Storyboard) -> int:
    content = storyboard.content if isinstance(storyboard.content, dict) else {}
    try:
        return max(1, int(content.get("scene_index") or content.get("storyboard_index") or 1))
    except (TypeError, ValueError):
        return 1


def _order_key(chapter: Chapter, storyboard: Storyboard, shot: Shot) -> tuple[Any, ...]:
    return (
        int(chapter.chapter_number or 0),
        _scene_index(storyboard),
        storyboard.created_at,
        int(shot.shot_number or 0),
        shot.created_at,
        shot.id,
    )


async def find_previous_successful_video(
    db: AsyncSession,
    *,
    user_id: str,
    shot: Shot,
) -> Shot | None:
    """Return the nearest strict predecessor, never crossing user or novel."""
    same_board = await db.scalar(
        select(Shot)
        .where(and_(
            Shot.user_id == user_id,
            Shot.storyboard_id == shot.storyboard_id,
            Shot.shot_number < shot.shot_number,
            Shot.video_status == "succeeded",
            Shot.video_url.is_not(None),
        ))
        .order_by(Shot.shot_number.desc(), Shot.updated_at.desc(), Shot.id)
        .limit(1)
    )
    if same_board is not None:
        return same_board
    current = await db.execute(
        select(Storyboard, Script, Chapter)
        .join(Script, Script.id == Storyboard.script_id)
        .join(Chapter, Chapter.id == Script.chapter_id)
        .where(and_(Storyboard.id == shot.storyboard_id, Storyboard.user_id == user_id))
    )
    current_row = current.first()
    if current_row is None:
        return None
    current_board, current_script, current_chapter = current_row
    novel_id = current_board.novel_id or current_script.novel_id or current_chapter.novel_id
    rows = (await db.execute(
        select(Shot, Storyboard, Chapter)
        .join(Storyboard, Storyboard.id == Shot.storyboard_id)
        .join(Script, Script.id == Storyboard.script_id)
        .join(Chapter, Chapter.id == Script.chapter_id)
        .where(and_(
            Shot.user_id == user_id,
            Storyboard.user_id == user_id,
            Storyboard.novel_id == novel_id,
            Shot.video_status == "succeeded",
            Shot.video_url.is_not(None),
        ))
    )).all()
    current_key = _order_key(current_chapter, current_board, shot)
    predecessors = [
        (candidate, _order_key(chapter, board, candidate))
        for candidate, board, chapter in rows
        if candidate.id != shot.id and _order_key(chapter, board, candidate) < current_key
    ]
    if not predecessors:
        return None
    return max(predecessors, key=lambda item: item[1])[0]


async def find_previous_successful_video_cover(
    db: AsyncSession,
    *,
    user_id: str,
    shot: Shot,
) -> tuple[Shot, str] | None:
    previous = await find_previous_successful_video(db, user_id=user_id, shot=shot)
    if previous is None:
        return None
    job = await db.scalar(
        select(VideoJob)
        .where(and_(
            VideoJob.user_id == user_id,
            VideoJob.shot_id == previous.id,
            VideoJob.status == "succeeded",
            VideoJob.cover_url.is_not(None),
            VideoJob.is_active.is_(True),
        ))
        .order_by(VideoJob.updated_at.desc(), VideoJob.created_at.desc(), VideoJob.id)
        .limit(1)
    )
    return (previous, str(job.cover_url)) if job and job.cover_url else None


__all__ = ["find_previous_successful_video", "find_previous_successful_video_cover"]
