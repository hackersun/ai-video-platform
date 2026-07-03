"""Read-only production card aggregation for characters, scenes and props."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Character, Shot, StoryBible, StoryEntity
from app.services.asset_generation_service import ASSET_VIEW_PRESETS, AssetGenerationService, _view_key
from app.services.entity_ref_normalizer import entity_ref_ids
from app.services.production_bible import (
    _asset_matches_entity,
    _load_assets,
    _load_entities,
    _load_novel,
    _load_story_bible,
)
from app.services.voice_service import get_character_voice_from_story_bible


PRODUCTION_CARD_ENTITY_TYPES = {"character", "scene", "prop"}
SUPPORTING_VOICE_POOL = ["supporting_voice_1", "supporting_voice_2", "supporting_voice_3"]


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _default_supporting_voice_pool() -> List[str]:
    try:
        from app.core.minimax_config import TTS_VOICES
    except ImportError:
        return SUPPORTING_VOICE_POOL

    voices = [
        str(item.get("voice_id")).strip()
        for item in TTS_VOICES
        if isinstance(item, dict) and item.get("voice_id")
    ]
    return voices or SUPPORTING_VOICE_POOL


def _entity_refs_key(entity_type: str) -> str:
    return {
        "character": "characters",
        "scene": "scenes",
        "prop": "props",
    }.get(entity_type, f"{entity_type}s")


def _asset_fix_url(entity: StoryEntity) -> str:
    return "/assets?" + urlencode(
        {
            "novel_id": entity.novel_id or "",
            "entity_type": entity.entity_type,
            "entity_id": entity.id,
        }
    )


def _story_bible_fix_url(entity: StoryEntity) -> str:
    return "/story-bibles?" + urlencode(
        {
            "novel_id": entity.novel_id or "",
            "entity_id": entity.id,
        }
    )


def _preset_views(entity_type: str) -> List[Dict[str, Any]]:
    preset = ASSET_VIEW_PRESETS.get(entity_type) or {}
    return [view for view in _json_list(preset.get("views")) if isinstance(view, dict)]


def _view_labels(entity_type: str) -> Dict[str, str]:
    return {str(view.get("key")): str(view.get("label") or view.get("key")) for view in _preset_views(entity_type)}


def _entity_role_tier(entity: StoryEntity) -> Optional[str]:
    attrs = _json_dict(entity.attributes)
    extra = _json_dict(entity.extra_data)
    value = attrs.get("role_tier") or attrs.get("role") or extra.get("role_tier") or extra.get("role")
    return str(value).strip().lower() if value else None


def required_view_keys(entity_type: str, role_tier: Optional[str] = None) -> List[str]:
    """Return the production-card required view keys for an entity type."""
    if entity_type == "character" and role_tier == "supporting":
        return ["front"]
    if entity_type == "prop":
        return ["main"]
    return [str(view.get("key")) for view in _preset_views(entity_type) if view.get("key")]


def _asset_rank(asset: Asset) -> tuple[int, int, int, int, str]:
    return (
        1 if asset.is_locked and asset.is_final else 0,
        1 if asset.is_locked else 0,
        1 if asset.is_final else 0,
        int(asset.version or 0),
        str(asset.updated_at or asset.created_at or ""),
    )


def _best_asset_by_view(entity: StoryEntity, assets: Iterable[Asset]) -> Dict[str, Asset]:
    by_view: Dict[str, Asset] = {}
    for asset in assets:
        if not _asset_matches_entity(asset, entity):
            continue
        view_key = _view_key(asset)
        if not view_key:
            continue
        current = by_view.get(view_key)
        if current is None or _asset_rank(asset) > _asset_rank(current):
            by_view[view_key] = asset
    return by_view


def _build_visual(entity: StoryEntity, assets: List[Asset]) -> Dict[str, Any]:
    required_views = required_view_keys(entity.entity_type, _entity_role_tier(entity))
    labels = _view_labels(entity.entity_type)
    by_view = _best_asset_by_view(entity, assets)
    ordered_keys = [*required_views, *sorted(key for key in by_view if key not in required_views)]

    views = []
    for view_key in ordered_keys:
        asset = by_view.get(view_key)
        if asset is None:
            continue
        views.append(
            {
                "view_key": view_key,
                "view_label": labels.get(view_key, view_key),
                "asset_id": asset.id,
                "url": asset.url,
                "is_locked": bool(asset.is_locked),
                "is_final": bool(asset.is_final),
                "version": asset.version or 1,
            }
        )

    missing_views = [view_key for view_key in required_views if view_key not in by_view]
    locked_count = sum(1 for view in views if view["is_locked"] and view["is_final"])
    return {
        "views": views,
        "required_views": required_views,
        "missing_views": missing_views,
        "locked_count": locked_count,
    }


async def _build_voice(db: AsyncSession, entity: StoryEntity, story_bible: Optional[StoryBible]) -> Optional[Dict[str, Any]]:
    if entity.entity_type != "character":
        return None
    if story_bible is None:
        return {"voice": None, "voice_speed": None, "story_bible_id": story_bible.id if story_bible else None, "locked": False}

    voice_config = await get_character_voice_from_story_bible(db, entity.name, story_bible.id)
    voice = None
    voice_speed = None
    if voice_config:
        voice = (
            voice_config.get("voice")
            or voice_config.get("voice_model")
            or voice_config.get("voice_profile")
            or voice_config.get("voice_id")
        )
        voice_speed = voice_config.get("voice_speed")
    return {
        "voice": voice,
        "voice_speed": voice_speed,
        "story_bible_id": story_bible.id,
        "locked": bool(voice),
    }


def _character_matches_entity(character: Character, entity: StoryEntity) -> bool:
    names = {entity.name, entity.canonical_name, *[str(alias) for alias in _json_list(entity.aliases)]}
    return bool(character.name and character.name in names)


def _build_profile(entity: StoryEntity, characters: List[Character]) -> Dict[str, Any]:
    attrs = _json_dict(entity.attributes)
    character = next((item for item in characters if _character_matches_entity(item, entity)), None)
    visual_dna = attrs.get("visual_dna") or attrs.get("scene_dna") or attrs.get("prop_dna")
    return {
        "description": entity.description or (character.description if character else None),
        "visual_dna": visual_dna,
        "personality": attrs.get("personality") or (character.personality if character else None),
        "relationships": attrs.get("relationships") or entity.relations or [],
        "forbidden_changes": attrs.get("forbidden_changes") or attrs.get("forbidden") or [],
    }


def _state_for_entity(entity: StoryEntity, story_bible: Optional[StoryBible]) -> Dict[str, Any]:
    if story_bible is None:
        return {}
    state_machine = _json_dict(_json_dict(story_bible.extra_data).get("state_machine"))
    current_state = _json_dict(state_machine.get("current_state"))
    bucket = _json_dict(current_state.get(_entity_refs_key(entity.entity_type)))
    for key in (entity.id, entity.name, entity.canonical_name):
        if key and key in bucket:
            value = bucket.get(key)
            return value if isinstance(value, dict) else {"value": value}
    return {}


async def _usage_for_entity(db: AsyncSession, user_id: str, entity: StoryEntity) -> Dict[str, Any]:
    result = await db.execute(
        select(Shot)
        .where(Shot.user_id == user_id, Shot.extra_data.isnot(None))
        .order_by(desc(Shot.updated_at), desc(Shot.created_at))
        .limit(500)
    )
    refs_key = _entity_refs_key(entity.entity_type)
    shot_count = 0
    last_used_at = None
    for shot in result.scalars().all():
        extra_data = _json_dict(shot.extra_data)
        shot_novel_id = extra_data.get("novel_id")
        if shot_novel_id and entity.novel_id and shot_novel_id != entity.novel_id:
            continue
        if entity.id not in entity_ref_ids(extra_data.get("entity_refs"), refs_key):
            continue
        shot_count += 1
        if last_used_at is None:
            last_used_at = (shot.updated_at or shot.created_at).isoformat() if (shot.updated_at or shot.created_at) else None
        if shot_count >= 50:
            break
    return {"shot_count": shot_count, "last_used_at": last_used_at}


def evaluate_entity_final_readiness(
    entity: StoryEntity, visual: Dict[str, Any], voice: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Evaluate production-card readiness from visual locks and character voice."""
    gaps: List[Dict[str, str]] = []
    fix_url = _asset_fix_url(entity)
    views_by_key = {view["view_key"]: view for view in visual["views"]}
    completed = 0
    total = len(visual["required_views"])

    for view_key in visual["required_views"]:
        view = views_by_key.get(view_key)
        if view is None:
            gaps.append(
                {
                    "code": f"view_missing:{view_key}",
                    "message": f"缺少{view_key}视图定稿资产",
                    "fix_url": fix_url,
                }
            )
            continue
        if not view["is_locked"]:
            gaps.append(
                {
                    "code": f"view_unlocked:{view_key}",
                    "message": f"{view_key}视图尚未锁定",
                    "fix_url": fix_url,
                }
            )
            continue
        if not view["is_final"]:
            gaps.append(
                {
                    "code": f"view_not_final:{view_key}",
                    "message": f"{view_key}视图尚未标记为定稿",
                    "fix_url": fix_url,
                }
            )
            continue
        completed += 1

    if entity.entity_type == "character":
        total += 1
        if voice and voice.get("locked"):
            completed += 1
        else:
            gaps.append(
                {
                    "code": "voice_missing",
                    "message": "角色缺少 Story Bible 声线配置",
                    "fix_url": _story_bible_fix_url(entity),
                }
            )

    score = int(round((completed / total) * 100)) if total else 100
    return {
        "score": score,
        "final_ready": not gaps,
        "gaps": gaps,
    }


