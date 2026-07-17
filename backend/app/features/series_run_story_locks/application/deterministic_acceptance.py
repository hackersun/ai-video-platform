"""Non-secret deterministic Story Lock fixture contracts."""

from __future__ import annotations

import hashlib
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoryEntity
from app.services.dialogue_lineage_service import extract_explicit_dialogue
from app.services.story_entity_lifecycle import ARCHIVED, set_entity_review_status

from ..domain.scoped_reference import canonical_identity_sha256, sign_merge_edge


def deterministic_evidence_contract(chapter: object) -> dict[str, object]:
    content = str(getattr(chapter, "content", None) or "")
    return {
        "status": "verified", "chapter_id": str(getattr(chapter, "id")),
        "source_span": [0, 1], "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "source_excerpt": content[:1], "parser_version": "deterministic-extraction-v2",
    }


def deterministic_anchor_entity_refs(
    entities: dict[str, object], episode_number: int,
) -> dict[str, list[dict[str, str]]]:
    event = {2: "道具被发现", 3: "道具发生变化", 4: "主角完成最终事件"}.get(episode_number)
    ref = lambda name: {"entity_id": str(getattr(entities[name], "id"))}
    return {
        "characters": [ref("主角")], "scenes": [ref("连续场景")],
        "props": ([ref("连续性道具")] if episode_number >= 2 else []),
        "events": ([ref(event)] if event else []),
    }


def apply_deterministic_voice_binding(
    entity: object, tts_snapshot: dict[str, str], selection: dict[str, object],
) -> None:
    if not selection.get("voice_id") or selection.get("provider_id") != tts_snapshot.get("provider_id"):
        return
    attributes = dict(getattr(entity, "attributes", None) or {})
    attributes["voice_binding"] = {
        "voice_id": selection["voice_id"], "version": int(selection.get("version") or 1), "status": "locked",
        "provider_id": tts_snapshot["provider_id"], "config_id": tts_snapshot["config_id"],
        "db_model_id": tts_snapshot["db_model_id"], "api_model_id": tts_snapshot["api_model_id"],
        "tested_at": tts_snapshot["tested_at"],
    }
    entity.attributes = attributes


async def seed_deterministic_local_mentions(
    db: AsyncSession, *, user_id: str, novel_id: str, episodes: list[dict[str, object]],
    chapters_by_id: dict[str, object], fixture_entities: dict[str, object],
) -> None:
    """Seed signed chapter-local sources for deterministic cross-chapter refs."""
    rows = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id,
    ))).all())
    speakers = [line["speaker"] for chapter in chapters_by_id.values()
                for line in extract_explicit_dialogue(str(getattr(chapter, "content", "") or ""))]
    character_alias = str(speakers[0]) if speakers else ""
    protagonist = fixture_entities.get("主角")
    if protagonist is not None and character_alias:
        protagonist.canonical_name = character_alias
        protagonist.aliases = list(dict.fromkeys([*(protagonist.aliases or []), character_alias]))
        identity = canonical_identity_sha256(entity_type="character", canonical_name=character_alias)
        for row in rows:
            if row.id == protagonist.id or (row.attributes or {}).get("merged_into_entity_id") != protagonist.id:
                continue
            edge = sign_merge_edge({"source_entity_id": row.id, "canonical_entity_id": protagonist.id,
                "user_id": user_id, "novel_id": novel_id, "entity_type": "character",
                "canonical_identity_sha256": identity})
            row.extra_data = {**(row.extra_data or {}), "merge_edges": [edge]}
    for episode in episodes:
        chapter_id = str((episode.get("chapter_ids") or [""])[0])
        number = int(episode.get("episode_number") or 0)
        refs = deterministic_anchor_entity_refs(fixture_entities, number)
        for values in refs.values():
            for ref in values:
                canonical = next(item for item in fixture_entities.values()
                                 if str(getattr(item, "id", "")) == ref["entity_id"])
                if str(getattr(canonical, "chapter_id", "")) == chapter_id:
                    continue
                canonical_name = character_alias if canonical.entity_type == "character" and character_alias else canonical.name
                existing = [item for item in rows if item.chapter_id == chapter_id
                            and item.entity_type == canonical.entity_type
                            and str(item.canonical_name or item.name or "") == str(canonical_name)]
                if len(existing) > 1:
                    raise ValueError("deterministic chapter-local source is ambiguous")
                mention = existing[0] if existing else StoryEntity(
                    id=str(uuid4()), user_id=user_id, novel_id=novel_id,
                    chapter_id=chapter_id, first_seen_chapter_id=chapter_id,
                    entity_type=canonical.entity_type,
                    name=f"{canonical_name}·第{number}章提及", canonical_name=canonical_name,
                    source="deterministic", version=1, attributes={}, extra_data={},
                )
                identity = canonical_identity_sha256(
                    entity_type=mention.entity_type, canonical_name=str(mention.canonical_name or mention.name or ""),
                )
                edge = sign_merge_edge({"source_entity_id": mention.id,
                    "canonical_entity_id": canonical.id, "user_id": user_id,
                    "novel_id": novel_id, "entity_type": mention.entity_type,
                    "canonical_identity_sha256": identity})
                mention.attributes = {**(mention.attributes or {}),
                    "evidence_contract": deterministic_evidence_contract(chapters_by_id[chapter_id]),
                    "merged_into_entity_id": canonical.id}
                mention.extra_data = {**(mention.extra_data or {}), "merge_edges": [edge],
                    "normalized_merge": {"status": "merged_superseded", "canonical_entity_id": canonical.id}}
                set_entity_review_status(mention, ARCHIVED, changed_by=user_id,
                                         reason="deterministic_chapter_local_mention")
                if not existing:
                    db.add(mention)
                    rows.append(mention)
