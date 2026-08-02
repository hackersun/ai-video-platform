"""Infer and validate video generation lineage."""

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.video_generation.errors import VideoGenerationError
from app.features.video_generation.schemas import VideoGenerateRequest
from app.models import Chapter, Novel, Script, Shot, Storyboard, Workflow
from app.services.workflow_shot_scope import workflow_owns_storyboard


@dataclass
class _LineageState:
    values: dict[str, Optional[str]]
    objects: dict[str, Any] = field(default_factory=dict)


def _match(current: Optional[str], incoming: Optional[str], detail: str) -> Optional[str]:
    if current and incoming and current != incoming:
        raise VideoGenerationError(422, detail)
    return current or incoming


async def _owned(db: AsyncSession, model, object_id: str, user_id: str, missing: str):
    value = await db.scalar(select(model).where(model.id == object_id, model.user_id == user_id))
    if value is None:
        raise VideoGenerationError(404, missing)
    return value


async def _workflow_stage(
    db: AsyncSession, state: _LineageState, user_id: str,
) -> None:
    workflow_id = state.values.get("workflow_id")
    if not workflow_id:
        return
    workflow = await _owned(db, Workflow, workflow_id, user_id, "工作流不存在")
    state.objects["workflow"] = workflow
    for key, detail in (
        ("novel_id", "workflow_id 与 novel_id 不匹配"),
        ("chapter_id", "workflow_id 与 chapter_id 不匹配"),
        ("script_id", "workflow_id 与 script_id 不匹配"),
    ):
        state.values[key] = _match(state.values.get(key), getattr(workflow, key), detail)
    requested_storyboard_id = state.values.get("storyboard_id")
    if requested_storyboard_id:
        if not await workflow_owns_storyboard(
            db, workflow=workflow, user_id=user_id, storyboard_id=requested_storyboard_id,
        ):
            raise VideoGenerationError(422, "workflow_id 与 storyboard_id 不匹配")
    else:
        state.values["storyboard_id"] = workflow.storyboard_id


async def _shot_storyboard_stage(
    db: AsyncSession, state: _LineageState, user_id: str,
) -> None:
    shot_id = state.values.get("shot_id")
    if shot_id:
        shot = await _owned(db, Shot, shot_id, user_id, "镜头不存在")
        state.objects["shot"] = shot
        state.values["storyboard_id"] = _match(
            state.values.get("storyboard_id"), shot.storyboard_id, "shot_id 与 storyboard_id 不匹配",
        )
    storyboard_id = state.values.get("storyboard_id")
    if not storyboard_id:
        return
    storyboard = await _owned(db, Storyboard, storyboard_id, user_id, "分镜不存在")
    state.objects["storyboard"] = storyboard
    state.values["script_id"] = _match(
        state.values.get("script_id"), storyboard.script_id, "storyboard_id 与 script_id 不匹配",
    )
    state.values["novel_id"] = _match(
        state.values.get("novel_id"), storyboard.novel_id, "storyboard_id 与 novel_id 不匹配",
    )
    content = storyboard.content if isinstance(storyboard.content, dict) else {}
    state.values["chapter_id"] = _match(
        state.values.get("chapter_id"), content.get("chapter_id"), "storyboard_id 与 chapter_id 不匹配",
    )


async def _script_chapter_novel_stage(
    db: AsyncSession, state: _LineageState, user_id: str,
) -> None:
    script_id = state.values.get("script_id")
    if script_id:
        script = await _owned(db, Script, script_id, user_id, "剧本不存在")
        state.objects["script"] = script
        state.values["novel_id"] = _match(
            state.values.get("novel_id"), script.novel_id, "script_id 与 novel_id 不匹配",
        )
        extra = script.extra_data if isinstance(script.extra_data, dict) else {}
        state.values["chapter_id"] = _match(
            state.values.get("chapter_id"), extra.get("chapter_id"), "script_id 与 chapter_id 不匹配",
        )
    chapter_id = state.values.get("chapter_id")
    if chapter_id:
        chapter = await _owned(db, Chapter, chapter_id, user_id, "章节不存在")
        state.objects["chapter"] = chapter
        state.values["novel_id"] = _match(
            state.values.get("novel_id"), chapter.novel_id, "chapter_id 与 novel_id 不匹配",
        )
    novel_id = state.values.get("novel_id")
    if novel_id:
        state.objects["novel"] = await _owned(db, Novel, novel_id, user_id, "小说不存在")


def _result(state: _LineageState) -> dict[str, Any]:
    objects = state.objects
    workflow = objects.get("workflow")
    if workflow:
        for key in ("novel_id", "chapter_id", "script_id", "storyboard_id"):
            if not getattr(workflow, key):
                setattr(workflow, key, state.values.get(key))
    novel, chapter = objects.get("novel"), objects.get("chapter")
    script, storyboard, shot = objects.get("script"), objects.get("storyboard"), objects.get("shot")
    return {
        **state.values,
        "novel_title": novel.title if novel else None,
        "chapter_title": chapter.title if chapter else None,
        "chapter_number": chapter.chapter_number if chapter else None,
        "script_title": script.title if script else None,
        "storyboard_title": storyboard.title if storyboard else None,
        "shot_number": shot.shot_number if shot else None,
        "shot": shot, "storyboard": storyboard, "script": script,
    }


async def resolve_video_lineage(
    db: AsyncSession, user_id: str, request: VideoGenerateRequest,
) -> dict[str, Any]:
    keys = ("project_id", "workflow_id", "novel_id", "chapter_id", "script_id", "storyboard_id", "shot_id")
    state = _LineageState({key: getattr(request, key) for key in keys})
    await _workflow_stage(db, state, user_id)
    await _shot_storyboard_stage(db, state, user_id)
    await _script_chapter_novel_stage(db, state, user_id)
    return _result(state)