async def _load_characters(db: AsyncSession, user_id: str, novel_id: str) -> List[Character]:
    result = await db.execute(
        select(Character).where(
            Character.user_id == user_id,
            or_(Character.novel_id == novel_id, Character.novel_id.is_(None)),
        )
    )
    return list(result.scalars().all())


async def _build_card(
    db: AsyncSession,
    user_id: str,
    entity: StoryEntity,
    assets: List[Asset],
    story_bible: Optional[StoryBible],
    characters: List[Character],
) -> Dict[str, Any]:
    visual = _build_visual(entity, assets)
    voice = await _build_voice(db, entity, story_bible)
    readiness = evaluate_entity_final_readiness(entity, visual, voice)
    return {
        "entity_id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "novel_id": entity.novel_id,
        "visual": visual,
        "voice": voice,
        "profile": _build_profile(entity, characters),
        "state": _state_for_entity(entity, story_bible),
        "usage": await _usage_for_entity(db, user_id, entity),
        "readiness": readiness,
    }


async def build_production_cards_for_novel(db: AsyncSession, user_id: str, novel_id: str) -> Dict[str, Any]:
    await _load_novel(db, user_id, novel_id)
    story_bible = await _load_story_bible(db, user_id, novel_id)
    entities = [
        entity
        for entity in await _load_entities(db, user_id, novel_id)
        if entity.novel_id == novel_id and entity.entity_type in PRODUCTION_CARD_ENTITY_TYPES
    ]
    assets = await _load_assets(db, user_id, novel_id)
    characters = await _load_characters(db, user_id, novel_id)
    cards = [await _build_card(db, user_id, entity, assets, story_bible, characters) for entity in entities]
    ready = sum(1 for card in cards if card["readiness"]["final_ready"])
    return {
        "novel_id": novel_id,
        "cards": cards,
        "summary": {"ready": ready, "incomplete": len(cards) - ready},
    }


