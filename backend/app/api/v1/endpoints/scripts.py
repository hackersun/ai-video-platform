"""
剧本管理 API 端点
"""

from app.core.time_utils import utc_now
from datetime import datetime
import json
import re
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.api_key_utils import get_user_text_generation_service
from app.core.dev_generation import is_dev_mode
from app.core.security import get_current_user_id
from app.models import Script, Novel, Chapter, StoryEntity
from app.services.consistency_context import build_consistency_prompt
from app.services.novel_continuity import build_novel_continuity_package
from app.services.prompt_skill_service import apply_active_prompt_skill_template
from app.services.story_prompt_context import (
    build_story_context_block,
    compact_text,
    load_story_prompt_context,
)
from app.services.story_entity_lifecycle import query_story_entities_for_production
from app.services.chapter_naming import format_chapter_label, normalize_duplicate_chapter_label_text
from app.services.episode_production_service import create_script_record
from app.api.v1.endpoints.dashboard import log_activity

router = APIRouter(tags=["剧本管理"])


# ============== Pydantic 模型 ==============

class ScriptCreate(BaseModel):
    """创建剧本"""
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    content: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    duration: Optional[int] = None

    @field_validator("novel_id", mode="before")
    @classmethod
    def validate_novel_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("novel_id cannot be blank")
        return value

    @field_validator("chapter_id", mode="before")
    @classmethod
    def validate_chapter_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("chapter_id cannot be blank")
        return value


class ScriptUpdate(BaseModel):
    """更新剧本"""
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    duration: Optional[int] = None
    status: Optional[str] = None

    @field_validator("novel_id", mode="before")
    @classmethod
    def validate_novel_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("novel_id cannot be blank")
        return value

    @field_validator("chapter_id", mode="before")
    @classmethod
    def validate_chapter_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("chapter_id cannot be blank")
        return value


class ScriptResponse(BaseModel):
    """剧本响应"""
    id: str
    user_id: str
    novel_id: Optional[str]
    chapter_id: Optional[str] = None
    novel_title: Optional[str] = None
    title: str
    description: Optional[str]
    content: Optional[str]
    genre: Optional[str]
    style: Optional[str]
    duration: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime


class ScriptContextResponse(BaseModel):
    """剧本生成上下文响应"""
    novel_id: str
    chapter_id: str
    story_bible_id: Optional[str] = None
    chapter_title: Optional[str] = None
    previous_chapter: Optional[Dict[str, Any]] = None
    next_chapter: Optional[Dict[str, Any]] = None
    context_block: str
    summary: Dict[str, Any]
    generation_context: Dict[str, Any]


class ScriptConsistencyCheckResponse(BaseModel):
    """剧本一致性检查响应"""
    script_id: str
    issue_count: int
    issues: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ScriptVersionResponse(BaseModel):
    """剧本版本快照响应"""
    id: str
    note: Optional[str] = None
    created_at: str
    title: str
    description: Optional[str] = None
    status: Optional[str] = None


class ScriptVersionCreateRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=200, description="版本备注")


class ScriptVersionRestoreRequest(BaseModel):
    snapshot_id: str = Field(..., description="要恢复的版本ID")


class ScriptAIAssistRequest(BaseModel):
    """剧本编辑 AI 辅助请求"""
    title: str = Field("", description="当前剧本标题")
    description: Optional[str] = Field(None, description="当前剧本简介")
    content: Optional[str] = Field(None, description="当前剧本正文")
    genre: Optional[str] = Field(None, description="题材")
    style: Optional[str] = Field(None, description="风格")
    mode: Literal["polish_description", "polish_content", "short_drama"] = Field(
        "polish_content",
        description="辅助方式",
    )
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class ScriptAIAssistResponse(BaseModel):
    """剧本编辑 AI 辅助响应"""
    title: str
    description: str
    content: str
    warnings: List[str] = Field(default_factory=list)


class ScriptGenerateRequest(BaseModel):
    """AI生成剧本请求"""
    chapter_id: str = Field(..., description="章节ID")
    style: str = Field(default="anime", description="剧本风格（anime/anime_cartoon/realistic等）")
    genre: Optional[str] = Field(None, description="剧本类型（可选）")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


async def get_novel_for_user(db: AsyncSession, novel_id: str, user_id: str):
    from app.models import Novel

    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="所属小说不存在")
    return novel


async def get_chapter_for_user(db: AsyncSession, chapter_id: str, user_id: str) -> Chapter:
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


async def list_chapters_for_novel(db: AsyncSession, novel_id: str, user_id: str) -> list[Chapter]:
    result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
        .order_by(Chapter.chapter_number)
    )
    return list(result.scalars().all())


def chapter_neighbors(chapters: list[Chapter], chapter_id: str) -> tuple[Optional[Chapter], Optional[Chapter]]:
    for index, chapter in enumerate(chapters):
        if chapter.id == chapter_id:
            prev_chapter = chapters[index - 1] if index > 0 else None
            next_chapter = chapters[index + 1] if index < len(chapters) - 1 else None
            return prev_chapter, next_chapter
    return None, None


async def get_novel_title_map(db: AsyncSession, user_id: str, novel_ids: set[str]) -> dict[str, str]:
    if not novel_ids:
        return {}

    from app.models import Novel

    result = await db.execute(
        select(Novel).where(and_(Novel.user_id == user_id, Novel.id.in_(novel_ids)))
    )
    novels = result.scalars().all()
    return {novel.id: novel.title for novel in novels}


def build_script_response(script: Script, novel_title: Optional[str] = None) -> ScriptResponse:
    extra_data = script.extra_data if isinstance(script.extra_data, dict) else {}
    return ScriptResponse(
        id=script.id,
        user_id=script.user_id,
        novel_id=script.novel_id,
        chapter_id=script.chapter_id or extra_data.get("chapter_id"),
        novel_title=novel_title,
        title=normalize_duplicate_chapter_label_text(script.title) or script.title,
        description=normalize_duplicate_chapter_label_text(script.description) or script.description,
        content=script.content,
        genre=script.genre,
        style=script.style,
        duration=script.duration,
        status=script.status or "draft",
        created_at=script.created_at,
        updated_at=script.updated_at,
    )


