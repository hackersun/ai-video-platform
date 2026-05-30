"""
Novel-level continuity package for long-form anime production.

This service turns the whole novel into a stable continuity contract that can
be reused by script, storyboard, shot and video generation.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Novel, StoryBible, StoryEntity
from app.services.story_prompt_context import compact_text
from app.services.story_state_machine import build_story_state_machine, format_state_machine_summary


MAX_PROVIDER_SEED = 2_147_483_647


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def derive_stable_seed(parts: List[Optional[Any]]) -> Optional[int]:
    seed_source = "|".join(str(part) for part in parts if part)
    if not seed_source:
        return None
    digest = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % MAX_PROVIDER_SEED) or 1


def _chapter_summary(chapter: Optional[Chapter], *, limit: int = 420) -> Optional[Dict[str, Any]]:
    if not chapter:
        return None
    return {
        "id": chapter.id,
        "title": chapter.title,
        "chapter_number": chapter.chapter_number,
        "summary": compact_text(chapter.content, limit),
    }


def _select_neighbor_chapters(chapters: List[Chapter], chapter_id: Optional[str]) -> tuple[Optional[Chapter], Optional[Chapter], Optional[Chapter]]:
    if not chapters:
        return None, None, None
    if not chapter_id:
        return None, chapters[0], chapters[1] if len(chapters) > 1 else None
    for index, chapter in enumerate(chapters):
        if chapter.id == chapter_id:
            previous_chapter = chapters[index - 1] if index > 0 else None
            next_chapter = chapters[index + 1] if index < len(chapters) - 1 else None
            return previous_chapter, chapter, next_chapter
    return None, None, None


def _state_summary(state: Dict[str, Any], *, limit: int = 6) -> str:
    if not state:
        return ""
    lines: List[str] = []
    for key, label in (("characters", "人物"), ("scenes", "场景"), ("props", "道具")):
        values = _json_dict(state.get(key))
        if not values:
            continue
        parts = []
        for name, payload in list(values.items())[:limit]:
            if isinstance(payload, dict):
                detail = (
                    payload.get("state")
                    or payload.get("costume")
                    or payload.get("weather")
                    or payload.get("lighting")
                    or payload.get("owner")
                    or "已记录"
                )
                parts.append(f"{name}：{detail}")
            else:
                parts.append(str(name))
        if parts:
            lines.append(f"{label}状态：" + "；".join(parts))
    events = _json_list(state.get("events"))
    if events:
        event_parts = []
        for event in events[-limit:]:
            if isinstance(event, dict):
                event_parts.append(str(event.get("name") or event.get("title") or "事件"))
        if event_parts:
            lines.append("事件状态：" + "；".join(event_parts))
    return "\n".join(lines)


def _snapshot_summary(snapshot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not snapshot:
        return None
    return {
        "chapter_id": snapshot.get("chapter_id"),
        "chapter_number": snapshot.get("chapter_number"),
        "title": snapshot.get("title"),
        "summary": compact_text(snapshot.get("summary"), 320),
        "state_summary": _state_summary(
            {
                "characters": snapshot.get("characters"),
                "scenes": snapshot.get("scenes"),
                "props": snapshot.get("props"),
                "events": snapshot.get("events"),
            },
            limit=6,
        ),
    }


def _find_snapshot(state_machine: Dict[str, Any], chapter_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not chapter_id:
        return None
    for snapshot in _json_list(state_machine.get("chapter_snapshots")):
        if isinstance(snapshot, dict) and snapshot.get("chapter_id") == chapter_id:
            return snapshot
    return None


def _event_tail(state_machine: Dict[str, Any], *, chapter_number: Optional[int], limit: int = 8) -> List[Dict[str, Any]]:
    events = [event for event in _json_list(state_machine.get("event_timeline")) if isinstance(event, dict)]
    if chapter_number:
        events = [event for event in events if not event.get("chapter_number") or event.get("chapter_number") <= chapter_number]
    return [
        {
            "name": event.get("name") or event.get("title"),
            "chapter_number": event.get("chapter_number"),
            "summary": compact_text(event.get("description") or event.get("evidence") or event.get("state"), 180),
        }
        for event in events[-limit:]
    ]


def _entity_locks(entities: List[StoryEntity], *, limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {"characters": [], "scenes": [], "props": [], "events": []}
    mapping = {
        "character": "characters",
        "scene": "scenes",
        "prop": "props",
        "event": "events",
    }
    seen: set[tuple[str, str]] = set()
    for entity in entities:
        key = mapping.get(entity.entity_type)
        if not key:
            continue
        dedupe = (key, entity.name)
        if dedupe in seen or len(grouped[key]) >= limit:
            continue
        seen.add(dedupe)
        attrs = _json_dict(entity.attributes)
        grouped[key].append(
            {
                "id": entity.id,
                "name": entity.name,
                "description": compact_text(entity.description or entity.evidence, 180),
                "chapter_id": entity.chapter_id,
                "visual_dna": attrs.get("visual_dna") or attrs.get("scene_dna") or attrs.get("prop_dna"),
                "state": attrs.get("state"),
                "owner": attrs.get("owner"),
                "source": entity.source,
            }
        )
    return grouped


def format_continuity_prompt_block(package: Dict[str, Any]) -> str:
    if not package:
        return "【整部小说连续性锁】\n未找到小说级连续性上下文。"
    continuity_lock = _json_dict(package.get("continuity_lock"))
    previous_context = _json_dict(package.get("previous_chapter_context"))
    current_context = _json_dict(package.get("current_chapter_context"))
    next_context = _json_dict(package.get("next_chapter_constraint"))
    previous_state = _json_dict(package.get("previous_chapter_state"))
    current_state = _json_dict(package.get("chapter_state_snapshot"))
    event_tail = _json_list(package.get("event_timeline_tail"))
    lock_lines = [
        "【整部小说连续性锁】",
        f"小说级系列种子：{package.get('novel_series_seed')}",
        f"章节连续性种子：{package.get('chapter_seed')}",
        f"锁定范围：{continuity_lock.get('scope') or 'novel_series'}",
        f"故事标题：《{package.get('novel_title') or '未命名小说'}》",
        f"题材/风格：{package.get('genre') or '通用'} / {package.get('style') or '统一动漫风格'}",
        f"硬规则：{continuity_lock.get('rule') or '人物、场景、道具、事件和画风必须承接全书状态。'}",
    ]
    if previous_context:
        lock_lines.append(
            f"上一章承接：第{previous_context.get('chapter_number')}章《{previous_context.get('title')}》："
            f"{previous_context.get('summary') or ''}"
        )
    if previous_state.get("state_summary"):
        lock_lines.append("上一章状态：\n" + previous_state["state_summary"])
    if current_context:
        lock_lines.append(
            f"当前章节：第{current_context.get('chapter_number')}章《{current_context.get('title')}》："
            f"{current_context.get('summary') or ''}"
        )
    if current_state.get("state_summary"):
        lock_lines.append("当前章状态锁：\n" + current_state["state_summary"])
    if next_context:
        lock_lines.append(
            f"下一章不可矛盾约束：第{next_context.get('chapter_number')}章《{next_context.get('title')}》："
            f"{next_context.get('summary') or ''}"
        )
    if event_tail:
        events = "；".join(
            f"第{item.get('chapter_number')}章 {item.get('name')}"
            for item in event_tail
            if isinstance(item, dict) and item.get("name")
        )
        if events:
            lock_lines.append("最近事件线：" + events)
    if package.get("state_machine_summary"):
        lock_lines.append("人物/场景/道具状态机：\n" + compact_text(package.get("state_machine_summary"), 900))
    lock_lines.append(
        "生成要求：本次生成只能改编当前章节已经发生的内容；角色形象、服装、伤势、关系、场景天气光影、"
        "道具持有人与状态、事件因果必须承接上述锁定信息，不能把后续章节提前当成已发生剧情。"
    )
    return "\n".join(lock_lines)


async def _load_latest_story_bible(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str],
    story_bible_id: Optional[str],
) -> Optional[StoryBible]:
    if story_bible_id:
        result = await db.execute(
            select(StoryBible).where(and_(StoryBible.id == story_bible_id, StoryBible.user_id == user_id))
        )
        return result.scalar_one_or_none()
    if not novel_id:
        return None
    result = await db.execute(
        select(StoryBible)
        .where(and_(StoryBible.user_id == user_id, StoryBible.novel_id == novel_id))
        .order_by(desc(StoryBible.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_novel_continuity_package(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str] = None,
    story_bible_id: Optional[str] = None,
    project_id: Optional[str] = None,
    model_id: Optional[str] = None,
    task: str = "shot_video",
) -> Dict[str, Any]:
    if not novel_id:
        return {}

    novel_result = await db.execute(select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id)))
    novel = novel_result.scalar_one_or_none()
    if not novel:
        return {}

    chapter_result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.user_id == user_id, Chapter.novel_id == novel.id))
        .order_by(Chapter.chapter_number, Chapter.created_at)
    )
    chapters = list(chapter_result.scalars().all())
    previous_chapter, current_chapter, next_chapter = _select_neighbor_chapters(chapters, chapter_id)
    current_chapter_id = chapter_id or getattr(current_chapter, "id", None)

    story_bible = await _load_latest_story_bible(db, user_id, novel_id=novel.id, story_bible_id=story_bible_id)
    state_machine: Dict[str, Any] = {}
    if story_bible:
        state_machine = _json_dict(_json_dict(story_bible.extra_data).get("state_machine"))
        if not state_machine:
            try:
                state_machine = await build_story_state_machine(
                    db,
                    user_id,
                    story_bible_id=story_bible.id,
                    novel_id=novel.id,
                    persist=False,
                )
            except Exception:
                state_machine = {}

    current_snapshot = _find_snapshot(state_machine, current_chapter_id)
    previous_snapshot = _find_snapshot(state_machine, getattr(previous_chapter, "id", None))

    entity_filters = [StoryEntity.user_id == user_id, or_(StoryEntity.novel_id == novel.id, StoryEntity.novel_id.is_(None))]
    if current_chapter_id:
        entity_filters.append(or_(StoryEntity.chapter_id == current_chapter_id, StoryEntity.chapter_id.is_(None)))
    entity_result = await db.execute(
        select(StoryEntity)
        .where(and_(*entity_filters))
        .order_by(StoryEntity.entity_type, desc(StoryEntity.updated_at))
        .limit(120)
    )
    entity_locks = _entity_locks(list(entity_result.scalars().all()))

    novel_series_seed = derive_stable_seed([
        "novel_series",
        project_id,
        story_bible.id if story_bible else story_bible_id,
        novel.id,
    ])
    chapter_seed = derive_stable_seed(["chapter", novel_series_seed, current_chapter_id])

    package = {
        "task": task,
        "novel_id": novel.id,
        "novel_title": novel.title,
        "story_bible_id": story_bible.id if story_bible else story_bible_id,
        "project_id": project_id,
        "preferred_model_id": model_id,
        "chapter_id": current_chapter_id,
        "genre": novel.genre,
        "style": getattr(story_bible, "style", None) if story_bible else None,
        "novel_series_seed": novel_series_seed,
        "chapter_seed": chapter_seed,
        "continuity_lock": {
            "scope": "novel_series",
            "novel_id": novel.id,
            "story_bible_id": story_bible.id if story_bible else story_bible_id,
            "novel_series_seed": novel_series_seed,
            "chapter_seed": chapter_seed,
            "rule": "整部小说共享同一角色视觉DNA、世界观风格、场景/道具状态机和事件因果链；章节只派生节奏和局部状态，不重置人物形象。",
        },
        "previous_chapter_context": _chapter_summary(previous_chapter),
        "current_chapter_context": _chapter_summary(current_chapter),
        "next_chapter_constraint": _chapter_summary(next_chapter, limit=300),
        "previous_chapter_state": _snapshot_summary(previous_snapshot),
        "chapter_state_snapshot": _snapshot_summary(current_snapshot),
        "state_machine_version": state_machine.get("version"),
        "state_machine_summary": format_state_machine_summary(state_machine),
        "state_machine_rules": _json_list(state_machine.get("rules")),
        "event_timeline_tail": _event_tail(
            state_machine,
            chapter_number=getattr(current_chapter, "chapter_number", None),
        ),
        "entity_locks": entity_locks,
    }
    package["prompt_block"] = format_continuity_prompt_block(package)
    return package
