"""
Story Bible API for consistency management.
"""

from app.core.time_utils import utc_now
from datetime import datetime
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_utils import create_text_generation_service, get_user_text_model_config
from app.core.database import get_db
from app.core.dev_generation import is_dev_mode
from app.core.security import get_current_user_id
from app.models import Asset, Character, Chapter, Novel, Project, Script, Shot, StoryBible, StoryEntity
from app.services.entity_extraction_service import (
    ENTITY_TYPES,
    build_story_bible_sections,
    extract_story_entities,
    normalize_extracted_entities,
)
from app.services.default_anime_library import ensure_default_story_entities
from app.services.prompt_composer import compose_generation_prompt
from app.services.prompt_skill_service import active_prompt_skill_blocks
from app.services.story_state_machine import (
    build_story_state_machine,
    check_story_state_machine,
    get_story_state_machine,
)

router = APIRouter(tags=["故事圣经"])


class StoryBibleBase(BaseModel):
    project_id: Optional[str] = None
    novel_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    style: Optional[str] = None
    worldview: Optional[str] = None
    character_rules: List[Dict[str, Any]] = Field(default_factory=list)
    scene_rules: List[Dict[str, Any]] = Field(default_factory=list)
    prop_rules: List[Dict[str, Any]] = Field(default_factory=list)
    event_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    negative_prompt: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class StoryBibleCreateRequest(StoryBibleBase):
    pass