def _extract_names(items: list[Any], key: str = "name", limit: int = 12) -> list[str]:
    names: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            name = str(item.get(key) or item.get("title") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


SCRIPT_CHARACTER_BLOCKLIST = {
    "两人",
    "二人",
    "众人",
    "他们",
    "我们",
    "星轨线",
    "铜铃会指",
    "信纸上",
    "灯塔顶部",
}


def _normalize_character_anchor(value: str) -> Optional[str]:
    name = re.sub(r"\s+", "", value or "").strip("，。！？；:：、")
    if "把" in name:
        name = name.split("把")[-1]
    name = re.sub(r"^(?:少年|少女|青年|女孩|男孩|老人)", "", name)
    name = re.sub(r"(?:带进|带入|追来|提醒|决定|发现|看见|约定|冲向|稳住|握紧|说|问|喊)$", "", name)
    if len(name) < 2 or len(name) > 4:
        return None
    if name in SCRIPT_CHARACTER_BLOCKLIST:
        return None
    if any(token in name for token in ("星轨", "铜铃", "信纸", "镜面", "线索", "回声", "失踪", "雾港", "永远", "午夜", "夹层", "空间")):
        return None
    if not re.search(r"[\u4e00-\u9fff]", name):
        return None
    return name


def _append_character_anchor(names: list[str], value: str) -> None:
    name = _normalize_character_anchor(value)
    if name and name not in names:
        names.append(name)


def _chapter_character_anchors(content: str, known_names: list[str]) -> list[str]:
    text = content or ""
    names: list[str] = []
    for match in re.finditer(r"([\u4e00-\u9fff]{2,4})(?:和|与)([\u4e00-\u9fff]{2,4})", text):
        _append_character_anchor(names, match.group(1))
        _append_character_anchor(names, match.group(2))
    for match in re.finditer(r"(?:少年|少女|青年|女孩|男孩|老人)?([\u4e00-\u9fff]{2,4})(?:在|从|追来|提醒|决定|发现|看见|约定|冲向|稳住|握紧|说|问|喊)", text):
        _append_character_anchor(names, match.group(1))
    for known_name in known_names:
        if known_name in text:
            _append_character_anchor(names, known_name)
    return names


def _first_valid_entity_name(candidates: list[str], chapter_content: str, fallback: str) -> str:
    for candidate in candidates:
        name = re.sub(r"\s+", "", candidate or "").strip("，。！？；:：、")
        if not name or len(name) > 16:
            continue
        if name.startswith(("的", "的人", "而是", "可", "把")):
            continue
        if name not in chapter_content:
            continue
        return name
    return fallback


def _derive_scene_anchor(chapter_content: str, fallback: str) -> str:
    specific_matches = [
        (chapter_content.find(token), token)
        for token in ("旧邮局", "暗巷", "废弃灯塔", "灯塔", "维修舱", "控制台")
        if token in chapter_content
    ]
    if specific_matches:
        return min(specific_matches, key=lambda item: item[0])[1]
    ambient_matches = [
        (chapter_content.find(token), token)
        for token in ("雾港", "海边")
        if token in chapter_content
    ]
    if ambient_matches:
        return min(ambient_matches, key=lambda item: item[0])[1]
    return fallback


def _derive_prop_anchor(chapter_content: str, candidates: list[str], fallback: str) -> str:
    for token in ("铜铃芯", "铜铃", "手电", "维修徽章", "徽章", "信纸", "信", "镜面", "星轨线"):
        if token in chapter_content:
            return token
    return _first_valid_entity_name(candidates, chapter_content, fallback)


def _relationship_items(entities: list[StoryEntity]) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for entity in entities:
        attrs = entity.attributes if isinstance(entity.attributes, dict) else {}
        raw_items = attrs.get("relationships")
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if isinstance(item, dict):
                relationships.append(
                    {
                        **item,
                        "source_entity_id": entity.id,
                        "source_entity_name": entity.name,
                    }
                )
    return relationships


async def load_story_entities_for_scope(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
    chapter_id: Optional[str] = None,
) -> list[StoryEntity]:
    entities = await query_story_entities_for_production(
        db,
        user_id=user_id,
        novel_id=novel_id,
    )
    recent_first = sorted(
        entities,
        key=lambda entity: entity.updated_at or entity.created_at or datetime.min,
        reverse=True,
    )
    return sorted(recent_first, key=lambda entity: entity.entity_type or "")


def _priority_sort_entities(items: list[StoryEntity], priority_text: str) -> list[StoryEntity]:
    def score(entity: StoryEntity) -> tuple[int, int, str]:
        name = entity.name or ""
        position = priority_text.find(name) if name else -1
        in_text = 0 if position >= 0 else 1
        return (in_text, position if position >= 0 else 999999, name)

    return sorted(items, key=score)


def build_production_pack_summary(entities: list[StoryEntity], *, priority_text: str = "") -> dict[str, Any]:
    grouped: dict[str, list[StoryEntity]] = {
        "character": [],
        "scene": [],
        "prop": [],
        "event": [],
    }
    for entity in entities:
        grouped.setdefault(entity.entity_type, []).append(entity)
    for entity_type in grouped:
        grouped[entity_type] = _priority_sort_entities(grouped[entity_type], priority_text)
    relationships = _relationship_items(grouped.get("character", []))
    return {
        "characters": [
            {"id": item.id, "name": item.name, "description": compact_text(item.description or item.evidence, 120)}
            for item in grouped.get("character", [])[:12]
        ],
        "scenes": [
            {"id": item.id, "name": item.name, "description": compact_text(item.description or item.evidence, 120)}
            for item in grouped.get("scene", [])[:10]
        ],
        "props": [
            {"id": item.id, "name": item.name, "description": compact_text(item.description or item.evidence, 120)}
            for item in grouped.get("prop", [])[:10]
        ],
        "events": [
            {"id": item.id, "name": item.name, "description": compact_text(item.description or item.evidence, 140)}
            for item in grouped.get("event", [])[:12]
        ],
        "relationships": relationships[:20],
    }


def merge_story_context_into_production_pack(
    production_pack: dict[str, Any],
    story_context: dict[str, Any],
) -> dict[str, Any]:
    mapping = {
        "characters": "character",
        "scenes": "scene",
        "props": "prop",
        "events": "event",
    }
    merged = {key: list(production_pack.get(key) or []) for key in ("characters", "scenes", "props", "events")}
    for key, entity_type in mapping.items():
        seen = {str(item.get("name") or "").strip() for item in merged[key] if isinstance(item, dict)}
        for item in story_context.get(key) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("title") or "").strip()
            if not name or name in seen:
                continue
            merged[key].append(
                {
                    "id": item.get("id"),
                    "name": name,
                    "description": compact_text(item.get("description") or item.get("evidence"), 120),
                    "entity_type": item.get("entity_type") or entity_type,
                    "source": item.get("source") or "text_context",
                }
            )
            seen.add(name)
    return {
        **production_pack,
        **merged,
        "relationships": production_pack.get("relationships") or [],
    }


