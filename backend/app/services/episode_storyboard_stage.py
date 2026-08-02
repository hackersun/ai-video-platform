"""Scene-aware storyboard stage for series-production episodes."""

from __future__ import annotations

import copy
import re
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.series_skill_execution.public import bind_series_stage_skill, execute_skill_model_or_fallback
from app.features.series_skill_execution.stage_contracts import validate_storyboard
from app.models import Storyboard
from app.services.chapter_scene_planner import ChapterScenePlan, plan_chapter_scenes


def _tag_matches(board: Storyboard, run: Any, episode: dict[str, Any]) -> bool:
    content = board.content if isinstance(board.content, dict) else {}
    return (
        content.get("series_run_id") == run.id
        and content.get("episode_number") == int(episode["episode_number"])
    )


def _is_scene_board(board: Storyboard, script: Any) -> bool:
    content = board.content if isinstance(board.content, dict) else {}
    return (
        content.get("chapter_id") == script.chapter_id
        and int(content.get("scene_index") or 0) > 0
        and bool(str(content.get("source_text") or "").strip())
        and int(content.get("planned_shot_count") or 0) > 0
        and isinstance(content.get("continuity"), dict)
    )


def _shot_source_slices(source_text: str, count: int) -> list[str]:
    text = str(source_text or "").strip()
    pattern = r".*?[。！？!?](?:[”’\"']?)(?=.|$)|.+$"
    sentences = [item.strip() for item in re.findall(pattern, text, re.S) if item.strip()]
    if len(sentences) >= count:
        return [
            "".join(sentences[round(index * len(sentences) / count):round((index + 1) * len(sentences) / count)])
            for index in range(count)
        ]
    if count <= 1 or len(text) <= 1:
        return [text] * count
    boundaries = [round(index * len(text) / count) for index in range(count + 1)]
    return [text[boundaries[index]:boundaries[index + 1]].strip() or text for index in range(count)]


def _fallback_shots(scene: ChapterScenePlan) -> list[dict[str, Any]]:
    source_slices = _shot_source_slices(scene.source_text, scene.shot_count)
    return [
        {
            "shot_number": index,
            "visual_description": source_slices[index - 1],
            "prompt": (
                f"{scene.title}，镜头{index}：{source_slices[index - 1]}"
                "保持人物服装、场景空间和道具状态连续"
            ),
            "dialogue": None,
        }
        for index in range(1, scene.shot_count + 1)
    ]


def _normalize_shots(value: Any, scene: ChapterScenePlan) -> list[dict[str, Any]]:
    generated = value.get("shots") if isinstance(value, dict) else None
    shots = [dict(item) for item in (generated or []) if isinstance(item, dict)]
    fallbacks = _fallback_shots(scene)
    for index in range(len(shots), scene.shot_count):
        shots.append(fallbacks[index])
    return [{**fallbacks[index], **shot, "shot_number": index + 1}
            for index, shot in enumerate(shots[:scene.shot_count])]


async def _create_board(
    db: AsyncSession, *, run: Any, episode: dict[str, Any], script: Any, scene: ChapterScenePlan,
) -> Storyboard:
    number, storyboard_id = int(episode["episode_number"]), str(uuid4())
    binding = await bind_series_stage_skill(
        db, user_id=run.user_id, task="storyboard_generation", stage="content",
        context={
            "title": scene.title,
            "source_content": scene.source_text,
            "episode_number": number,
            "scene_index": scene.scene_index,
            "shot_count": scene.shot_count,
            "continuity": scene.continuity,
        },
        internal_prompt=scene.source_text,
        artifact_type="storyboard",
        artifact_id=storyboard_id,
    )
    fallback = {"shots": _fallback_shots(scene)}
    result = await execute_skill_model_or_fallback(
        db, user_id=run.user_id,
        rendered_prompt=(binding.rendered_prompt +
                         f"\n仅输出 JSON，格式为 {{\"shots\":[...]}}，必须包含 {scene.shot_count} 个连续镜头。"),
        output_contract="json_object",
        validator=lambda value: validate_storyboard(value),
        fallback=lambda: fallback,
        series_id=run.novel_id,
    )
    prompt_evidence = {
        **binding.evidence,
        "model_execution": result.evidence,
        "execution_mode": result.evidence["execution_mode"],
    }
    board = Storyboard(
        id=storyboard_id,
        user_id=run.user_id,
        novel_id=run.novel_id,
        script_id=script.id,
        title=f"第 {number} 集 · {scene.title}",
        content={
            "series_run_id": run.id,
            "episode_number": number,
            "input_hash": episode["input_hash"],
            "chapter_id": script.chapter_id,
            "scene_index": scene.scene_index,
            "scene_count": None,
            "source_text": scene.source_text,
            "planned_shot_count": scene.shot_count,
            "continuity": scene.continuity,
            "shots": _normalize_shots(result.value, scene),
            "prompt_skill": prompt_evidence,
        },
        shot_count=0,
        status="draft",
    )
    db.add(board)
    await db.flush()
    return board


def _record_evidence(run: Any, episode_number: int, boards: list[Storyboard]) -> None:
    metadata = copy.deepcopy(run.run_metadata or {})
    evidence = dict(metadata.get("skill_evidence") or {})
    stage = dict(evidence.get("storyboard_generation") or {})
    items = {
        str(board.id): dict((board.content or {}).get("prompt_skill") or {}) for board in boards
    }
    stage[str(episode_number)] = next(iter(items.values())) if len(items) == 1 else items
    evidence["storyboard_generation"] = stage
    metadata["skill_evidence"] = evidence
    run.run_metadata = metadata


async def create_or_resolve_episode_storyboards(
    db: AsyncSession, *, run: Any, episode: dict[str, Any], workflow: Any, script: Any, source_text: str,
) -> dict[str, Any]:
    rows = list((await db.scalars(select(Storyboard).where(
        Storyboard.user_id == run.user_id,
        Storyboard.novel_id == run.novel_id,
    ))).all())
    tagged_boards = [board for board in rows if _tag_matches(board, run, episode)]
    if any(board.script_id != script.id for board in tagged_boards):
        raise ValueError("storyboard script lineage mismatch")
    if any((board.content or {}).get("input_hash") != episode.get("input_hash") for board in tagged_boards):
        raise ValueError("storyboard input_hash mismatch")
    boards = [board for board in tagged_boards if _is_scene_board(board, script)]
    legacy_ids = {board.id for board in tagged_boards if board not in boards}
    if not boards:
        scenes = plan_chapter_scenes(source_text, chapter_title=script.title)
        boards = [
            await _create_board(db, run=run, episode=episode, script=script, scene=scene)
            for scene in scenes
        ]
        for board in boards:
            board.content = {**(board.content or {}), "scene_count": len(boards)}
    boards.sort(key=lambda board: int((board.content or {}).get("scene_index") or 1))
    if not boards:
        raise ValueError("episode has no storyboard scene plan")
    if (
        workflow.storyboard_id is not None
        and workflow.storyboard_id != boards[0].id
        and workflow.storyboard_id not in legacy_ids
    ):
        raise ValueError("workflow storyboard link conflict")
    workflow.storyboard_id = boards[0].id
    _record_evidence(run, int(episode["episode_number"]), boards)
    await db.flush()
    return {"storyboard_id": boards[0].id, "storyboard_ids": [board.id for board in boards]}


__all__ = ["create_or_resolve_episode_storyboards"]
