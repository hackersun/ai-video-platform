"""Shot-stage owner for episode production and complete scoped references."""

from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Shot, Storyboard
from app.services.episode_shot_plan import dialogue_lines_by_storyboard, dialogue_source_evidence, planned_shots
from app.services.entity_ref_normalizer import normalize_entity_refs
from app.services.entity_review_service import reconcile_chapter_entity_evidence
from app.services.owned_shot_entity_refs import resolve_owned_shot_entity_context
from app.features.series_run_story_locks.application.production_scoped_inputs import (
    ProductionScopedRefCommand, build_production_scoped_refs,
)
from app.features.series_skill_execution.public import (
    bind_series_stage_skill,
    execute_skill_model_or_fallback,
)
from app.features.series_skill_execution.stage_contracts import validate_shot


@dataclass(frozen=True)
class ShotStageContext:
    db: AsyncSession
    run: Any
    episode: dict[str, Any]
    workflow: Any
    script: Any
    storyboard: Storyboard
    source_text: str


def _command(
    context: ShotStageContext, shot: Shot, entity_refs: dict[str, Any],
) -> ProductionScopedRefCommand:
    episode, run = context.episode, context.run
    chapter_id = str((shot.extra_data or {}).get("chapter_id") or episode["chapter_ids"][0])
    if chapter_id not in {str(value) for value in episode["chapter_ids"]}:
        raise ValueError("shot chapter is outside the production episode")
    shot_text = " ".join(value for value in (shot.prompt, shot.dialogue, shot.visual_description) if value)
    return ProductionScopedRefCommand(
        run_id=run.id, user_id=run.user_id, novel_id=run.novel_id,
        workflow_id=context.workflow.id, storyboard_id=context.storyboard.id, shot_id=shot.id,
        episode_number=int(episode["episode_number"]), episode_input_hash=episode["input_hash"],
        chapter_ids=tuple(episode["chapter_ids"]), chapter_id=chapter_id,
        script_id=context.script.id, prompt=shot.prompt or "", dialogue=shot.dialogue or "",
        visual_description=shot.visual_description or "", source_text=context.source_text,
        shot_text=shot_text, entity_refs=entity_refs,
    )


async def _new_shot(
    context: ShotStageContext,
    *,
    shot_number: int,
    episode_shot_number: int,
    shot_plan: dict[str, Any],
    dialogue_index: int | None = None,
    dialogue_line: dict[str, Any] | None = None,
) -> Shot:
    db, run, episode, script = context.db, context.run, context.episode, context.script
    number, shot_id = int(episode["episode_number"]), str(uuid4())
    dialogue_lines = list((script.extra_data or {}).get("dialogue_lines") or [])
    dialogue = dialogue_line
    if dialogue is None and dialogue_index is not None and dialogue_index < len(dialogue_lines):
        dialogue = dialogue_lines[dialogue_index]
    chapter_id = str((dialogue or {}).get("chapter_id") or episode["chapter_ids"][0])
    if chapter_id not in {str(value) for value in episode["chapter_ids"]}:
        raise ValueError("dialogue chapter is outside the production episode")
    board_content = context.storyboard.content if isinstance(context.storyboard.content, dict) else {}
    shot_extra = {
        "series_run_id": run.id, "episode_number": number,
        "input_hash": episode["input_hash"], "chapter_id": chapter_id,
        "scene_index": board_content.get("scene_index"),
        "scene_count": board_content.get("scene_count"),
        "scene_title": context.storyboard.title,
        "episode_shot_number": episode_shot_number,
        "scene_continuity": board_content.get("continuity"),
    }
    if dialogue:
        shot_extra.update({"dialogue_speaker": dialogue["speaker"], "parsed_speaker": dialogue["speaker"],
            "dialogue_spoken_text": dialogue["spoken_text"], "dialogue_source": dialogue_source_evidence(
                script.id, dialogue, board_content.get("scene_index"))})
    dialogue_text = dialogue["dialogue"] if dialogue else None
    shot_text = " ".join(value for value in (context.source_text[:1000], dialogue_text) if value)
    entity_context = await resolve_owned_shot_entity_context(
        db, user_id=run.user_id, novel_id=run.novel_id,
        chapter_ids=list(episode["chapter_ids"]), as_of_chapter_id=chapter_id,
        source_text=context.source_text, shot_text=shot_text)
    skill_binding = await bind_series_stage_skill(
        db, user_id=run.user_id, task="shot_prompt", stage="generation",
        context={"source_content": context.source_text[:1000], "dialogue": dialogue_text or "",
                 "episode_number": number, "scene_index": board_content.get("scene_index"),
                 "shot_number": shot_number, "aspect_ratio": "9:16"},
        internal_prompt=str(shot_plan.get("prompt") or context.source_text[:1000]),
        artifact_type="shot", artifact_id=shot_id,
    )
    required_dialogue = dialogue_text
    fallback_shot = {
        "prompt": skill_binding.rendered_prompt,
        "visual_description": str(shot_plan.get("visual_description") or context.source_text[:1000]),
        "dialogue": required_dialogue,
    }
    model_result = await execute_skill_model_or_fallback(
        db, user_id=run.user_id,
        rendered_prompt=skill_binding.rendered_prompt + (
            "\n仅输出 JSON 对象，包含 prompt、visual_description、dialogue；dialogue 必须逐字保持输入对白。"
        ),
        output_contract="json_object",
        validator=lambda value: validate_shot(value, required_dialogue=required_dialogue),
        fallback=lambda: fallback_shot, series_id=run.novel_id,
    )
    generated = model_result.value
    shot_extra["prompt_skill"] = {
        **skill_binding.evidence, "model_execution": model_result.evidence,
        "execution_mode": model_result.evidence["execution_mode"],
    }
    shot = Shot(id=shot_id, user_id=run.user_id, storyboard_id=context.storyboard.id,
        shot_number=shot_number, duration=4, prompt=generated["prompt"],
        visual_description=generated["visual_description"], dialogue=generated["dialogue"],
        character_refs=[], extra_data={**shot_extra, **entity_context})
    if any(entity_context["entity_refs"].values()):
        scoped = await build_production_scoped_refs(
            db, _command(context, shot, entity_context["entity_refs"]),
        )
        shot.extra_data = {**shot.extra_data, "entity_refs": scoped.entity_refs}
    shot.character_refs = shot.extra_data["entity_refs"]["characters"] or (
        [{"name": dialogue["speaker"]}] if dialogue else [])
    db.add(shot)
    await db.flush()
    return shot