class StoryBibleUpdateRequest(BaseModel):
    project_id: Optional[str] = None
    novel_id: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    style: Optional[str] = None
    worldview: Optional[str] = None
    character_rules: Optional[List[Dict[str, Any]]] = None
    scene_rules: Optional[List[Dict[str, Any]]] = None
    prop_rules: Optional[List[Dict[str, Any]]] = None
    event_timeline: Optional[List[Dict[str, Any]]] = None
    negative_prompt: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class StoryBibleResponse(StoryBibleBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class ComposePromptRequest(BaseModel):
    task: str = Field("shot_video", description="生成任务，如 shot_video/character_image/tts_dialogue")
    story_bible_id: Optional[str] = None
    project_id: Optional[str] = None
    shot_id: Optional[str] = None
    character_ids: List[str] = Field(default_factory=list)
    extra_context: Dict[str, Any] = Field(default_factory=dict)


class ComposePromptResponse(BaseModel):
    prompt: str
    story_bible_id: Optional[str] = None
    project_id: Optional[str] = None
    shot_id: Optional[str] = None
    character_ids: List[str]


class StoryEntityResponse(BaseModel):
    id: str
    user_id: str
    novel_id: Optional[str]
    chapter_id: Optional[str]
    script_id: Optional[str] = None
    entity_type: str
    name: str
    canonical_name: Optional[str] = None
    description: Optional[str]
    aliases: List[str] = Field(default_factory=list)
    appearance: Optional[str] = None  # 外观描述
    visual_prompt: Optional[str] = None  # 图像生成提示词
    first_seen_chapter_id: Optional[str] = None
    relations: List[Dict[str, Any]] = Field(default_factory=list)  # 关系
    state_changes: List[Dict[str, Any]] = Field(default_factory=list)  # 状态变化
    attributes: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    version: int = 1
    is_approved: bool = False
    consistency_score: float = 1.0
    evidence: Optional[str]
    confidence: int
    source: str
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class StoryEntityStatsResponse(BaseModel):
    total: int
    counts: Dict[str, int]


class StoryEntityCreateRequest(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_type: str = Field(..., description="character/scene/prop/event")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    evidence: Optional[str] = None
    confidence: int = Field(100, ge=0, le=100)
    source: str = Field("manual", max_length=20)


class StoryEntityUpdateRequest(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_type: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    aliases: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    evidence: Optional[str] = None
    confidence: Optional[int] = Field(None, ge=0, le=100)
    source: Optional[str] = Field(None, max_length=20)


class StoryEntityVersionSnapshotRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=200)


class StoryEntityVersionRestoreRequest(BaseModel):
    snapshot_id: str = Field(..., min_length=1)


class StoryEntityScopeUpdate(BaseModel):
    scope: str = Field(..., description="global/novel/chapter/script")
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None


class EntityConsistencyCheckRequest(BaseModel):
    novel_id: str = Field(..., min_length=1)
    chapter_id: Optional[str] = None


class EntityConsistencyCheckResponse(BaseModel):
    novel_id: str
    chapter_id: Optional[str] = None
    issue_count: int
    issues: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ProductionPackResponse(BaseModel):
    novel_id: str
    counts: Dict[str, int]
    characters: List[StoryEntityResponse]
    scenes: List[StoryEntityResponse]
    props: List[StoryEntityResponse]
    events: List[StoryEntityResponse]
    relationships: List[Dict[str, Any]]
    event_timeline: List[Dict[str, Any]]
    scene_tags: List[Dict[str, Any]]
    asset_requirements: List[Dict[str, Any]]


class EntityExtractionRequest(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    text: Optional[str] = None
    entity_types: List[str] = Field(default_factory=lambda: sorted(ENTITY_TYPES))
    persist: bool = True
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class EntityExtractionResponse(BaseModel):
    novel_id: Optional[str]
    chapter_id: Optional[str]
    script_id: Optional[str] = None
    entities: List[StoryEntityResponse]


class ExtractedAssetResponse(BaseModel):
    id: str
    category: str
    name: str
    asset_type: str
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    entity_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class EntityAssetExtractionRequest(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    text: Optional[str] = None
    entity_types: List[str] = Field(default_factory=lambda: sorted(ENTITY_TYPES))
    persist_entities: bool = True
    create_assets: bool = True
    asset_scope: str = Field("entity", description="global/novel/chapter/script/entity")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class EntityAssetExtractionResponse(BaseModel):
    novel_id: Optional[str]
    chapter_id: Optional[str]
    script_id: Optional[str] = None
    entities: List[StoryEntityResponse]
    assets: List[ExtractedAssetResponse] = Field(default_factory=list)


class GenerateFromNovelRequest(BaseModel):
    novel_id: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=200)
    project_id: Optional[str] = None
    style: Optional[str] = None
    negative_prompt: Optional[str] = None
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class SyncFromChapterRequest(BaseModel):
    story_bible_id: str = Field(..., min_length=1)
    chapter_id: str = Field(..., min_length=1)


class ConsistencyCheckRequest(BaseModel):
    story_bible_id: str = Field(..., min_length=1)
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    text: Optional[str] = None


class ConsistencyIssue(BaseModel):
    entity_type: str
    name: str
    severity: str
    message: str
    evidence: Optional[str] = None


class ConsistencyCheckResponse(BaseModel):
    story_bible_id: str
    checked_entity_count: int
    issue_count: int
    issues: List[ConsistencyIssue]


class ResolveConflictRequest(BaseModel):
    story_bible_id: str = Field(..., min_length=1)
    issue_code: str = Field(..., description="冲突代码，如 character_appearance_conflict")
    resolution: str = Field(..., description="解决方式: accept_incoming/reject_incoming/merge/manual")
    resolved_data: Optional[Dict[str, Any]] = Field(None, description="手动解决时的新数据")
    entity_id: Optional[str] = Field(None, description="关联的实体ID")


class ResolveConflictResponse(BaseModel):
    resolved: bool
    issue_code: str
    resolution: str
    updated_entity: Optional[StoryEntityResponse] = None
    updated_story_bible: Optional[StoryBibleResponse] = None


class StoryStateMachineRequest(BaseModel):
    novel_id: Optional[str] = None
    persist: bool = True


class StoryStateMachineResponse(BaseModel):
    story_bible_id: str
    novel_id: Optional[str] = None
    state_machine: Dict[str, Any]


class StoryStateMachineCheckResponse(BaseModel):
    story_bible_id: str
    novel_id: Optional[str] = None
    generated_transient: bool
    issue_count: int
    issues: List[Dict[str, Any]]
    summary: Dict[str, Any]


def build_story_bible_response(story_bible: StoryBible) -> StoryBibleResponse:
    return StoryBibleResponse(
        id=story_bible.id,
        user_id=story_bible.user_id,
        project_id=story_bible.project_id,
        novel_id=story_bible.novel_id,
        title=story_bible.title,
        style=story_bible.style,
        worldview=story_bible.worldview,
        character_rules=story_bible.character_rules or [],
        scene_rules=story_bible.scene_rules or [],
        prop_rules=story_bible.prop_rules or [],
        event_timeline=story_bible.event_timeline or [],
        negative_prompt=story_bible.negative_prompt,
        extra_data=story_bible.extra_data or {},
        created_at=story_bible.created_at,
        updated_at=story_bible.updated_at,
    )


def build_story_entity_response(entity: StoryEntity) -> StoryEntityResponse:
    return StoryEntityResponse(
        id=entity.id,
        user_id=entity.user_id,
        novel_id=entity.novel_id,
        chapter_id=entity.chapter_id,
        script_id=getattr(entity, "script_id", None),
        entity_type=entity.entity_type,
        name=entity.name,
        canonical_name=getattr(entity, "canonical_name", None),
        description=entity.description,
        aliases=entity.aliases or [],
        appearance=getattr(entity, "appearance", None),
        visual_prompt=getattr(entity, "visual_prompt", None),
        first_seen_chapter_id=getattr(entity, "first_seen_chapter_id", None),
        relations=getattr(entity, "relations", []) or [],
        state_changes=getattr(entity, "state_changes", []) or [],
        attributes=entity.attributes or {},
        tags=getattr(entity, "tags", []) or [],
        version=getattr(entity, "version", 1) or 1,
        is_approved=getattr(entity, "is_approved", False) or False,
        consistency_score=getattr(entity, "consistency_score", 1.0) or 1.0,
        evidence=entity.evidence,
        confidence=entity.confidence or 0,
        source=entity.source or "deterministic",
        extra_data=getattr(entity, "extra_data", {}) or {},
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


async def _get_story_bible_or_404(db: AsyncSession, story_bible_id: str, user_id: str) -> StoryBible:
    result = await db.execute(
        select(StoryBible).where(StoryBible.id == story_bible_id, StoryBible.user_id == user_id)
    )
    story_bible = result.scalar_one_or_none()
    if story_bible is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story Bible 不存在")
    return story_bible


async def _get_novel_or_404(db: AsyncSession, novel_id: str, user_id: str) -> Novel:
    result = await db.execute(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")
    return novel


async def _get_chapter_or_404(db: AsyncSession, chapter_id: str, user_id: str) -> Chapter:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == user_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")
    return chapter


async def _get_script_or_404(db: AsyncSession, script_id: str, user_id: str) -> Script:
    result = await db.execute(select(Script).where(Script.id == script_id, Script.user_id == user_id))
    script = result.scalar_one_or_none()
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="剧本不存在")
    return script


async def _get_story_entity_or_404(db: AsyncSession, entity_id: str, user_id: str) -> StoryEntity:
    result = await db.execute(
        select(StoryEntity).where(StoryEntity.id == entity_id, StoryEntity.user_id == user_id)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="实体不存在")
    return entity


def _validate_entity_type(entity_type: str) -> str:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的实体类型")
    return entity_type


def _apply_story_entity_scope_filters(
    query: Any,
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
    scope: Optional[str],
) -> Any:
    if not scope:
        if novel_id:
            query = query.where(or_(StoryEntity.novel_id == novel_id, StoryEntity.novel_id.is_(None)))
        if chapter_id:
            query = query.where(or_(StoryEntity.chapter_id == chapter_id, StoryEntity.chapter_id.is_(None)))
        if script_id:
            query = query.where(or_(StoryEntity.script_id == script_id, StoryEntity.script_id.is_(None)))
        return query

    if scope == "novel":
        if novel_id:
            query = query.where(StoryEntity.novel_id == novel_id)
        return query.where(
            StoryEntity.novel_id.is_not(None),
            StoryEntity.chapter_id.is_(None),
            StoryEntity.script_id.is_(None),
        )

    if scope == "chapter":
        if novel_id:
            query = query.where(StoryEntity.novel_id == novel_id)
        if chapter_id:
            query = query.where(StoryEntity.chapter_id == chapter_id)
        return query.where(
            StoryEntity.chapter_id.is_not(None),
            StoryEntity.script_id.is_(None),
        )

    if scope == "script":
        if novel_id:
            query = query.where(StoryEntity.novel_id == novel_id)
        if chapter_id:
            query = query.where(StoryEntity.chapter_id == chapter_id)
        if script_id:
            query = query.where(StoryEntity.script_id == script_id)
        return query.where(StoryEntity.script_id.is_not(None))

    return query.where(
        StoryEntity.novel_id.is_(None),
        StoryEntity.chapter_id.is_(None),
        StoryEntity.script_id.is_(None),
    )


async def _resolve_entity_scope(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
) -> dict[str, Optional[str]]:
    resolved = {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "script_id": script_id,
    }
    if novel_id:
        await _get_novel_or_404(db, novel_id, user_id)
    if chapter_id:
        chapter = await _get_chapter_or_404(db, chapter_id, user_id)
        if novel_id and chapter.novel_id != novel_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="章节不属于指定小说")
        resolved["novel_id"] = chapter.novel_id
    if script_id:
        script = await _get_script_or_404(db, script_id, user_id)
        script_extra = script.extra_data if isinstance(script.extra_data, dict) else {}
        script_chapter_id = script.chapter_id or script_extra.get("chapter_id")
        if resolved["novel_id"] and script.novel_id and script.novel_id != resolved["novel_id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="剧本不属于指定小说")
        if resolved["chapter_id"] and script_chapter_id and script_chapter_id != resolved["chapter_id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="剧本不属于指定章节")
        if script_chapter_id:
            chapter = await _get_chapter_or_404(db, script_chapter_id, user_id)
            if script.novel_id and chapter.novel_id != script.novel_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="剧本章节与小说不匹配")
            if resolved["novel_id"] and chapter.novel_id != resolved["novel_id"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="剧本章节不属于指定小说")
            resolved["novel_id"] = resolved["novel_id"] or chapter.novel_id
        resolved["novel_id"] = resolved["novel_id"] or script.novel_id
        resolved["chapter_id"] = resolved["chapter_id"] or script_chapter_id
    return resolved


async def _resolve_extraction_text(
    db: AsyncSession,
    user_id: str,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
    text: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str], str]:
    if text and text.strip():
        scope = await _resolve_entity_scope(db, user_id, novel_id=novel_id, chapter_id=chapter_id, script_id=script_id)
        return scope["novel_id"], scope["chapter_id"], scope["script_id"], text

    if script_id:
        scope = await _resolve_entity_scope(db, user_id, novel_id=novel_id, chapter_id=chapter_id, script_id=script_id)
        script = await _get_script_or_404(db, script_id, user_id)
        return scope["novel_id"], scope["chapter_id"], scope["script_id"], script.content or script.description or ""

    if chapter_id:
        chapter = await _get_chapter_or_404(db, chapter_id, user_id)
        if novel_id and chapter.novel_id != novel_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="章节不属于指定小说")
        return chapter.novel_id, chapter.id, None, chapter.content or ""

    if novel_id:
        await _get_novel_or_404(db, novel_id, user_id)
        result = await db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id, Chapter.user_id == user_id)
            .order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()
        return novel_id, None, None, "\n\n".join(chapter.content or "" for chapter in chapters)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="必须提供 novel_id、chapter_id、script_id 或 text")


