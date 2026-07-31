"""
Consistency context helpers for generation endpoints.

The goal is to keep story, character and shot constraints flowing through all
generation tasks without making each endpoint duplicate ownership and prompt
composition logic.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_registry import get_task_default
from app.core.time_utils import utc_now
from app.models import Character, Project, Script, Shot, StoryBible, StoryEntity, Storyboard
from app.services.entity_extraction_service import ENTITY_TYPES
from app.services.entity_review_service import run_candidate_entity_extraction
from app.services.entity_ref_normalizer import normalize_entity_refs
from app.services.prompt_composer import compose_generation_prompt
from app.services.prompt_skill_service import active_prompt_skill_entries
from app.services.story_entity_lifecycle import query_story_entities_for_prompt_context


def _compact_ids(values: Iterable[Optional[str]]) -> List[str]:
    seen: dict[str, None] = {}
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return list(seen.keys())


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _name_tokens(ref: Dict[str, Any]) -> List[str]:
    values = [ref.get("name")]
    values.extend(ref.get("aliases") or [])
    return [value for value in values if isinstance(value, str) and value.strip()]


def _entity_ref(entity: StoryEntity, character: Optional[Character] = None) -> Dict[str, Any]:
    visual_dna = _json_dict(_json_dict(entity.attributes).get("visual_dna"))
    ref = {
        "entity_id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "description": entity.description,
        "aliases": entity.aliases or [],
        "confidence": entity.confidence or 0,
        "source": entity.source or "deterministic",
        "visual_dna": visual_dna,
    }
    if character:
        ref.update(
            {
                "character_id": character.id,
                "appearance": character.appearance,
                "avatar": character.avatar,
                "personality": character.personality,
                "voice": character.voice,
            }
        )
    return ref


NOISE_CHARACTER_NAME_MARKERS = ("因果", "小说", "对白", "字幕", "标注", "关键", "与", "并", "来的不")
NOISE_CHARACTER_EXACT_NAMES = {"霓虹", "追来的不"}
NOISE_CHARACTER_SCENE_SUFFIXES = ("列车", "车站", "站台", "车厢")
NOISE_CHARACTER_RECIPIENT_PREFIXES = ("对", "向", "给", "把", "将", "被")
NOISE_PROP_NAMES = {
    "开场钩",
    "视觉钩",
    "本场视觉钩",
    "成为本场视觉钩",
    "下一集钩",
    "形成下一集钩",
    "最后一句钩",
    "保留最后一句钩",
    "拉镜",
    "推镜",
    "摇镜",
    "运镜",
    "镜",
    "紧铜铃",
    "对孙剑",
    "白色药",
}
NOISE_PROP_HOOK_MARKERS = ("开场", "结尾", "视觉", "本场", "下一集", "最后一句", "保留", "形成", "成为")
NOISE_PROP_CAMERA_MARKERS = ("拉", "推", "摇", "运", "跟", "固定", "全景", "近景", "中景", "远景", "特写")
NOISE_SCENE_COPY_MARKERS = ("这一刻", "指向", "推向", "注意力", "重新", "保证", "字幕", "对白")
NOISE_PROP_COPY_MARKERS = ("推向", "指向", "注意到", "注意力", "重新", "刻着", "守住", "吹灭")


def _is_noise_character_entity(entity: StoryEntity) -> bool:
    if entity.entity_type != "character":
        return False
    name = (entity.name or "").strip()
    if not name:
        return True
    if name in NOISE_CHARACTER_EXACT_NAMES:
        return True
    if len(name) > 2 and name.startswith(NOISE_CHARACTER_RECIPIENT_PREFIXES):
        return True
    if name.endswith(NOISE_CHARACTER_SCENE_SUFFIXES):
        return True
    return any(marker in name for marker in NOISE_CHARACTER_NAME_MARKERS)


def _is_noise_prop_entity(entity: StoryEntity) -> bool:
    if entity.entity_type != "prop":
        return False
    name = (entity.name or "").strip()
    if not name:
        return True
    if name in NOISE_PROP_NAMES:
        return True
    if name.endswith("钩") and any(marker in name for marker in NOISE_PROP_HOOK_MARKERS):
        return True
    if name.endswith("镜") and any(marker in name for marker in NOISE_PROP_CAMERA_MARKERS):
        return True
    if any(marker in name for marker in NOISE_PROP_COPY_MARKERS) and len(name) > 4:
        return True
    return False


def _is_noise_scene_entity(entity: StoryEntity) -> bool:
    if entity.entity_type != "scene":
        return False
    name = (entity.name or "").strip()
    if not name:
        return True
    if any(marker in name for marker in NOISE_SCENE_COPY_MARKERS):
        return True
    return False


def _is_noise_story_entity(entity: StoryEntity) -> bool:
    return (
        _is_noise_character_entity(entity)
        or _is_noise_prop_entity(entity)
        or _is_noise_scene_entity(entity)
    )


def _summarize_refs(refs: List[Dict[str, Any]]) -> str:
    parts = []
    for ref in refs:
        name = ref.get("name")
        visual_dna = _json_dict(ref.get("visual_dna"))
        description = ref.get("description") or ref.get("appearance") or "；".join(str(value) for value in visual_dna.values() if value)
        if name and description:
            parts.append(f"{name}: {description}")
        elif name:
            parts.append(str(name))
    return "；".join(parts)


def _merge_prompt_scope_entities(
    chapter_entities: List[StoryEntity], novel_entities: List[StoryEntity],
) -> List[StoryEntity]:
    """Keep chapter context while inheriting approved novel-wide identity locks."""
    merged = list(chapter_entities)
    seen = {entity.id for entity in merged}
    for entity in novel_entities:
        if entity.entity_type == "character" and entity.id not in seen:
            merged.append(entity)
            seen.add(entity.id)
    return merged


def _character_scope_rank(character: Character, novel_id: Optional[str], chapter_id: Optional[str]) -> int:
    if chapter_id and character.chapter_id == chapter_id:
        return 3
    if novel_id and character.novel_id == novel_id:
        return 2
    if character.novel_id is None:
        return 1
    return 0


def _build_character_name_index(
    characters: Iterable[Character],
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str],
) -> Dict[str, Character]:
    indexed: Dict[str, Character] = {}
    ranks: Dict[str, int] = {}
    for character in characters:
        if not character.name:
            continue
        rank = _character_scope_rank(character, novel_id, chapter_id)
        existing_rank = ranks.get(character.name, -1)
        if rank > existing_rank:
            indexed[character.name] = character
            ranks[character.name] = rank
    return indexed


def match_entities_to_text(
    entities: List[StoryEntity], text: str
) -> Dict[str, List[StoryEntity]]:
    """Match entities against text using name and aliases.

    Returns grouped matches by entity_type.
    """
    matched: Dict[str, List[StoryEntity]] = {}
    if not text:
        return matched

    haystack = text.lower()
    for entity in entities:
        names = [entity.name] + list(entity.aliases or [])
        if any(name and name.lower() in haystack for name in names if isinstance(name, str)):
            matched.setdefault(entity.entity_type, []).append(entity)
    return matched


def _select_fallback_entities_for_generation(
    entities: List[StoryEntity],
    grouped: Dict[str, List[StoryEntity]],
    *,
    max_total: int = 36,
) -> Dict[str, List[StoryEntity]]:
    """Fill missing entity groups without the old tiny 2/1/1/1 caps.

    Matched groups are left intact. Only missing groups receive high-confidence
    fallback entities, bounded by an overall prompt budget instead of fixed
    per-type counts.
    """
    result: Dict[str, List[StoryEntity]] = {
        entity_type: list(grouped.get(entity_type) or [])
        for entity_type in ENTITY_TYPES
    }
    remaining = max(0, max_total - sum(len(items) for items in result.values()))
    if remaining <= 0:
        return result

    for entity_type in ("character", "scene", "prop", "event"):
        if result.get(entity_type):
            continue
        fallback = sorted(
            [entity for entity in entities if entity.entity_type == entity_type],
            key=lambda entity: (entity.confidence or 0, len(entity.name or "")),
            reverse=True,
        )
        if not fallback:
            continue
        selected = fallback[:remaining]
        result[entity_type] = selected
        remaining -= len(selected)
        if remaining <= 0:
            break
    return result


async def load_or_extract_story_entities(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str] = None,
    text: Optional[str] = None,
    persist_missing: bool = True,
) -> List[StoryEntity]:
    """Load story entities and optionally create deterministic missing ones.

    This keeps generation endpoints usable even when the user has not manually
    run the entity extraction workflow yet.
    """
    if not novel_id and not chapter_id:
        return []

    entities = await query_story_entities_for_prompt_context(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
    )
    if novel_id and chapter_id:
        novel_entities = await query_story_entities_for_prompt_context(
            db, user_id=user_id, novel_id=novel_id,
        )
        entities = _merge_prompt_scope_entities(entities, novel_entities)

    if not persist_missing or not text:
        return entities

    await run_candidate_entity_extraction(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        source_type="chapter" if chapter_id else "novel",
        source_id=chapter_id or novel_id,
        text=text,
        entity_types=sorted(ENTITY_TYPES),
        persist=True,
    )
    refreshed = await query_story_entities_for_prompt_context(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
    )
    if novel_id and chapter_id:
        novel_entities = await query_story_entities_for_prompt_context(
            db, user_id=user_id, novel_id=novel_id,
        )
        return _merge_prompt_scope_entities(refreshed, novel_entities)
    return refreshed


async def build_shot_entity_context(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str] = None,
    source_text: Optional[str] = None,
    shot_text: Optional[str] = None,
) -> Dict[str, Any]:
    entities = await load_or_extract_story_entities(
        db,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        text=source_text,
        persist_missing=True,
    )
    if not entities:
        return {
            "character_refs": [],
            "scene_refs": [],
            "prop_refs": [],
            "event_refs": [],
            "entity_refs": {"characters": [], "scenes": [], "props": [], "events": []},
            "environment_context": None,
        }
    entities = [entity for entity in entities if not _is_noise_story_entity(entity)]
    if not entities:
        return {
            "character_refs": [],
            "scene_refs": [],
            "prop_refs": [],
            "event_refs": [],
            "entity_refs": {"characters": [], "scenes": [], "props": [], "events": []},
            "environment_context": None,
        }

    character_filters = [Character.user_id == user_id]
    if novel_id:
        character_filters.append(or_(Character.novel_id == novel_id, Character.novel_id.is_(None)))
    elif chapter_id:
        character_filters.append(or_(Character.chapter_id == chapter_id, Character.novel_id.is_(None)))
    character_result = await db.execute(select(Character).where(and_(*character_filters)))
    characters = list(character_result.scalars().all())
    character_by_name = _build_character_name_index(characters, novel_id=novel_id, chapter_id=chapter_id)

    haystack = shot_text or ""
    grouped: Dict[str, List[StoryEntity]] = {entity_type: [] for entity_type in ENTITY_TYPES}
    for entity in entities:
        names = [entity.name] + list(entity.aliases or [])
        matched = any(name and name in haystack for name in names)
        if matched:
            grouped.setdefault(entity.entity_type, []).append(entity)

    grouped = _select_fallback_entities_for_generation(entities, grouped)

    character_refs = [
        _entity_ref(entity, character_by_name.get(entity.name))
        for entity in grouped.get("character", [])
    ]
    scene_refs = [_entity_ref(entity) for entity in grouped.get("scene", [])]
    prop_refs = [_entity_ref(entity) for entity in grouped.get("prop", [])]
    event_refs = [_entity_ref(entity) for entity in grouped.get("event", [])]
    environment_parts = []
    for label, refs in (("场景", scene_refs), ("道具", prop_refs), ("事件", event_refs)):
        summary = _summarize_refs(refs)
        if summary:
            environment_parts.append(f"{label}: {summary}")

    return {
        "character_refs": character_refs,
        "scene_refs": scene_refs,
        "prop_refs": prop_refs,
        "event_refs": event_refs,
        "entity_refs": {
            "characters": character_refs,
            "scenes": scene_refs,
            "props": prop_refs,
            "events": event_refs,
        },
        "environment_context": "；".join(environment_parts) or None,
    }


def _ids_from_character_refs(refs: Any) -> List[str]:
    if not isinstance(refs, list):
        return []

    ids: List[Optional[str]] = []
    for ref in refs:
        if isinstance(ref, str):
            ids.append(ref)
        elif isinstance(ref, dict):
            ids.append(ref.get("character_id") or ref.get("id"))
    return _compact_ids(ids)


async def get_story_bible_for_context(
    db: AsyncSession,
    user_id: str,
    *,
    story_bible_id: Optional[str] = None,
    project_id: Optional[str] = None,
    novel_id: Optional[str] = None,
) -> Optional[StoryBible]:
    """Load an explicit Story Bible or the most recent matching default."""
    if story_bible_id:
        result = await db.execute(
            select(StoryBible).where(StoryBible.id == story_bible_id, StoryBible.user_id == user_id)
        )
        story_bible = result.scalar_one_or_none()
        if story_bible is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Story Bible 不存在",
            )
        return story_bible

    filters = [StoryBible.user_id == user_id]
    scope_filters = []
    if project_id:
        scope_filters.append(StoryBible.project_id == project_id)
    if novel_id:
        scope_filters.append(StoryBible.novel_id == novel_id)
    if not scope_filters:
        return None

    result = await db.execute(
        select(StoryBible)
        .where(*filters, or_(*scope_filters))
        .order_by(desc(StoryBible.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_project_for_context(
    db: AsyncSession,
    user_id: str,
    project_id: Optional[str],
    *,
    strict: bool = False,
) -> Optional[Project]:
    if not project_id:
        return None
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None and strict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return project


async def get_shot_for_context(
    db: AsyncSession,
    user_id: str,
    shot_id: Optional[str],
) -> tuple[Optional[Shot], Optional[Storyboard], Optional[Script]]:
    if not shot_id:
        return None, None, None

    shot_result = await db.execute(select(Shot).where(Shot.id == shot_id, Shot.user_id == user_id))
    shot = shot_result.scalar_one_or_none()
    if shot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    storyboard_result = await db.execute(
        select(Storyboard).where(Storyboard.id == shot.storyboard_id, Storyboard.user_id == user_id)
    )
    storyboard = storyboard_result.scalar_one_or_none()

    script = None
    if storyboard and storyboard.script_id:
        script_result = await db.execute(
            select(Script).where(Script.id == storyboard.script_id, Script.user_id == user_id)
        )
        script = script_result.scalar_one_or_none()

    return shot, storyboard, script


async def get_characters_for_context(
    db: AsyncSession,
    user_id: str,
    *,
    character_ids: Optional[List[str]] = None,
    shot: Optional[Shot] = None,
    fallback_character_id: Optional[str] = None,
    novel_id: Optional[str] = None,
) -> List[Character]:
    ids = _compact_ids((character_ids or []) + _ids_from_character_refs(getattr(shot, "character_refs", None)))
    if fallback_character_id:
        ids = _compact_ids(ids + [fallback_character_id])
    if not ids:
        return []

    result = await db.execute(select(Character).where(Character.id.in_(ids), Character.user_id == user_id))
    characters = list(result.scalars().all())
    found_ids = {character.id for character in characters}
    missing = [item for item in ids if item not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"角色不存在: {', '.join(missing)}",
        )
    if novel_id:
        mismatched = [
            character.name
            for character in characters
            if character.novel_id and character.novel_id != novel_id
        ]
        if mismatched:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"角色不属于当前小说: {', '.join(mismatched)}",
            )
    return characters


def _locked_asset_refs_from_extra(extra_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    locked_assets = extra_data.get("locked_assets")
    if isinstance(locked_assets, dict):
        iterable = locked_assets.values()
    elif isinstance(locked_assets, list):
        iterable = locked_assets
    else:
        iterable = []

    for item in iterable:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "type": item.get("category") or item.get("entity_type") or item.get("type") or "资产",
                "name": item.get("asset_name") or item.get("entity_name") or item.get("name") or "Unknown",
                "description": item.get("description"),
                "asset_id": item.get("asset_id"),
                "entity_id": item.get("entity_id"),
                "url": item.get("asset_url") or item.get("url") or item.get("thumbnail_url"),
                "version": item.get("version"),
            }
        )

    production_context = _json_dict(extra_data.get("production_context"))
    asset_version_locks = production_context.get("asset_version_locks")
    if isinstance(asset_version_locks, list):
        for item in asset_version_locks:
            if not isinstance(item, dict):
                continue
            refs.append(
                {
                    "type": item.get("category") or item.get("entity_type") or item.get("type") or "资产",
                    "name": item.get("entity_name") or item.get("asset_name") or item.get("name") or "Unknown",
                    "description": item.get("description"),
                    "asset_id": item.get("asset_id"),
                    "entity_id": item.get("entity_id"),
                    "url": item.get("url") or item.get("thumbnail_url"),
                    "version": item.get("version"),
                }
            )

    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for ref in refs:
        key = str(ref.get("asset_id") or ref.get("entity_id") or ref.get("name") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(ref)
    return deduped


async def build_consistency_prompt(
    db: AsyncSession,
    user_id: str,
    *,
    task: str,
    base_prompt: Optional[str] = None,
    story_bible_id: Optional[str] = None,
    project_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    character_ids: Optional[List[str]] = None,
    fallback_character_id: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return composed prompt and resolved context metadata."""
    shot, storyboard, script = await get_shot_for_context(db, user_id, shot_id)
    inferred_novel_id = novel_id or getattr(storyboard, "novel_id", None) or getattr(script, "novel_id", None)

    project = await get_project_for_context(db, user_id, project_id, strict=False)
    story_bible = await get_story_bible_for_context(
        db,
        user_id,
        story_bible_id=story_bible_id,
        project_id=project_id,
        novel_id=inferred_novel_id,
    )
    characters = await get_characters_for_context(
        db,
        user_id,
        character_ids=character_ids,
        shot=shot,
        fallback_character_id=fallback_character_id,
        novel_id=inferred_novel_id,
    )

    context = dict(extra_context or {})
    if base_prompt:
        context["用户提示词"] = base_prompt
    if storyboard:
        context.setdefault("分镜标题", storyboard.title)
        if getattr(storyboard, "style", None):
            context.setdefault("分镜风格", storyboard.style)
        if getattr(storyboard, "genre", None):
            context.setdefault("分镜题材", storyboard.genre)
        if getattr(storyboard, "description", None):
            context.setdefault("分镜说明", storyboard.description)
    if script:
        context.setdefault("剧本标题", script.title)
        if getattr(script, "style", None):
            context.setdefault("剧本风格", script.style)
        if getattr(script, "genre", None):
            context.setdefault("剧本题材", script.genre)
        if getattr(script, "description", None):
            context.setdefault("剧本说明", script.description)
    if shot:
        shot_extra = _json_dict(shot.extra_data)
        context.setdefault("镜头编号", shot.shot_number)
        entity_refs = normalize_entity_refs(shot_extra.get("entity_refs"))
        for key, label in (
            ("characters", "本镜头人物实体"),
            ("scenes", "本镜头场景实体"),
            ("props", "本镜头道具实体"),
            ("events", "本镜头事件实体"),
        ):
            summary = _summarize_refs(entity_refs.get(key) or [])
            if summary:
                context.setdefault(label, summary)
        if shot_extra.get("environment_context"):
            context.setdefault("场景环境连续性", shot_extra["environment_context"])
        subtitle_text = shot_extra.get("subtitle_text") or shot.dialogue
        if subtitle_text:
            context.setdefault("字幕/对白文本", subtitle_text)
    locked_assets = _locked_asset_refs_from_extra(_json_dict(getattr(shot, "extra_data", None))) if shot else []
    prompt_skill_entries = await active_prompt_skill_entries(db, user_id, task=task, context=context)

    prompt = compose_generation_prompt(
        task=task,
        shot=shot,
        story_bible=story_bible,
        characters=characters,
        project=project,
        extra_context=context,
        locked_assets=locked_assets,
        skill_blocks=[entry["content"] for entry in prompt_skill_entries],
    )

    task_default = get_task_default(task)
    return {
        "prompt": prompt,
        "story_bible": story_bible,
        "project": project,
        "shot": shot,
        "storyboard": storyboard,
        "script": script,
        "characters": characters,
        "task_default": task_default,
        "metadata": {
            "task": task,
            "story_bible_id": story_bible.id if story_bible else story_bible_id,
            "project_id": project.id if project else project_id,
            "novel_id": inferred_novel_id,
            "shot_id": shot.id if shot else shot_id,
            "character_ids": [character.id for character in characters],
            "entity_refs": normalize_entity_refs(_json_dict(getattr(shot, "extra_data", None)).get("entity_refs")) if shot else {},
            "locked_assets": locked_assets,
            "prompt_skill_count": len(prompt_skill_entries),
            "prompt_skills": [
                {**{key: entry[key] for key in ("id", "name", "task", "stage", "version")}, "prompt_profile_version_id": entry.get("prompt_profile_version_id")}
                for entry in prompt_skill_entries
            ],
            "subtitle_text": (_json_dict(getattr(shot, "extra_data", None)).get("subtitle_text") or getattr(shot, "dialogue", None)) if shot else None,
            "default_model_id": task_default.get("default_model_id") if task_default else None,
        },
    }


