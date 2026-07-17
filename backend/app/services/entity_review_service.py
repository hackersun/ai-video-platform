"""Review-oriented entity extraction services.

This module is the V2 entry point for safer extraction: it records extraction
runs, writes evidence mentions, and stores new results as review candidates
instead of silently pushing uncertain entities into production flows.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import Asset, EntityExtractionRun, EntityFeedback, StoryEntity, StoryEntityMention
from app.services.entity_extraction_schema import CanonicalEntityCandidate
from app.services.entity_extraction_service import (
    CHARACTER_RE,
    EVENT_RE,
    PROP_RE,
    SCENE_RE,
    ENTITY_TYPES,
    extract_story_entities_with_quality,
)
from app.services.entity_evidence_mentions import build_story_entity_mention as _build_mention
from app.services.entity_quality_service import AUTO_APPROVE, REJECT_NOISE, score_entity_candidate
from app.services.prompt_template_router import select_prompt_skill_for_model
from app.services.story_entity_lifecycle import (
    APPROVED,
    CANDIDATE,
    ARCHIVED,
    LEGACY_ACTIVE,
    REJECTED,
    get_entity_review_status,
    query_story_entities_for_review,
    set_entity_review_status,
)


LABEL_PATTERNS = {
    "character": CHARACTER_RE,
    "scene": SCENE_RE,
    "prop": PROP_RE,
    "event": EVENT_RE,
}


class EntityApprovalEvidenceError(ValueError):
    """Raised when an extracted entity lacks auditable source evidence."""


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _entity_key(entity_type: str, name: str) -> tuple[str, str]:
    return (entity_type, name.strip().lower())


def _explicit_label_candidates(text: str, requested_types: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entity_type, pattern in LABEL_PATTERNS.items():
        if entity_type not in requested_types:
            continue
        for match in pattern.finditer(text or ""):
            name = str(match.group(1) or "").strip(" ：:，。；;、\t\n")
            if not name:
                continue
            candidates.append(
                {
                    "entity_type": entity_type,
                    "name": name[:200],
                    "description": f"文本标注{entity_type}",
                    "aliases": [],
                    "attributes": {},
                    "evidence": match.group(0)[:500],
                    "confidence": 80,
                    "source": "deterministic_label",
                }
            )
    return candidates


def _quality_payload(item: dict[str, Any]) -> dict[str, Any]:
    if isinstance(item.get("quality"), dict):
        return dict(item["quality"])
    return score_entity_candidate(CanonicalEntityCandidate.model_validate(item)).model_dump()


def _candidate_items(text: str, requested_types: set[str], *, include_rejected: bool) -> list[dict[str, Any]]:
    items = [dict(item) for item in extract_story_entities_with_quality(text, requested_types)]
    seen = {_entity_key(item["entity_type"], item["name"]) for item in items}
    if include_rejected:
        for item in _explicit_label_candidates(text, requested_types):
            key = _entity_key(item["entity_type"], item["name"])
            if key in seen:
                continue
            quality = _quality_payload(item)
            if quality.get("auto_decision") != REJECT_NOISE:
                continue
            candidate = dict(item)
            candidate["quality"] = quality
            items.append(candidate)
            seen.add(key)
    return items


async def _load_existing_entities(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
    entity_types: Iterable[str],
) -> dict[tuple[str, str], StoryEntity]:
    query = select(StoryEntity).where(StoryEntity.user_id == user_id, StoryEntity.entity_type.in_(list(entity_types)))
    query = query.where(StoryEntity.novel_id == novel_id if novel_id else StoryEntity.novel_id.is_(None))
    query = query.where(StoryEntity.chapter_id == chapter_id if chapter_id else StoryEntity.chapter_id.is_(None))
    query = query.where(StoryEntity.script_id == script_id if script_id else StoryEntity.script_id.is_(None))
    result = await db.execute(query)
    return {_entity_key(entity.entity_type, entity.name): entity for entity in result.scalars().all()}


def _merge_quality_metadata(entity: StoryEntity, *, run_id: str, item: dict[str, Any], quality: dict[str, Any]) -> None:
    extra = dict(_json_dict(entity.extra_data))
    extra["quality"] = quality
    extra["extraction_run_id"] = run_id
    extra["auto_decision"] = quality.get("auto_decision")
    extra.setdefault("source_evidence", item.get("evidence"))
    extra["provenance"] = {
        "source_chapter_id": item.get("source_chapter_id") or entity.chapter_id,
        "source_chapter_number": item.get("source_chapter_number"),
        "evidence_span": item.get("evidence_span") or item.get("evidence"),
        "char_start": item.get("char_start"),
        "char_end": item.get("char_end"),
        "extraction_model": item.get("extraction_model"),
        "extraction_config": _json_dict(item.get("extraction_config")),
        "review_state": item.get("review_state") or CANDIDATE,
    }
    if item.get("future_intent") is not None:
        extra["future_intent"] = item["future_intent"]
    if item.get("foreshadowing") is not None:
        extra["foreshadowing"] = item["foreshadowing"]
    entity.extra_data = extra
    entity.updated_at = utc_now()


def _apply_candidate_fields(entity: StoryEntity, item: dict[str, Any]) -> None:
    attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    entity.description = item.get("description") or entity.description
    entity.canonical_name = item.get("canonical_name") or entity.canonical_name
    entity.aliases = item.get("aliases") or entity.aliases or []
    semantic_attrs = {
        "current_state": _json_dict(item.get("current_state")),
        "known_to_characters": item.get("known_to_characters") if isinstance(item.get("known_to_characters"), list) else [],
        "introduced_at": item.get("introduced_at") or item.get("source_chapter_number"),
        "resolved_at": item.get("resolved_at"),
        "source_chapter_number": item.get("source_chapter_number"),
    }
    if item.get("entity_type") == "event":
        semantic_attrs["event"] = {key: item.get(key) for key in ("actor", "action", "object", "outcome")}
    entity.attributes = {**_json_dict(entity.attributes), **attrs, **semantic_attrs}
    entity.first_seen_chapter_id = entity.first_seen_chapter_id or item.get("source_chapter_id") or entity.chapter_id
    entity.appearance = item.get("appearance") or attrs.get("appearance") or entity.appearance
    entity.visual_prompt = item.get("visual_prompt") or attrs.get("visual_prompt") or entity.visual_prompt
    entity.relations = item.get("relations") or attrs.get("relationships") or entity.relations or []
    entity.state_changes = item.get("state_changes") or attrs.get("state_changes") or entity.state_changes or []
    entity.evidence = item.get("evidence") or entity.evidence
    entity.confidence = item.get("confidence") or entity.confidence or 100
    entity.source = item.get("source") or entity.source or "deterministic"


def _new_entity(
    *,
    user_id: str,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
    item: dict[str, Any],
) -> StoryEntity:
    attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    entity = StoryEntity(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        entity_type=item["entity_type"],
        name=item["name"],
        description=item.get("description"),
        canonical_name=item.get("canonical_name"),
        aliases=item.get("aliases") or [],
        appearance=item.get("appearance") or attrs.get("appearance"),
        visual_prompt=item.get("visual_prompt") or attrs.get("visual_prompt"),
        attributes=attrs,
        relations=item.get("relations") or attrs.get("relationships") or [],
        state_changes=item.get("state_changes") or attrs.get("state_changes") or [],
        evidence=item.get("evidence"),
        confidence=item.get("confidence") or 100,
        source=item.get("source") or "deterministic",
    )
    _apply_candidate_fields(entity, item)
    return entity


def _mention_has_approval_evidence(mention: StoryEntityMention) -> bool:
    return bool(
        str(mention.source_id or "").strip()
        and str(mention.evidence or "").strip()
        and mention.confidence is not None
    )


def _quality_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = Counter(_quality_payload(item).get("auto_decision") for item in items)
    scores = [_quality_payload(item).get("score", 0) for item in items]
    return {
        "total": len(items),
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "decisions": dict(decisions),
    }


async def run_candidate_entity_extraction(
    db: AsyncSession,
    *,
    user_id: str,
    text: str,
    source_type: str,
    source_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    entity_types: Optional[list[str]] = None,
    model_config_id: Optional[str] = None,
    provider: Optional[str] = None,
    model_id: Optional[str] = None,
    prompt_version: Optional[str] = None,
    persist: bool = True,
    persist_rejected: bool = False,
    allow_auto_approve: bool = False,
    candidate_items: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    requested = set(entity_types or sorted(ENTITY_TYPES))
    unknown = requested - ENTITY_TYPES
    if unknown:
        raise ValueError(f"不支持的实体类型: {', '.join(sorted(unknown))}")

    prompt_route = await select_prompt_skill_for_model(
        db,
        user_id=user_id,
        task="entity_extraction",
        provider_name=provider,
        model_id=model_id,
        model_capabilities=[],
        output_contract="json_array",
        stage="analysis",
        context={
            "entity_types": "、".join(sorted(requested)),
            "allowed_entity_types": ", ".join(sorted(requested)),
            "source_type": source_type,
            "source_content": (text or "")[:30000],
            "output_format": "JSON 数组",
        },
        internal_prompt="抽取小说动漫制作实体候选，必须保留证据，并由质量门禁决定候选/拒绝/批准状态。",
    )
    prompt_route_metadata = {key: value for key, value in prompt_route.items() if key != "prompt"}

    run_id = str(uuid4())
    run = EntityExtractionRun(
        id=run_id,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        source_type=source_type,
        source_id=source_id,
        text_hash=_text_hash(text),
        entity_types=sorted(requested),
        model_config_id=model_config_id,
        provider=provider,
        model_id=model_id,
        prompt_version=prompt_version,
        status="running",
        stats={},
        quality_summary={},
        extra_data={"pipeline": "entity_extraction_v2", "prompt_routing": prompt_route_metadata},
    )
    if persist:
        db.add(run)

    items = (
        [dict(item) for item in candidate_items if item.get("entity_type") in requested]
        if candidate_items is not None
        else _candidate_items(text, requested, include_rejected=persist_rejected)
    )
    existing_by_key = await _load_existing_entities(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        entity_types=requested,
    )

    stats = {"created": 0, "updated": 0, "candidate": 0, "approved": 0, "rejected": 0, "skipped": 0}
    entities: list[StoryEntity] = []
    mentions: list[StoryEntityMention] = []
    for item in items:
        quality = _quality_payload(item)
        auto_decision = quality.get("auto_decision")
        key = _entity_key(item["entity_type"], item["name"])
        existing = existing_by_key.get(key)

        if auto_decision == REJECT_NOISE and not persist_rejected:
            stats["rejected"] += 1
            stats["skipped"] += 1
            mentions.append(
                _build_mention(
                    user_id=user_id,
                    run_id=run_id,
                    entity_id=None,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    script_id=script_id,
                    source_type=source_type,
                    source_id=source_id,
                    text=text,
                    item=item,
                )
            )
            continue

        entity = existing or _new_entity(
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            item=item,
        )
        previous_status = get_entity_review_status(entity)
        preserve_existing_status = existing is not None and previous_status in {APPROVED, LEGACY_ACTIVE}
        if not preserve_existing_status:
            _apply_candidate_fields(entity, item)
        _merge_quality_metadata(entity, run_id=run_id, item=item, quality=quality)

        mention = _build_mention(
            user_id=user_id,
            run_id=run_id,
            entity_id=entity.id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            source_type=source_type,
            source_id=source_id,
            text=text,
            item=item,
        )

        if preserve_existing_status:
            final_status = previous_status
            stats["updated"] += 1
        elif auto_decision == REJECT_NOISE:
            final_status = REJECTED
            stats["rejected"] += 1
        elif allow_auto_approve and auto_decision == AUTO_APPROVE and _mention_has_approval_evidence(mention):
            final_status = APPROVED
            stats["approved"] += 1
        else:
            final_status = CANDIDATE
            stats["candidate"] += 1

        if existing is None:
            stats["created"] += 1
            existing_by_key[key] = entity
            if persist:
                db.add(entity)
        elif not preserve_existing_status:
            stats["updated"] += 1

        set_entity_review_status(entity, final_status, changed_by=user_id, reason=f"entity_extraction_v2:{auto_decision}")
        entities.append(entity)
        mentions.append(mention)

    run.status = "completed"
    run.completed_at = utc_now()
    run.stats = stats
    run.quality_summary = _quality_summary(items)
    if persist:
        for mention in mentions:
            db.add(mention)
        await db.commit()
        await db.refresh(run)
        for entity in entities:
            await db.refresh(entity)

    return {
        "run_id": run.id,
        "status": run.status,
        "stats": stats,
        "quality_summary": run.quality_summary,
        "prompt_routing": prompt_route_metadata,
        "entities": entities,
        "mentions": mentions,
    }


def _entity_snapshot(entity: StoryEntity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "description": entity.description,
        "aliases": entity.aliases or [],
        "is_approved": bool(entity.is_approved),
        "review_status": get_entity_review_status(entity),
        "extra_data": _json_dict(entity.extra_data),
    }


async def _get_entity_for_user(db: AsyncSession, *, user_id: str, entity_id: str) -> StoryEntity:
    entity = await db.get(StoryEntity, entity_id)
    if entity is None or entity.user_id != user_id:
        raise ValueError("实体不存在")
    return entity


def _is_manual_entity(entity: StoryEntity) -> bool:
    return str(entity.source or "").strip().lower() == "manual"


async def _require_entity_approval_evidence(
    db: AsyncSession,
    *,
    user_id: str,
    entity: StoryEntity,
) -> None:
    if _is_manual_entity(entity):
        return

    result = await db.execute(
        select(StoryEntityMention.id).where(
            StoryEntityMention.user_id == user_id,
            StoryEntityMention.entity_id == entity.id,
            StoryEntityMention.source_id.is_not(None),
            func.length(func.trim(StoryEntityMention.source_id)) > 0,
            StoryEntityMention.evidence.is_not(None),
            func.length(func.trim(StoryEntityMention.evidence)) > 0,
            StoryEntityMention.confidence.is_not(None),
        ).limit(1)
    )
    if result.scalar_one_or_none() is None:
        raise EntityApprovalEvidenceError("AI 抽取实体缺少可验证原文证据，不能进入生产状态")


async def _write_feedback(
    db: AsyncSession,
    *,
    user_id: str,
    entity: StoryEntity,
    action: str,
    before_data: dict[str, Any],
    reason: Optional[str] = None,
    run_id: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> EntityFeedback:
    feedback = EntityFeedback(
        id=str(uuid4()),
        user_id=user_id,
        entity_id=entity.id,
        run_id=run_id or _json_dict(entity.extra_data).get("extraction_run_id"),
        action=action,
        before_data=before_data,
        after_data=_entity_snapshot(entity),
        reason=reason,
        extra_data=extra_data or {},
    )
    db.add(feedback)
    return feedback


async def approve_review_entity(
    db: AsyncSession,
    *,
    user_id: str,
    entity_id: str,
    reason: Optional[str] = None,
) -> StoryEntity:
    entity = await _get_entity_for_user(db, user_id=user_id, entity_id=entity_id)
    if get_entity_review_status(entity) != APPROVED:
        await _require_entity_approval_evidence(db, user_id=user_id, entity=entity)
    before = _entity_snapshot(entity)
    approval_reason = reason or "manual approve"
    approved_at = utc_now()
    set_entity_review_status(entity, APPROVED, changed_by=user_id, reason=approval_reason)
    attributes = dict(entity.attributes or {})
    approval_record = dict(attributes.get("approval_record") or {})
    approval_record.setdefault("approved_by", user_id)
    approval_record.setdefault("approved_at", approved_at.isoformat())
    approval_record.setdefault("reason", approval_reason)
    attributes["approval_record"] = approval_record
    entity.attributes = attributes
    entity.is_approved = True
    entity.updated_at = approved_at
    await _write_feedback(db, user_id=user_id, entity=entity, action="approve", before_data=before, reason=reason)
    await db.commit()
    await db.refresh(entity)
    return entity


async def reject_review_entity(
    db: AsyncSession,
    *,
    user_id: str,
    entity_id: str,
    reason: Optional[str] = None,
) -> StoryEntity:
    entity = await _get_entity_for_user(db, user_id=user_id, entity_id=entity_id)
    before = _entity_snapshot(entity)
    set_entity_review_status(entity, REJECTED, changed_by=user_id, reason=reason or "manual reject")
    entity.is_approved = False
    entity.updated_at = utc_now()
    await _write_feedback(db, user_id=user_id, entity=entity, action="reject", before_data=before, reason=reason)
    await db.commit()
    await db.refresh(entity)
    return entity


def _quality(entity: StoryEntity) -> dict[str, Any]:
    return _json_dict(_json_dict(entity.extra_data).get("quality"))


async def suggest_entity_merges(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    entities = await query_story_entities_for_review(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        limit=1000,
    )
    groups: dict[str, list[StoryEntity]] = {}
    for entity in entities:
        canonical = (entity.canonical_name or entity.name or "").strip()
        if not canonical:
            continue
        groups.setdefault(f"{entity.entity_type}:{canonical}", []).append(entity)

    suggestions: list[dict[str, Any]] = []
    for canonical_key, items in groups.items():
        if len(items) < 2:
            continue
        preferred = next((item for item in items if get_entity_review_status(item) == APPROVED), items[0])
        suggestions.append(
            {
                "canonical_key": canonical_key,
                "target_entity_id": preferred.id,
                "entity_ids": [item.id for item in items],
                "names": [item.name for item in items],
                "reason": "规范名相同，建议人工确认是否合并",
                "confidence": 80,
            }
        )
    return suggestions


async def entity_has_duplicate_risk(
    db: AsyncSession,
    *,
    user_id: str,
    entity: StoryEntity,
) -> bool:
    """Return whether bulk approval should defer this entity to merge review."""
    canonical = str(entity.canonical_name or entity.name or "").strip()
    if not canonical:
        return False
    entities = await query_story_entities_for_review(
        db,
        user_id=user_id,
        novel_id=entity.novel_id,
        chapter_id=entity.chapter_id,
        script_id=entity.script_id,
        entity_types=[entity.entity_type],
        limit=1000,
    )
    duplicates = [
        item
        for item in entities
        if str(item.canonical_name or item.name or "").strip() == canonical
    ]
    return len(duplicates) > 1


async def get_entity_review_summary(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
) -> dict[str, Any]:
    query = select(StoryEntity).where(StoryEntity.user_id == user_id)
    if novel_id:
        query = query.where(StoryEntity.novel_id == novel_id)
    if chapter_id:
        query = query.where(StoryEntity.chapter_id == chapter_id)
    if script_id:
        query = query.where(StoryEntity.script_id == script_id)
    entities = list((await db.execute(query.limit(2000))).scalars().all())
    counts = {LEGACY_ACTIVE: 0, CANDIDATE: 0, APPROVED: 0, REJECTED: 0, ARCHIVED: 0}
    by_type = {entity_type: 0 for entity_type in sorted(ENTITY_TYPES)}
    missing_evidence = 0
    rejected_noise = 0
    for entity in entities:
        status = get_entity_review_status(entity)
        counts[status] = counts.get(status, 0) + 1
        by_type[entity.entity_type] = by_type.get(entity.entity_type, 0) + 1
        quality = _quality(entity)
        flags = quality.get("flags") if isinstance(quality.get("flags"), list) else []
        if not entity.evidence or "missing_evidence" in flags:
            missing_evidence += 1
        if quality.get("auto_decision") == REJECT_NOISE:
            rejected_noise += 1

    entity_ids = [entity.id for entity in entities if get_entity_review_status(entity) == APPROVED]
    asset_entity_ids: set[str] = set()
    if entity_ids:
        asset_result = await db.execute(
            select(Asset.entity_id).where(Asset.user_id == user_id, Asset.entity_id.in_(entity_ids), Asset.is_active == True)
        )
        asset_entity_ids = {str(value) for value in asset_result.scalars().all() if value}
    asset_gap = len([entity for entity in entities if get_entity_review_status(entity) == APPROVED and entity.id not in asset_entity_ids])
    merge_suggestions = await suggest_entity_merges(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
    )

    if counts.get(CANDIDATE, 0):
        recommended = "review_candidates"
    elif merge_suggestions:
        recommended = "review_merge_suggestions"
    elif asset_gap:
        recommended = "generate_missing_assets"
    else:
        recommended = "run_analysis"

    return {
        "counts": counts,
        "by_type": by_type,
        "candidate_count": counts.get(CANDIDATE, 0),
        "approved_count": counts.get(APPROVED, 0),
        "rejected_count": counts.get(REJECTED, 0),
        "duplicate_risk_count": len(merge_suggestions),
        "missing_evidence_count": missing_evidence,
        "rejected_noise_count": rejected_noise,
        "asset_gap_count": asset_gap,
        "recommended_next_action": recommended,
        "merge_suggestion_count": len(merge_suggestions),
    }


async def get_extraction_run_detail(
    db: AsyncSession,
    *,
    user_id: str,
    run_id: str,
) -> dict[str, Any]:
    run = await db.get(EntityExtractionRun, run_id)
    if run is None or run.user_id != user_id:
        raise ValueError("抽取任务不存在")
    mentions = (
        await db.execute(select(StoryEntityMention).where(StoryEntityMention.user_id == user_id, StoryEntityMention.run_id == run_id))
    ).scalars().all()
    entity_ids = [mention.entity_id for mention in mentions if mention.entity_id]
    entities: list[StoryEntity] = []
    if entity_ids:
        entities = list((await db.execute(select(StoryEntity).where(StoryEntity.id.in_(entity_ids)))).scalars().all())
    return {
        "id": run.id,
        "status": run.status,
        "novel_id": run.novel_id,
        "chapter_id": run.chapter_id,
        "script_id": run.script_id,
        "source_type": run.source_type,
        "source_id": run.source_id,
        "entity_types": run.entity_types or [],
        "provider": run.provider,
        "model_id": run.model_id,
        "prompt_version": run.prompt_version,
        "stats": run.stats or {},
        "quality_summary": run.quality_summary or {},
        "extra_data": run.extra_data or {},
        "mention_count": len(mentions),
        "entities": [_entity_snapshot(entity) for entity in entities],
    }
