"""
Shared story prompt context for novel, chapter, storyboard and video generation.

This module keeps generation prompts anchored to the same novel context without
adding new persistence tables. It compacts existing Novel, Chapter, StoryBible
and StoryEntity data into reusable prompt blocks.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Character, Novel, Script, StoryBible, StoryEntity
from app.services.image_prompt_policy import GLOBAL_IMAGE_NEGATIVE_CONSTRAINT
from app.services.entity_extraction_service import ENTITY_TYPES, extract_story_entities
from app.services.story_state_machine import format_state_machine_summary


def compact_text(value: Optional[str], limit: int = 500) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _item_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("title") or "").strip()
    return str(item or "").strip()


def _item_description(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("description", "appearance", "state", "rule", "evidence"):
        value = item.get(key)
        if value:
            return compact_text(str(value), 140)
    return ""


def _format_items(items: Iterable[Any], *, limit: int = 6) -> str:
    parts: List[str] = []
    seen: set[str] = set()
    for item in items:
        name = _item_name(item)
        if not name or name in seen:
            continue
        seen.add(name)
        description = _item_description(item)
        parts.append(f"{name}（{description}）" if description else name)
        if len(parts) >= limit:
            break
    return "、".join(parts)


def _entity_to_item(entity: StoryEntity) -> Dict[str, Any]:
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description or entity.evidence,
        "aliases": entity.aliases or [],
        "entity_type": entity.entity_type,
    }


def _group_entities(entities: Iterable[StoryEntity]) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {"characters": [], "scenes": [], "props": [], "events": []}
    mapping = {
        "character": "characters",
        "scene": "scenes",
        "prop": "props",
        "event": "events",
    }
    seen: set[tuple[str, str]] = set()
    for entity in entities:
        group_key = mapping.get(entity.entity_type)
        if not group_key:
            continue
        dedupe_key = (group_key, entity.name)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        grouped[group_key].append(_entity_to_item(entity))
    return grouped


def _group_extracted_entities(text: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {"characters": [], "scenes": [], "props": [], "events": []}
    mapping = {
        "character": "characters",
        "scene": "scenes",
        "prop": "props",
        "event": "events",
    }
    for entity in extract_story_entities(text, set(ENTITY_TYPES)):
        group_key = mapping.get(entity["entity_type"])
        if group_key:
            grouped[group_key].append(
                {
                    "name": entity["name"],
                    "description": entity.get("description") or entity.get("evidence"),
                    "aliases": entity.get("aliases") or [],
                    "entity_type": entity["entity_type"],
                }
            )
    return grouped


def _merge_grouped_entities(*groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    merged = {"characters": [], "scenes": [], "props": [], "events": []}
    for group in groups:
        for key in merged:
            seen = {item.get("name") for item in merged[key]}
            for item in group.get(key) or []:
                name = item.get("name")
                if name and name not in seen:
                    merged[key].append(item)
                    seen.add(name)
    return merged


def _story_bible_items(story_bible: Optional[StoryBible]) -> Dict[str, List[Any]]:
    if not story_bible:
        return {"characters": [], "scenes": [], "props": [], "events": []}
    return {
        "characters": _json_list(story_bible.character_rules),
        "scenes": _json_list(story_bible.scene_rules),
        "props": _json_list(story_bible.prop_rules),
        "events": _json_list(story_bible.event_timeline),
    }


async def load_story_prompt_context(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
    title: Optional[str] = None,
    genre: Optional[str] = None,
    description: Optional[str] = None,
    style: Optional[str] = None,
    limit_chapters: int = 4,
) -> Dict[str, Any]:
    """Load compact story context for prompt construction."""
    novel: Optional[Novel] = None
    chapter: Optional[Chapter] = None
    script: Optional[Script] = None
    chapters: List[Chapter] = []

    if script_id:
        script_result = await db.execute(
            select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
        )
        script = script_result.scalar_one_or_none()
        if script:
            script_extra = _json_dict(script.extra_data)
            novel_id = novel_id or script.novel_id
            chapter_id = chapter_id or script.chapter_id or script_extra.get("chapter_id")

    if novel_id:
        novel_result = await db.execute(
            select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
        )
        novel = novel_result.scalar_one_or_none()

    if chapter_id:
        chapter_result = await db.execute(
            select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
        )
        chapter = chapter_result.scalar_one_or_none()
        if chapter and not novel:
            novel_result = await db.execute(
                select(Novel).where(and_(Novel.id == chapter.novel_id, Novel.user_id == user_id))
            )
            novel = novel_result.scalar_one_or_none()
            novel_id = novel.id if novel else novel_id

    if novel_id:
        chapter_query = (
            select(Chapter)
            .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
            .order_by(Chapter.chapter_number)
        )
        chapter_result = await db.execute(chapter_query)
        chapters = list(chapter_result.scalars().all())[:limit_chapters]

    story_bible: Optional[StoryBible] = None
    if novel_id:
        story_bible_result = await db.execute(
            select(StoryBible)
            .where(and_(StoryBible.user_id == user_id, StoryBible.novel_id == novel_id))
            .order_by(desc(StoryBible.updated_at))
            .limit(1)
        )
        story_bible = story_bible_result.scalar_one_or_none()

    source_text_parts = [
        title or getattr(novel, "title", None),
        genre or getattr(novel, "genre", None),
        description or getattr(novel, "description", None),
        getattr(chapter, "content", None),
        getattr(script, "title", None),
        getattr(script, "description", None),
        getattr(script, "content", None),
    ]
    source_text_parts.extend(chapter.content for chapter in chapters if chapter.content)
    source_text = "\n".join(part for part in source_text_parts if part)

    entity_group = {"characters": [], "scenes": [], "props": [], "events": []}
    if novel_id:
        entity_filters = [StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id]
        if chapter_id:
            entity_filters.append(or_(StoryEntity.chapter_id == chapter_id, StoryEntity.chapter_id.is_(None)))
        entity_result = await db.execute(
            select(StoryEntity)
            .where(and_(*entity_filters))
            .order_by(desc(StoryEntity.updated_at))
            .limit(80)
        )
        entity_group = _group_entities(entity_result.scalars().all())

        character_result = await db.execute(
            select(Character)
            .where(
                and_(
                    Character.user_id == user_id,
                    or_(Character.novel_id == novel_id, Character.novel_id.is_(None)),
                )
            )
            .order_by(desc(Character.updated_at))
            .limit(20)
        )
        character_items = [
            {
                "name": character.name,
                "description": character.appearance or character.personality or character.description,
                "aliases": [],
                "entity_type": "character",
            }
            for character in character_result.scalars().all()
            if character.name
        ]
        entity_group = _merge_grouped_entities(entity_group, {"characters": character_items, "scenes": [], "props": [], "events": []})

    extracted_group = _group_extracted_entities(source_text) if source_text else {"characters": [], "scenes": [], "props": [], "events": []}
    bible_group = _story_bible_items(story_bible)
    entities = _merge_grouped_entities(entity_group, extracted_group, bible_group)

    chapter_summaries = [
        {
            "id": chapter_item.id,
            "title": chapter_item.title,
            "chapter_number": chapter_item.chapter_number,
            "summary": compact_text(chapter_item.content, 220),
        }
        for chapter_item in chapters
    ]

    return {
        "novel_id": novel_id or getattr(novel, "id", None),
        "chapter_id": chapter_id or getattr(chapter, "id", None),
        "script_id": script_id or getattr(script, "id", None),
        "title": title or getattr(novel, "title", None) or "未命名小说",
        "genre": genre or getattr(novel, "genre", None) or "通用",
        "description": description or getattr(novel, "description", None) or "",
        "style": style or getattr(story_bible, "style", None) or "",
        "worldview": getattr(story_bible, "worldview", None) or "",
        "negative_prompt": getattr(story_bible, "negative_prompt", None) or "",
        "state_machine_summary": format_state_machine_summary(
            _json_dict(getattr(story_bible, "extra_data", None)).get("state_machine")
            if story_bible
            else None
        ),
        "story_bible_id": getattr(story_bible, "id", None),
        "chapter_title": getattr(chapter, "title", None),
        "chapter_summary": compact_text(getattr(chapter, "content", None), 500),
        "script_title": getattr(script, "title", None),
        "script_summary": compact_text(getattr(script, "content", None) or getattr(script, "description", None), 500),
        "chapters": chapter_summaries,
        "characters": entities["characters"],
        "scenes": entities["scenes"],
        "props": entities["props"],
        "events": entities["events"],
    }


def build_story_context_block(context: Dict[str, Any], *, include_chapters: bool = True) -> str:
    lines = [
        f"作品：《{context.get('title') or '未命名小说'}》",
        f"题材：{context.get('genre') or '通用'}",
    ]
    if context.get("description"):
        lines.append(f"简介：{compact_text(context.get('description'), 420)}")
    if context.get("style"):
        lines.append(f"风格：{compact_text(context.get('style'), 260)}")
    if context.get("worldview"):
        lines.append(f"世界观：{compact_text(context.get('worldview'), 360)}")

    for key, label in (
        ("characters", "人物角色"),
        ("scenes", "场景环境"),
        ("props", "关键道具"),
        ("events", "关键事件"),
    ):
        summary = _format_items(context.get(key) or [], limit=8)
        if summary:
            lines.append(f"{label}：{summary}")

    if context.get("state_machine_summary"):
        lines.append("Story Bible 状态机：\n" + compact_text(context.get("state_machine_summary"), 900))

    if include_chapters and context.get("chapters"):
        chapter_lines = []
        for chapter in context["chapters"][:4]:
            if chapter.get("summary"):
                chapter_lines.append(f"第{chapter.get('chapter_number')}章《{chapter.get('title')}》：{chapter.get('summary')}")
        if chapter_lines:
            lines.append("已保存章节承接：\n" + "\n".join(chapter_lines))

    return "\n".join(lines)


def build_cover_prompt(context: Dict[str, Any], *, user_prompt: Optional[str] = None, style: str = "anime") -> str:
    parts = [
        "动漫小说封面生成任务。",
        build_story_context_block(context, include_chapters=True),
    ]
    if user_prompt:
        parts.append(f"用户补充要求：{compact_text(user_prompt, 260)}")
    if style:
        parts.append(f"画风标签：{compact_text(style, 80)} style")
    parts.append(
        "封面画面要求：竖版海报构图，主体清晰，优先呈现主要人物与核心场景，"
        "把关键事件或道具作为视觉钩子，画面应符合题材气质并能暗示故事冲突。"
    )
    parts.append(
        "一致性硬约束：不要新增与小说无关的主角，不要改变人物身份、年龄感、服装气质、"
        "关键道具外观和主要场景时代氛围；封面画面不要生成可读文字排版。"
    )
    parts.append(GLOBAL_IMAGE_NEGATIVE_CONSTRAINT)
    if context.get("negative_prompt"):
        parts.append(f"负面约束：{compact_text(context.get('negative_prompt'), 240)}")
    return "\n".join(part for part in parts if part).strip()


def build_chapter_continuity_block(context: Dict[str, Any]) -> str:
    return (
        "【小说连续性上下文】\n"
        f"{build_story_context_block(context, include_chapters=True)}\n"
        "写作时必须让人物动机、事件因果、场景位置、道具状态和对话口吻承接以上信息；"
        "新增内容要能继续进入分镜、镜头、配音、字幕和视频生成。"
    )


def build_shot_dialogue_context(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": context.get("title"),
        "genre": context.get("genre"),
        "characters": context.get("characters") or [],
        "scenes": context.get("scenes") or [],
        "props": context.get("props") or [],
        "events": context.get("events") or [],
        "style": context.get("style"),
    }


def build_video_continuity_constraints(context: Dict[str, Any]) -> str:
    return (
        "动漫连续性硬约束：视频必须承接同一小说、章节、剧本、分镜和镜头上下文；"
        "人物脸型、发型、服装、年龄感、身份关系和说话口吻必须稳定；"
        "场景空间、天气光影、关键道具状态、事件结果和对白字幕必须与上游一致；"
        "不要新增无关角色，不要改变关键事件结论，不要让字幕与人物口型/对白含义冲突。\n"
        f"{build_story_context_block(context, include_chapters=False)}"
    )