async def _refresh_existing(
    context: ShotStageContext, shot: Shot, *, episode_shot_number: int,
    dialogue_line: dict[str, Any] | None = None,
) -> None:
    episode = context.episode
    original = copy.deepcopy(shot.extra_data or {})
    board_content = context.storyboard.content if isinstance(context.storyboard.content, dict) else {}
    detached = {
        **original, "chapter_id": original.get("chapter_id") or episode["chapter_ids"][0],
        "scene_index": board_content.get("scene_index"), "scene_count": board_content.get("scene_count"),
        "scene_title": context.storyboard.title, "episode_shot_number": episode_shot_number,
    }
    proposed_dialogue = shot.dialogue
    if dialogue_line:
        proposed_dialogue = str(dialogue_line.get("dialogue") or "").strip() or None
        detached.update({
            "dialogue_speaker": dialogue_line["speaker"], "parsed_speaker": dialogue_line["speaker"],
            "dialogue_spoken_text": dialogue_line["spoken_text"], "dialogue_source": dialogue_source_evidence(
                context.script.id, dialogue_line, board_content.get("scene_index")),
        })
    existing = normalize_entity_refs(detached.get("entity_refs"))
    if any(existing.values()):
        with context.db.no_autoflush:
            scoped = await build_production_scoped_refs(
                context.db, _command(context, shot, existing),
            )
        if scoped.owned_by_evidence_ref_id:
            detached = {**detached, "entity_refs": scoped.entity_refs}
            shot.character_refs = scoped.entity_refs["characters"] or shot.character_refs
        shot.dialogue, shot.extra_data = proposed_dialogue, detached
        flag_modified(shot, "extra_data")
        return
    shot_text = " ".join(value for value in (shot.prompt, proposed_dialogue, shot.visual_description) if value)
    with context.db.no_autoflush:
        discovered = await resolve_owned_shot_entity_context(
            context.db, user_id=context.run.user_id, novel_id=context.run.novel_id,
            chapter_ids=list(episode["chapter_ids"]), as_of_chapter_id=str(detached["chapter_id"]),
            source_text=context.source_text, shot_text=shot_text)
    if any(discovered["entity_refs"].values()):
        candidate = {**detached, **discovered}
        with context.db.no_autoflush:
            scoped = await build_production_scoped_refs(
                context.db, _command(context, shot, candidate["entity_refs"]),
            )
        shot.extra_data = {**candidate, "entity_refs": scoped.entity_refs}
        shot.character_refs = scoped.entity_refs["characters"] or shot.character_refs
        flag_modified(shot, "extra_data")
        shot.dialogue = proposed_dialogue
        return
    shot.dialogue, shot.extra_data = proposed_dialogue, detached
    if detached != original:
        flag_modified(shot, "extra_data")


