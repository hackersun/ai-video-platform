"""Strict chapter-owned entity references for series-production shots."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoryEntity


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
    grouped: dict[tuple[str, str], list[StoryEntity]] = defaultdict(list)
    for entity in rows:
        identity = _canonical_identity(entity)
        if entity.entity_type in REF_KEYS and identity:
            grouped[(entity.entity_type, identity)].append(entity)
    for (entity_type, identity), entities in sorted(grouped.items()):
        if len(entities) != 1:
            continue
        entity = entities[0]
        if _exact_identity_match(source_text, identity) and _exact_identity_match(shot_text, identity):
            refs[REF_KEYS[entity_type]].append(_ref(entity))
    context = "；".join(
        f"{key}:{','.join(str(item['name']) for item in values)}"
        for key, values in refs.items() if values
    )
    return {"entity_refs": refs, "environment_context": context or None}
