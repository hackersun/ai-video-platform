"""Strict chapter-owned entity references for series-production shots."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoryEntity
from app.services.story_entity_lifecycle import is_entity_production_visible


REF_KEYS = {
    "character": "characters",
    "scene": "scenes",
    "prop": "props",
    "event": "events",
}


def _exact_identity_match(text: str, identity: str) -> bool:
    if not text or not identity:
        return False
    if identity.isascii():
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(identity)}(?![A-Za-z0-9_])", text) is not None
    return identity in text


def _canonical_identity(entity: StoryEntity) -> str:
    return str(entity.canonical_name or entity.name or "").strip()


def _ref(entity: StoryEntity) -> dict[str, Any]:
    return {
        "entity_id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "canonical_name": entity.canonical_name or entity.name,
        "chapter_id": entity.chapter_id,
        "first_seen_chapter_id": entity.first_seen_chapter_id,
        "aliases": entity.aliases or [],
        "description": entity.description,
        "confidence": entity.confidence or 0,
        "source": entity.source or "deterministic",
    }


def _preferred_chapter_source(entities: list[StoryEntity]) -> StoryEntity | None:
    if len(entities) == 1:
        return entities[0]
    entity_ids = {entity.id for entity in entities}
    merged = [entity for entity in entities if (
        ((entity.extra_data or {}).get("normalized_merge") or {}).get("status") == "merged_superseded"
        and str(((entity.extra_data or {}).get("normalized_merge") or {}).get("canonical_entity_id") or "")
        in entity_ids
    )]
    return merged[0] if len(merged) == 1 else None


async def resolve_owned_shot_entity_context(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    chapter_ids: list[str],
    as_of_chapter_id: str | None = None,
    source_text: str,
    shot_text: str,
) -> dict[str, Any]:
    """Resolve only unique identities owned by the episode's source chapters."""
    refs = {key: [] for key in REF_KEYS.values()}
    if not chapter_ids:
        return {"entity_refs": refs, "environment_context": None}
    rows = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == user_id,
        StoryEntity.novel_id == novel_id,
        StoryEntity.chapter_id.in_([as_of_chapter_id] if as_of_chapter_id else chapter_ids),
    ))).all())
    canonical_ids = {
        str(((entity.extra_data or {}).get("normalized_merge") or {}).get("canonical_entity_id") or "")
        for entity in rows
    } - {""}
    canonical_by_id = {
        entity.id: entity for entity in (await db.scalars(select(StoryEntity).where(
            StoryEntity.user_id == user_id,
            StoryEntity.novel_id == novel_id,
            StoryEntity.id.in_(canonical_ids),
        ))).all()
    } if canonical_ids else {}
    grouped: dict[tuple[str, str], list[StoryEntity]] = defaultdict(list)
    for entity in rows:
        normalized_merge = (entity.extra_data or {}).get("normalized_merge") or {}
        canonical = canonical_by_id.get(str(normalized_merge.get("canonical_entity_id") or ""))
        is_merged_source = (
            normalized_merge.get("status") == "merged_superseded"
            and canonical is not None
            and is_entity_production_visible(canonical)
        )
        if not is_entity_production_visible(entity) and not is_merged_source:
            continue
        identity = _canonical_identity(entity)
        if entity.entity_type in REF_KEYS and identity:
            grouped[(entity.entity_type, identity)].append(entity)
    for (entity_type, identity), entities in sorted(grouped.items()):
        entity = _preferred_chapter_source(entities)
        if entity is None:
            continue
        if _exact_identity_match(source_text, identity) and _exact_identity_match(shot_text, identity):
            refs[REF_KEYS[entity_type]].append(_ref(entity))
    context = "；".join(
        f"{key}:{','.join(str(item['name']) for item in values)}"
        for key, values in refs.items() if values
    )
    return {"entity_refs": refs, "environment_context": context or None}