async def _episode_storyboards(
    db: AsyncSession, run: Any, episode: dict[str, Any], script: Any,
) -> list[Storyboard]:
    canonical = episode.get("canonical_ids") or {}
    board_ids = list(canonical.get("storyboard_ids") or [])
    if not board_ids and canonical.get("storyboard_id"):
        board_ids = [canonical["storyboard_id"]]
    boards = list((await db.scalars(select(Storyboard).where(
        Storyboard.id.in_(board_ids), Storyboard.user_id == run.user_id,
        Storyboard.novel_id == run.novel_id, Storyboard.script_id == script.id,
    ))).all()) if board_ids else []
    by_id = {board.id: board for board in boards}
    ordered = [by_id[board_id] for board_id in board_ids if board_id in by_id]
    if len(ordered) != len(board_ids):
        raise ValueError("canonical storyboard workflow lineage is invalid")
    return ordered


def _record_prompt_evidence(run: Any, number: int, shots: list[Shot]) -> None:
    items = {
        shot.id: dict((shot.extra_data or {}).get("prompt_skill") or {})
        for shot in shots if (shot.extra_data or {}).get("prompt_skill")
    }
    if not items:
        return
    metadata = copy.deepcopy(run.run_metadata or {})
    skill_evidence = dict(metadata.get("skill_evidence") or {})
    episode_evidence = dict((skill_evidence.get("shot_prompt") or {}).get(str(number)) or {})
    episode_evidence.update(items)
    skill_evidence["shot_prompt"] = {
        **dict(skill_evidence.get("shot_prompt") or {}), str(number): episode_evidence,
    }
    metadata["skill_evidence"] = skill_evidence
    run.run_metadata = metadata
    flag_modified(run, "run_metadata")


async def _resolve_board_shots(
    context: ShotStageContext, *, episode_shot_offset: int, dialogue_lines: list[dict[str, Any]],
) -> list[Shot]:
    db, run, episode, board = context.db, context.run, context.episode, context.storyboard
    plans = planned_shots(board)
    rows = list((await db.scalars(select(Shot).where(
        Shot.user_id == run.user_id, Shot.storyboard_id == board.id,
    ).order_by(Shot.shot_number, Shot.id))).all())
    tagged = [row for row in rows if (
        (row.extra_data or {}).get("series_run_id") == run.id
        and (row.extra_data or {}).get("episode_number") == int(episode["episode_number"])
    )]
    by_number = {int(row.shot_number): row for row in tagged}
    if len(by_number) != len(tagged):
        raise ValueError("duplicate shot numbers for series run storyboard")
    resolved: list[Shot] = []
    for index, plan in enumerate(plans, start=1):
        shot = by_number.get(index)
        if shot is None:
            dialogue_line = dialogue_lines[index - 1] if index <= len(dialogue_lines) else None
            shot = await _new_shot(
                context, shot_number=index, episode_shot_number=episode_shot_offset + index, shot_plan=plan,
                dialogue_line=dialogue_line,
            )
        else:
            from app.services.episode_production_service import _validate_tag
            _validate_tag(shot.extra_data, run, episode, "shot")
            await _refresh_existing(
                context, shot, episode_shot_number=episode_shot_offset + index,
                dialogue_line=dialogue_lines[index - 1] if index <= len(dialogue_lines) else None,
            )
        resolved.append(shot)
    board.shot_count = len(resolved)
    return resolved


async def create_or_resolve_shots_stage(db: AsyncSession, *, run: Any, episode: dict[str, Any]) -> dict[str, Any]:
    from app.services.episode_production_service import _canonical_script, _canonical_workflow, _source, _validate_tag
    number = int(episode["episode_number"])
    chapters, source_text = await _source(db, run.user_id, run.novel_id, list(episode["chapter_ids"]))
    for chapter in chapters:
        await reconcile_chapter_entity_evidence(
            db, user_id=run.user_id, novel_id=run.novel_id,
            chapter_id=chapter.id, entity_types=("character", "scene", "prop", "event"),
            content=str(chapter.content or ""),
        )
    workflow, script = await _canonical_workflow(db, run, episode), await _canonical_script(db, run, episode)
    storyboards = await _episode_storyboards(db, run, episode, script)
    if not storyboards or workflow.script_id != script.id or workflow.storyboard_id != storyboards[0].id:
        raise ValueError("canonical storyboard workflow lineage is invalid")
    resolved: list[Shot] = []
    episode_shot_offset = 0
    dialogue_map = dialogue_lines_by_storyboard(
        list((script.extra_data or {}).get("dialogue_lines") or []), storyboards,
    )
    for storyboard in storyboards:
        _validate_tag(storyboard.content, run, episode, "storyboard")
        content = storyboard.content if isinstance(storyboard.content, dict) else {}
        context = ShotStageContext(
            db, run, episode, workflow, script, storyboard,
            str(content.get("source_text") or source_text),
        )
        board_shots = await _resolve_board_shots(
            context, episode_shot_offset=episode_shot_offset,
            dialogue_lines=dialogue_map.get(str(storyboard.id), []),
        )
        resolved.extend(board_shots)
        episode_shot_offset += len(board_shots)
    _record_prompt_evidence(run, number, resolved)
    await db.flush()
    return {"shot_ids": [shot.id for shot in resolved]}
