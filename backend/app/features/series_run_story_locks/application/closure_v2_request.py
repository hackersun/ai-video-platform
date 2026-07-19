"""Build closure-v2 requests only from persisted complete scoped references."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Novel, Shot, StoryEntity, Storyboard, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.story_entity_lifecycle import get_entity_review_status
from .visual_style import resolve_novel_visual_style

from ..domain.closure_v2 import edge
from ..domain.scoped_reference import canonical_json_sha256, resolve_scoped_reference
from .production_scoped_inputs import ProductionScopedRefCommand, build_production_scoped_refs


def _episode(run: SeriesProductionRun, shot_id: str) -> dict[str, Any]:
    matches = [item for item in (run.episodes or [])
               if shot_id in ((item.get("canonical_ids") or {}).get("shot_ids") or [])]
    if len(matches) != 1:
        raise ValueError("selected shot is outside or ambiguous in run episodes")
    return matches[0]


async def _scoped_for_shot(
    db: AsyncSession, run: SeriesProductionRun, shot: Shot, *, refresh: bool = False,
):
    if shot.user_id != run.user_id:
        raise ValueError("selected shot belongs to another owner")
    episode = _episode(run, shot.id)
    canonical = episode.get("canonical_ids") or {}
    workflow = await db.scalar(select(Workflow).where(
        Workflow.id == canonical.get("workflow_id"), Workflow.user_id == run.user_id,
        Workflow.novel_id == run.novel_id, Workflow.storyboard_id == shot.storyboard_id,
    ).with_for_update())
    board = await db.scalar(select(Storyboard).where(
        Storyboard.id == shot.storyboard_id, Storyboard.user_id == run.user_id,
        Storyboard.novel_id == run.novel_id,
    ).with_for_update())
    chapter_ids = tuple(str(value) for value in episode.get("chapter_ids") or [])
    chapter_id = str((shot.extra_data or {}).get("chapter_id") or "")
    chapters = list((await db.scalars(select(Chapter).where(
        Chapter.id.in_(chapter_ids), Chapter.user_id == run.user_id, Chapter.novel_id == run.novel_id,
    ).order_by(Chapter.chapter_number).with_for_update())).all())
    if workflow is None or board is None or not chapter_id or len(chapters) != len(chapter_ids):
        raise ValueError("selected shot owner chain is incomplete")
    source_text = "\n\n".join(str(chapter.content or "") for chapter in chapters)
    shot_text = " ".join(value for value in (shot.prompt, shot.dialogue, shot.visual_description) if value)
    command = ProductionScopedRefCommand(
        run_id=run.id,user_id=run.user_id,novel_id=run.novel_id,workflow_id=workflow.id,
        storyboard_id=board.id,shot_id=shot.id,episode_number=int(episode["episode_number"]),
        episode_input_hash=str(episode.get("input_hash") or ""),chapter_ids=chapter_ids,
        chapter_id=chapter_id,script_id=str(workflow.script_id or ""),prompt=shot.prompt or "",
        dialogue=shot.dialogue or "",visual_description=shot.visual_description or "",
        source_text=source_text,shot_text=shot_text,
        entity_refs=(shot.extra_data or {}).get("entity_refs") or {},
    )
    rebuilt = await build_production_scoped_refs(db, command)
    if rebuilt.entity_refs != (shot.extra_data or {}).get("entity_refs"):
        if not refresh:
            raise ValueError(f"persisted scoped references are stale forged or legacy for shot {shot.id}")
        shot.extra_data = {**(shot.extra_data or {}), "entity_refs": rebuilt.entity_refs}
    return rebuilt


async def refresh_scoped_for_shot(
    db: AsyncSession, run: SeriesProductionRun, shot: Shot,
):
    """Re-sign a selected shot after an explicit media retry changes its input text."""
    return await _scoped_for_shot(db, run, shot, refresh=True)


async def build_closure_v2_request(
    db: AsyncSession, run_id: str, *, expected_run_version: int | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    run = await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.id == run_id,
    ).with_for_update().execution_options(populate_existing=True))
    if run is None or (user_id is not None and run.user_id != user_id):
        raise ValueError("run owner boundary mismatch")
    if expected_run_version is not None and int(run.version) != int(expected_run_version):
        raise ValueError("run version drift")
    selected_ids = [str(value) for value in
                    ((run.run_metadata or {}).get("selected_anchor_shot_ids") or [])]
    episode_ids = {str(value) for episode in (run.episodes or [])
                   for value in ((episode.get("canonical_ids") or {}).get("shot_ids") or [])}
    if not selected_ids or len(selected_ids) != len(set(selected_ids)) or not set(selected_ids).issubset(episode_ids):
        raise ValueError("selected shots are missing duplicate or outside fresh run episodes")
    rows = list((await db.scalars(select(Shot).where(
        Shot.id.in_(selected_ids), Shot.user_id == run.user_id,
    ).with_for_update().execution_options(populate_existing=True))).all())
    by_id = {shot.id: shot for shot in rows}
    if set(by_id) != set(selected_ids):
        raise ValueError("selected shot missing or foreign owned")
    selected_shots = [by_id[shot_id] for shot_id in selected_ids]
    scoped_inputs, subjects, evidence_edges = [], {}, []
    for shot in selected_shots:
        scoped = await _scoped_for_shot(db, run, shot)
        for values in scoped.entity_refs.values():
            for reference in values:
                evidence_id = str(reference.get("evidence_ref_id") or "")
                owned = scoped.owned_by_evidence_ref_id.get(evidence_id)
                if owned is None:
                    raise ValueError("manual or unresolved reference is not v2 ready")
                resolved = resolve_scoped_reference(reference, owned)
                subject = {"entity_type": resolved.entity_type,
                    "canonical_entity_id": resolved.canonical_entity_id,
                    "canonical_identity_sha256": reference["canonical_identity_sha256"]}
                subjects[(resolved.entity_type, resolved.canonical_entity_id)] = subject
                scoped_inputs.append({"reference": reference, "owned": owned})
                evidence_edges.append(edge(reference, resolved.canonical_entity_id))
    candidates = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == run.user_id, StoryEntity.novel_id == run.novel_id,
    ).with_for_update())).all())
    candidate_counts = {kind: sum(entity.entity_type == kind for entity in candidates)
                        for kind in ("character", "scene", "prop", "event")}
    ordered_subjects = [subjects[key] for key in sorted(subjects)]
    required_ids = {item["canonical_entity_id"] for item in ordered_subjects}
    novel = await db.scalar(select(Novel).where(
        Novel.id == run.novel_id, Novel.user_id == run.user_id).with_for_update())
    if novel is None:
        raise ValueError("production novel missing or cross-owner")
    drift_factors = {"voice_selection": dict((run.run_metadata or {}).get("voice_selection") or {}),
        "visual_style": resolve_novel_visual_style(novel),
        "required_entity_versions": sorted((entity.id, int(entity.version or 0))
                                            for entity in candidates if entity.id in required_ids),
        "required_entity_lifecycle": sorted((entity.id, get_entity_review_status(entity))
                                             for entity in candidates if entity.id in required_ids)}
    source_hash = canonical_json_sha256({"run_id":run.id,"shots":[shot.id for shot in selected_shots],
                                         "scoped_inputs":scoped_inputs})
    closure_hash = canonical_json_sha256({"subjects":ordered_subjects,"edges":evidence_edges,
                                          "candidate_counts":candidate_counts})
    return {"closure_contract_version":"required_entity_closure_v2","source_hash":source_hash,
        "closure_hash":closure_hash,"snapshot_hash":canonical_json_sha256({
            "source_hash":source_hash,"closure_hash":closure_hash}),"subjects":ordered_subjects,
        "evidence_edges":evidence_edges,"scoped_inputs":scoped_inputs,
        "candidate_counts":candidate_counts,"drift_factors":drift_factors}
