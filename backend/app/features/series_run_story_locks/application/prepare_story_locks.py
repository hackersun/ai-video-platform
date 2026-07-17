"""Thin use-case orchestration for required-anchor Story Locks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from ..domain import StoryLockSourceStale, build_closure, validate_reference_scope, validate_required_facts
from ..repositories import StoryLockRepository


class RunInput(Protocol):
    episodes: list[dict[str, Any]]


@dataclass(frozen=True)
class RequiredStoryContext:
    selected_shots: list[object]
    chapters: list[object]
    entities: list[object]
    required_entities: list[object]
    closure: object


def referenced_entity_ids(selected_shots: list[object]) -> dict[str, list[str]]:
    references = {kind: [] for kind in ("character", "scene", "prop", "event")}
    keys = {"characters": "character", "scenes": "scene", "props": "prop", "events": "event"}
    for shot in selected_shots:
        entity_refs = (getattr(shot, "extra_data", None) or {}).get("entity_refs") or {}
        for plural, kind in keys.items():
            for reference in entity_refs.get(plural) or []:
                if not isinstance(reference, dict):
                    raise StoryLockSourceStale("selected_typed_ref_malformed")
                entity_id = str(reference.get("entity_id") or "").strip()
                if not entity_id:
                    raise StoryLockSourceStale("selected_typed_ref_malformed")
                references[kind].append(entity_id)
    return references


def scoped_references(selected_shots: list[object]) -> list[tuple[str, str, str]]:
    scoped: list[tuple[str, str, str]] = []
    keys = {"characters": "character", "scenes": "scene", "props": "prop", "events": "event"}
    for shot in selected_shots:
        extra = getattr(shot, "extra_data", None) or {}
        chapter_id = str(extra.get("chapter_id") or "")
        if not chapter_id:
            raise StoryLockSourceStale("selected_shot_chapter_missing")
        for plural, kind in keys.items():
            for reference in (extra.get("entity_refs") or {}).get(plural) or []:
                if not isinstance(reference, dict):
                    raise StoryLockSourceStale("selected_typed_ref_malformed")
                entity_id = str(
                    reference.get("source_entity_id")
                    if reference.get("contract_version") == "chapter_evidence_ref_v1"
                    else reference.get("entity_id") or ""
                ).strip()
                if not entity_id:
                    raise StoryLockSourceStale("selected_typed_ref_malformed")
                scoped.append((kind, entity_id, chapter_id))
    return scoped


def chapter_ranks(run: RunInput) -> dict[str, int]:
    chapter_ids = [
        str(chapter_id)
        for episode in sorted(run.episodes or [], key=lambda item: int(item.get("episode_number") or 0))
        for chapter_id in (episode.get("chapter_ids") or [])
    ]
    if not chapter_ids or len(chapter_ids) != len(set(chapter_ids)):
        raise StoryLockSourceStale("episode_chapter_shape_invalid")
    return {chapter_id: rank for rank, chapter_id in enumerate(chapter_ids)}


async def load_required_context(repository: StoryLockRepository, run: Any) -> RequiredStoryContext:
    selected_shots = await repository.selected_shots(run)
    chapters = await repository.owned_chapters(run)
    entities = await repository.candidate_entities(run)
    chapter_hashes = {chapter.id: hashlib.sha256(str(chapter.content or "").encode()).hexdigest() for chapter in chapters}
    chapter_lengths = {chapter.id: len(str(chapter.content or "")) for chapter in chapters}
    facts = repository.facts(entities, chapter_hashes, chapter_lengths)
    references = referenced_entity_ids(selected_shots)
    if not any(references.values()):
        raise StoryLockSourceStale("selected_typed_refs_missing")
    closure = build_closure(references, facts)
    validate_reference_scope(scoped_references(selected_shots), facts, chapter_ranks(run))
    validate_required_facts(closure, facts)
    required_ids = set(closure.required_entity_ids)
    required = [entity for entity in entities if entity.id in required_ids]
    return RequiredStoryContext(selected_shots, chapters, entities, required, closure)
