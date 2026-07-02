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
from app.models import Asset, Novel, StoryBible, StoryEntity, Workflow

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
    result = await db.execute(
        select(StoryEntity)
        .where(
            StoryEntity.user_id == user_id,
            or_(StoryEntity.novel_id == novel_id, StoryEntity.novel_id.is_(None)),
        )
        .order_by(StoryEntity.entity_type, StoryEntity.updated_at)
    )
    return list(result.scalars().all())


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
    matched_assets = [asset for asset in assets if _asset_matches_entity(asset, entity)]
    visual_dna = _json_dict(attrs.get("visual_dna") or attrs.get("scene_dna") or attrs.get("prop_dna"))
    voice = attrs.get("voice") or attrs.get("voice_profile") or attrs.get("voice_id")
    return {
        "entity_id": entity.id,
        "name": entity.name,
        "canonical_name": entity.canonical_name,
        "description": _compact(entity.description or entity.evidence),
        "approved": bool(entity.is_approved),
        "confidence": entity.confidence or 0,
        "chapter_id": entity.chapter_id,
        "visual_dna": visual_dna,
        "voice": voice,
        "asset_count": len(matched_assets),
        "asset_ids": [asset.id for asset in matched_assets[:6]],
        "missing_asset": entity.entity_type in {"character", "scene", "prop"} and not matched_assets,
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
            voices.append({
                "character_name": character.get("name"),
                "entity_id": character.get("entity_id"),
                "voice": character.get("voice"),
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
    }


async def build_production_bible_summary(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
    *,
    story_bible_id: Optional[str] = None,
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

    missing_requirements: List[Dict[str, Any]] = []
    if story_bible is None:
        missing_requirements.append({"code": "story_bible_missing", "message": "小说尚未绑定 Story Bible"})
    if story_bible and not (story_bible.style or "").strip():
        missing_requirements.append({"code": "style_missing", "message": "Story Bible 缺少统一风格描述"})
    if not characters:
        missing_requirements.append({"code": "characters_missing", "message": "Production Bible 中没有角色实体"})
    if missing_assets:
        missing_requirements.append({
            "code": "asset_references_missing",
            "message": "部分角色/场景/道具缺少定稿资产",
            "count": len(missing_assets),
            "items": [{"entity_id": item["entity_id"], "name": item["name"]} for item in missing_assets[:20]],
        })
    if not state_machine["available"]:
        missing_requirements.append({"code": "state_machine_missing", "message": "Story Bible 状态机尚未生成"})

    return {
        "version": "production-bible-summary-v1",
        "novel_id": novel.id,
        "novel_title": novel.title,
        "story_bible_id": story_bible.id if story_bible else None,
        "generated_at": utc_now().isoformat(),
        "style": _style_summary(novel, story_bible),
        "characters": characters[:60],
        "scenes": scenes[:60],
        "props": props[:60],
        "events": events[:80],
        "voices": _voices_summary(story_bible, characters),
        "state_machine": state_machine,
        "asset_readiness": {
            "asset_count": len(assets),
            "asset_counts_by_category": dict(asset_counts),
            "required_entity_count": len(characters) + len(scenes) + len(props),
            "missing_asset_count": len(missing_assets),
            "ready": len(missing_assets) == 0,
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