async def _extract_and_optionally_persist(
    db: AsyncSession,
    user_id: str,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
    text: str,
    entity_types: List[str],
    persist: bool,
    model_config_id: Optional[str] = None,
) -> list[StoryEntity]:
    try:
        extracted = await _extract_story_entities_with_optional_ai(
            db,
            user_id,
            text,
            entity_types,
            model_config_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    entities = [
        StoryEntity(
            id=str(uuid4()),
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            entity_type=item["entity_type"],
            name=item["name"],
            description=item.get("description"),
            aliases=item.get("aliases") or [],
            attributes=item.get("attributes") or {},
            evidence=item.get("evidence"),
            confidence=item.get("confidence") or 100,
            source=item.get("source") or "deterministic",
        )
        for item in extracted
    ]
    if persist:
        for entity in entities:
            db.add(entity)
        await db.commit()
        for entity in entities:
            await db.refresh(entity)
    return entities


def _entity_dicts(entities: list[StoryEntity]) -> list[dict[str, Any]]:
    return [
        {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "name": entity.name,
            "description": entity.description,
            "evidence": entity.evidence,
        }
        for entity in entities
    ]


def _merge_rules(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(existing or [])
    names = {item.get("name") or item.get("title") for item in merged}
    for item in incoming:
        key = item.get("name") or item.get("title")
        if key not in names:
            merged.append(item)
            names.add(key)
    return merged


def _parse_entity_json(content: str) -> list[dict[str, Any]]:
    json_str = (content or "").strip()
    if "```json" in json_str:
        json_str = json_str.split("```json", 1)[1]
    elif "```" in json_str:
        json_str = json_str.split("```", 1)[1]
    if "```" in json_str:
        json_str = json_str.split("```", 1)[0]
    parsed = json.loads(json_str.strip())
    if isinstance(parsed, dict):
        parsed = parsed.get("entities") or [parsed]
    if not isinstance(parsed, list):
        return []
    allowed = ENTITY_TYPES
    entities = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        entity_type = str(item.get("entity_type") or item.get("type") or "").strip()
        name = str(item.get("name") or item.get("title") or "").strip()
        if entity_type not in allowed or not name:
            continue
        entities.append({
            "entity_type": entity_type,
            "name": name[:200],
            "description": item.get("description") or item.get("evidence"),
            "aliases": item.get("aliases") if isinstance(item.get("aliases"), list) else [],
            "attributes": item.get("attributes") if isinstance(item.get("attributes"), dict) else {},
            "evidence": item.get("evidence") or item.get("description"),
            "confidence": item.get("confidence") or 90,
            "source": "ai",
        })
    return normalize_extracted_entities(entities)


async def _extract_story_entities_with_optional_ai(
    db: AsyncSession,
    user_id: str,
    text: str,
    entity_types: List[str],
    model_config_id: Optional[str],
) -> list[dict[str, Any]]:
    requested = set(entity_types)
    if model_config_id:
        try:
            api_key, provider_name, model_id, base_url = await get_user_text_model_config(
                db,
                user_id,
                config_id=model_config_id,
            )
            service = create_text_generation_service(api_key or "", provider_name or "", base_url)
            prompt = f"""请从小说文本中提取结构化实体，严格输出 JSON 数组。

实体类型只能使用：{', '.join(sorted(requested))}
每个实体字段：
- entity_type: character/scene/prop/event
- name: 中文名称
- description: 简短描述
- aliases: 别名数组
- attributes: 对象，可包含人物关系、场景标签、道具状态、事件参与者等
- evidence: 来自原文的依据
- confidence: 0-100

分类规则：
- character：明确命名的单个人物、妖兽、可持续追踪的个体，通常有动作、台词、身份或关系。
- scene：可复用的地点、空间、环境，如宗门、石屋、街巷、洞府、城门、战场。
- prop：可见且需要前后一致的物件、装备、法器、服饰、钥匙、令牌、武器等。
- event：情节动作或状态变化，不要把事件短句当作人物/场景/道具。

负面规则：
- 不要把地点、房间、建筑、道具、装备分类为 character。
- 不要把“外门弟子们、众人、守卫们、路人”等群体背景分类为 character，除非原文明确给出单个姓名。
- 不要把人物姓名分类为 scene/prop；如果人物有“说、问、低声道、醒来、发现”等行为，应归为 character。
- 道具与场景必须来自小说文本或剧本证据，不要凭题材臆造无关资产。

不要输出 Markdown、解释或推理过程。

小说文本：
{text[:30000]}"""
            response = await service.safe_chat_completion(
                model=model_id or "",
                messages=[
                    {"role": "system", "content": "你是小说动漫制作的实体抽取专家，输出必须可被 JSON 解析。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=5000,
            )
            ai_entities = _parse_entity_json(response["choices"][0]["message"]["content"])
            ai_entities = [item for item in ai_entities if item["entity_type"] in requested]
            if ai_entities:
                return ai_entities
        except HTTPException:
            if not is_dev_mode():
                raise
        except Exception as exc:
            if not is_dev_mode():
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI实体抽取失败: {str(exc)}")

    return extract_story_entities(text, requested)


def _known_bible_names(story_bible: StoryBible, entity_type: str) -> set[str]:
    if entity_type == "character":
        items = story_bible.character_rules or []
    elif entity_type == "scene":
        items = story_bible.scene_rules or []
    elif entity_type == "prop":
        items = story_bible.prop_rules or []
    elif entity_type == "event":
        items = story_bible.event_timeline or []
    else:
        items = []
    return {item.get("name") or item.get("title") for item in items if item.get("name") or item.get("title")}


def _entity_attr(entity: StoryEntity) -> Dict[str, Any]:
    return entity.attributes if isinstance(entity.attributes, dict) else {}


def _append_entity_snapshot(entity: StoryEntity, note: Optional[str]) -> Dict[str, Any]:
    attrs = dict(_entity_attr(entity))
    snapshots = list(attrs.get("version_snapshots") or [])
    snapshot = {
        "id": str(uuid4()),
        "note": note or "手动快照",
        "created_at": utc_now().isoformat(),
        "entity_type": entity.entity_type,
        "name": entity.name,
        "description": entity.description,
        "aliases": entity.aliases or [],
        "attributes": {
            key: value for key, value in attrs.items()
            if key != "version_snapshots"
        },
        "evidence": entity.evidence,
        "confidence": entity.confidence or 0,
        "source": entity.source or "manual",
    }
    snapshots.append(snapshot)
    attrs["version_snapshots"] = snapshots[-20:]
    entity.attributes = attrs
    entity.updated_at = utc_now()
    return snapshot


def _relationship_items(entity: StoryEntity) -> List[Dict[str, Any]]:
    attrs = _entity_attr(entity)
    relationships = attrs.get("relationships")
    if not isinstance(relationships, list):
        return []
    return [
        {
            **relationship,
            "source_entity_id": entity.id,
            "source_entity_name": entity.name,
        }
        for relationship in relationships
        if isinstance(relationship, dict)
    ]


def _event_item(entity: StoryEntity) -> Dict[str, Any]:
    attrs = _entity_attr(entity)
    return {
        "id": entity.id,
        "name": entity.name,
        "chapter_id": entity.chapter_id,
        "description": entity.description,
        "sequence": attrs.get("sequence"),
        "participants": attrs.get("participants") or [],
        "location": attrs.get("location"),
        "prop_state_changes": attrs.get("prop_state_changes") or [],
        "evidence": entity.evidence,
    }


def _scene_tag_item(entity: StoryEntity) -> Dict[str, Any]:
    attrs = _entity_attr(entity)
    tags = attrs.get("scene_tags") or attrs.get("tags") or []
    if isinstance(tags, str):
        tags = [item.strip() for item in tags.split(",") if item.strip()]
    return {
        "id": entity.id,
        "name": entity.name,
        "chapter_id": entity.chapter_id,
        "tags": tags if isinstance(tags, list) else [],
        "scene_dna": attrs.get("scene_dna") or attrs.get("visual_dna") or {},
        "description": entity.description,
    }


def _asset_requirement_items(entity: StoryEntity) -> List[Dict[str, Any]]:
    attrs = _entity_attr(entity)
    if entity.entity_type == "character":
        return [{
            "entity_id": entity.id,
            "entity_name": entity.name,
            "entity_type": entity.entity_type,
            "required": ["front", "side", "full_body", "expression_neutral", "expression_emotion", "costume_default"],
            "available": attrs.get("asset_pack") or attrs.get("reference_assets") or {},
        }]
    if entity.entity_type == "scene":
        return [{
            "entity_id": entity.id,
            "entity_name": entity.name,
            "entity_type": entity.entity_type,
            "required": ["wide_shot", "lighting_reference", "layout"],
            "available": attrs.get("scene_assets") or attrs.get("reference_assets") or {},
        }]
    if entity.entity_type == "prop":
        return [{
            "entity_id": entity.id,
            "entity_name": entity.name,
            "entity_type": entity.entity_type,
            "required": ["front", "scale", "material_reference"],
            "available": attrs.get("prop_assets") or attrs.get("reference_assets") or {},
        }]
    return []


def _asset_category_for_entity(entity_type: str) -> str:
    if entity_type in {"character", "scene", "prop"}:
        return entity_type
    return "prompt"


def _build_extracted_asset_response(asset: Asset) -> ExtractedAssetResponse:
    return ExtractedAssetResponse(
        id=asset.id,
        category=asset.category,
        name=asset.name,
        asset_type=asset.asset_type or "text",
        novel_id=asset.novel_id,
        chapter_id=asset.chapter_id,
        script_id=asset.script_id,
        entity_id=asset.entity_id,
        tags=asset.tags or [],
    )


def _asset_scope_values_for_entity(
    entity: StoryEntity,
    asset_scope: str,
) -> dict[str, Optional[str]]:
    if asset_scope == "global":
        return {"novel_id": None, "chapter_id": None, "script_id": None, "entity_id": None}
    if asset_scope == "novel":
        return {"novel_id": entity.novel_id, "chapter_id": None, "script_id": None, "entity_id": None}
    if asset_scope == "chapter":
        return {"novel_id": entity.novel_id, "chapter_id": entity.chapter_id, "script_id": None, "entity_id": None}
    if asset_scope == "script":
        return {
            "novel_id": entity.novel_id,
            "chapter_id": entity.chapter_id,
            "script_id": getattr(entity, "script_id", None),
            "entity_id": None,
        }
    if asset_scope == "entity":
        return {
            "novel_id": entity.novel_id,
            "chapter_id": entity.chapter_id,
            "script_id": getattr(entity, "script_id", None),
            "entity_id": entity.id,
        }
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的资产作用域")


async def _create_assets_for_entities(
    db: AsyncSession,
    user_id: str,
    entities: list[StoryEntity],
    asset_scope: str,
) -> list[Asset]:
    if asset_scope not in {"global", "novel", "chapter", "script", "entity"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的资产作用域")
    assets: list[Asset] = []
    for entity in entities:
        scope = _asset_scope_values_for_entity(entity, asset_scope)
        if asset_scope == "novel" and not scope["novel_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="小说资产作用域需要 novel_id")
        if asset_scope == "chapter" and not scope["chapter_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="章节资产作用域需要 chapter_id")
        if asset_scope == "script" and not scope["script_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="剧本资产作用域需要 script_id")
        asset = Asset(
            id=str(uuid4()),
            user_id=user_id,
            category=_asset_category_for_entity(entity.entity_type),
            name=entity.name,
            description=entity.description or entity.evidence,
            asset_type="text",
            project_id=None,
            novel_id=scope["novel_id"],
            chapter_id=scope["chapter_id"],
            script_id=scope["script_id"],
            entity_id=scope["entity_id"],
            tags=["AI抽取", entity.entity_type],
            style_tags=[],
            prompt_template=None,
            variables=[],
            shot_template=None,
            is_public=False,
            generation_params={
                "source": "entity_extraction",
                "asset_scope": asset_scope,
                "entity_id": entity.id,
                "entity_type": entity.entity_type,
                "evidence": entity.evidence,
                "confidence": entity.confidence or 0,
                "novel_id": entity.novel_id,
                "chapter_id": entity.chapter_id,
                "script_id": getattr(entity, "script_id", None),
            },
        )
        db.add(asset)
        assets.append(asset)
    if assets:
        await db.commit()
        for asset in assets:
            await db.refresh(asset)
    return assets


def _build_entity_consistency(entities: List[StoryEntity]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    by_type: Dict[str, List[StoryEntity]] = {entity_type: [] for entity_type in sorted(ENTITY_TYPES)}
    for entity in entities:
        by_type.setdefault(entity.entity_type, []).append(entity)

    names_by_type = {
        entity_type: {entity.name for entity in items}
        for entity_type, items in by_type.items()
    }

    for character in by_type.get("character", []):
        attrs = _entity_attr(character)
        asset_pack = attrs.get("asset_pack") or attrs.get("reference_assets") or {}
        missing = [
            key for key in ["front", "side", "full_body"]
            if not (isinstance(asset_pack, dict) and asset_pack.get(key))
        ]
        if missing:
            issues.append({
                "code": "missing_character_views",
                "severity": "warning",
                "entity_id": character.id,
                "entity_name": character.name,
                "message": f"角色缺少多角度参考：{', '.join(missing)}",
            })

    for scene in by_type.get("scene", []):
        attrs = _entity_attr(scene)
        tags = attrs.get("scene_tags") or attrs.get("tags")
        if not tags:
            issues.append({
                "code": "missing_scene_tags",
                "severity": "warning",
                "entity_id": scene.id,
                "entity_name": scene.name,
                "message": "场景缺少室内/室外/战斗/日常等标签",
            })

    for prop in by_type.get("prop", []):
        attrs = _entity_attr(prop)
        if not attrs.get("prop_dna") and not attrs.get("visual_dna"):
            issues.append({
                "code": "missing_prop_dna",
                "severity": "warning",
                "entity_id": prop.id,
                "entity_name": prop.name,
                "message": "道具缺少视觉 DNA，跨场景一致性无法稳定检查",
            })

    for event in by_type.get("event", []):
        attrs = _entity_attr(event)
        for participant in attrs.get("participants") or []:
            if participant and participant not in names_by_type.get("character", set()):
                issues.append({
                    "code": "unknown_event_participant",
                    "severity": "warning",
                    "entity_id": event.id,
                    "entity_name": event.name,
                    "message": f"事件参与者未在角色库中登记：{participant}",
                })
        for prop_change in attrs.get("prop_state_changes") or []:
            prop_name = prop_change.get("prop") if isinstance(prop_change, dict) else None
            if prop_name and prop_name not in names_by_type.get("prop", set()):
                issues.append({
                    "code": "unknown_event_prop",
                    "severity": "warning",
                    "entity_id": event.id,
                    "entity_name": event.name,
                    "message": f"事件涉及道具未登记：{prop_name}",
                })

    summary = {
        "characters": len(by_type.get("character", [])),
        "scenes": len(by_type.get("scene", [])),
        "props": len(by_type.get("prop", [])),
        "events": len(by_type.get("event", [])),
    }
    return issues, summary


@router.post("/entities/extract", response_model=EntityExtractionResponse)
async def extract_entities(
    request: EntityExtractionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel_id, chapter_id, script_id, text = await _resolve_extraction_text(
        db, user_id, request.novel_id, request.chapter_id, request.script_id, request.text
    )
    entities = await _extract_and_optionally_persist(
        db,
        user_id,
        novel_id,
        chapter_id,
        script_id,
        text,
        request.entity_types,
        request.persist,
        model_config_id=request.model_config_id,
    )
    return EntityExtractionResponse(
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        entities=[build_story_entity_response(entity) for entity in entities],
    )


@router.post("/entities/extract-assets", response_model=EntityAssetExtractionResponse)
async def extract_entities_and_assets(
    request: EntityAssetExtractionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if request.create_assets and not request.persist_entities:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="创建资产需要同时持久化实体")
    novel_id, chapter_id, script_id, text = await _resolve_extraction_text(
        db, user_id, request.novel_id, request.chapter_id, request.script_id, request.text
    )
    entities = await _extract_and_optionally_persist(
        db,
        user_id,
        novel_id,
        chapter_id,
        script_id,
        text,
        request.entity_types,
        request.persist_entities,
        model_config_id=request.model_config_id,
    )
    assets: list[Asset] = []
    if request.create_assets:
        assets = await _create_assets_for_entities(db, user_id, entities, request.asset_scope)
    return EntityAssetExtractionResponse(
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        entities=[build_story_entity_response(entity) for entity in entities],
        assets=[_build_extracted_asset_response(asset) for asset in assets],
    )


@router.get("/entities", response_model=List[StoryEntityResponse])
async def list_story_entities(
    novel_id: Optional[str] = Query(None),
    chapter_id: Optional[str] = Query(None),
    script_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    scope: Optional[str] = Query(None, description="global/novel/chapter/script"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if entity_type:
        _validate_entity_type(entity_type)
    await ensure_default_story_entities(db, user_id)
    allowed_scopes = {"global", "novel", "chapter", "script"}
    if scope and scope not in allowed_scopes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的实体作用域")
    query = select(StoryEntity).where(StoryEntity.user_id == user_id)
    query = _apply_story_entity_scope_filters(
        query,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        scope=scope,
    )
    if entity_type:
        query = query.where(StoryEntity.entity_type == entity_type)
    result = await db.execute(query.order_by(desc(StoryEntity.updated_at)).limit(limit))
    return [build_story_entity_response(entity) for entity in result.scalars().all()]


@router.get("/entities/stats", response_model=StoryEntityStatsResponse)
async def get_story_entity_stats(
    novel_id: Optional[str] = Query(None),
    chapter_id: Optional[str] = Query(None),
    script_id: Optional[str] = Query(None),
    scope: Optional[str] = Query(None, description="global/novel/chapter/script"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await ensure_default_story_entities(db, user_id)
    allowed_scopes = {"global", "novel", "chapter", "script"}
    if scope and scope not in allowed_scopes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的实体作用域")
    query = select(StoryEntity.entity_type, func.count(StoryEntity.id)).where(StoryEntity.user_id == user_id)
    query = _apply_story_entity_scope_filters(
        query,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        scope=scope,
    )
    result = await db.execute(query.group_by(StoryEntity.entity_type))
    counts = {entity_type: 0 for entity_type in sorted(ENTITY_TYPES)}
    for entity_type, count in result.all():
        counts[str(entity_type)] = int(count or 0)
    return StoryEntityStatsResponse(total=sum(counts.values()), counts=counts)


@router.get("/entities/production-pack/{novel_id}", response_model=ProductionPackResponse)
async def get_story_production_pack(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_novel_or_404(db, novel_id, user_id)
    result = await db.execute(
        select(StoryEntity)
        .where(StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id)
        .order_by(StoryEntity.entity_type, StoryEntity.updated_at)
    )
    entities = list(result.scalars().all())
    characters = [entity for entity in entities if entity.entity_type == "character"]
    scenes = [entity for entity in entities if entity.entity_type == "scene"]
    props = [entity for entity in entities if entity.entity_type == "prop"]
    events = [entity for entity in entities if entity.entity_type == "event"]
    relationships = [
        item
        for entity in characters
        for item in _relationship_items(entity)
    ]
    asset_requirements = [
        item
        for entity in entities
        for item in _asset_requirement_items(entity)
    ]

    return ProductionPackResponse(
        novel_id=novel_id,
        counts={
            "characters": len(characters),
            "scenes": len(scenes),
            "props": len(props),
            "events": len(events),
            "relationships": len(relationships),
        },
        characters=[build_story_entity_response(entity) for entity in characters],
        scenes=[build_story_entity_response(entity) for entity in scenes],
        props=[build_story_entity_response(entity) for entity in props],
        events=[build_story_entity_response(entity) for entity in events],
        relationships=relationships,
        event_timeline=sorted(
            [_event_item(entity) for entity in events],
            key=lambda item: (item.get("sequence") is None, item.get("sequence") or 0, item.get("name") or ""),
        ),
        scene_tags=[_scene_tag_item(entity) for entity in scenes],
        asset_requirements=asset_requirements,
    )


@router.post("/entities/check-consistency", response_model=EntityConsistencyCheckResponse)
async def check_entities_consistency(
    request: EntityConsistencyCheckRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_novel_or_404(db, request.novel_id, user_id)
    query = select(StoryEntity).where(
        StoryEntity.user_id == user_id,
        StoryEntity.novel_id == request.novel_id,
    )
    if request.chapter_id:
        query = query.where(StoryEntity.chapter_id == request.chapter_id)
    result = await db.execute(query)
    entities = list(result.scalars().all())
    issues, summary = _build_entity_consistency(entities)
    return EntityConsistencyCheckResponse(
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        issue_count=len(issues),
        issues=issues,
        summary=summary,
    )


@router.post("/entities", response_model=StoryEntityResponse, status_code=status.HTTP_201_CREATED)
async def create_story_entity(
    request: StoryEntityCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    _validate_entity_type(request.entity_type)
    scope = await _resolve_entity_scope(
        db,
        user_id,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
    )

    entity_data = request.model_dump()
    entity_data.update(scope)
    entity = StoryEntity(id=str(uuid4()), user_id=user_id, **entity_data)
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return build_story_entity_response(entity)


@router.get("/entities/{entity_id}", response_model=StoryEntityResponse)
async def get_story_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return build_story_entity_response(await _get_story_entity_or_404(db, entity_id, user_id))


@router.put("/entities/{entity_id}", response_model=StoryEntityResponse)
async def update_story_entity(
    entity_id: str,
    request: StoryEntityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    entity = await _get_story_entity_or_404(db, entity_id, user_id)
    update_data = request.model_dump(exclude_unset=True)
    if "entity_type" in update_data and update_data["entity_type"] is not None:
        _validate_entity_type(update_data["entity_type"])
    if any(key in update_data for key in ("novel_id", "chapter_id", "script_id")):
        scope = await _resolve_entity_scope(
            db,
            user_id,
            novel_id=update_data.get("novel_id", entity.novel_id),
            chapter_id=update_data.get("chapter_id", entity.chapter_id),
            script_id=update_data.get("script_id", getattr(entity, "script_id", None)),
        )
        update_data.update(scope)
    if isinstance(update_data.get("attributes"), dict):
        existing_snapshots = _entity_attr(entity).get("version_snapshots")
        if existing_snapshots and "version_snapshots" not in update_data["attributes"]:
            update_data["attributes"] = {
                **update_data["attributes"],
                "version_snapshots": existing_snapshots,
            }

    for field, value in update_data.items():
        setattr(entity, field, value)
    entity.updated_at = utc_now()
    await db.commit()
    await db.refresh(entity)
    return build_story_entity_response(entity)


@router.post("/entities/{entity_id}/scope", response_model=StoryEntityResponse)
async def update_story_entity_scope(
    entity_id: str,
    request: StoryEntityScopeUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    entity = await _get_story_entity_or_404(db, entity_id, user_id)
    if request.scope not in {"global", "novel", "chapter", "script"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的实体作用域")
    if request.scope == "global":
        resolved = {"novel_id": None, "chapter_id": None, "script_id": None}
    else:
        resolved = await _resolve_entity_scope(
            db,
            user_id,
            novel_id=request.novel_id,
            chapter_id=request.chapter_id if request.scope in {"chapter", "script"} else None,
            script_id=request.script_id if request.scope == "script" else None,
        )
        if request.scope == "novel" and not resolved["novel_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="小说作用域必须提供 novel_id")
        if request.scope == "chapter" and not resolved["chapter_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="章节作用域必须提供 chapter_id")
        if request.scope == "script" and not resolved["script_id"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="剧本作用域必须提供 script_id")
    entity.novel_id = resolved["novel_id"]
    entity.chapter_id = resolved["chapter_id"]
    entity.script_id = resolved["script_id"]
    entity.updated_at = utc_now()
    await db.commit()
    await db.refresh(entity)
    return build_story_entity_response(entity)


@router.post("/entities/{entity_id}/versions", response_model=Dict[str, Any])
async def create_story_entity_version_snapshot(
    entity_id: str,
    request: StoryEntityVersionSnapshotRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    entity = await _get_story_entity_or_404(db, entity_id, user_id)
    snapshot = _append_entity_snapshot(entity, request.note)
    await db.commit()
    await db.refresh(entity)
    return {"entity_id": entity.id, "snapshot": snapshot, "snapshots": _entity_attr(entity).get("version_snapshots") or []}


@router.post("/entities/{entity_id}/versions/restore", response_model=StoryEntityResponse)
async def restore_story_entity_version_snapshot(
    entity_id: str,
    request: StoryEntityVersionRestoreRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    entity = await _get_story_entity_or_404(db, entity_id, user_id)
    attrs = dict(_entity_attr(entity))
    snapshots = list(attrs.get("version_snapshots") or [])
    snapshot = next((item for item in snapshots if item.get("id") == request.snapshot_id), None)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本快照不存在")

    _append_entity_snapshot(entity, "恢复前自动快照")
    latest_attrs = dict(_entity_attr(entity))
    entity.entity_type = snapshot.get("entity_type") or entity.entity_type
    _validate_entity_type(entity.entity_type)
    entity.name = snapshot.get("name") or entity.name
    entity.description = snapshot.get("description")
    entity.aliases = snapshot.get("aliases") or []
    restored_attrs = dict(snapshot.get("attributes") or {})
    restored_attrs["version_snapshots"] = latest_attrs.get("version_snapshots") or snapshots
    entity.attributes = restored_attrs
    entity.evidence = snapshot.get("evidence")
    entity.confidence = snapshot.get("confidence") or entity.confidence
    entity.source = snapshot.get("source") or entity.source
    entity.updated_at = utc_now()
    await db.commit()
    await db.refresh(entity)
    return build_story_entity_response(entity)


@router.delete("/entities/{entity_id}")
async def delete_story_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    entity = await _get_story_entity_or_404(db, entity_id, user_id)
    await db.delete(entity)
    await db.commit()
    return {"message": "实体已删除", "entity_id": entity_id}


class EntityMergeRequest(BaseModel):
    source_entity_ids: List[str] = Field(..., min_length=2, description="要合并的实体ID列表")
    target_entity_id: str = Field(..., description="合并到的目标实体ID")
    keep_source_as_alias: bool = Field(True, description="是否将源实体名称保留为目标实体的别名")


class EntityMergeResponse(BaseModel):
    merged_entity: StoryEntityResponse
    merged_count: int
    aliases_added: List[str]


@router.post("/entities/merge", response_model=EntityMergeResponse)
async def merge_story_entities(
    request: EntityMergeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # 获取目标实体
    target = await _get_story_entity_or_404(db, request.target_entity_id, user_id)

    # 获取源实体列表
    source_entities: List[StoryEntity] = []
    for source_id in request.source_entity_ids:
        if source_id == request.target_entity_id:
            continue
        source = await _get_story_entity_or_404(db, source_id, user_id)
        source_entities.append(source)

    if not source_entities:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可合并的源实体")

    # 收集要合并的别名
    aliases_added: List[str] = []
    existing_aliases = set(target.aliases or [])

    for source in source_entities:
        # 添加源实体名称和别名
        if source.name and source.name != target.name:
            if source.name not in existing_aliases:
                existing_aliases.add(source.name)
                aliases_added.append(source.name)

        for alias in (source.aliases or []):
            if alias and alias not in existing_aliases:
                existing_aliases.add(alias)
                aliases_added.append(alias)

        # 合并attributes中的有用信息
        source_attrs = source.attributes or {}
        target_attrs = dict(target.attributes or {})

        # 合并relationships
        source_relations = source_attrs.get("relationships", [])
        target_relations = target_attrs.get("relationships", [])
        if source_relations and isinstance(source_relations, list):
            existing_rel_entities = {r.get("target") for r in (target_relations or []) if isinstance(r, dict)}
            for rel in source_relations:
                if isinstance(rel, dict) and rel.get("target") not in existing_rel_entities:
                    target_relations.append(rel)
                    existing_rel_entities.add(rel.get("target"))
            target_attrs["relationships"] = target_relations

        # 合并tags
        source_tags = source_attrs.get("tags") or []
        target_tags = target_attrs.get("tags") or []
        if source_tags and isinstance(source_tags, list):
            existing_tags = set(target_tags if isinstance(target_tags, list) else [])
            for tag in source_tags:
                if tag and tag not in existing_tags:
                    existing_tags.add(tag)
                    target_tags.append(tag)
            target_attrs["tags"] = list(existing_tags)

        target.attributes = target_attrs

    # 更新目标实体
    target.aliases = list(existing_aliases)
    target.version = (target.version or 1) + 1
    target.updated_at = utc_now()

    # 删除源实体
    for source in source_entities:
        await db.delete(source)

    await db.commit()
    await db.refresh(target)

    return EntityMergeResponse(
        merged_entity=build_story_entity_response(target),
        merged_count=len(source_entities),
        aliases_added=aliases_added,
    )


class EntityBulkApproveRequest(BaseModel):
    entity_ids: List[str] = Field(..., min_length=1, description="要确认的实体ID列表")
    approved: bool = Field(True, description="是否确认")


class EntityBulkApproveResponse(BaseModel):
    updated_count: int
    approved_entities: List[StoryEntityResponse]


@router.post("/entities/bulk-approve", response_model=EntityBulkApproveResponse)
async def bulk_approve_story_entities(
    request: EntityBulkApproveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    updated_entities: List[StoryEntity] = []

    for entity_id in request.entity_ids:
        entity = await _get_story_entity_or_404(db, entity_id, user_id)
        entity.is_approved = request.approved
        entity.updated_at = utc_now()
        updated_entities.append(entity)

    await db.commit()
    for entity in updated_entities:
        await db.refresh(entity)

    return EntityBulkApproveResponse(
        updated_count=len(updated_entities),
        approved_entities=[build_story_entity_response(e) for e in updated_entities],
    )


@router.post("/generate-from-novel", response_model=StoryBibleResponse, status_code=status.HTTP_201_CREATED)
async def generate_story_bible_from_novel(
    request: GenerateFromNovelRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel = await _get_novel_or_404(db, request.novel_id, user_id)
    novel_id, _, _, text = await _resolve_extraction_text(db, user_id, request.novel_id, None, None, None)
    entities = await _extract_and_optionally_persist(
        db,
        user_id,
        novel_id,
        None,
        None,
        text,
        sorted(ENTITY_TYPES),
        True,
        model_config_id=request.model_config_id,
    )
    sections = build_story_bible_sections(_entity_dicts(entities))
    story_bible = StoryBible(
        id=str(uuid4()),
        user_id=user_id,
        project_id=request.project_id,
        novel_id=novel.id,
        title=request.title or f"{novel.title} Story Bible",
        style=request.style,
        worldview=(novel.description or "")[:1000] or None,
        character_rules=sections["character_rules"],
        scene_rules=sections["scene_rules"],
        prop_rules=sections["prop_rules"],
        event_timeline=sections["event_timeline"],
        negative_prompt=request.negative_prompt,
        extra_data={"generated_from": "novel", "entity_count": len(entities)},
    )
    db.add(story_bible)
    await db.commit()
    await db.refresh(story_bible)
    return build_story_bible_response(story_bible)


@router.post("/sync-from-chapter", response_model=StoryBibleResponse)
async def sync_story_bible_from_chapter(
    request: SyncFromChapterRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """从章节增量同步 Story Bible，并检测冲突"""
    story_bible = await _get_story_bible_or_404(db, request.story_bible_id, user_id)
    chapter = await _get_chapter_or_404(db, request.chapter_id, user_id)

    # 记录同步前的规则数量
    before_rules = {
        "character": set(item.get("name") for item in (story_bible.character_rules or [])),
        "scene": set(item.get("name") for item in (story_bible.scene_rules or [])),
        "prop": set(item.get("name") for item in (story_bible.prop_rules or [])),
        "event": set(item.get("title") or item.get("name") for item in (story_bible.event_timeline or [])),
    }

    # 抽取章节实体
    entities = await _extract_and_optionally_persist(
        db, user_id, chapter.novel_id, chapter.id, None, chapter.content or "", sorted(ENTITY_TYPES), True
    )
    sections = build_story_bible_sections(_entity_dicts(entities))

    # 合并新规则
    story_bible.character_rules = _merge_rules(story_bible.character_rules or [], sections["character_rules"])
    story_bible.scene_rules = _merge_rules(story_bible.scene_rules or [], sections["scene_rules"])
    story_bible.prop_rules = _merge_rules(story_bible.prop_rules or [], sections["prop_rules"])
    story_bible.event_timeline = _merge_rules(story_bible.event_timeline or [], sections["event_timeline"])

    # 检测新发现的实体（潜在冲突）
    conflicts = []
    for rule in sections["character_rules"]:
        if rule.get("name") not in before_rules["character"]:
            conflicts.append({
                "code": f"new_character_{rule.get('name')}",
                "entity_type": "character",
                "name": rule.get("name"),
                "severity": "info",
                "message": f"从第{chapter.chapter_number}章发现新角色",
                "evidence": rule.get("description"),
            })
    for rule in sections["scene_rules"]:
        if rule.get("name") not in before_rules["scene"]:
            conflicts.append({
                "code": f"new_scene_{rule.get('name')}",
                "entity_type": "scene",
                "name": rule.get("name"),
                "severity": "info",
                "message": f"从第{chapter.chapter_number}章发现新场景",
                "evidence": rule.get("description"),
            })
    for rule in sections["prop_rules"]:
        if rule.get("name") not in before_rules["prop"]:
            conflicts.append({
                "code": f"new_prop_{rule.get('name')}",
                "entity_type": "prop",
                "name": rule.get("name"),
                "severity": "info",
                "message": f"从第{chapter.chapter_number}章发现新道具",
                "evidence": rule.get("description"),
            })

    # 更新 extra_data
    extra_data = dict(story_bible.extra_data or {})
    extra_data["last_synced_chapter_id"] = chapter.id
    extra_data["last_synced_chapter_number"] = chapter.chapter_number
    extra_data["last_sync_entity_count"] = len(entities)
    existing_conflicts = extra_data.get("conflicts", [])
    extra_data["conflicts"] = existing_conflicts + conflicts
    story_bible.extra_data = extra_data

    await db.commit()
    await db.refresh(story_bible)
    return build_story_bible_response(story_bible)


@router.post("/check-consistency", response_model=ConsistencyCheckResponse)
async def check_story_bible_consistency(
    request: ConsistencyCheckRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """检测 Story Bible 中的一致性冲突"""
    story_bible = await _get_story_bible_or_404(db, request.story_bible_id, user_id)
    novel_id, chapter_id, script_id, text = await _resolve_extraction_text(
        db, user_id, request.novel_id or story_bible.novel_id, request.chapter_id, None, request.text
    )
    entities = await _extract_and_optionally_persist(
        db, user_id, novel_id, chapter_id, script_id, text, sorted(ENTITY_TYPES), False
    )
    issues = []

    # 获取现有 Story Bible 中的实体名称
    known_names = {
        "character": _known_bible_names(story_bible, "character"),
        "scene": _known_bible_names(story_bible, "scene"),
        "prop": _known_bible_names(story_bible, "prop"),
        "event": _known_bible_names(story_bible, "event"),
    }

    for entity in entities:
        entity_type = entity.entity_type

        # 1. 检测未收录实体
        if entity.name not in known_names.get(entity_type, set()):
            issues.append(
                ConsistencyIssue(
                    entity_type=entity_type,
                    name=entity.name,
                    severity="warning",
                    message=f"{entity_type} 未收录在 Story Bible 中",
                    evidence=entity.evidence,
                )
            )

        # 2. 检测外观冲突（角色）
        if entity_type == "character" and entity.appearance:
            for rule in (story_bible.character_rules or []):
                if rule.get("name") == entity.name and rule.get("appearance"):
                    if entity.appearance != rule.get("appearance"):
                        issues.append(
                            ConsistencyIssue(
                                entity_type="character",
                                name=entity.name,
                                severity="error",
                                message="角色外观描述与 Story Bible 记录不一致",
                                evidence=f"Story Bible: {rule.get('appearance')[:100]}... 新检测: {entity.appearance[:100]}...",
                            )
                        )

        # 3. 检测道具状态冲突
        if entity_type == "prop" and entity.attributes:
            attrs = entity.attributes or {}
            state = attrs.get("state") or attrs.get("prop_state")
            if state:
                for rule in (story_bible.prop_rules or []):
                    if rule.get("name") == entity.name and rule.get("attributes", {}).get("state"):
                        existing_state = rule["attributes"].get("state")
                        if state != existing_state:
                            issues.append(
                                ConsistencyIssue(
                                    entity_type="prop",
                                    name=entity.name,
                                    severity="warning",
                                    message=f"道具状态从 '{existing_state}' 变为 '{state}'",
                                    evidence=entity.evidence,
                                )
                            )

        # 4. 检测场景设定冲突
        if entity_type == "scene" and entity.attributes:
            attrs = entity.attributes or {}
            time = attrs.get("time") or attrs.get("scene_time")
            weather = attrs.get("weather")
            if time or weather:
                for rule in (story_bible.scene_rules or []):
                    if rule.get("name") == entity.name:
                        rule_attrs = rule.get("attributes", {})
                        if time and rule_attrs.get("time") and time != rule_attrs.get("time"):
                            issues.append(
                                ConsistencyIssue(
                                    entity_type="scene",
                                    name=entity.name,
                                    severity="warning",
                                    message=f"场景时间从 '{rule_attrs.get('time')}' 变为 '{time}'",
                                    evidence=entity.evidence,
                                )
                            )
                        if weather and rule_attrs.get("weather") and weather != rule_attrs.get("weather"):
                            issues.append(
                                ConsistencyIssue(
                                    entity_type="scene",
                                    name=entity.name,
                                    severity="warning",
                                    message=f"场景天气从 '{rule_attrs.get('weather')}' 变为 '{weather}'",
                                    evidence=entity.evidence,
                                )
                            )

        # 5. 检测事件顺序冲突
        if entity_type == "event" and entity.attributes:
            attrs = entity.attributes or {}
            sequence = attrs.get("sequence")
            if sequence:
                for rule in (story_bible.event_timeline or []):
                    if rule.get("title") == entity.name or rule.get("name") == entity.name:
                        rule_seq = rule.get("sequence") or rule.get("attributes", {}).get("sequence")
                        if rule_seq and abs(int(sequence) - int(rule_seq)) > 1:
                            issues.append(
                                ConsistencyIssue(
                                    entity_type="event",
                                    name=entity.name,
                                    severity="warning",
                                    message=f"事件序号从 {rule_seq} 变为 {sequence}，可能存在顺序矛盾",
                                    evidence=entity.evidence,
                                )
                            )

    return ConsistencyCheckResponse(
        story_bible_id=story_bible.id,
        checked_entity_count=len(entities),
        issue_count=len(issues),
        issues=issues,
    )


@router.post("/resolve-conflict", response_model=ResolveConflictResponse)
async def resolve_story_bible_conflict(
    request: ResolveConflictRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """解决 Story Bible 中的一致性冲突"""
    story_bible = await _get_story_bible_or_404(db, request.story_bible_id, user_id)

    # 获取冲突记录
    extra_data = dict(story_bible.extra_data or {})
    conflicts = extra_data.get("conflicts", [])
    conflict = next((c for c in conflicts if c.get("code") == request.issue_code), None)

    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到冲突记录: {request.issue_code}",
        )

    # 标记为已解决
    conflict["resolved"] = True
    conflict["resolution"] = request.resolution
    conflict["resolved_at"] = utc_now().isoformat()
    conflict["resolved_data"] = request.resolved_data

    # 根据解决方式处理
    updated_entity = None
    if request.entity_id and request.resolution == "manual" and request.resolved_data:
        # 手动解决：更新实体
        entity = await _get_story_entity_or_404(db, request.entity_id, user_id)
        for key, value in request.resolved_data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        entity.updated_at = utc_now()
        await db.commit()
        await db.refresh(entity)
        updated_entity = build_story_entity_response(entity)
    elif request.entity_id and request.resolution == "accept_incoming":
        # 接受新数据：更新实体
        entity = await _get_story_entity_or_404(db, request.entity_id, user_id)
        incoming = conflict.get("incoming_data", {})
        for key, value in incoming.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        entity.updated_at = utc_now()
        await db.commit()
        await db.refresh(entity)
        updated_entity = build_story_entity_response(entity)

    # 保存更新后的 extra_data
    story_bible.extra_data = extra_data
    story_bible.updated_at = utc_now()
    await db.commit()
    await db.refresh(story_bible)

    return ResolveConflictResponse(
        resolved=True,
        issue_code=request.issue_code,
        resolution=request.resolution,
        updated_entity=updated_entity,
        updated_story_bible=build_story_bible_response(story_bible),
    )


@router.get("/{story_bible_id}/state-machine", response_model=StoryStateMachineResponse)
async def read_story_bible_state_machine(
    story_bible_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    state_machine = await get_story_state_machine(db, user_id, story_bible_id=story_bible_id)
    return StoryStateMachineResponse(
        story_bible_id=story_bible_id,
        novel_id=state_machine.get("novel_id"),
        state_machine=state_machine,
    )


@router.post("/{story_bible_id}/state-machine", response_model=StoryStateMachineResponse)
async def generate_story_bible_state_machine(
    story_bible_id: str,
    request: StoryStateMachineRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    state_machine = await build_story_state_machine(
        db,
        user_id,
        story_bible_id=story_bible_id,
        novel_id=request.novel_id,
        persist=request.persist,
    )
    return StoryStateMachineResponse(
        story_bible_id=story_bible_id,
        novel_id=state_machine.get("novel_id"),
        state_machine=state_machine,
    )


@router.post("/{story_bible_id}/state-machine/check", response_model=StoryStateMachineCheckResponse)
async def check_story_bible_state_machine(
    story_bible_id: str,
    request: StoryStateMachineRequest = StoryStateMachineRequest(persist=False),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await check_story_state_machine(
        db,
        user_id,
        story_bible_id=story_bible_id,
        novel_id=request.novel_id,
    )
    return StoryStateMachineCheckResponse(**result)


@router.post("", response_model=StoryBibleResponse, status_code=status.HTTP_201_CREATED)
async def create_story_bible(
    request: StoryBibleCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    story_bible = StoryBible(id=str(uuid4()), user_id=user_id, **request.model_dump())
    db.add(story_bible)
    await db.commit()
    await db.refresh(story_bible)
    return build_story_bible_response(story_bible)


@router.get("", response_model=List[StoryBibleResponse])
async def list_story_bibles(
    project_id: Optional[str] = Query(None),
    novel_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    query = select(StoryBible).where(StoryBible.user_id == user_id)
    if project_id:
        query = query.where(StoryBible.project_id == project_id)
    if novel_id:
        query = query.where(StoryBible.novel_id == novel_id)
    query = query.order_by(desc(StoryBible.updated_at)).limit(limit)
    result = await db.execute(query)
    return [build_story_bible_response(item) for item in result.scalars().all()]


@router.get("/{story_bible_id}", response_model=StoryBibleResponse)
async def get_story_bible(
    story_bible_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return build_story_bible_response(await _get_story_bible_or_404(db, story_bible_id, user_id))


@router.put("/{story_bible_id}", response_model=StoryBibleResponse)
async def update_story_bible(
    story_bible_id: str,
    request: StoryBibleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    story_bible = await _get_story_bible_or_404(db, story_bible_id, user_id)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(story_bible, field, value)
    await db.commit()
    await db.refresh(story_bible)
    return build_story_bible_response(story_bible)


@router.delete("/{story_bible_id}")
async def delete_story_bible(
    story_bible_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    story_bible = await _get_story_bible_or_404(db, story_bible_id, user_id)
    await db.delete(story_bible)
    await db.commit()
    return {"message": "Story Bible 已删除"}


@router.post("/compose-prompt", response_model=ComposePromptResponse)
async def compose_prompt(
    request: ComposePromptRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    story_bible = None
    if request.story_bible_id:
        story_bible = await _get_story_bible_or_404(db, request.story_bible_id, user_id)

    project = None
    if request.project_id:
        project_result = await db.execute(
            select(Project).where(Project.id == request.project_id, Project.user_id == user_id)
        )
        project = project_result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    shot = None
    if request.shot_id:
        shot_result = await db.execute(select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id))
        shot = shot_result.scalar_one_or_none()
        if shot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    characters = []
    if request.character_ids:
        char_result = await db.execute(
            select(Character).where(Character.id.in_(request.character_ids), Character.user_id == user_id)
        )
        characters = list(char_result.scalars().all())

    skill_blocks = await active_prompt_skill_blocks(
        db,
        user_id,
        task=request.task,
        context=request.extra_context,
    )

    prompt = compose_generation_prompt(
        task=request.task,
        shot=shot,
        story_bible=story_bible,
        characters=characters,
        project=project,
        extra_context=request.extra_context,
        skill_blocks=skill_blocks,
    )
    return ComposePromptResponse(
        prompt=prompt,
        story_bible_id=request.story_bible_id,
        project_id=request.project_id,
        shot_id=request.shot_id,
        character_ids=[character.id for character in characters],
    )


class PropagateChangeRequest(BaseModel):
    """变更传播请求"""
    change_type: str = Field(
        ...,
        description="变更类型: character_update, scene_update, prop_update, event_update, voice_update"
    )
    affected_entity_ids: List[str] = Field(default_factory=list, description="受影响的实体ID列表")


class AffectedShotInfo(BaseModel):
    """受影响的镜头信息"""
    id: str
    shot_number: int
    review_reason: Optional[str] = None
    review_at: Optional[str] = None


class AffectedShotsResponse(BaseModel):
    """受影响的镜头列表响应"""
    shots: List[AffectedShotInfo]
    total: int


class PropagateChangeResponse(BaseModel):
    """变更传播响应"""
    status: str
    affected_shots: int
    change_type: str
    affected_entity_ids: List[str]
    action: str


@router.post("/{story_bible_id}/propagate-change", response_model=PropagateChangeResponse)
async def propagate_story_bible_change(
    story_bible_id: str,
    request: PropagateChangeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """将Story Bible变更传播到相关镜头"""
    # 1. 验证Story Bible所有权
    story_bible = await _get_story_bible_or_404(db, story_bible_id, user_id)

    # 2. 如果没有指定实体ID，从变更类型推断
    affected_entity_ids = list(request.affected_entity_ids)
    if not affected_entity_ids:
        # 从character_rules/scene_rules/prop_rules/event_timeline获取所有实体
        rules = list(story_bible.character_rules or [])
        rules.extend(story_bible.scene_rules or [])
        rules.extend(story_bible.prop_rules or [])
        rules.extend(story_bible.event_timeline or [])
        for rule in rules:
            if rule.get("id"):
                affected_entity_ids.append(rule["id"])

    # 3. 确定变更类型对应的引用字段
    entity_ref_field = "entity_refs"
    change_type_mapping = {
        "character_update": "characters",
        "scene_update": "scenes",
        "prop_update": "props",
        "event_update": "events",
        "voice_update": "voices",
    }
    ref_key = change_type_mapping.get(request.change_type, "entities")

    # 4. 查找使用这些实体的所有镜头
    affected_shots: List[Shot] = []
    existing_shot_ids = set()

    for entity_id in affected_entity_ids:
        # 查询所有镜头并过滤
        result = await db.execute(select(Shot).where(Shot.user_id == user_id))
        for shot in result.scalars().all():
            if shot.id in existing_shot_ids:
                continue
            # 检查shot.extra_data中的entity_refs
            extra_data = shot.extra_data or {}
            entity_refs = extra_data.get(entity_ref_field, {})
            ref_list = entity_refs.get(ref_key, [])
            if entity_id in ref_list:
                affected_shots.append(shot)
                existing_shot_ids.add(shot.id)

    # 5. 标记这些镜头需要审查
    now = utc_now()
    for shot in affected_shots:
        extra_data = shot.extra_data or {}
        extra_data["needs_review"] = True
        extra_data["review_reason"] = f"Story Bible {request.change_type} changed"
        extra_data["review_at"] = now.isoformat()
        shot.extra_data = extra_data
        shot.updated_at = now

    await db.commit()

    return PropagateChangeResponse(
        status="success",
        affected_shots=len(affected_shots),
        change_type=request.change_type,
        affected_entity_ids=affected_entity_ids,
        action="marked_for_review",
    )


@router.get("/{story_bible_id}/affected-shots", response_model=AffectedShotsResponse)
async def get_affected_shots(
    story_bible_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """获取Story Bible变更影响的镜头列表"""
    # 验证Story Bible所有权
    await _get_story_bible_or_404(db, story_bible_id, user_id)

    # 查找所有需要审查的镜头
    result = await db.execute(
        select(Shot).where(
            Shot.extra_data.contains({"needs_review": True}),
            Shot.user_id == user_id,
        )
    )

    shots: List[AffectedShotInfo] = []
    for shot in result.scalars().all():
        extra_data = shot.extra_data or {}
        review_reason = extra_data.get("review_reason", "")
        # 只返回Story Bible相关的镜头
        if review_reason and review_reason.startswith("Story Bible"):
            shots.append(AffectedShotInfo(
                id=shot.id,
                shot_number=shot.shot_number,
                review_reason=review_reason,
                review_at=extra_data.get("review_at"),
            ))

    return AffectedShotsResponse(shots=shots, total=len(shots))