def build_relationship_block(relationships: list[dict[str, Any]]) -> str:
    if not relationships:
        return "暂无明确人物关系，请仅依据小说正文和 Story Bible 中已有设定。"
    lines = []
    for item in relationships[:20]:
        source = item.get("source_entity_name") or item.get("source") or item.get("from") or "未知角色"
        target = item.get("target") or item.get("target_name") or item.get("to") or item.get("name") or "未知对象"
        relation = item.get("relation") or item.get("type") or item.get("description") or "关联"
        status_text = item.get("status") or item.get("state") or ""
        lines.append(f"- {source} -> {target}：{relation}{f'（{status_text}）' if status_text else ''}")
    return "\n".join(lines)


def build_event_timeline_block(events: list[dict[str, Any]]) -> str:
    if not events:
        return "暂无明确事件线，请从当前章节正文中抽取事件因果。"
    lines = []
    for index, event in enumerate(events[:16], start=1):
        name = event.get("name") or event.get("title") or f"事件{index}"
        desc = compact_text(event.get("description"), 160)
        lines.append(f"{index}. {name}{f'：{desc}' if desc else ''}")
    return "\n".join(lines)


async def build_script_generation_context(
    db: AsyncSession,
    user_id: str,
    *,
    chapter: Chapter,
    novel: Novel,
    style: str,
    genre: Optional[str] = None,
) -> dict[str, Any]:
    chapters = await list_chapters_for_novel(db, novel.id, user_id)
    prev_chapter, next_chapter = chapter_neighbors(chapters, chapter.id)
    story_context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        title=novel.title,
        genre=genre or novel.genre,
        description=novel.description,
        style=style,
        limit_chapters=8,
    )
    entities = await load_story_entities_for_scope(db, user_id, novel.id, chapter.id)
    priority_text = "\n".join(
        part
        for part in (
            chapter.content or "",
            prev_chapter.content if prev_chapter else "",
            novel.description or "",
        )
        if part
    )
    production_pack = merge_story_context_into_production_pack(
        build_production_pack_summary(entities, priority_text=priority_text),
        story_context,
    )
    current_chapter_label = format_chapter_label(chapter.title, chapter.chapter_number)
    prev_chapter_label = format_chapter_label(prev_chapter.title, prev_chapter.chapter_number) if prev_chapter else None
    next_chapter_label = format_chapter_label(next_chapter.title, next_chapter.chapter_number) if next_chapter else None
    consistency_context = await build_consistency_prompt(
        db,
        user_id,
        task="script_generation",
        base_prompt=chapter.content or novel.description or novel.title,
        novel_id=novel.id,
        extra_context={
            "小说标题": novel.title,
            "小说类型": genre or novel.genre,
            "当前章节": current_chapter_label,
            "上一章": f"{prev_chapter_label}: {compact_text(prev_chapter.content, 800)}" if prev_chapter else None,
            "下一章": f"{next_chapter_label}: {compact_text(next_chapter.content, 600)}" if next_chapter else None,
            "人物关系": build_relationship_block(production_pack["relationships"]),
            "事件时间线": build_event_timeline_block(production_pack["events"]),
        },
    )
    novel_continuity = await build_novel_continuity_package(
        db,
        user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        story_bible_id=story_context.get("story_bible_id"),
        model_id=consistency_context["metadata"].get("default_model_id"),
        task="script_generation",
    )
    return {
        "novel": novel,
        "chapter": chapter,
        "chapters": chapters,
        "prev_chapter": prev_chapter,
        "next_chapter": next_chapter,
        "story_context": story_context,
        "production_pack": production_pack,
        "consistency_prompt": consistency_context["prompt"],
        "consistency_metadata": consistency_context["metadata"],
        "novel_continuity": novel_continuity,
    }


def summarize_script_context(context: dict[str, Any]) -> dict[str, Any]:
    story_context = context["story_context"]
    production_pack = context["production_pack"]
    prev_chapter = context.get("prev_chapter")
    next_chapter = context.get("next_chapter")
    return {
        "story_bible_id": story_context.get("story_bible_id"),
        "previous_chapter": (
            {
                "id": prev_chapter.id,
                "title": prev_chapter.title,
                "chapter_number": prev_chapter.chapter_number,
                "summary": compact_text(prev_chapter.content, 260),
            }
            if prev_chapter
            else None
        ),
        "next_chapter": (
            {
                "id": next_chapter.id,
                "title": next_chapter.title,
                "chapter_number": next_chapter.chapter_number,
                "summary": compact_text(next_chapter.content, 220),
            }
            if next_chapter
            else None
        ),
        "characters": _extract_names(production_pack.get("characters") or []),
        "scenes": _extract_names(production_pack.get("scenes") or []),
        "props": _extract_names(production_pack.get("props") or []),
        "events": _extract_names(production_pack.get("events") or []),
        "relationships": production_pack.get("relationships") or [],
        "counts": {
            "characters": len(production_pack.get("characters") or []),
            "scenes": len(production_pack.get("scenes") or []),
            "props": len(production_pack.get("props") or []),
            "events": len(production_pack.get("events") or []),
            "relationships": len(production_pack.get("relationships") or []),
        },
    }


SPEAKER_NAME_BLOCKLIST = {
    "低声",
    "轻声",
    "沉声",
    "急声",
    "坚定",
    "这里",
    "系统",
    "不能",
    "他说",
    "她说",
    "他低声",
    "她低声", "喊道", "问道", "答道", "回答", "回应",
}


def _is_valid_dialogue_speaker_name(value: str) -> bool:
    name = re.sub(r"\s+", "", value or "").strip("，。！？；:：、")
    if len(name) < 2 or len(name) > 8:
        return False
    if name in SPEAKER_NAME_BLOCKLIST:
        return False
    if any(token in name for token in ("第", "场", "章", "说", "低声", "轻声", "沉声", "急声", "这里", "系统")):
        return False
    if name.startswith(("他", "她", "它", "这", "那")):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", name))


def _append_unique_speaker(names: list[str], value: str) -> None:
    name = re.sub(r"\s+", "", value or "").strip("，。！？；:：、")
    if _is_valid_dialogue_speaker_name(name) and name not in names:
        names.append(name)


