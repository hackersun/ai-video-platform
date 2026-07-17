"""Shared low-level persistence operations for episode production entry points."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.script import Script
from app.models.storyboard import Storyboard
from app.models.workflow import Workflow
from app.services.dialogue_lineage_service import extract_explicit_dialogue


def _same_tag(value: Any, run_id: str, episode_number: int) -> bool:
    return isinstance(value, dict) and value.get("series_run_id") == run_id and value.get("episode_number") == episode_number


def _validate_tag(value: Any, run, episode: dict[str, Any], label: str) -> None:
    if not _same_tag(value, run.id, int(episode["episode_number"])):
        raise ValueError(f"{label} does not belong to this series run episode")
    if value.get("input_hash") != episode.get("input_hash"):
        raise ValueError(f"{label} input_hash mismatch")


def _resolve_single(rows: list[Any], metadata_name: str, run, episode: dict[str, Any], label: str):
    matches = [row for row in rows if _same_tag(getattr(row, metadata_name), run.id, int(episode["episode_number"]))]
    if len(matches) > 1:
        raise ValueError(f"duplicate {label} rows for series run episode")
    if matches:
        _validate_tag(getattr(matches[0], metadata_name), run, episode, label)
        return matches[0]
    return None


async def _canonical_workflow(db: AsyncSession, run, episode: dict[str, Any]) -> Workflow:
    workflow_id = (episode.get("canonical_ids") or {}).get("workflow_id")
    workflow = await db.scalar(select(Workflow).where(
        Workflow.id == workflow_id, Workflow.user_id == run.user_id, Workflow.novel_id == run.novel_id
    ))
    if workflow is None:
        raise ValueError("canonical workflow is missing or belongs to another owner")
    _validate_tag(workflow.metadata_, run, episode, "workflow")
    return workflow


async def _canonical_script(db: AsyncSession, run, episode: dict[str, Any]) -> Script:
    script_id = (episode.get("canonical_ids") or {}).get("script_id")
    script = await db.scalar(select(Script).where(
        Script.id == script_id, Script.user_id == run.user_id, Script.novel_id == run.novel_id
    ))
    if script is None:
        raise ValueError("canonical script is missing or belongs to another owner")
    _validate_tag(script.extra_data, run, episode, "script")
    return script


async def create_script_record(
    db: AsyncSession, *, user_id: str, novel_id: str | None, chapter_id: str | None,
    title: str, content: str | None, description: str | None = None,
    genre: str | None = None, style: str | None = None, duration: int | None = None,
    extra_data: dict[str, Any] | None = None,
) -> Script:
    """Shared script persistence primitive. Transaction ownership stays with caller."""
    script = Script(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
        title=title, description=description, content=content, genre=genre, style=style,
        duration=duration, status="draft", extra_data=extra_data or {},
    )
    db.add(script)
    await db.flush()
    return script


async def _source(db: AsyncSession, user_id: str, novel_id: str, chapter_ids: list[str]) -> tuple[list[Chapter], str]:
    chapters = (await db.scalars(select(Chapter).where(
        Chapter.id.in_(chapter_ids), Chapter.user_id == user_id, Chapter.novel_id == novel_id
    ).order_by(Chapter.chapter_number))).all()
    if len(chapters) != len(chapter_ids):
        raise ValueError("episode contains invalid chapters")
    text = "\n\n".join(chapter.content or "" for chapter in chapters).strip()
    if not text:
        raise ValueError("episode has no verified chapter content")
    return list(chapters), text


async def create_or_resolve_workflow_stage(db: AsyncSession, *, run, episode: dict[str, Any]) -> dict[str, Any]:
    number = int(episode["episode_number"])
    chapters, _ = await _source(db, run.user_id, run.novel_id, list(episode["chapter_ids"]))
    rows = (await db.scalars(select(Workflow).where(Workflow.user_id == run.user_id, Workflow.novel_id == run.novel_id))).all()
    workflow = _resolve_single(list(rows), "metadata_", run, episode, "workflow")
    if workflow is None:
        workflow = Workflow(
            id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
            chapter_id=chapters[0].id, title=f"第 {number} 集生产工程",
            status="pending", metadata_={"series_run_id": run.id, "episode_number": number, "input_hash": episode["input_hash"]},
        )
        db.add(workflow)
        await db.flush()
    return {"workflow_id": workflow.id}


async def create_or_resolve_script_stage(db: AsyncSession, *, run, episode: dict[str, Any]) -> dict[str, Any]:
    number = int(episode["episode_number"])
    chapters, text = await _source(db, run.user_id, run.novel_id, list(episode["chapter_ids"]))
    workflow = await _canonical_workflow(db, run, episode)
    rows = (await db.scalars(select(Script).where(Script.user_id == run.user_id, Script.novel_id == run.novel_id))).all()
    script = _resolve_single(list(rows), "extra_data", run, episode, "script")
    if script is None:
        dialogue_lines = [
            {**line, "chapter_id": chapter.id}
            for chapter in chapters
            for line in extract_explicit_dialogue(str(chapter.content or ""))
        ]
        script = await create_script_record(
            db, user_id=run.user_id, novel_id=run.novel_id, chapter_id=chapters[0].id,
            title=f"第 {number} 集剧本草稿", content=text,
            extra_data={"series_run_id": run.id, "episode_number": number, "input_hash": episode["input_hash"],
                        "dialogue_lines": dialogue_lines},
        )
    if workflow.script_id is not None and workflow.script_id != script.id:
        raise ValueError("workflow script link conflict")
    workflow.script_id = script.id
    await db.flush()
    return {"script_id": script.id}


async def create_or_resolve_storyboard_stage(db: AsyncSession, *, run, episode: dict[str, Any]) -> dict[str, Any]:
    number = int(episode["episode_number"])
    canonical = episode.get("canonical_ids") or {}
    workflow = await _canonical_workflow(db, run, episode)
    script = await _canonical_script(db, run, episode)
    rows = (await db.scalars(select(Storyboard).where(Storyboard.user_id == run.user_id, Storyboard.novel_id == run.novel_id))).all()
    storyboard = _resolve_single(list(rows), "content", run, episode, "storyboard")
    if storyboard is not None and storyboard.script_id != script.id:
        raise ValueError("storyboard script lineage mismatch")
    if storyboard is None:
        storyboard = Storyboard(
            id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
            script_id=canonical["script_id"], title=f"第 {number} 集分镜草稿",
            content={"series_run_id": run.id, "episode_number": number, "input_hash": episode["input_hash"]},
            shot_count=0, status="draft",
        )
        db.add(storyboard)
        await db.flush()
    if workflow.storyboard_id is not None and workflow.storyboard_id != storyboard.id:
        raise ValueError("workflow storyboard link conflict")
    workflow.storyboard_id = storyboard.id
    await db.flush()
    return {"storyboard_id": storyboard.id}


async def create_or_resolve_shots_stage(db: AsyncSession, *, run, episode: dict[str, Any]) -> dict[str, Any]:
    from app.services.episode_shot_stage import create_or_resolve_shots_stage as owner
    return await owner(db, run=run, episode=episode)
