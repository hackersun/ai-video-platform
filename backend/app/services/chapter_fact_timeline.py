"""Chapter-bounded projections for production-visible story facts."""

from __future__ import annotations

from copy import copy
from typing import Any, Iterable

from app.services.story_entity_lifecycle import is_entity_production_visible


def _attributes(entity: Any) -> dict[str, Any]:
    value = getattr(entity, "attributes", None)
    return value if isinstance(value, dict) else {}


def project_entities_as_of_chapter(
    entities: Iterable[Any],
    chapters: Iterable[Any],
    *,
    chapter_number: int,
    strict: bool = False,
) -> list[Any]:
    """Return approved/legacy facts first evidenced by the requested chapter."""
    chapter_numbers = {
        str(chapter.id): int(chapter.chapter_number)
        for chapter in chapters
        if getattr(chapter, "id", None) is not None and getattr(chapter, "chapter_number", None) is not None
    }
    projected = []
    for entity in entities:
        if not is_entity_production_visible(entity):
            continue
        source_id = getattr(entity, "first_seen_chapter_id", None) or getattr(entity, "chapter_id", None)
        source_index = chapter_numbers.get(str(source_id)) if source_id else None
        if source_index is None:
            raw_index = _attributes(entity).get("source_chapter_number")
            if raw_index is None:
                raw_index = _attributes(entity).get("source_chapter_index")
            try:
                source_index = int(raw_index) if raw_index is not None else None
            except (TypeError, ValueError):
                source_index = None
        if source_index is None:
            if strict and not bool(_attributes(entity).get("is_global_fact")):
                continue
        elif source_index > chapter_number:
            continue
        attrs = dict(_attributes(entity))
        identity_provenance = attrs.get("identity_fact_provenance") or {}
        filtered = copy(entity)
        for key, source_ids in identity_provenance.items():
            source_numbers = [chapter_numbers.get(str(source_id)) for source_id in (source_ids or [])]
            if source_numbers and all(number is None or number > chapter_number for number in source_numbers):
                attrs.pop(key, None)
        filtered.attributes = attrs
        filtered.relations = [item for item in (getattr(entity, "relations", None) or []) if (
            chapter_numbers.get(str(item.get("chapter_id"))) is None
            or chapter_numbers.get(str(item.get("chapter_id"))) <= chapter_number
        )] if all(isinstance(item, dict) for item in (getattr(entity, "relations", None) or [])) else list(getattr(entity, "relations", None) or [])
        filtered.state_changes = [item for item in (getattr(entity, "state_changes", None) or []) if (
            chapter_numbers.get(str(item.get("chapter_id"))) is None
            or chapter_numbers.get(str(item.get("chapter_id"))) <= chapter_number
        )] if all(isinstance(item, dict) for item in (getattr(entity, "state_changes", None) or [])) else list(getattr(entity, "state_changes", None) or [])
        tag_provenance = attrs.get("tag_fact_provenance") or {}
        filtered.tags = [tag for tag in (getattr(entity, "tags", None) or []) if any(
            chapter_numbers.get(str(source_id)) is None or chapter_numbers.get(str(source_id)) <= chapter_number
            for source_id in (tag_provenance.get(tag) or [])
        )] if tag_provenance else list(getattr(entity, "tags", None) or [])
        projected.append(filtered)
    return projected


def project_entity_fact(entity: Any, *, include_foreshadowing: bool = False) -> dict[str, Any]:
    """Serialize present-tense state without leaking future intent by default."""
    attrs = _attributes(entity)
    extra = getattr(entity, "extra_data", None)
    extra = extra if isinstance(extra, dict) else {}
    result = {
        "entity_id": getattr(entity, "id", None),
        "entity_type": getattr(entity, "entity_type", None),
        "canonical_name": getattr(entity, "canonical_name", None) or getattr(entity, "name", None),
        "current_state": attrs.get("current_state") or {},
        "known_to_characters": attrs.get("known_to_characters") or [],
        "introduced_at": attrs.get("introduced_at"),
        "resolved_at": attrs.get("resolved_at"),
    }
    if include_foreshadowing:
        future_intent = attrs.get("future_intent", extra.get("future_intent"))
        foreshadowing = attrs.get("foreshadowing", extra.get("foreshadowing"))
        if future_intent is not None:
            result["future_intent"] = future_intent
        if foreshadowing is not None:
            result["foreshadowing"] = foreshadowing
    return result