async def auto_fill_shot_entity_refs(
    db: AsyncSession,
    shot: Shot,
    novel_id: Optional[str],
    chapter_id: Optional[str],
) -> Shot:
    """Fill or refresh entity_refs for a single shot based on its content and context.

    This function updates the shot's extra_data with fresh entity references by
    re-analyzing the shot's prompt, dialogue, visual_description, and other text fields.

    Args:
        db: Database session
        shot: The shot to update
        novel_id: Novel ID for entity lookup scope
        chapter_id: Chapter ID for entity lookup scope

    Returns:
        The updated shot object
    """
    shot_text = _shot_text_from_values(
        shot.prompt,
        shot.dialogue,
        shot.visual_description,
        getattr(shot, "ambient_sound", None),
        getattr(shot, "sfx_cue", None),
        getattr(shot, "music_cue", None),
    )

    entity_context = await build_shot_entity_context(
        db,
        shot.user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        source_text=None,  # Don't re-extract, just match existing entities
        shot_text=shot_text,
    )

    extra_data = dict(_json_dict(shot.extra_data))
    extra_data["entity_refs"] = normalize_entity_refs(entity_context["entity_refs"])
    extra_data["scene_refs"] = entity_context["scene_refs"]
    extra_data["prop_refs"] = entity_context["prop_refs"]
    extra_data["event_refs"] = entity_context["event_refs"]
    extra_data["environment_context"] = entity_context["environment_context"]
    extra_data["entity_refs_filled_at"] = utc_now().isoformat()

    shot.extra_data = extra_data
    shot.character_refs = entity_context["character_refs"]
    shot.updated_at = utc_now()

    return shot


def _shot_text_from_values(*values: Optional[str]) -> str:
    """Concatenate non-empty string values into a single text for entity matching."""
    return " ".join(v for v in values if v)
