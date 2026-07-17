"""Build complete scoped references from locked production owner rows."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, StoryEntity, Storyboard, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.entity_ref_normalizer import ENTITY_REF_KEYS, normalize_entity_refs
from app.services.story_entity_lifecycle import ARCHIVED, get_entity_review_status

from ..domain.errors import ProductionRequiredEntityBlocked
from ..domain.scoped_reference import (
    build_scoped_reference, canonical_identity_sha256, resolve_scoped_reference,
    sign_history_record, sign_merge_edge,
)


@dataclass(frozen=True)
class ProductionScopedRefCommand:
    run_id: str
    user_id: str
    novel_id: str
    workflow_id: str
    storyboard_id: str
    shot_id: str
    episode_number: int
    episode_input_hash: str
    chapter_ids: tuple[str, ...]
    chapter_id: str
    script_id: str
    prompt: str
    dialogue: str
    visual_description: str
    source_text: str
    shot_text: str
    entity_refs: Mapping[str, Any]


@dataclass(frozen=True)
class ProductionScopedRefs:
    entity_refs: dict[str, list[dict[str, Any]]]
    owned_by_evidence_ref_id: dict[str, dict[str, Any]]


def _entity_row(entity: StoryEntity) -> dict[str, Any]:
    return {
        "id": entity.id, "user_id": entity.user_id, "novel_id": entity.novel_id,
        "chapter_id": entity.chapter_id, "entity_type": entity.entity_type,
        "name": entity.name, "canonical_name": entity.canonical_name,
        "evidence_contract": dict((entity.attributes or {}).get("evidence_contract") or {}),
    }


def _is_signed_merged_competitor(candidate: StoryEntity, canonical_id: str) -> bool:
    normalized = (candidate.extra_data or {}).get("normalized_merge") or {}
    edges = (candidate.extra_data or {}).get("merge_edges") or []
    if (get_entity_review_status(candidate) != ARCHIVED
            or normalized.get("status") != "merged_superseded"
            or normalized.get("canonical_entity_id") != canonical_id
            or (candidate.attributes or {}).get("merged_into_entity_id") != canonical_id
            or len(edges) != 1):
        return False
    edge = edges[0]
    unsigned = {key: value for key, value in edge.items()
                if key not in {"merge_audit_version", "merge_audit_sha256"}}
    return edge.get("source_entity_id") == candidate.id \
        and edge.get("canonical_entity_id") == canonical_id \
        and edge.get("user_id") == candidate.user_id \
        and edge.get("novel_id") == candidate.novel_id \
        and edge.get("entity_type") == candidate.entity_type \
        and sign_merge_edge(unsigned) == edge


def _raise_if_required_evidence_ambiguous(
    entity: StoryEntity, entities: list[StoryEntity], edges: list[dict[str, Any]],
) -> None:
    target = entity
    matching = [edge for edge in edges if edge.get("source_entity_id") == entity.id]
    if len(matching) == 1:
        candidate = next((item for item in entities if item.id == matching[0].get("canonical_entity_id")), None)
        if candidate is not None and _is_signed_merged_competitor(entity, candidate.id):
            target = candidate
    evidence = dict((target.attributes or {}).get("evidence_contract") or {})
    values = tuple(evidence.get("conflicting_values") or ())
    if evidence.get("status") != "ambiguous" and not values:
        return
    category = "identity_state" if target.entity_type == "character" else f"{target.entity_type}_state"
    raise ProductionRequiredEntityBlocked(
        code="required_entity_evidence_ambiguous", blocker_category=category,
        field="state", values=values, required_counts={},
    )


def _chapter_row(chapter: Chapter) -> dict[str, Any]:
    content = str(chapter.content or "")
    return {"id": chapter.id, "chapter_number": chapter.chapter_number, "content": content,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(), "content_length": len(content)}


def _episode(run: SeriesProductionRun, command: ProductionScopedRefCommand) -> dict[str, Any]:
    matches = [item for item in (run.episodes or [])
               if int(item.get("episode_number") or 0) == command.episode_number]
    if len(matches) != 1:
        raise ValueError("production episode missing or ambiguous")
    episode = matches[0]
    canonical = episode.get("canonical_ids") or {}
    if (tuple(str(value) for value in episode.get("chapter_ids") or []) != command.chapter_ids
            or canonical.get("workflow_id") not in {None, command.workflow_id}
            or canonical.get("storyboard_id") not in {None, command.storyboard_id}):
        raise ValueError("production episode owner chain is stale")
    return episode


async def _authority(
    db: AsyncSession, command: ProductionScopedRefCommand,
) -> tuple[SeriesProductionRun, Chapter, list[StoryEntity]]:
    run = await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.id == command.run_id, SeriesProductionRun.user_id == command.user_id,
        SeriesProductionRun.novel_id == command.novel_id,
    ).with_for_update())
    if run is None:
        raise ValueError("production run missing or cross-owner")
    _episode(run, command)
    workflow = await db.scalar(select(Workflow).where(
        Workflow.id == command.workflow_id, Workflow.user_id == command.user_id,
        Workflow.novel_id == command.novel_id, Workflow.chapter_id == command.chapter_id,
        Workflow.script_id == command.script_id, Workflow.storyboard_id == command.storyboard_id,
    ).with_for_update())
    board = await db.scalar(select(Storyboard).where(
        Storyboard.id == command.storyboard_id, Storyboard.user_id == command.user_id,
        Storyboard.novel_id == command.novel_id, Storyboard.script_id == command.script_id,
    ).with_for_update())
    chapter = await db.scalar(select(Chapter).where(
        Chapter.id == command.chapter_id, Chapter.id.in_(command.chapter_ids),
        Chapter.user_id == command.user_id, Chapter.novel_id == command.novel_id,
    ).with_for_update())
    if workflow is None or board is None or chapter is None:
        raise ValueError("workflow storyboard chapter owner chain is invalid")
    tag = workflow.metadata_ or {}
    if (tag.get("series_run_id") != command.run_id
            or int(tag.get("episode_number") or 0) != command.episode_number
            or tag.get("input_hash") != command.episode_input_hash):
        raise ValueError("workflow production tag is stale")
    entities = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == command.user_id, StoryEntity.novel_id == command.novel_id,
    ).with_for_update())).all())
    return run, chapter, entities


def _owned(
    command: ProductionScopedRefCommand, chapter: dict[str, Any], source: dict[str, Any],
    entities: list[StoryEntity], context: dict[str, Any], reference: dict[str, Any],
) -> dict[str, Any]:
    typed = [entity for entity in entities if entity.entity_type == source["entity_type"]]
    rows = [_entity_row(entity) for entity in typed]
    histories = [record for entity in typed
                 for record in ((entity.extra_data or {}).get("canonical_histories") or [])]
    edges = [record for entity in typed for record in ((entity.extra_data or {}).get("merge_edges") or [])]
    expected = (source["id"], command.chapter_id, reference["evidence_ref_id"])
    relevant = [record for record in histories if (
        record.get("source_entity_id"), record.get("chapter_id"), record.get("evidence_ref_id")) == expected]
    if len(relevant) > 1:
        raise ValueError("canonical history source chapter or evidence reference is ambiguous")
    return {"user_id": command.user_id, "novel_id": command.novel_id,
            "run_id": command.run_id, "shot_id": command.shot_id,
            "chapter_id": command.chapter_id, "entity_type": source["entity_type"],
            "current_context": context, "authoritative_chapters": {chapter["id"]: chapter},
            "source_rows": [source], "canonical_histories": histories,
            "merge_edges": edges, "canonical_subjects": rows}


def _ensure_merged_history(
    source: StoryEntity, entities: list[StoryEntity], reference: dict[str, Any],
    legacy: Mapping[str, Any], command: ProductionScopedRefCommand,
) -> None:
    edges = [edge for owner in entities for edge in ((owner.extra_data or {}).get("merge_edges") or [])
             if edge.get("source_entity_id") == source.id]
    if not edges:
        return
    if len(edges) != 1:
        raise ValueError("chapter-local source merge is ambiguous")
    canonical_id = str(edges[0].get("canonical_entity_id") or "")
    canonical = next((item for item in entities if item.id == canonical_id), None)
    if canonical is None:
        raise ValueError("canonical merge target is missing")
    histories = [record for owner in entities
                 for record in ((owner.extra_data or {}).get("canonical_histories") or [])
                 if (record.get("source_entity_id"), record.get("chapter_id"))
                 == (source.id, command.chapter_id)]
    matching = [record for record in histories
                if record.get("evidence_ref_id") == reference["evidence_ref_id"]]
    if matching:
        if len(matching) != 1:
            raise ValueError("canonical history evidence reference is ambiguous")
        return
    complete = legacy.get("contract_version") == "chapter_evidence_ref_v1"
    if complete and str(legacy.get("entity_id") or "") == canonical_id:
        previous = [record for record in histories
                    if record.get("evidence_ref_id") == legacy.get("evidence_ref_id")]
        trusted_previous = len(previous) == 1 and all((
            previous[0].get("owner_user_id") == command.user_id,
            previous[0].get("owner_novel_id") == command.novel_id,
            previous[0].get("owner_entity_type") == source.entity_type,
            previous[0].get("source_entity_id") == source.id,
            previous[0].get("canonical_entity_id") == canonical_id,
            sign_history_record(previous[0]) == previous[0],
        ))
        if not trusted_previous:
            raise ValueError("canonical history is missing for persisted merged reference")
    history = sign_history_record({"owner_user_id": command.user_id,
        "owner_novel_id": command.novel_id, "owner_entity_type": source.entity_type,
        "canonical_entity_id": canonical_id, "source_entity_id": source.id,
        "chapter_id": command.chapter_id, "evidence_ref_id": reference["evidence_ref_id"],
        "metadata": {"evidence_contract": dict(reference["evidence"])},
        "merge_audit": {"canonical_identity_sha256": reference["canonical_identity_sha256"]}})
    canonical.extra_data = {**(canonical.extra_data or {}), "canonical_histories": [
        *((canonical.extra_data or {}).get("canonical_histories") or []), history,
    ]}


async def build_production_scoped_refs(
    db: AsyncSession, command: ProductionScopedRefCommand,
) -> ProductionScopedRefs:
    """Resolve selected real entity refs and replace them with complete v1 contracts."""
    _run, chapter_model, entities = await _authority(db, command)
    chapter = _chapter_row(chapter_model)
    normalized = normalize_entity_refs(command.entity_refs)
    if not any(normalized.values()):
        raise ValueError("production shot has no recognized entity references")
    by_id = {entity.id: entity for entity in entities}
    all_edges = [edge for owner in entities
                 for edge in ((owner.extra_data or {}).get("merge_edges") or [])]
    context = {"run_id": command.run_id, "series_run_id": command.run_id,
        "shot_id": command.shot_id, "episode_number": command.episode_number,
        "episode_input_hash": command.episode_input_hash, "chapter_id": command.chapter_id,
        "chapter_ids": list(command.chapter_ids), "script_id": command.script_id,
        "storyboard_id": command.storyboard_id, "prompt": command.prompt,
        "dialogue": command.dialogue, "visual_description": command.visual_description,
        "source_text": command.source_text, "shot_text": command.shot_text}
    output = {key: [] for key in ENTITY_REF_KEYS}
    authority: dict[str, dict[str, Any]] = {}
    for bucket, expected_type in ENTITY_REF_KEYS.items():
        for legacy in normalized[bucket]:
            legacy_id = (legacy.get("source_entity_id")
                         if legacy.get("contract_version") == "chapter_evidence_ref_v1"
                         else legacy.get("entity_id"))
            entity = by_id.get(str(legacy_id or ""))
            if entity is None:
                if legacy.get("contract_version") == "chapter_evidence_ref_v1":
                    raise ValueError("chapter-local source is missing or unresolved")
                foreign = await db.get(StoryEntity, str(legacy.get("entity_id") or ""))
                if foreign is not None:
                    raise ValueError("referenced entity belongs to another owner or novel")
                output[bucket].append(dict(legacy))
                continue
            if entity.entity_type == expected_type and entity.chapter_id != command.chapter_id:
                local = [candidate for candidate in entities if candidate.entity_type == expected_type
                    and candidate.chapter_id == command.chapter_id
                    and any(edge.get("source_entity_id") == candidate.id
                            and edge.get("canonical_entity_id") == entity.id
                            for edge in all_edges)]
                if len(local) != 1:
                    raise ValueError("referenced canonical chapter-local source is missing or ambiguous")
                entity = local[0]
            if entity.entity_type != expected_type or entity.chapter_id != command.chapter_id:
                raise ValueError("referenced entity owner type or chapter mismatch")
            source = _entity_row(entity)
            identity_hash = canonical_identity_sha256(
                entity_type=entity.entity_type,
                canonical_name=str(entity.canonical_name or entity.name or ""),
            )
            competitors = [candidate for candidate in entities if candidate.id != entity.id
                and candidate.entity_type == entity.entity_type and candidate.chapter_id == entity.chapter_id
                and canonical_identity_sha256(entity_type=candidate.entity_type,
                    canonical_name=str(candidate.canonical_name or candidate.name or "")) == identity_hash
                and not _is_signed_merged_competitor(candidate, entity.id)
                and not _is_signed_merged_competitor(entity, candidate.id)]
            if competitors:
                raise ValueError("authoritative entity evidence is ambiguous")
            _raise_if_required_evidence_ambiguous(entity, entities, all_edges)
            reference = build_scoped_reference(context=context, source=source, chapter=chapter)
            reference = {**reference, "entity_id": entity.id, "chapter_id": command.chapter_id}
            _ensure_merged_history(entity, entities, reference, legacy, command)
            owned = _owned(command, chapter, source, entities, context, reference)
            resolved = resolve_scoped_reference(reference, owned)
            if (legacy.get("contract_version") == "chapter_evidence_ref_v1"
                    and (str(legacy.get("canonical_entity_id") or legacy.get("entity_id") or "")
                         != resolved.canonical_entity_id
                         or str(legacy.get("entity_id") or "") != resolved.canonical_entity_id)):
                raise ValueError("persisted canonical entity reference is stale or forged")
            reference = {**reference, "entity_id": resolved.canonical_entity_id,
                         "canonical_entity_id": resolved.canonical_entity_id}
            output[bucket].append(reference)
            authority[str(reference["evidence_ref_id"])] = owned
    return ProductionScopedRefs(output, authority)
