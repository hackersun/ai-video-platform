"""Production Bible summary and snapshot helpers.

The production bible is intentionally stored on existing JSON columns so P0 can
ship without schema migrations: StoryBible.extra_data, StoryEntity.attributes
and Workflow.metadata_.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import Asset, Chapter, Novel, StoryBible, StoryEntity, Workflow
from app.services.chapter_fact_timeline import project_entities_as_of_chapter, project_entity_fact
from app.services.story_entity_lifecycle import query_story_entities_for_production
from app.services.production_graph_service import project_story_state

PRODUCTION_SNAPSHOT_KEY = "production_snapshot"


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _compact(value: Optional[str], limit: int = 180) -> Optional[str]:
    text = " ".join(str(value or "").split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _uniq(values: Iterable[Any], limit: int = 12) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


async def approve_story_entity(
    db: AsyncSession,
    user_id: str,
    entity_id: str,
    approved: bool,
    note: str | None = None,
) -> Dict[str, Any]:
    from app.services.entity_review_service import approve_review_entity, reject_review_entity

    try:
        if approved:
            entity = await approve_review_entity(db, user_id=user_id, entity_id=entity_id, reason=note)
        else:
            entity = await reject_review_entity(db, user_id=user_id, entity_id=entity_id, reason=note)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    attrs = dict(_json_dict(entity.attributes))
    attrs["approval_note"] = note
    attrs["approved_at"] = utc_now().isoformat() if approved else None
    entity.attributes = attrs
    await db.commit()
    return {"entity_id": entity.id, "approved": entity.is_approved, "attributes": attrs}


async def _load_novel(db: AsyncSession, user_id: str, novel_id: str) -> Novel:
    result = await db.execute(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")
    return novel


async def _load_story_bible(db: AsyncSession, user_id: str, novel_id: str) -> Optional[StoryBible]:
    result = await db.execute(
        select(StoryBible)
        .where(StoryBible.user_id == user_id, StoryBible.novel_id == novel_id)
        .order_by(desc(StoryBible.updated_at), desc(StoryBible.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_entities(db: AsyncSession, user_id: str, novel_id: str) -> List[StoryEntity]:
    entities = await query_story_entities_for_production(
        db,
        user_id=user_id,
        novel_id=novel_id,
    )
    return sorted(entities, key=lambda entity: (entity.entity_type or "", str(entity.updated_at or "")))


async def _load_chapters(db: AsyncSession, user_id: str, novel_id: str) -> List[Chapter]:
    result = await db.execute(
        select(Chapter)
        .where(Chapter.user_id == user_id, Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number, Chapter.created_at)
    )
    return list(result.scalars().all())


def _entity_identity(entity: StoryEntity) -> tuple[str, str]:
    return (entity.entity_type, str(entity.canonical_name or entity.name or "").strip())


def _dedupe_entities(entities: List[StoryEntity]) -> List[StoryEntity]:
    by_key: Dict[tuple[str, str], StoryEntity] = {}
    for entity in entities:
        key = _entity_identity(entity)
        if not key[1]:
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = entity
            continue
        if existing.chapter_id and not entity.chapter_id:
            by_key[key] = entity
            continue
        if existing.script_id and not entity.script_id:
            by_key[key] = entity
    return list(by_key.values())


async def _load_assets(db: AsyncSession, user_id: str, novel_id: str) -> List[Asset]:
    result = await db.execute(
        select(Asset).where(
            Asset.is_active == True,
            or_(Asset.user_id == user_id, Asset.is_public == True),
            or_(Asset.novel_id == novel_id, Asset.novel_id.is_(None)),
        )
    )
    return list(result.scalars().all())


def _asset_matches_entity(asset: Asset, entity: StoryEntity) -> bool:
    if asset.entity_id and asset.entity_id == entity.id:
        return True
    if asset.category != entity.entity_type and not (entity.entity_type == "character" and asset.category == "costume"):
        return False
    names = [entity.name, *_json_list(entity.aliases)]
    haystack = f"{asset.name or ''} {asset.description or ''} {' '.join(asset.tags or [])}"
    return any(str(name or "").strip() and str(name) in haystack for name in names)


def _entity_summary(entity: StoryEntity, assets: List[Asset]) -> Dict[str, Any]:
    attrs = _json_dict(entity.attributes)
    fact = project_entity_fact(entity)
    matched_assets = [asset for asset in assets if _asset_matches_entity(asset, entity)]
    visual_dna = _json_dict(attrs.get("visual_dna") or attrs.get("scene_dna") or attrs.get("prop_dna"))
    reference_requirements = _json_dict(attrs.get("reference_requirements"))
    if matched_assets and not visual_dna:
        visual_dna = {"reference_asset": matched_assets[0].name or matched_assets[0].id}
    if matched_assets and entity.entity_type == "character" and not _json_list(reference_requirements.get("character_multiview")):
        reference_requirements = {**reference_requirements, "character_multiview": ["reference_asset"]}
    if matched_assets and entity.entity_type == "prop" and not _json_list(reference_requirements.get("prop_multiview")):
        reference_requirements = {**reference_requirements, "prop_multiview": ["reference_asset"]}
    voice_binding = _json_dict(attrs.get("voice_binding"))
    voice = (
        attrs.get("voice")
        or attrs.get("voice_profile")
        or attrs.get("voice_id")
        or voice_binding.get("voice_id")
    )
    return {
        "entity_id": entity.id,
        "name": entity.name,
        "canonical_name": entity.canonical_name,
        "description": _compact(entity.description or entity.evidence),
        "approved": bool(entity.is_approved),
        "confidence": entity.confidence or 0,
        "chapter_id": entity.chapter_id,
        "visual_dna": visual_dna,
        "reference_requirements": reference_requirements,
        "scene_tags": _json_list(attrs.get("scene_tags") or attrs.get("tags")),
        "weather": attrs.get("weather") or visual_dna.get("weather"),
        "lighting": attrs.get("lighting") or visual_dna.get("lighting"),
        "voice": voice,
        "voice_binding": voice_binding,
        "asset_count": len(matched_assets),
        "asset_ids": [asset.id for asset in matched_assets[:6]],
        "missing_asset": entity.entity_type in {"character", "scene", "prop"} and not matched_assets,
        "current_state": fact["current_state"],
        "known_to_characters": fact["known_to_characters"],
        "introduced_at": fact["introduced_at"],
        "resolved_at": fact["resolved_at"],
    }


def _style_summary(novel: Novel, story_bible: Optional[StoryBible]) -> Dict[str, Any]:
    bible_extra = _json_dict(story_bible.extra_data) if story_bible else {}
    novel_extra = _json_dict(novel.extra_data)
    return {
        "title": story_bible.title if story_bible else novel.title,
        "style": story_bible.style if story_bible else novel_extra.get("style"),
        "worldview": story_bible.worldview if story_bible else novel.description,
        "negative_prompt": story_bible.negative_prompt if story_bible else None,
        "visual_style": bible_extra.get("visual_style") or novel_extra.get("visual_style"),
        "rules": {
            "character_rules": len(story_bible.character_rules or []) if story_bible else 0,
            "scene_rules": len(story_bible.scene_rules or []) if story_bible else 0,
            "prop_rules": len(story_bible.prop_rules or []) if story_bible else 0,
            "event_timeline": len(story_bible.event_timeline or []) if story_bible else 0,
        },
    }


def _voices_summary(story_bible: Optional[StoryBible], characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bible_extra = _json_dict(story_bible.extra_data) if story_bible else {}
    explicit = bible_extra.get("voices") or bible_extra.get("voice_cast") or []
    voices: List[Dict[str, Any]] = [item for item in _json_list(explicit) if isinstance(item, dict)]
    for character in characters:
        if character.get("voice"):
            binding = _json_dict(character.get("voice_binding"))
            voices.append({
                "character_name": character.get("name"),
                "entity_id": character.get("entity_id"),
                "voice": character.get("voice"),
                "voice_id": binding.get("voice_id") or character.get("voice"),
                "voice_version": binding.get("version") or 1,
                "status": binding.get("status"),
                "source": "entity_attributes",
            })
    return voices[:30]


def _state_machine_summary(story_bible: Optional[StoryBible]) -> Dict[str, Any]:
    state_machine = _json_dict(_json_dict(story_bible.extra_data).get("state_machine")) if story_bible else {}
    current_state = _json_dict(state_machine.get("current_state"))
    return {
        "available": bool(state_machine),
        "generated_at": state_machine.get("generated_at"),
        "summary": _json_dict(state_machine.get("summary")),
        "current_state_counts": {
            "characters": len(_json_dict(current_state.get("characters"))),
            "scenes": len(_json_dict(current_state.get("scenes"))),
            "props": len(_json_dict(current_state.get("props"))),
            "events": len(_json_list(current_state.get("events"))),
        },
        "latest_events": _json_list(current_state.get("events"))[-6:],
        "issues": _json_list(state_machine.get("issues"))[:20],
        "status": state_machine.get("status"),
    }


def _readiness_score(missing_requirements: List[Dict[str, Any]]) -> int:
    return max(0, 100 - len(missing_requirements) * 25)


async def build_production_bible_summary(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
    *,
    story_bible_id: Optional[str] = None,
    as_of_chapter_id: Optional[str] = None,
    as_of_chapter_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a compact production bible for pre-production and episode snapshots."""
    novel = await _load_novel(db, user_id, novel_id)
    if story_bible_id:
        result = await db.execute(
            select(StoryBible).where(
                StoryBible.id == story_bible_id,
                StoryBible.user_id == user_id,
                StoryBible.novel_id == novel_id,
            )
        )
        story_bible = result.scalar_one_or_none()
        if story_bible is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story Bible 不存在")
    else:
        story_bible = await _load_story_bible(db, user_id, novel_id)

    entities = await _load_entities(db, user_id, novel_id)
    if as_of_chapter_id is not None or as_of_chapter_number is not None:
        chapters = await _load_chapters(db, user_id, novel_id)
        boundary = as_of_chapter_number
        if as_of_chapter_id is not None:
            matched = next((chapter for chapter in chapters if chapter.id == as_of_chapter_id), None)
            if matched is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节边界不存在")
            boundary = matched.chapter_number
        entities = project_entities_as_of_chapter(
            entities, chapters, chapter_number=int(boundary), strict=True
        )
    entities = _dedupe_entities(entities)
    assets = await _load_assets(db, user_id, novel_id)
    by_type: Dict[str, List[StoryEntity]] = {"character": [], "scene": [], "prop": [], "event": []}
    for entity in entities:
        by_type.setdefault(entity.entity_type, []).append(entity)

    characters = [_entity_summary(entity, assets) for entity in by_type.get("character", [])]
    scenes = [_entity_summary(entity, assets) for entity in by_type.get("scene", [])]
    props = [_entity_summary(entity, assets) for entity in by_type.get("prop", [])]
    events = [_entity_summary(entity, assets) for entity in by_type.get("event", [])]
    missing_assets = [item for item in [*characters, *scenes, *props] if item.get("missing_asset")]
    asset_counts = Counter(asset.category for asset in assets)
    state_machine = _state_machine_summary(story_bible)
    production_graph = await project_story_state(db, user_id=user_id, novel_id=novel_id)
    character_contract_ready = [
        item for item in characters
        if item.get("visual_dna") and _json_list(_json_dict(item.get("reference_requirements")).get("character_multiview"))
    ]
    scene_contract_ready = [
        item for item in scenes
        if item.get("visual_dna") and (item.get("weather") or item.get("lighting") or item.get("scene_tags"))
    ]
    prop_contract_ready = [
        item for item in props
        if item.get("visual_dna") and _json_list(_json_dict(item.get("reference_requirements")).get("prop_multiview"))
    ]
    visual_contract_missing = (
        len(characters) - len(character_contract_ready)
        + len(scenes) - len(scene_contract_ready)
        + len(props) - len(prop_contract_ready)
    )

    missing_requirements: List[Dict[str, Any]] = []
    if story_bible is None:
        missing_requirements.append({"code": "story_bible_missing", "message": "小说尚未绑定 Story Bible"})
    if story_bible and not (story_bible.style or "").strip():
        missing_requirements.append({"code": "style_missing", "message": "Story Bible 缺少统一风格描述"})
    if not characters:
        missing_requirements.append({"code": "characters_missing", "message": "Production Bible 中没有角色实体"})
    if visual_contract_missing:
        missing_requirements.append({
            "code": "visual_contract_missing",
            "message": "部分角色/场景/道具缺少视觉 DNA、多视图规划或天气光影标签",
            "count": visual_contract_missing,
        })
    if not state_machine["available"]:
        missing_requirements.append({"code": "state_machine_missing", "message": "Story Bible 状态机尚未生成"})

    return {
        "version": "production-bible-summary-v1",
        "novel_id": novel.id,
        "novel_title": novel.title,
        "story_bible_id": story_bible.id if story_bible else None,
        "story_bible_status": _json_dict(story_bible.extra_data).get("production_status") if story_bible else None,
        "story_bible_approval_record": _json_dict(story_bible.extra_data).get("approval_record") if story_bible else None,
        "story_bible_version": story_bible.updated_at.isoformat() if story_bible and story_bible.updated_at else None,
        "generated_at": utc_now().isoformat(),
        "readiness_score": _readiness_score(missing_requirements),
        "style": _style_summary(novel, story_bible),
        "characters": characters[:60],
        "scenes": scenes[:60],
        "props": props[:60],
        "events": events[:80],
        "voices": _voices_summary(story_bible, characters),
        "state_machine": state_machine,
        "production_graph": production_graph,
        "asset_readiness": {
            "asset_count": len(assets),
            "asset_counts_by_category": dict(asset_counts),
            "required_entity_count": len(characters) + len(scenes) + len(props),
            "missing_asset_count": len(missing_assets),
            "ready": len(missing_assets) == 0,
            "missing_assets": [{"entity_id": item["entity_id"], "name": item["name"]} for item in missing_assets[:20]],
        },
        "asset_lock_snapshots": [
            {"asset_id": asset.id, "version": int(asset.version or 1), "is_locked": bool(asset.is_locked)}
            for asset in assets if asset.is_final
        ],
        "visual_contract_readiness": {
            "character_multiview_contract_count": len(character_contract_ready),
            "character_count": len(characters),
            "scene_environment_contract_count": len(scene_contract_ready),
            "scene_count": len(scenes),
            "prop_visual_contract_count": len(prop_contract_ready),
            "prop_count": len(props),
            "missing_contract_count": visual_contract_missing,
            "ready": visual_contract_missing == 0,
        },
        "missing_requirements": missing_requirements,
        "counts": {
            "characters": len(characters),
            "scenes": len(scenes),
            "props": len(props),
            "events": len(events),
            "voices": len(_voices_summary(story_bible, characters)),
        },
        "anchors": {
            "character_names": _uniq(item.get("name") for item in characters),
            "scene_names": _uniq(item.get("name") for item in scenes),
            "prop_names": _uniq(item.get("name") for item in props),
        },
    }


def build_production_snapshot(summary: Dict[str, Any], *, reason: str) -> Dict[str, Any]:
    return {
        "version": "production-snapshot-v1",
        "snapshot_at": utc_now().isoformat(),
        "reason": reason,
        "summary": summary,
    }


def workflow_extra_data(workflow: Workflow) -> Dict[str, Any]:
    return _json_dict(workflow.metadata_)