def extract_chapter_dialogue_speakers(content: str, known_names: list[str]) -> list[str]:
    names: list[str] = []
    for name in known_names:
        _append_unique_speaker(names, name)

    text = content or ""
    patterns = [
        r"([\u4e00-\u9fffA-Za-z0-9_·]{2,8})(?:单人|独自|同框|站在|看着|扶住|走向|冲向|说|问|喊|回答|回应)",
        r"(?:和|与)([\u4e00-\u9fffA-Za-z0-9_·]{2,8})(?:同框|争执|站在|说|问|喊|回答|回应)",
        r"([\u4e00-\u9fffA-Za-z0-9_·]{2,8})[：:][^。！？\n]{1,80}",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            _append_unique_speaker(names, match.group(1))
    return names


def _last_speaker_in_text(text: str, speakers: list[str]) -> Optional[str]:
    last_name: Optional[str] = None
    last_index = -1
    for speaker in speakers:
        index = text.rfind(speaker)
        if index > last_index:
            last_name = speaker
            last_index = index
    return last_name


def extract_chapter_dialogue_lines(content: str, known_names: list[str]) -> list[dict[str, str]]:
    speakers = extract_chapter_dialogue_speakers(content, known_names)
    if not speakers:
        return []

    speech_verb = r"(?:低声说|轻声说|沉声说|急声说|说道|说|问道|问|喊道|喊|回答|回应|答道)"
    sentences = [part for part in re.split(r"(?<=[。！？])", content or "") if part.strip()]
    lines: list[dict[str, str]] = []
    last_speaker: Optional[str] = None

    for sentence in sentences:
        matches = list(re.finditer(rf"{speech_verb}[：:][“‘\"']?([^。！？\n]+)", sentence))
        if not matches:
            last_speaker = _last_speaker_in_text(sentence, speakers) or last_speaker
            continue
        for match in matches:
            prefix = sentence[:match.start()]
            speaker = _last_speaker_in_text(prefix, speakers) or last_speaker
            text = match.group(1).strip().strip("“”‘’\"' ")
            if speaker and text:
                lines.append({"speaker": speaker, "text": text})
                last_speaker = speaker
        last_speaker = _last_speaker_in_text(sentence, speakers) or last_speaker

    return lines[:8]


def _format_dialogue_bullets(lines: list[dict[str, str]], fallback: str) -> str:
    if not lines:
        return fallback
    return "\n".join(f"- {line['speaker']}：\"{line['text']}。\"" for line in lines)


def build_script_prompt_blocks(
    *,
    novel: Novel,
    chapter: Chapter,
    context: dict[str, Any],
    style_desc: str,
    genre_hint: str,
) -> tuple[str, str]:
    story_context = context["story_context"]
    production_pack = context["production_pack"]
    prev_chapter = context.get("prev_chapter")
    next_chapter = context.get("next_chapter")
    chapter_content = chapter.content or ""
    max_chars = 20000
    chapter_for_prompt = chapter_content[:max_chars]
    if len(chapter_content) > max_chars:
        chapter_for_prompt += "\n\n[章节内容过长已截断]"
    current_chapter_label = format_chapter_label(chapter.title, chapter.chapter_number)
    prev_chapter_label = format_chapter_label(prev_chapter.title, prev_chapter.chapter_number) if prev_chapter else None
    next_chapter_label = format_chapter_label(next_chapter.title, next_chapter.chapter_number) if next_chapter else None
    continuity_prompt_block = (
        (context.get("novel_continuity") or {}).get("prompt_block")
        or "【整部小说连续性锁】\n未找到小说级连续性上下文。"
    )
    system_prompt = f"""你是专业中文影视剧本作家、分镜导演和动漫短剧统筹。你需要把小说章节改编为可直接进入分镜、镜头、配音、字幕和视频生成的剧本。

【基本信息】
小说名称：《{novel.title}》
小说简介：{novel.description or '暂无'}
{genre_hint}
目标风格：{style_desc}

【连续性硬约束】
1. 只能把当前章节已经发生的内容改编成剧本，上一章只作为前情，下一章只作为不可矛盾的后续约束。
2. 不能凭空更改人物姓名、身份关系、场景位置、道具状态、事件结果和对白口吻。
3. 必须使用 Story Bible/实体库中的人物、场景、道具、事件作为主要生产锚点。
4. 每场必须有清晰戏剧功能：人物目标、阻碍、冲突变化、事件结果或下一场钩子。
5. 对白必须符合人物关系和小说题材，避免“角色A/角色B”这类占位称呼。
6. 输出必须是中文剧本正文，不要输出 Markdown 表格、解释、推理过程。

【输出格式】
第一行必须是：剧本标题：[标题]
后续按“第N场”组织，每场包含：场景类型、时长、地点、人物、戏剧核心、画面描述、对话/旁白、镜头序列、音效/音乐提示、字幕要点。"""

    user_prompt = f"""【统一故事上下文】
{build_story_context_block(story_context, include_chapters=True)}

{continuity_prompt_block}

【上一章前情】
{f"{prev_chapter_label}：{compact_text(prev_chapter.content, 1200)}" if prev_chapter else "无，本章为开端或缺少上一章。"}

【下一章不可矛盾约束】
{f"{next_chapter_label}：{compact_text(next_chapter.content, 900)}" if next_chapter else "无。"}

【人物关系】
{build_relationship_block(production_pack.get("relationships") or [])}

【事件时间线】
{build_event_timeline_block(production_pack.get("events") or [])}

【一致性组合提示】
{context["consistency_prompt"]}

【当前章节】
{current_chapter_label}

【章节正文】
{chapter_for_prompt}

请把当前章节改编为 3-5 个主要场景，每个场景拆出 3-8 个镜头。"""
    return system_prompt, user_prompt


def build_dev_script_content(
    *,
    novel: Novel,
    chapter: Chapter,
    context: dict[str, Any],
    style_desc: str,
) -> str:
    summary = summarize_script_context(context)
    dialogue_lines = extract_chapter_dialogue_lines(chapter.content or "", summary["characters"] or [])
    dialogue_speakers: list[str] = []
    for line in dialogue_lines:
        _append_unique_speaker(dialogue_speakers, line["speaker"])

    chapter_content = chapter.content or ""
    character_anchors = _chapter_character_anchors(chapter_content, summary["characters"] or [])
    protagonist = (character_anchors or dialogue_speakers or ["主角"])[0]
    second_actor = (
        dialogue_speakers[1]
        if len(dialogue_speakers) > 1
        else (character_anchors[1] if len(character_anchors) > 1 else protagonist)
    )
    closing_actors = "、".join(dialogue_speakers or character_anchors) if (dialogue_speakers or character_anchors) else protagonist
    scene = _derive_scene_anchor(chapter_content, _first_valid_entity_name(summary["scenes"] or [], chapter_content, "核心场景"))
    prop = _derive_prop_anchor(chapter_content, summary["props"] or [], "关键道具")
    event = _first_valid_entity_name(summary["events"] or [], chapter_content, "关键事件")
    previous_chapter = summary.get("previous_chapter")
    prev_title = previous_chapter["title"] if previous_chapter else None
    next_title = summary["next_chapter"]["title"] if summary.get("next_chapter") else "后续章节"
    chapter_label = format_chapter_label(chapter.title, chapter.chapter_number)
    first_scene_core = (
        f"承接《{prev_title}》的结果，用{prop}或异常画面引出{event}。"
        if prev_title
        else f"从当前章节开端建立悬念，用{prop}或异常画面引出{event}。"
    )
    opening_narration = (
        f'- （旁白）"上一章留下的线索，在这一刻重新指向{event}。"'
        if prev_title
        else f'- （旁白）"本章开场的线索，在这一刻指向{event}。"'
    )
    first_scene_dialogue = _format_dialogue_bullets(
        dialogue_lines[:1],
        f'- {protagonist}：（低声）"这件事还没有结束。"',
    )
    second_scene_dialogue = _format_dialogue_bullets(
        dialogue_lines[1:2],
        f'- {second_actor}：（坚定）"我会查清楚。"',
    )
    third_scene_dialogue = _format_dialogue_bullets(
        dialogue_lines[2:],
        '- （旁白）"真正的答案，还藏在下一道门后。"',
    )
    return f"""剧本标题：{chapter_label} 动漫短剧改编

【第1场】开场钩子
- 场景类型：外景/内景 日夜依据原文
- 时长：约8秒
- 地点：{scene}
- 人物：{protagonist}
- 戏剧核心：{first_scene_core}

【画面描述】
{style_desc}。镜头先交代{scene}的空间和氛围，再把注意力推向{protagonist}与{prop}，保证人物造型、道具状态和事件因果与小说一致。

【对话/旁白】
{first_scene_dialogue}
{opening_narration}

【镜头序列】
1. 全景 - 固定 - 展示{scene}和当前气氛。
2. 近景 - 推镜 - {protagonist}注意到{prop}的状态变化。
3. 特写 - 固定 - {prop}成为本场视觉钩子。

【音效/音乐提示】
- 环境音：贴合{scene}的空间声。
- 背景音乐：悬念推进。
- 字幕要点：保留关键对白并标注说话人。

【第2场】冲突推进
- 场景类型：中景动作场
- 时长：约12秒
- 地点：{scene}
- 人物：{second_actor}
- 戏剧核心：{second_actor}围绕{event}做出选择，推动下一场。

【画面描述】
角色动作、表情和站位要清楚，避免新增无关角色。道具状态必须承接上一场。

【对话/旁白】
{second_scene_dialogue}

【镜头序列】
1. 中景 - 跟拍 - 角色移动并确认线索。
2. 特写 - 固定 - 表情变化。
3. 远景 - 拉镜 - 留出转场空间。

【音效/音乐提示】
- 环境音：节奏加快。
- 背景音乐：冲突升级。
- 字幕要点：对白短句化，适配短视频。

【第3场】结尾承接
- 场景类型：悬念场
- 时长：约8秒
- 地点：{scene}
- 人物：{closing_actors}
- 戏剧核心：本章结果必须能自然接到《{next_title}》，不提前改写后续事件。

【画面描述】
用一个未解决动作或关键信号收束，形成下一集钩子。

【对话/旁白】
{third_scene_dialogue}

【镜头序列】
1. 特写 - 固定 - 关键物件或线索。
2. 近景 - 推镜 - 角色反应。
3. 黑场/转场 - 固定 - 留出字幕和片尾节奏。

【音效/音乐提示】
- 环境音：短暂停顿。
- 背景音乐：悬念收束。
- 字幕要点：保留最后一句钩子。"""


def _script_context_metadata(
    *,
    context: dict[str, Any],
    provider: str,
    model_id: str,
    ai_refined: bool,
) -> dict[str, Any]:
    summary = summarize_script_context(context)
    novel_continuity = context.get("novel_continuity") or {}
    return {
        "story_bible_id": summary.get("story_bible_id"),
        "provider": provider,
        "model_id": model_id,
        "ai_refined": ai_refined,
        "generated_at": utc_now().isoformat(),
        "prev_chapter_id": summary["previous_chapter"]["id"] if summary.get("previous_chapter") else None,
        "next_chapter_id": summary["next_chapter"]["id"] if summary.get("next_chapter") else None,
        "characters": summary.get("characters") or [],
        "scenes": summary.get("scenes") or [],
        "props": summary.get("props") or [],
        "events": summary.get("events") or [],
        "relationships": summary.get("relationships") or [],
        "counts": summary.get("counts") or {},
        "consistency_metadata": context.get("consistency_metadata") or {},
        "novel_series_seed": novel_continuity.get("novel_series_seed"),
        "chapter_seed": novel_continuity.get("chapter_seed"),
        "continuity_lock": novel_continuity.get("continuity_lock"),
        "previous_chapter_context": novel_continuity.get("previous_chapter_context"),
        "current_chapter_context": novel_continuity.get("current_chapter_context"),
        "next_chapter_constraint": novel_continuity.get("next_chapter_constraint"),
        "previous_chapter_state": novel_continuity.get("previous_chapter_state"),
        "chapter_state_snapshot": novel_continuity.get("chapter_state_snapshot"),
        "state_machine_version": novel_continuity.get("state_machine_version"),
        "event_timeline_tail": novel_continuity.get("event_timeline_tail") or [],
    }


def _append_script_snapshot(script: Script, note: Optional[str]) -> dict[str, Any]:
    extra_data = dict(script.extra_data or {})
    snapshots = list(extra_data.get("version_snapshots") or [])
    snapshot = {
        "id": str(uuid4()),
        "note": note or "手动快照",
        "created_at": utc_now().isoformat(),
        "title": script.title,
        "description": script.description,
        "content": script.content,
        "genre": script.genre,
        "style": script.style,
        "duration": script.duration,
        "status": script.status,
        "novel_id": script.novel_id,
        "chapter_id": script.chapter_id or extra_data.get("chapter_id"),
    }
    snapshots.append(snapshot)
    extra_data["version_snapshots"] = snapshots[-30:]
    script.extra_data = extra_data
    script.updated_at = utc_now()
    return snapshot


def _issue(code: str, severity: str, message: str, evidence: Optional[str] = None) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "evidence": evidence}


