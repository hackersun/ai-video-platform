"""Shared low-level persistence operations for episode production entry points."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.chapter import Chapter
from app.models.script import Script
from app.models.workflow import Workflow
from app.services.dialogue_lineage_service import extract_explicit_dialogue
from app.services.entity_review_service import run_candidate_entity_extraction
from app.features.series_skill_execution.public import (
    bind_series_stage_skill,
    execute_skill_model_or_fallback,
)
from app.features.series_skill_execution.stage_contracts import validate_script


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
    extra_data: dict[str, Any] | None = None, record_id: str | None = None,
) -> Script:
    """Shared script persistence primitive. Transaction ownership stays with caller."""
    script = Script(
        id=record_id or str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
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
    dialogue_lines = [
        {**line, "chapter_id": chapter.id}
        for chapter in chapters
        for line in extract_explicit_dialogue(str(chapter.content or ""))
    ]
    if script is None:
        entity_runs = []
        for chapter in chapters:
            extraction = await run_candidate_entity_extraction(
                db,
                user_id=run.user_id,
                text=str(chapter.content or ""),
                source_type="chapter",
                source_id=chapter.id,
                novel_id=run.novel_id,
                chapter_id=chapter.id,
                entity_types=["character", "scene", "prop", "event"],
                persist=True,
                commit=False,
                allow_auto_approve=True,
            )
            entity_runs.append({
                "chapter_id": chapter.id,
                "run_id": extraction["run_id"],
                "stats": extraction["stats"],
                "prompt_skill": dict(extraction["prompt_routing"]),
            })
        script_id = str(uuid4())
        skill_binding = await bind_series_stage_skill(
            db, user_id=run.user_id, task="script_generation", stage="content",
            context={"title": f"第 {number} 集剧本草稿", "content": text,
                     "chapter_ids": [chapter.id for chapter in chapters],
                     "episode_number": number},
            internal_prompt=text, artifact_type="script", artifact_id=script_id,
        )
        required_dialogues = [str(line.get("spoken_text") or "") for line in dialogue_lines]
        deterministic_script = {"content": text, "scenes": [], "dialogue_lines": dialogue_lines}
        model_result = await execute_skill_model_or_fallback(
            db, user_id=run.user_id,
            rendered_prompt=skill_binding.rendered_prompt + "\n仅输出 JSON 对象，包含 content、scenes、dialogue_lines。",
            output_contract="json_object",
            validator=lambda value: validate_script(value, required_dialogues=required_dialogues),
            fallback=lambda: deterministic_script, series_id=run.novel_id,
        )
        generated = model_result.value
        generated_content = str(generated.get("content") or "").strip() or json.dumps(
            generated, ensure_ascii=False,
        )
        prompt_evidence = {**skill_binding.evidence, "model_execution": model_result.evidence,
                           "execution_mode": model_result.evidence["execution_mode"]}
        script = await create_script_record(
            db, user_id=run.user_id, novel_id=run.novel_id, chapter_id=chapters[0].id,
            title=f"第 {number} 集剧本草稿", content=generated_content,
            extra_data={"series_run_id": run.id, "episode_number": number, "input_hash": episode["input_hash"],
                        "dialogue_lines": dialogue_lines,
                        "entity_extraction_runs": entity_runs,
                        "generated_structure": generated,
                        "prompt_skill": prompt_evidence}, record_id=script_id,
        )
    elif dialogue_lines and not list((script.extra_data or {}).get("dialogue_lines") or []):
        generated = dict((script.extra_data or {}).get("generated_structure") or {})
        generated["dialogue_lines"] = dialogue_lines
        script.extra_data = {
            **(script.extra_data or {}),
            "dialogue_lines": dialogue_lines,
            "generated_structure": generated,
        }
        flag_modified(script, "extra_data")
    if workflow.script_id is not None and workflow.script_id != script.id:
        raise ValueError("workflow script link conflict")
    workflow.script_id = script.id
    prompt_skill = dict((script.extra_data or {}).get("prompt_skill") or {})
    if prompt_skill:
        metadata = dict(run.run_metadata or {})
        skill_evidence = dict(metadata.get("skill_evidence") or {})
        script_evidence = dict(skill_evidence.get("script_generation") or {})
        script_evidence[str(number)] = prompt_skill
        skill_evidence["script_generation"] = script_evidence
        entity_runs = list((script.extra_data or {}).get("entity_extraction_runs") or [])
        if entity_runs:
            previous_entity = dict(skill_evidence.get("entity_extraction") or {})
            previous_runs = list(previous_entity.get("runs") or [])
            runs_by_chapter = {
                str(item.get("chapter_id")): item
                for item in [*previous_runs, *entity_runs]
                if item.get("chapter_id")
            }
            skill_evidence["entity_extraction"] = {
                **previous_entity,
                **dict(entity_runs[0].get("prompt_skill") or {}),
                "runs": list(runs_by_chapter.values()),
            }
        metadata["skill_evidence"] = skill_evidence
        run.run_metadata = metadata
    await db.flush()
    return {"script_id": script.id}


async def create_or_resolve_storyboard_stage(db: AsyncSession, *, run, episode: dict[str, Any]) -> dict[str, Any]:
    from app.services.episode_storyboard_stage import create_or_resolve_episode_storyboards

    workflow = await _canonical_workflow(db, run, episode)
    script = await _canonical_script(db, run, episode)
    _, source_text = await _source(db, run.user_id, run.novel_id, list(episode["chapter_ids"]))
    return await create_or_resolve_episode_storyboards(
        db, run=run, episode=episode, workflow=workflow, script=script, source_text=source_text,
    )


async def create_or_resolve_shots_stage(db: AsyncSession, *, run, episode: dict[str, Any]) -> dict[str, Any]:
    from app.services.episode_shot_stage import create_or_resolve_shots_stage as owner
    return await owner(db, run=run, episode=episode)