async def build_production_card_for_entity(db: AsyncSession, user_id: str, entity_id: str) -> Dict[str, Any]:
    result = await db.execute(select(StoryEntity).where(StoryEntity.id == entity_id, StoryEntity.user_id == user_id))
    entity = result.scalar_one_or_none()
    if entity is None or entity.entity_type not in PRODUCTION_CARD_ENTITY_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定稿卡实体不存在")
    if not entity.novel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="实体未绑定小说")

    await _load_novel(db, user_id, entity.novel_id)
    story_bible = await _load_story_bible(db, user_id, entity.novel_id)
    assets = await _load_assets(db, user_id, entity.novel_id)
    characters = await _load_characters(db, user_id, entity.novel_id)
    return await _build_card(db, user_id, entity, assets, story_bible, characters)


def _story_bible_rule_for_entity(story_bible: Optional[StoryBible], entity: StoryEntity) -> Optional[Dict[str, Any]]:
    if story_bible is None:
        return None
    for rule in story_bible.character_rules or []:
        if not isinstance(rule, dict):
            continue
        if rule.get("entity_id") == entity.id or rule.get("name") == entity.name:
            return rule
    return None


def _is_protagonist(entity: StoryEntity, story_bible: Optional[StoryBible]) -> bool:
    role_tier = _entity_role_tier(entity)
    if role_tier in {"protagonist", "main", "lead", "hero"}:
        return True
    rule = _story_bible_rule_for_entity(story_bible, entity) or {}
    role = str(rule.get("role_tier") or rule.get("role") or "").strip().lower()
    return role in {"protagonist", "main", "lead", "hero"}


def _locked_front_asset(entity: StoryEntity, assets: List[Asset]) -> Optional[Asset]:
    for asset in assets:
        if not _asset_matches_entity(asset, entity):
            continue
        if _view_key(asset) == "front" and asset.is_locked and asset.is_final:
            return asset
    return None