async def check_script_consistency_internal(
    db: AsyncSession,
    user_id: str,
    script: Script,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    extra_data = script.extra_data if isinstance(script.extra_data, dict) else {}
    chapter_id = script.chapter_id or extra_data.get("chapter_id")
    known_names = {"characters": [], "scenes": [], "props": [], "events": []}
    chapter = None
    novel = None
    if chapter_id:
        chapter = await get_chapter_for_user(db, chapter_id, user_id)
        if script.novel_id and chapter.novel_id != script.novel_id:
            issues.append(_issue("chapter_novel_mismatch", "error", "剧本绑定章节不属于剧本绑定小说"))
        novel = await get_novel_for_user(db, chapter.novel_id, user_id)
        context = await build_script_generation_context(
            db,
            user_id,
            chapter=chapter,
            novel=novel,
            style=script.style or "anime",
            genre=script.genre,
        )
        summary = summarize_script_context(context)
        known_names = {
            "characters": summary.get("characters") or [],
            "scenes": summary.get("scenes") or [],
            "props": summary.get("props") or [],
            "events": summary.get("events") or [],
        }
        if summary.get("next_chapter") and script.content and summary["next_chapter"]["title"] in script.content:
            issues.append(
                _issue(
                    "future_chapter_as_past",
                    "warning",
                    "剧本文本疑似把下一章标题写入当前章内容，请确认没有提前改写后续剧情。",
                    summary["next_chapter"]["title"],
                )
            )
    else:
        issues.append(_issue("missing_chapter_link", "warning", "剧本未绑定章节，无法做完整章节连续性检查"))

    content = script.content or ""
    if "角色A" in content or "角色B" in content:
        issues.append(_issue("placeholder_speaker", "error", "对白中仍存在角色A/角色B占位称呼"))

    dialogue_speakers = sorted(set(re.findall(r"^\s*-\s*([^：（:]{1,12})[：:（]", content, flags=re.MULTILINE)))
    for speaker in dialogue_speakers:
        if speaker in {"旁白", "画外音"}:
            continue
        if known_names["characters"] and speaker not in known_names["characters"]:
            issues.append(_issue("unknown_dialogue_speaker", "warning", f"对白说话人未在角色库中登记：{speaker}", speaker))

    for label, names in (("scene", known_names["scenes"]), ("prop", known_names["props"]), ("event", known_names["events"])):
        if names and not any(name in content for name in names[:8]):
            label_cn = {"scene": "场景", "prop": "道具", "event": "事件"}[label]
            issues.append(_issue(f"missing_{label}_anchor", "warning", f"剧本没有明显引用已登记{label_cn}锚点"))

    context_meta = extra_data.get("generation_context") if isinstance(extra_data.get("generation_context"), dict) else {}
    if not context_meta:
        issues.append(_issue("missing_generation_context", "warning", "剧本缺少生成上下文元数据，后续分镜一致性较弱"))

    summary = {
        "chapter_id": chapter_id,
        "novel_id": script.novel_id or getattr(novel, "id", None),
        "known_names": known_names,
        "dialogue_speakers": dialogue_speakers,
        "has_generation_context": bool(context_meta),
    }
    return issues, summary


# ============== API 端点 ==============

@router.get("", response_model=List[ScriptResponse])
async def list_scripts(
    novel_id: Optional[str] = Query(None, description="按小说过滤剧本"),
    chapter_id: Optional[str] = Query(None, description="按章节过滤剧本"),
    page: Optional[int] = Query(None, ge=1, description="分页页码；不传时保持返回全部兼容旧前端"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="分页大小；不传时保持返回全部兼容旧前端"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有剧本"""

    query = select(Script).where(Script.user_id == user_id)
    if novel_id:
        query = query.where(Script.novel_id == novel_id)
    result = await db.execute(query.order_by(desc(Script.updated_at)))
    scripts = result.scalars().all()
    if chapter_id:
        scripts = [
            script for script in scripts
            if script.chapter_id == chapter_id
            or (isinstance(script.extra_data, dict) and script.extra_data.get("chapter_id") == chapter_id)
        ]
    if page and page_size:
        start = (page - 1) * page_size
        scripts = scripts[start:start + page_size]

    novel_title_map = await get_novel_title_map(
        db,
        user_id,
        {script.novel_id for script in scripts if script.novel_id},
    )

    return [
        build_script_response(script, novel_title_map.get(script.novel_id))
        for script in scripts
    ]


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个剧本"""

    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()

    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")

    novel_title = None
    if script.novel_id:
        novel = await get_novel_for_user(db, script.novel_id, user_id)
        novel_title = novel.title

    return build_script_response(script, novel_title)


def _parse_script_ai_assist_content(content: str) -> dict:
    text = (content or "").strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    return parsed if isinstance(parsed, dict) else {}


def _build_dev_script_assist(request: ScriptAIAssistRequest) -> ScriptAIAssistResponse:
    title = (request.title or "未命名剧本").strip()
    description = (request.description or "").strip()
    content = (request.content or "").strip()
    warnings = ["DEV_MODE：未调用云端文本模型，已提供本地辅助草稿。"]

    if request.mode == "polish_description":
        description = description or f"围绕《{title}》的核心冲突、人物动机和章节承接整理剧本简介。"
        description = f"{description.rstrip('。')}。动画改编重点突出人物选择、场景氛围和镜头节奏。"
    elif request.mode == "short_drama":
        description = description or f"《{title}》短剧化改编，突出开场钩子、冲突升级和章尾悬念。"
        content = content or "【开场钩子】主角在关键场景中发现异常。\n【冲突推进】人物选择带出主要矛盾。\n【悬念收束】关键道具或事件留下下一镜头的问题。"
        content = f"{content.rstrip()}\n\n【短剧节奏提示】开场 3 秒给出冲突或悬念；对白短句化；结尾保留可继续生成下一镜头的动作或问题。"
    else:
        if not content:
            content = "【镜头段落】请补充剧本正文，AI 会围绕人物、事件、场景、台词和镜头节奏进行润色。"
        else:
            content = f"{content.rstrip()}\n\n【润色提示】保留原有人物和事件，后续可继续细化台词、动作、景别和转场。"

    return ScriptAIAssistResponse(
        title=title,
        description=description,
        content=content,
        warnings=warnings,
    )


@router.post("/ai-assist", response_model=ScriptAIAssistResponse)
async def ai_assist_script_edit(
    request: ScriptAIAssistRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """为剧本编辑弹窗提供轻量 AI 润色/改写辅助，不直接入库。"""
    if not (request.title or request.description or request.content):
        raise HTTPException(status_code=400, detail="请先填写标题、简介或正文后再使用 AI 辅助")

    mode_instruction = {
        "polish_description": "只优化 description，让简介更清晰、中文化、适合动漫短剧制作；content 原样返回。",
        "polish_content": "优化 content，让剧本正文承接章节、人物、事件、场景和台词；不要改变主要剧情。",
        "short_drama": "把 description 和 content 调整为短视频漫剧节奏：开场钩子、冲突推进、章尾悬念，保留人物和事件一致性。",
    }[request.mode]

    system_prompt = """你是专业的小说动漫剧本编辑。请帮助非专业创作者把剧本信息整理得更适合后续分镜、镜头、配音和视频生成。

规则：
1. 必须使用中文输出。
2. 不要发明与原文冲突的新人物、道具、场景和事件。
3. 有角色台词时使用“角色名：台词”格式；旁白使用“（旁白）台词”。
4. 输出 JSON，不要 markdown，不要解释。
5. 返回字段必须包含 title、description、content、warnings。"""

    user_prompt = f"""任务：{mode_instruction}

当前剧本：
标题：{request.title or '未填写'}
题材：{request.genre or '未设置'}
风格：{request.style or '未设置'}
简介：{request.description or '未填写'}
正文：
{compact_text(request.content, 5200) if request.content else '未填写'}

请返回：
{{
  "title": "标题",
  "description": "简介",
  "content": "剧本正文",
  "warnings": []
}}"""
    prompt_result = await apply_active_prompt_skill_template(
        db,
        user_id,
        task="script_generation",
        internal_prompt=user_prompt,
        context={
            "title": request.title or "未命名剧本",
            "genre": request.genre or "通用",
            "style": request.style or "",
            "description": request.description or "",
            "content": request.content or "",
            "mode": request.mode,
        },
    )
    user_prompt = prompt_result["prompt"]

    try:
        service, provider_name, model_id, _base_url = await get_user_text_generation_service(
            db, user_id, config_id=request.model_config_id,
        )
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=4000,
        )
        parsed = _parse_script_ai_assist_content(response["choices"][0]["message"]["content"])
    except HTTPException:
        if not is_dev_mode():
            raise
        return _build_dev_script_assist(request)
    except Exception as exc:
        if not is_dev_mode():
            raise HTTPException(status_code=500, detail=f"剧本 AI 辅助失败: {str(exc)}")
        return _build_dev_script_assist(request)

    warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []
    return ScriptAIAssistResponse(
        title=str(parsed.get("title") or request.title or "未命名剧本").strip(),
        description=str(parsed.get("description") or request.description or "").strip(),
        content=str(parsed.get("content") or request.content or "").strip(),
        warnings=[str(item).strip() for item in warnings if str(item).strip()],
    )


@router.get("/generate-context/{chapter_id}", response_model=ScriptContextResponse)
async def get_script_generate_context(
    chapter_id: str,
    style: str = Query("anime", description="剧本风格"),
    genre: Optional[str] = Query(None, description="剧本类型"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取从章节生成剧本时会使用的统一故事上下文。"""
    chapter = await get_chapter_for_user(db, chapter_id, user_id)
    novel = await get_novel_for_user(db, chapter.novel_id, user_id)
    context = await build_script_generation_context(
        db,
        user_id,
        chapter=chapter,
        novel=novel,
        style=style,
        genre=genre,
    )
    summary = summarize_script_context(context)
    return ScriptContextResponse(
        novel_id=novel.id,
        chapter_id=chapter.id,
        story_bible_id=summary.get("story_bible_id"),
        chapter_title=chapter.title,
        previous_chapter=summary.get("previous_chapter"),
        next_chapter=summary.get("next_chapter"),
        context_block=build_story_context_block(context["story_context"], include_chapters=True),
        summary=summary,
        generation_context=_script_context_metadata(
            context=context,
            provider="preview",
            model_id=context["consistency_metadata"].get("default_model_id") or "",
            ai_refined=False,
        ),
    )


@router.post("", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    script: ScriptCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建剧本"""

    novel_title = None
    novel_id = script.novel_id
    chapter_id = script.chapter_id
    if chapter_id:
        chapter = await get_chapter_for_user(db, chapter_id, user_id)
        if novel_id and chapter.novel_id != novel_id:
            raise HTTPException(status_code=422, detail="章节不属于指定小说")
        novel_id = chapter.novel_id
    if novel_id:
        novel = await get_novel_for_user(db, novel_id, user_id)
        novel_title = novel.title
    extra_data = {"chapter_id": chapter_id} if chapter_id else {}

    db_script = await create_script_record(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        title=script.title,
        description=script.description,
        content=script.content,
        genre=script.genre,
        style=script.style,
        duration=script.duration,
        extra_data=extra_data,
    )
    await db.commit()
    await db.refresh(db_script)

    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="created",
        entity_type="script",
        entity_id=db_script.id,
        title=f"创建剧本: {db_script.title}",
    )
    await db.commit()

    return build_script_response(db_script, novel_title)


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    script_update: ScriptUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新剧本"""

    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    db_script = result.scalar_one_or_none()

    if not db_script:
        raise HTTPException(status_code=404, detail="剧本不存在")

    update_data = script_update.model_dump(exclude_unset=True)
    if any(key in update_data for key in ("title", "description", "content", "genre", "style", "duration", "status", "novel_id", "chapter_id")):
        _append_script_snapshot(db_script, "更新前自动快照")

    next_novel_id = update_data.get("novel_id", db_script.novel_id)
    next_chapter_id = update_data.get("chapter_id", db_script.chapter_id)
    if next_chapter_id:
        chapter = await get_chapter_for_user(db, next_chapter_id, user_id)
        if next_novel_id and chapter.novel_id != next_novel_id:
            raise HTTPException(status_code=422, detail="章节不属于指定小说")
        next_novel_id = chapter.novel_id
        update_data["novel_id"] = next_novel_id
    elif "novel_id" in update_data and update_data["novel_id"]:
        await get_novel_for_user(db, update_data["novel_id"], user_id)

    for key, value in update_data.items():
        setattr(db_script, key, value)
    if "chapter_id" in update_data:
        extra_data = dict(db_script.extra_data or {})
        if update_data["chapter_id"]:
            extra_data["chapter_id"] = update_data["chapter_id"]
        else:
            extra_data.pop("chapter_id", None)
        db_script.extra_data = extra_data

    await db.commit()
    await db.refresh(db_script)

    novel_title = None
    if db_script.novel_id:
        novel = await get_novel_for_user(db, db_script.novel_id, user_id)
        novel_title = novel.title

    return build_script_response(db_script, novel_title)


@router.delete("/{script_id}")
async def delete_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除剧本"""

    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    db_script = result.scalar_one_or_none()

    if not db_script:
        raise HTTPException(status_code=404, detail="剧本不存在")

    await db.delete(db_script)
    await db.commit()

    return {"message": "剧本已删除"}


@router.get("/{script_id}/check-consistency", response_model=ScriptConsistencyCheckResponse)
async def check_script_consistency(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """检查剧本与小说、章节、人物、场景、道具和事件上下文的一致性。"""
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    issues, summary = await check_script_consistency_internal(db, user_id, script)
    return ScriptConsistencyCheckResponse(
        script_id=script.id,
        issue_count=len(issues),
        issues=issues,
        summary=summary,
    )


@router.get("/{script_id}/versions", response_model=List[ScriptVersionResponse])
async def list_script_versions(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取剧本版本快照。"""
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    extra_data = script.extra_data if isinstance(script.extra_data, dict) else {}
    snapshots = extra_data.get("version_snapshots") if isinstance(extra_data.get("version_snapshots"), list) else []
    return [
        ScriptVersionResponse(
            id=item.get("id"),
            note=item.get("note"),
            created_at=item.get("created_at"),
            title=item.get("title") or script.title,
            description=item.get("description"),
            status=item.get("status"),
        )
        for item in reversed(snapshots)
        if isinstance(item, dict) and item.get("id") and item.get("created_at")
    ]


@router.post("/{script_id}/versions", response_model=ScriptVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_script_version(
    script_id: str,
    request: ScriptVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """手动创建剧本版本快照。"""
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    snapshot = _append_script_snapshot(script, request.note)
    await db.commit()
    return ScriptVersionResponse(
        id=snapshot["id"],
        note=snapshot.get("note"),
        created_at=snapshot["created_at"],
        title=snapshot["title"],
        description=snapshot.get("description"),
        status=snapshot.get("status"),
    )


@router.post("/{script_id}/versions/restore", response_model=ScriptResponse)
async def restore_script_version(
    script_id: str,
    request: ScriptVersionRestoreRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """恢复剧本版本快照。"""
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    extra_data = dict(script.extra_data or {})
    snapshots = extra_data.get("version_snapshots") if isinstance(extra_data.get("version_snapshots"), list) else []
    snapshot = next((item for item in snapshots if isinstance(item, dict) and item.get("id") == request.snapshot_id), None)
    if not snapshot:
        raise HTTPException(status_code=404, detail="剧本版本不存在")

    _append_script_snapshot(script, "恢复前自动快照")
    script.title = snapshot.get("title") or script.title
    script.description = snapshot.get("description")
    script.content = snapshot.get("content")
    script.genre = snapshot.get("genre")
    script.style = snapshot.get("style")
    script.duration = snapshot.get("duration")
    script.status = snapshot.get("status") or script.status
    script.novel_id = snapshot.get("novel_id") or script.novel_id
    script.chapter_id = snapshot.get("chapter_id") or script.chapter_id
    extra_data = dict(script.extra_data or {})
    if script.chapter_id:
        extra_data["chapter_id"] = script.chapter_id
    extra_data["last_restored_snapshot_id"] = request.snapshot_id
    extra_data["last_restored_at"] = utc_now().isoformat()
    script.extra_data = extra_data
    script.updated_at = utc_now()
    await db.commit()
    await db.refresh(script)

    novel_title = None
    if script.novel_id:
        novel = await get_novel_for_user(db, script.novel_id, user_id)
        novel_title = novel.title
    return build_script_response(script, novel_title)


@router.post("/generate", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def generate_script(
    request: ScriptGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成剧本 - 将章节内容转换为分镜头剧本"""

    chapter = await get_chapter_for_user(db, request.chapter_id, user_id)
    if not chapter.content:
        raise HTTPException(status_code=400, detail="章节内容为空，无法生成剧本")

    chapter_id = chapter.id
    novel_id = chapter.novel_id
    chapter_title = chapter.title
    chapter_label = format_chapter_label(chapter.title, chapter.chapter_number)
    novel = await get_novel_for_user(db, novel_id, user_id)

    # 风格配置
    style_configs = {
        "anime": "动画风格：鲜艳色彩、夸张表情、流畅动作、幻想元素，镜头节奏明快",
        "anime_cartoon": "动画卡通风格：简化造型、可爱角色，明快节奏，适合轻松剧情",
        "realistic": "写实风格：真实光影、细腻表演，自然对话，电影感镜头",
        "cyberpunk": "赛博朋克风格：霓虹光效、高科技设定，未来城市感，冷色调",
        "fantasy": "奇幻风格：魔法效果、异世界设定、史诗场景，大场面调度",
    }
    style_desc = style_configs.get(request.style, f"风格：{request.style or '默认'}")
    genre_hint = f"类型：{request.genre or novel.genre or '通用'}"
    generation_context = await build_script_generation_context(
        db,
        user_id,
        chapter=chapter,
        novel=novel,
        style=request.style,
        genre=request.genre,
    )
    system_prompt, user_prompt = build_script_prompt_blocks(
        novel=novel,
        chapter=chapter,
        context=generation_context,
        style_desc=style_desc,
        genre_hint=genre_hint,
    )

    provider_name = "dev_mode"
    model_id = generation_context["consistency_metadata"].get("default_model_id") or ""
    ai_refined = False
    try:
        service, provider_name, model_id, _base_url = await get_user_text_generation_service(
            db, user_id, config_id=request.model_config_id,
        )
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.68,
            max_tokens=12000
        )
        script_content = response["choices"][0]["message"]["content"]
        ai_refined = True
    except HTTPException:
        if not is_dev_mode():
            raise
        script_content = build_dev_script_content(
            novel=novel,
            chapter=chapter,
            context=generation_context,
            style_desc=style_desc,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成剧本失败: {str(e)}"
        )

    # 从AI返回内容中提取标题
    script_content = (script_content or "").strip().strip("`").strip()
    title_match = re.search(r"[「\"]?剧本标题[：:]\s*(.+?)[」\"]?\s*(?:\n|$)", script_content)
    if title_match:
        script_title = title_match.group(1).strip(" 「」\"")
        lines = script_content.split('\n')
        content_start = 0
        for i, line in enumerate(lines):
            if '剧本标题' in line:
                content_start = i + 1
                break
        script_content = '\n'.join(lines[content_start:]).strip()
    else:
        script_title = f"{chapter_label} 剧本" if chapter else f"{chapter_title} - 剧本"
    script_title = normalize_duplicate_chapter_label_text(script_title) or script_title

    # 创建剧本记录
    script_id = str(uuid4())

    db_script = Script(
        id=script_id,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        title=script_title,
        description=f"改编自《{chapter_label}》，{style_desc}",
        content=script_content,
        genre=request.genre or novel.genre or "unknown",
        style=request.style,
        status="completed",
        extra_data={
            "source": "chapter_script_generation",
            "chapter_id": chapter_id,
            "chapter_title": chapter_label,
            "chapter_number": chapter.chapter_number,
            "generation_context": _script_context_metadata(
                context=generation_context,
                provider=provider_name or "unknown",
                model_id=model_id or "",
                ai_refined=ai_refined,
            ),
        },
    )
    db.add(db_script)
    await db.commit()
    await db.refresh(db_script)

    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="generated",
        entity_type="script",
        entity_id=db_script.id,
        title=f"AI生成剧本: {db_script.title}",
    )
    await db.commit()

    return build_script_response(db_script, novel.title)
