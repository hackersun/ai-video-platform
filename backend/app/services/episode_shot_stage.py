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
from app.services.entity_ref_normalizer import normalize_entity_refs
from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled
from app.services.owned_shot_entity_refs import resolve_owned_shot_entity_context
from app.features.series_run_story_locks.application.production_scoped_inputs import (
    ProductionScopedRefCommand, build_production_scoped_refs,
)


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


async def _new_shot(context: ShotStageContext) -> Shot:
    db, run, episode, script = context.db, context.run, context.episode, context.script
    number, shot_id = int(episode["episode_number"]), str(uuid4())
    dialogue_lines = list((script.extra_data or {}).get("dialogue_lines") or [])
    dialogue = dialogue_lines[0] if dialogue_lines else None
    chapter_id = str((dialogue or {}).get("chapter_id") or episode["chapter_ids"][0])
    if chapter_id not in {str(value) for value in episode["chapter_ids"]}:
        raise ValueError("dialogue chapter is outside the production episode")
    shot_extra = {"series_run_id": run.id, "episode_number": number,
                  "input_hash": episode["input_hash"], "chapter_id": chapter_id}
    if dialogue:
        shot_extra.update({"dialogue_speaker": dialogue["speaker"], "parsed_speaker": dialogue["speaker"],
            "dialogue_spoken_text": dialogue["spoken_text"], "dialogue_source": {
                "script_id": script.id, "source_span": dialogue.get("source_span")}})
    shot_text = " ".join(value for value in (context.source_text[:1000], dialogue["dialogue"] if dialogue else None) if value)
    entity_context = await resolve_owned_shot_entity_context(
        db, user_id=run.user_id, novel_id=run.novel_id,
        chapter_ids=list(episode["chapter_ids"]), as_of_chapter_id=chapter_id,
        source_text=context.source_text, shot_text=shot_text)
    shot = Shot(id=shot_id, user_id=run.user_id, storyboard_id=context.storyboard.id,
        shot_number=1, duration=4, prompt=context.source_text[:1000],
        visual_description=context.source_text[:1000], dialogue=dialogue["dialogue"] if dialogue else None,
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


async def _refresh_existing(context: ShotStageContext, shot: Shot) -> None:
    episode = context.episode
    original = copy.deepcopy(shot.extra_data or {})
    detached = {**original, "chapter_id": original.get("chapter_id") or episode["chapter_ids"][0]}
    existing = normalize_entity_refs(detached.get("entity_refs"))
    if any(existing.values()):
        with context.db.no_autoflush:
            scoped = await build_production_scoped_refs(
                context.db, _command(context, shot, existing),
            )
        if scoped.owned_by_evidence_ref_id and detached.get("entity_refs") != scoped.entity_refs:
            shot.extra_data = {**detached, "entity_refs": scoped.entity_refs}
            shot.character_refs = scoped.entity_refs["characters"] or shot.character_refs
            flag_modified(shot, "extra_data")
        return
    shot_text = " ".join(value for value in (shot.prompt, shot.dialogue, shot.visual_description) if value)
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


async def create_or_resolve_shots_stage(db: AsyncSession, *, run: Any, episode: dict[str, Any]) -> dict[str, Any]:
    from app.services.episode_production_service import _canonical_script, _canonical_workflow, _same_tag, _source, _validate_tag
    canonical, number = episode.get("canonical_ids") or {}, int(episode["episode_number"])
    _, source_text = await _source(db, run.user_id, run.novel_id, list(episode["chapter_ids"]))
    workflow, script = await _canonical_workflow(db, run, episode), await _canonical_script(db, run, episode)
    storyboard = await db.scalar(select(Storyboard).where(
        Storyboard.id == canonical.get("storyboard_id"), Storyboard.user_id == run.user_id,
        Storyboard.novel_id == run.novel_id, Storyboard.script_id == script.id))
    if storyboard is None or workflow.script_id != script.id or workflow.storyboard_id != storyboard.id:
        raise ValueError("canonical storyboard workflow lineage is invalid")
    _validate_tag(storyboard.content, run, episode, "storyboard")
    rows = list((await db.scalars(select(Shot).where(
        Shot.user_id == run.user_id, Shot.storyboard_id == storyboard.id))).all())
    tagged = [row for row in rows if _same_tag(row.extra_data, run.id, number)]
    if len(tagged) > 1:
        selected = set((run.run_metadata or {}).get("selected_anchor_shot_ids") or [])
        targets = [row for row in tagged if row.id in selected]
        if not deterministic_provider_fake_enabled() or not targets:
            raise ValueError("duplicate shot rows for series run episode")
        context = ShotStageContext(db,run,episode,workflow,script,storyboard,source_text)
        for row in targets:
            await _refresh_existing(context, row)
        await db.flush()
        return {"shot_ids": [row.id for row in targets], "created": False}
    context = ShotStageContext(db, run, episode, workflow, script, storyboard, source_text)
    shot = tagged[0] if tagged else await _new_shot(context)
    if tagged:
        _validate_tag(shot.extra_data, run, episode, "shot")
        await _refresh_existing(context, shot)
    storyboard.shot_count = len(rows) if tagged else len(rows) + 1
    await db.flush()
    return {"shot_ids": [shot.id]}