async def _character_occurrence_counts(db: AsyncSession, user_id: str, novel_id: str) -> Dict[str, int]:
    result = await db.execute(select(Shot).where(Shot.user_id == user_id, Shot.extra_data.isnot(None)))
    counts: Dict[str, int] = {}
    for shot in result.scalars().all():
        extra_data = _json_dict(shot.extra_data)
        shot_novel_id = extra_data.get("novel_id")
        if shot_novel_id and shot_novel_id != novel_id:
            continue
        for entity_id in entity_ref_ids(extra_data.get("entity_refs"), "characters"):
            counts[entity_id] = counts.get(entity_id, 0) + 1
    return counts


async def _ensure_story_bible(db: AsyncSession, user_id: str, novel_id: str) -> StoryBible:
    story_bible = await _load_story_bible(db, user_id, novel_id)
    if story_bible is not None:
        return story_bible
    novel = await _load_novel(db, user_id, novel_id)
    story_bible = StoryBible(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=novel_id,
        title=f"{novel.title} Story Bible",
        character_rules=[],
    )
    db.add(story_bible)
    await db.flush()
    return story_bible


def _upsert_supporting_voice_rule(story_bible: StoryBible, entity: StoryEntity, voice: str) -> None:
    rules = [dict(rule) for rule in (story_bible.character_rules or []) if isinstance(rule, dict)]
    for rule in rules:
        if rule.get("entity_id") == entity.id or rule.get("name") == entity.name:
            rule.update({"entity_id": entity.id, "name": entity.name, "role_tier": "supporting", "voice": voice})
            story_bible.character_rules = rules
            return
    rules.append({"entity_id": entity.id, "name": entity.name, "role_tier": "supporting", "voice": voice})
    story_bible.character_rules = rules


async def batch_finalize_supporting_characters(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
    *,
    min_occurrences: int = 2,
    image_model_config_id: Optional[str] = None,
    voice_pool: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Finalize recurring supporting characters with one locked front view and a voice."""
    await _load_novel(db, user_id, novel_id)
    story_bible = await _ensure_story_bible(db, user_id, novel_id)
    entities = [
        entity
        for entity in await _load_entities(db, user_id, novel_id)
        if entity.novel_id == novel_id and entity.entity_type == "character"
    ]
    assets = await _load_assets(db, user_id, novel_id)
    occurrence_counts = await _character_occurrence_counts(db, user_id, novel_id)
    default_voice_pool = _default_supporting_voice_pool()
    voices = [voice for voice in (voice_pool or default_voice_pool) if isinstance(voice, str) and voice.strip()]
    if not voices:
        voices = default_voice_pool

    finalized: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    generator = AssetGenerationService(db, user_id)
    if image_model_config_id:
        await generator.configure_image_model(image_model_config_id)

    for entity in entities:
        occurrences = occurrence_counts.get(entity.id, 0)
        if _is_protagonist(entity, story_bible):
            skipped.append({"entity_id": entity.id, "name": entity.name, "reason": "protagonist", "occurrences": occurrences})
            continue
        if occurrences < min_occurrences:
            skipped.append(
                {
                    "entity_id": entity.id,
                    "name": entity.name,
                    "reason": "occurrence_below_threshold",
                    "occurrences": occurrences,
                }
            )
            continue
        if _locked_front_asset(entity, assets):
            skipped.append({"entity_id": entity.id, "name": entity.name, "reason": "already_finalized", "occurrences": occurrences})
            continue

        generated = await generator.generate_entity_view_assets(
            entity_id=entity.id,
            entity_type="character",
            entity_name=entity.name,
            entity_description=entity.description or entity.appearance or entity.visual_prompt or "",
            style="anime",
            novel_id=novel_id,
            chapter_id=entity.chapter_id,
            script_id=entity.script_id,
            view_keys=["front"],
        )
        asset = await generator.lock_asset_version(generated["front"].id)
        generation_params = {
            **_json_dict(asset.generation_params),
            "source": "supporting_batch_finalize",
            "role_tier": "supporting",
        }
        if image_model_config_id:
            generation_params["image_model_config_id"] = image_model_config_id
        asset.generation_params = generation_params
        attrs = _json_dict(entity.attributes)
        entity.attributes = {**attrs, "role_tier": "supporting"}
        voice = voices[len(finalized) % len(voices)]
        _upsert_supporting_voice_rule(story_bible, entity, voice)
        finalized.append({"entity_id": entity.id, "name": entity.name, "asset_id": asset.id, "voice": voice})
        assets.append(asset)

    await db.commit()
    return {"novel_id": novel_id, "finalized": finalized, "skipped": skipped}
