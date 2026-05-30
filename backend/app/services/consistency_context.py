"""
Consistency context helpers for generation endpoints.

The goal is to keep story, character and shot constraints flowing through all
generation tasks without making each endpoint duplicate ownership and prompt
composition logic.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_registry import get_task_default
from app.core.time_utils import utc_now
from app.models import Character, Project, Script, Shot, StoryBible, StoryEntity, Storyboard
from app.services.entity_extraction_service import ENTITY_TYPES, extract_story_entities
from app.services.prompt_composer import compose_generation_prompt


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
    ref = {
        "entity_id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "description": entity.description,
        "aliases": entity.aliases or [],
        "confidence": entity.confidence or 0,
        "source": entity.source or "deterministic",
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


def _summarize_refs(refs: List[Dict[str, Any]]) -> str:
    parts = []
    for ref in refs:
        name = ref.get("name")
        description = ref.get("description") or ref.get("appearance")
        if name and description:
            parts.append(f"{name}: {description}")
        elif name:
            parts.append(str(name))
    return "；".join(parts)


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


async def auto_fill_shot_entity_refs(
    db: AsyncSession,
    shot: Shot,
    user_id: str,
    novel_id: str,
    chapter_id: Optional[str] = None,
) -> Shot:
    """Automatically fill shot.extra_data.entity_refs based on shot content.

    Loads or extracts story entities, then matches them against the shot's
    prompt, dialogue, and visual_description fields.
    """
    # 1. Build shot text from all relevant fields
    shot_text_parts = [shot.prompt or "", shot.dialogue or ""]
    extra_data = _json_dict(shot.extra_data)
    if extra_data.get("visual_description"):
        shot_text_parts.append(extra_data["visual_description"])
    shot_text = " ".join(part for part in shot_text_parts if part)

    # 2. Load or extract entities for matching
    entities = await load_or_extract_story_entities(
        db,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        text=shot_text,
        persist_missing=False,  # Don't create new entities during auto-fill
    )

    # 3. Match entities to shot text
    matched = match_entities_to_text(entities, shot_text)

    # 4. Build entity_refs structure with entity IDs
    entity_refs = {
        "characters": [e.id for e in matched.get("character", [])],
        "scenes": [e.id for e in matched.get("scene", [])],
        "props": [e.id for e in matched.get("prop", [])],
        "events": [e.id for e in matched.get("event", [])],
    }

    # 5. Update shot.extra_data
    extra_data["entity_refs"] = entity_refs
    shot.extra_data = extra_data

    return shot


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

    query = select(StoryEntity).where(StoryEntity.user_id == user_id)
    if novel_id:
        query = query.where(StoryEntity.novel_id == novel_id)
    if chapter_id:
        query = query.where(or_(StoryEntity.chapter_id == chapter_id, StoryEntity.chapter_id.is_(None)))
    result = await db.execute(query.order_by(desc(StoryEntity.updated_at)))
    entities = list(result.scalars().all())

    if not persist_missing or not text:
        return entities

    known = {(entity.entity_type, entity.name) for entity in entities}
    try:
        extracted = extract_story_entities(text, set(ENTITY_TYPES))
    except ValueError:
        extracted = []

    created: List[StoryEntity] = []
    for item in extracted:
        key = (item["entity_type"], item["name"])
        if key in known:
            continue
        entity = StoryEntity(
            id=str(uuid4()),
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            entity_type=item["entity_type"],
            name=item["name"],
            description=item.get("description"),
            aliases=item.get("aliases") or [],
            attributes=item.get("attributes") or {},
            evidence=item.get("evidence"),
            confidence=item.get("confidence") or 100,
            source=item.get("source") or "deterministic",
        )
        db.add(entity)
        created.append(entity)
        known.add(key)

    if created:
        await db.flush()
        entities.extend(created)
    return entities


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

    for entity_type, limit in (("character", 2), ("scene", 1), ("prop", 1), ("event", 1)):
        if grouped.get(entity_type):
            continue
        fallback = sorted(
            [entity for entity in entities if entity.entity_type == entity_type],
            key=lambda entity: (len(entity.name or ""), entity.confidence or 0),
            reverse=True,
        )
        grouped[entity_type] = fallback[:limit]

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
        entity_refs = _json_dict(shot_extra.get("entity_refs"))
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

    prompt = compose_generation_prompt(
        task=task,
        shot=shot,
        story_bible=story_bible,
        characters=characters,
        project=project,
        extra_context=context,
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
            "entity_refs": _json_dict(getattr(shot, "extra_data", None)).get("entity_refs") if shot else {},
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
    extra_data["entity_refs"] = entity_context["entity_refs"]
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
