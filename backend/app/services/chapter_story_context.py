"""Persist chapter-extracted entities and synchronize existing Story Bibles."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Novel, StoryBible, StoryEntity, StoryEntityMention
from app.services.entity_evidence_mentions import build_story_entity_mention
from app.services.entity_extraction_service import build_story_bible_sections
from app.services.entity_quality_service import AUTO_APPROVE, score_entity_candidate
from app.services.story_entity_lifecycle import is_entity_production_visible, set_entity_review_status


def _merge_rules(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(existing or [])
    names = {item.get("name") or item.get("title") for item in merged if isinstance(item, dict)}
    for item in incoming:
        key = item.get("name") or item.get("title")
        if key and key not in names:
            merged.append(item)
            names.add(key)
    return merged


def _upsert_entity(
    db: AsyncSession, existing: StoryEntity | None, *,
    user_id: str, novel: Novel, chapter: Chapter, item: dict[str, Any],
) -> StoryEntity:
    if existing:
        incoming_attributes = item.get("attributes") or {}
        existing.description = item.get("description")
        existing.aliases = list(dict.fromkeys([*(existing.aliases or []), *(item.get("aliases") or [])]))
        existing.attributes = {**incoming_attributes, **(existing.attributes or {})}
        if incoming_attributes.get("evidence_contract"):
            existing.attributes["evidence_contract"] = incoming_attributes["evidence_contract"]
        existing.evidence = item.get("evidence")
        existing.confidence = item.get("confidence") or 100
        existing.source = item.get("source") or "deterministic"
        existing.first_seen_chapter_id = existing.first_seen_chapter_id or chapter.id
        return existing
    entity = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel.id, chapter_id=chapter.id,
        entity_type=item["entity_type"], name=item["name"],
        description=item.get("description"), aliases=item.get("aliases") or [],
        attributes=item.get("attributes") or {}, evidence=item.get("evidence"),
        confidence=item.get("confidence") or 100,
        source=item.get("source") or "deterministic", first_seen_chapter_id=chapter.id,
    )
    db.add(entity)
    decision = "needs_review"
    auto_approved = False
    explicit_label = str(item.get("description") or "").startswith("文本标注")
    if explicit_label and item["entity_type"] in {"character", "scene", "prop"}:
        try:
            quality = score_entity_candidate(item)
            decision = quality.auto_decision
            auto_approved = decision == AUTO_APPROVE
        except ValueError:
            decision = "invalid_candidate"
    set_entity_review_status(
        entity, "approved" if auto_approved else "candidate",
        changed_by=user_id, reason=f"chapter_rule_extraction:{decision}",
    )
    return entity


async def _ensure_evidence_mention(
    db: AsyncSession, *, user_id: str, novel: Novel, chapter: Chapter,
    entity: StoryEntity, item: dict[str, Any],
) -> None:
    evidence = str(item.get("evidence") or "")[:1000] or None
    existing = await db.scalar(select(StoryEntityMention.id).where(
        StoryEntityMention.user_id == user_id,
        StoryEntityMention.entity_id == entity.id,
        StoryEntityMention.source_type == "chapter",
        StoryEntityMention.source_id == chapter.id,
        StoryEntityMention.evidence == evidence,
    ).limit(1))
    if existing is not None:
        return
    db.add(build_story_entity_mention(
        user_id=user_id, run_id=None, entity_id=entity.id,
        novel_id=novel.id, chapter_id=chapter.id, script_id=None,
        source_type="chapter", source_id=chapter.id,
        text=chapter.content or "", item=item,
    ))


async def _sync_story_bibles(
    db: AsyncSession, *, user_id: str, novel: Novel, chapter: Chapter,
    entities: list[dict[str, Any]],
) -> int:
    story_bibles = list((await db.scalars(select(StoryBible).where(
        StoryBible.novel_id == novel.id, StoryBible.user_id == user_id,
    ).order_by(desc(StoryBible.updated_at)))).all())
    sections = build_story_bible_sections(entities)
    for story_bible in story_bibles:
        story_bible.character_rules = _merge_rules(story_bible.character_rules or [], sections["character_rules"])
        story_bible.scene_rules = _merge_rules(story_bible.scene_rules or [], sections["scene_rules"])
        story_bible.prop_rules = _merge_rules(story_bible.prop_rules or [], sections["prop_rules"])
        story_bible.event_timeline = _merge_rules(story_bible.event_timeline or [], sections["event_timeline"])
        story_bible.extra_data = {
            **(story_bible.extra_data or {}), "last_synced_chapter_id": chapter.id,
            "last_sync_entity_count": len(entities),
        }
    return len(story_bibles)


async def persist_chapter_story_context(
    db: AsyncSession,
    user_id: str,
    novel: Novel,
    chapter: Chapter,
    *,
    extractor: Callable[..., list[dict[str, Any]]],
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Persist extracted entities and merge them into existing Story Bibles."""
    try:
        extracted = extractor(
            chapter.content or "", {"character", "scene", "prop", "event"},
            source_chapter_id=chapter.id, source_chapter_index=chapter.chapter_number,
        )
    except ValueError:
        extracted = []

    existing_result = await db.execute(select(StoryEntity).where(and_(
        StoryEntity.user_id == user_id,
        StoryEntity.novel_id == novel.id,
        StoryEntity.chapter_id == chapter.id,
    )))
    existing_entities = {
        (entity.entity_type, entity.name): entity for entity in existing_result.scalars().all()
    }

    entity_dicts: list[dict[str, Any]] = []
    production_entity_dicts: list[dict[str, Any]] = []
    for item in extracted:
        key = (item["entity_type"], item["name"])
        entity = _upsert_entity(
            db, existing_entities.get(key), user_id=user_id,
            novel=novel, chapter=chapter, item=item,
        )
        await _ensure_evidence_mention(
            db, user_id=user_id, novel=novel, chapter=chapter, entity=entity, item=item,
        )
        payload = {
            "id": entity.id, "entity_type": entity.entity_type, "name": entity.name,
            "description": entity.description, "evidence": entity.evidence,
        }
        entity_dicts.append(payload)
        if is_entity_production_visible(entity):
            production_entity_dicts.append(payload)

    story_bible_count = await _sync_story_bibles(
        db, user_id=user_id, novel=novel, chapter=chapter, entities=production_entity_dicts,
    )
    result = {"entity_count": len(entity_dicts), "story_bible_count": story_bible_count}
    if metadata is not None:
        metadata.update(result)
    return result
