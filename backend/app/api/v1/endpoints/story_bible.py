"""
Story Bible API for consistency management.
"""

from app.core.time_utils import utc_now
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.api_key_utils import create_text_generation_service, get_user_text_model_config
from app.core.database import get_db
from app.core.dev_generation import is_dev_mode
from app.core.security import get_current_user_id
from app.models import (
    Asset,
    Character,
    Chapter,
    Novel,
    ProductionStateEvent,
    Project,
    Script,
    Shot,
    StoryBible,
    StoryEntity,
)
from app.services.entity_extraction_service import (
    ENTITY_TYPES,
    build_story_bible_sections,
    extract_story_entities,
    normalize_extracted_entities,
)
from app.services.entity_chapter_provenance import attach_first_chapter_provenance
from app.services.entity_review_service import (
    EntityApprovalEvidenceError,
    approve_review_entity,
    entity_has_duplicate_risk,
    get_entity_review_summary,
    get_extraction_run_detail,
    reject_review_entity,
    run_candidate_entity_extraction,
    suggest_entity_merges,
)
from app.services.entity_targeted_enrichment_service import enrich_target_entity
from app.services.entity_extraction_schema import CanonicalEntityCandidate
from app.services.entity_quality_service import score_entity_candidate
from app.services.default_anime_library import ensure_default_story_entities
from app.services.entity_impact_service import analyze_entity_change_impact, mark_entity_change_impact_for_review
from app.services.continuity_review_tasks import (
    list_continuity_review_tasks as list_continuity_review_tasks_payload,
    resolve_continuity_review_task as resolve_continuity_review_task_payload,
    resolve_continuity_review_tasks_batch,
)
from app.services.prompt_composer import compose_generation_prompt
from app.services.prompt_skill_service import active_prompt_skill_blocks, apply_active_prompt_skill_template
from app.services.prompt_template_router import select_prompt_skill_for_model
from app.services.production_bible import approve_story_entity, build_production_bible_summary
from app.services.production_graph_service import append_state_event, project_story_state
from app.services.series_production import (
    mark_production_graph_artifact_impact,
    resolve_production_graph_artifact_impact,
)
from app.services.story_state_machine import (
    build_story_state_machine,
    check_story_state_machine,
    get_story_state_machine,
)
from app.services.story_entity_lifecycle import (
    APPROVED,
    get_entity_review_status,
    is_entity_asset_generation_allowed,
    is_entity_production_visible,
    query_story_entities_for_production,
    set_entity_review_status,
)
from app.services.story_entity_stats import production_entity_counts

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


class EntityApprovalRequest(BaseModel):
    approved: bool
    approval_note: Optional[str] = None


class EntityImpactReviewPlanRequest(BaseModel):
    episode_index: int = Field(..., ge=1, description="从第几集起生成复审任务")
    change_note: Optional[str] = Field(None, description="变更说明")


class ProductionBiblePatchRequest(BaseModel):
    style: Optional[Dict[str, Any]] = None
    voices: Optional[List[Dict[str, Any]]] = None
    state_machine: Optional[Dict[str, Any]] = None


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
    canonical_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    appearance: Optional[str] = None
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


class EntityCandidateAnalysisRequest(EntityExtractionRequest):
    source_type: str = Field("novel", max_length=40)
    source_id: Optional[str] = None
    persist_rejected: bool = False
    allow_auto_approve: bool = False


class EntityReviewActionRequest(BaseModel):
    reason: Optional[str] = None


class EntityMergeSuggestionRequest(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None


class TargetedEntityEnrichmentRequest(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    text: str = Field(..., min_length=1)
    entity_type: str = Field(..., description="character/scene/prop/event")
    entity_name: str = Field(..., min_length=1, max_length=200)
    target_entity_id: Optional[str] = None
    fields: List[str] = Field(default_factory=list)
    mode: str = Field("preview", pattern="^(preview|merge_candidate|apply_to_candidate|apply_to_approved_requires_confirmation)$")
    model_config_id: Optional[str] = None


class ProductionGraphEventAppendRequest(BaseModel):
    novel_id: str = Field(..., min_length=1)
    chapter_id: Optional[str] = None
    episode_index: Optional[int] = Field(None, ge=1)
    entity_id: Optional[str] = None
    event_type: str = Field(..., min_length=1, max_length=64)
    story_time: Dict[str, Any] = Field(default_factory=dict)
    production_time: Dict[str, Any] = Field(default_factory=dict)
    before_state: Dict[str, Any] = Field(default_factory=dict)
    after_state: Dict[str, Any] = Field(default_factory=dict)
    evidence: Any = None
    approval_status: str = Field("pending", pattern="^(pending|approved|rejected)$")
    restore_version: Optional[int] = Field(None, ge=0)


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


class EntityBulkActionRequest(BaseModel):
    entity_ids: List[str] = Field(..., min_length=1, description="要批量维护的实体ID")
    action: str = Field(..., description="delete/approve/set_scope/set_tags")
    approved: Optional[bool] = None
    scope: Optional[str] = Field(None, description="global/novel/chapter/script")
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    tags: Optional[List[str]] = None
    allow_test_override: bool = Field(False, description="测试模式允许跳过生产限制")


class EntityReextractRequest(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    text: Optional[str] = None
    entity_types: List[str] = Field(default_factory=lambda: sorted(ENTITY_TYPES))
    mode: str = Field("overwrite", pattern="^(append|overwrite|delete_then_extract)$")
    create_assets: bool = False
    asset_scope: str = "entity"
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")
    allow_test_override: bool = Field(False, description="测试模式允许跳过生产限制")


class BulkSkippedItem(BaseModel):
    id: str
    reason: str
    repair_action: Optional[str] = None


class EntityBulkActionResponse(BaseModel):
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    updated_count: int = 0
    deleted_count: int = 0
    created_count: int = 0
    skipped: List[BulkSkippedItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    entities: List[StoryEntityResponse] = Field(default_factory=list)
    assets: List[ExtractedAssetResponse] = Field(default_factory=list)


def ensure_entity_scope_payload(scope: Optional[str], payload: EntityBulkActionRequest | EntityReextractRequest | StoryEntityScopeUpdate) -> None:
    if scope == "novel" and not payload.novel_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="小说作用域必须提供 novel_id")
    if scope == "chapter" and not payload.chapter_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="章节作用域必须提供 chapter_id")
    if scope == "script" and not payload.script_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="剧本作用域必须提供 script_id")


class GenerateFromNovelRequest(BaseModel):
    novel_id: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=200)
    project_id: Optional[str] = None
    style: Optional[str] = Field(None, max_length=100)
    negative_prompt: Optional[str] = None
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")

    @field_validator("style")
    @classmethod
    def normalize_style(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        style = value.strip()
        return style or None


class SyncFromChapterRequest(BaseModel):
    story_bible_id: str = Field(..., min_length=1)
    chapter_id: str = Field(..., min_length=1)


class ConsistencyCheckRequest(BaseModel):
    story_bible_id: str = Field(..., min_length=1)
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    text: Optional[str] = None


class ConsistencyIssue(BaseModel):
    code: str
    entity_type: str
    name: str
    severity: str
    message: str
    evidence: Optional[str] = None
    resolved: bool = False
    resolution: Optional[str] = None
    suggested_action: Optional[str] = None


class ConsistencyCheckResponse(BaseModel):
    story_bible_id: str
    checked_entity_count: int
    issue_count: int
    pending_count: int = 0
    resolved_count: int = 0
    last_checked_at: Optional[str] = None
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


class ProductionBibleSummaryResponse(BaseModel):
    summary: Dict[str, Any]


class ContinuityReviewTask(BaseModel):
    shot_id: str
    shot_number: int
    storyboard_id: Optional[str] = None
    storyboard_title: Optional[str] = None
    novel_id: Optional[str] = None
    novel_title: Optional[str] = None
    workflow_id: Optional[str] = None
    workflow_title: Optional[str] = None
    shot_summary: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None
    episode_index: Optional[int] = None
    review_reason: Optional[str] = None
    review_at: Optional[str] = None
    review_state: Optional[str] = None
    review_notes: Optional[str] = None
    change_note: Optional[str] = None
    marked_at: Optional[str] = None
    status: Optional[str] = None
    shot_review_url: Optional[str] = None
    shot_url: Optional[str] = None
    storyboard_url: Optional[str] = None


class ContinuityReviewTasksResponse(BaseModel):
    tasks: List[ContinuityReviewTask]
    total: int
    filters: Dict[str, Any] = Field(default_factory=dict)
    sort: str = "updated_desc"
    workflow_id: Optional[str] = None


class ContinuityReviewResolveRequest(BaseModel):
    resolution_note: Optional[str] = Field(None, max_length=500)


class ContinuityReviewResolveResponse(BaseModel):
    status: str
    shot_id: str
    review_state: str
    resolved_at: str
    resolution_note: Optional[str] = None


class ContinuityReviewBatchResolveRequest(BaseModel):
    shot_ids: List[str] = Field(..., min_length=1)
    resolution_note: Optional[str] = Field(None, max_length=500)


class ContinuityReviewBatchResolveResponse(BaseModel):
    status: str
    resolved_count: int
    shot_ids: List[str]
    tasks: List[ContinuityReviewResolveResponse] = Field(default_factory=list)


def infer_approval_state(summary: Dict[str, Any]) -> str:
    missing = summary.get("missing_requirements") or []
    if missing:
        return "needs_review"
    return "approved" if summary.get("readiness_score", 0) >= 80 else "draft"


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


def _validated_evidence_span(text: str, item: dict[str, Any]) -> tuple[Optional[int], Optional[int], str]:
    span = str(item.get("evidence_span") or item.get("evidence") or "")
    start, end = item.get("char_start"), item.get("char_end")
    if start is not None or end is not None:
        if (
            isinstance(start, int) and isinstance(end, int)
            and 0 <= start <= end <= len(text)
            and text[start:end] == span
        ):
            return start, end, "verified"
        return None, None, "unmatched"
    if not span:
        return None, None, "unmatched"
    matches = [match.start() for match in re.finditer(re.escape(span), text)]
    if len(matches) == 1:
        return matches[0], matches[0] + len(span), "verified"
    return None, None, "ambiguous" if len(matches) > 1 else "unmatched"


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

    chapter_number = None
    if chapter_id:
        chapter = await _get_chapter_or_404(db, chapter_id, user_id)
        chapter_number = chapter.chapter_number
    for item in extracted:
        evidence = str(item.get("evidence_span") or item.get("evidence") or "")
        start, end, span_status = _validated_evidence_span(text, item)
        item["source_chapter_id"] = chapter_id
        item["source_chapter_number"] = chapter_number
        item["evidence_span"] = evidence
        item["char_start"] = start
        item["char_end"] = end
        item.setdefault("extraction_model", "deterministic-v2")
        item["extraction_config"] = {
            **(item.get("extraction_config") if isinstance(item.get("extraction_config"), dict) else {}),
            "span_status": span_status,
        }
        item.setdefault("review_state", "candidate")
    if novel_id and not chapter_id:
        await attach_first_chapter_provenance(db, user_id=user_id, novel_id=novel_id, items=extracted)

    if persist:
        result = await run_candidate_entity_extraction(
            db,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            source_type="script" if script_id else ("chapter" if chapter_id else "novel"),
            source_id=script_id or chapter_id or novel_id,
            text=text,
            entity_types=entity_types,
            model_config_id=model_config_id,
            persist=True,
            candidate_items=extracted,
        )
        return result["entities"]

    return [
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
        payload = dict(item)
        payload.update({
            "entity_type": entity_type,
            "name": name[:200],
            "description": item.get("description") or item.get("evidence"),
            "aliases": item.get("aliases") if isinstance(item.get("aliases"), list) else [],
            "attributes": item.get("attributes") if isinstance(item.get("attributes"), dict) else {},
            "evidence": item.get("evidence") or item.get("description"),
            "confidence": item.get("confidence") or 90,
            "source": "ai",
        })
        entities.append(payload)
    return normalize_extracted_entities(entities)


def _entity_match_key(entity_type: str, name: Optional[str], canonical_name: Optional[str] = None) -> str:
    clean_name = (canonical_name or name or "").strip().lower()
    return f"{entity_type}:{clean_name}"


def _extracted_entity_quality(item: dict[str, Any]) -> dict[str, Any]:
    candidate = CanonicalEntityCandidate.model_validate(item)
    return score_entity_candidate(candidate).model_dump()


def _apply_extracted_entity(entity: StoryEntity, item: dict[str, Any]) -> None:
    attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    semantic_attrs = {
        "current_state": item.get("current_state") if isinstance(item.get("current_state"), dict) else {},
        "known_to_characters": item.get("known_to_characters") if isinstance(item.get("known_to_characters"), list) else [],
        "introduced_at": item.get("introduced_at") or item.get("source_chapter_number"),
        "resolved_at": item.get("resolved_at"),
        "source_chapter_number": item.get("source_chapter_number"),
    }
    if item.get("entity_type") == "event":
        semantic_attrs["event"] = {key: item.get(key) for key in ("actor", "action", "object", "outcome")}
    entity.description = item.get("description") or entity.description
    entity.canonical_name = item.get("canonical_name") or entity.canonical_name
    entity.aliases = item.get("aliases") or entity.aliases or []
    existing_attrs = entity.attributes if isinstance(entity.attributes, dict) else {}
    entity.attributes = {**existing_attrs, **attrs, **semantic_attrs}
    entity.chapter_id = entity.chapter_id or item.get("source_chapter_id")
    entity.first_seen_chapter_id = entity.first_seen_chapter_id or item.get("source_chapter_id") or entity.chapter_id
    entity.appearance = item.get("appearance") or attrs.get("appearance") or entity.appearance
    entity.visual_prompt = item.get("visual_prompt") or attrs.get("visual_prompt") or entity.visual_prompt
    entity.relations = item.get("relations") or attrs.get("relationships") or entity.relations or []
    entity.state_changes = item.get("state_changes") or attrs.get("state_changes") or entity.state_changes or []
    entity.evidence = item.get("evidence") or entity.evidence
    entity.confidence = item.get("confidence") or entity.confidence or 100
    entity.source = item.get("source") or entity.source or "deterministic"
    extra_data = dict(entity.extra_data) if isinstance(entity.extra_data, dict) else {}
    extra_data["quality"] = _extracted_entity_quality(item)
    extra_data["provenance"] = {
        "source_chapter_id": item.get("source_chapter_id") or entity.chapter_id,
        "source_chapter_number": item.get("source_chapter_number"),
        "evidence_span": item.get("evidence_span") or item.get("evidence"),
        "char_start": item.get("char_start"), "char_end": item.get("char_end"),
        "extraction_model": item.get("extraction_model"),
        "extraction_config": item.get("extraction_config") if isinstance(item.get("extraction_config"), dict) else {},
        "review_state": item.get("review_state") or "candidate",
    }
    if item.get("future_intent") is not None:
        extra_data["future_intent"] = item["future_intent"]
    if item.get("foreshadowing") is not None:
        extra_data["foreshadowing"] = item["foreshadowing"]
    entity.extra_data = extra_data
    entity.version = int(entity.version or 1) + 1
    entity.updated_at = utc_now()


def _new_story_entity_from_extracted(
    *,
    user_id: str,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
    item: dict[str, Any],
) -> StoryEntity:
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
        appearance=item.get("appearance") or (item.get("attributes") or {}).get("appearance"),
        visual_prompt=item.get("visual_prompt") or (item.get("attributes") or {}).get("visual_prompt"),
        attributes=item.get("attributes") or {},
        relations=item.get("relations") or (item.get("attributes") or {}).get("relationships") or [],
        state_changes=item.get("state_changes") or (item.get("attributes") or {}).get("state_changes") or [],
        evidence=item.get("evidence"),
        confidence=item.get("confidence") or 100,
        source=item.get("source") or "deterministic",
        extra_data={},
    )
    _apply_extracted_entity(entity, item)
    return entity


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
- event 必须额外包含 actor/action/object/outcome，四项均不可为空
- evidence_span/char_start/char_end: 原文精确证据与字符偏移
- current_state/known_to_characters/introduced_at/resolved_at: 当前已发生状态
- future_intent/foreshadowing: 未来意图与伏笔，必须与当前状态分开

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
            prompt_result = await select_prompt_skill_for_model(
                db,
                user_id=user_id,
                task="entity_extraction",
                provider_name=provider_name,
                model_id=model_id,
                model_capabilities=[],
                output_contract="json_array",
                stage="analysis",
                internal_prompt=prompt,
                template_title="激活实体/资产抽取提示词模板",
                internal_title="内部实体抽取规则",
                context={
                    "source_content": text[:30000],
                    "entity_types": "、".join(sorted(requested)),
                    "allowed_entity_types": ", ".join(sorted(requested)),
                    "output_format": "JSON 数组",
                },
            )
            response = await service.safe_chat_completion(
                model=model_id or "",
                messages=[
                    {"role": "system", "content": "你是小说动漫制作的实体抽取专家，输出必须可被 JSON 解析。"},
                    {"role": "user", "content": prompt_result["prompt"]},
                ],
                temperature=0.2,
                max_tokens=5000,
            )
            ai_entities = _parse_entity_json(response["choices"][0]["message"]["content"])
            ai_entities = [item for item in ai_entities if item["entity_type"] in requested]
            if ai_entities:
                for item in ai_entities:
                    item["source"] = "ai"
                    item["extraction_model"] = model_id
                    item["extraction_config"] = {
                        **(item.get("extraction_config") if isinstance(item.get("extraction_config"), dict) else {}),
                        "provider_name": provider_name,
                        "model_config_id": model_config_id,
                        "model_id": model_id,
                    }
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


def _consistency_issue_code(entity_type: str, name: str, message: str) -> str:
    payload = json.dumps(
        {
            "entity_type": entity_type or "",
            "name": name or "",
            "message": message or "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"consistency_{entity_type}_{digest}"


def _story_bible_rule_attr(entity_type: str) -> Optional[str]:
    return {
        "character": "character_rules",
        "scene": "scene_rules",
        "prop": "prop_rules",
        "event": "event_timeline",
    }.get(entity_type)


def _story_bible_entity_label(entity_type: str) -> str:
    return {
        "character": "角色",
        "scene": "场景",
        "prop": "道具",
        "event": "事件",
    }.get(entity_type, entity_type)


def _rule_from_story_entity(entity: StoryEntity, attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rule: Dict[str, Any] = {
        "name": entity.name,
        "description": entity.description or entity.evidence or "",
        "evidence": entity.evidence,
    }
    merged_attributes = dict(entity.attributes or {})
    if attributes:
        merged_attributes.update(attributes)
    if merged_attributes:
        rule["attributes"] = merged_attributes
    if entity.entity_type == "event":
        rule["title"] = entity.name
    if entity.entity_type == "character" and getattr(entity, "appearance", None):
        rule["appearance"] = entity.appearance
    return rule


def _merge_incoming_story_bible_rule(
    story_bible: StoryBible,
    entity_type: str,
    incoming_rule: Dict[str, Any],
) -> None:
    attr = _story_bible_rule_attr(entity_type)
    if not attr or not incoming_rule:
        return

    rules = list(getattr(story_bible, attr) or [])
    incoming_key = incoming_rule.get("name") or incoming_rule.get("title")
    if not incoming_key:
        return

    for index, rule in enumerate(rules):
        rule_key = rule.get("name") or rule.get("title")
        if rule_key != incoming_key:
            continue

        merged = dict(rule)
        for key, value in incoming_rule.items():
            if key == "attributes" and isinstance(value, dict):
                merged["attributes"] = {**(merged.get("attributes") or {}), **value}
            elif value not in (None, "", [], {}):
                merged[key] = value
        rules[index] = merged
        setattr(story_bible, attr, rules)
        return

    rules.append(incoming_rule)
    setattr(story_bible, attr, rules)


def _apply_story_bible_conflict_resolution(
    story_bible: StoryBible,
    conflict: Dict[str, Any],
    request: ResolveConflictRequest,
) -> None:
    if request.resolution != "accept_incoming":
        return
    if conflict.get("source") != "consistency_check":
        return

    incoming = conflict.get("incoming_data") or {}
    incoming_rule = incoming.get("rule") or request.resolved_data
    if isinstance(incoming_rule, dict):
        _merge_incoming_story_bible_rule(story_bible, conflict.get("entity_type") or "", incoming_rule)


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
        if not is_entity_asset_generation_allowed(entity):
            continue
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
        requirements = attrs.get("reference_requirements") if isinstance(attrs.get("reference_requirements"), dict) else {}
        planned_views = requirements.get("character_multiview") or requirements.get("multiview") or []
        if not isinstance(planned_views, list):
            planned_views = []
        required_views = ["front", "side", "back"]
        legacy_aliases = {"back": ["back", "full_body"], "front": ["front"], "side": ["side"]}
        missing = []
        for key in required_views:
            has_asset = isinstance(asset_pack, dict) and any(asset_pack.get(alias) for alias in legacy_aliases[key])
            has_contract = key in planned_views
            if not has_asset and not has_contract:
                missing.append(key)
        if missing:
            issues.append({
                "code": "missing_character_views",
                "severity": "warning",
                "entity_id": character.id,
                "entity_name": character.name,
                "message": f"角色缺少多角度参考：{', '.join(missing)}",
            })
        if not attrs.get("visual_dna"):
            issues.append({
                "code": "missing_character_visual_dna",
                "severity": "warning",
                "entity_id": character.id,
                "entity_name": character.name,
                "message": "角色缺少视觉 DNA，跨集形象难以锁定",
            })

    for scene in by_type.get("scene", []):
        attrs = _entity_attr(scene)
        scene_dna = attrs.get("scene_dna") if isinstance(attrs.get("scene_dna"), dict) else {}
        tags = attrs.get("scene_tags") or attrs.get("tags")
        if not tags:
            issues.append({
                "code": "missing_scene_tags",
                "severity": "warning",
                "entity_id": scene.id,
                "entity_name": scene.name,
                "message": "场景缺少室内/室外/战斗/日常等标签",
            })
        if not (attrs.get("weather") or attrs.get("lighting") or scene_dna.get("weather") or scene_dna.get("lighting")):
            issues.append({
                "code": "missing_scene_environment_dna",
                "severity": "warning",
                "entity_id": scene.id,
                "entity_name": scene.name,
                "message": "场景缺少天气或光影标签，跨镜头环境一致性不足",
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


@router.post("/entities/analyze", response_model=Dict[str, Any])
async def analyze_entities_for_review(
    request: EntityCandidateAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel_id, chapter_id, script_id, text = await _resolve_extraction_text(
        db, user_id, request.novel_id, request.chapter_id, request.script_id, request.text
    )
    try:
        result = await run_candidate_entity_extraction(
            db,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            source_type=request.source_type,
            source_id=request.source_id or script_id or chapter_id or novel_id,
            text=text,
            entity_types=request.entity_types,
            model_config_id=request.model_config_id,
            persist=request.persist,
            persist_rejected=request.persist_rejected,
            allow_auto_approve=request.allow_auto_approve,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "run_id": result["run_id"],
        "status": result["status"],
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "script_id": script_id,
        "stats": result["stats"],
        "quality_summary": result["quality_summary"],
        "prompt_routing": result.get("prompt_routing") or {},
        "entities": [build_story_entity_response(entity) for entity in result["entities"]],
        "mention_count": len(result["mentions"]),
    }


@router.get("/entities/runs/{run_id}", response_model=Dict[str, Any])
async def get_entity_extraction_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await get_extraction_run_detail(db, user_id=user_id, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/entities/review-summary", response_model=Dict[str, Any])
async def get_story_entity_review_summary(
    novel_id: Optional[str] = Query(None),
    chapter_id: Optional[str] = Query(None),
    script_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await get_entity_review_summary(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
    )


@router.post("/entities/merge-suggestions", response_model=Dict[str, Any])
async def get_entity_merge_suggestions(
    request: EntityMergeSuggestionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    suggestions = await suggest_entity_merges(
        db,
        user_id=user_id,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
    )
    return {"items": suggestions, "count": len(suggestions)}


@router.post("/entities/enrich-target", response_model=Dict[str, Any])
async def enrich_story_entity_target(
    request: TargetedEntityEnrichmentRequest,
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
    try:
        return await enrich_target_entity(
            db,
            user_id=user_id,
            novel_id=scope["novel_id"],
            chapter_id=scope["chapter_id"],
            script_id=scope["script_id"],
            target_entity_id=request.target_entity_id,
            text=request.text,
            entity_type=request.entity_type,
            entity_name=request.entity_name,
            fields=request.fields,
            mode=request.mode,
            model_config_id=request.model_config_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _production_graph_event_payload(event: ProductionStateEvent) -> Dict[str, Any]:
    return {
        "id": event.id,
        "novel_id": event.novel_id,
        "chapter_id": event.chapter_id,
        "episode_index": event.episode_index,
        "entity_id": event.entity_id,
        "event_type": event.event_type,
        "story_time": event.story_time or {},
        "production_time": event.production_time or {},
        "before_state": event.before_state or {},
        "after_state": event.after_state or {},
        "evidence": event.evidence,
        "approval_status": event.approval_status,
        "approved_by": event.approved_by,
        "production_version": event.production_version,
        "previous_event_hash": event.previous_event_hash,
        "event_hash": event.event_hash,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


@router.post("/production-graph/events", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def append_production_graph_event(
    request: ProductionGraphEventAppendRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel = await _get_novel_or_404(db, request.novel_id, user_id)
    try:
        event = await append_state_event(
            db,
            user_id=user_id,
            novel_id=request.novel_id,
            chapter_id=request.chapter_id,
            episode_index=request.episode_index,
            entity_id=request.entity_id,
            event_type=request.event_type,
            story_time=request.story_time,
            production_time=request.production_time,
            before_state=request.before_state,
            after_state=request.after_state,
            evidence=request.evidence,
            approval_status=request.approval_status,
            approved_by=user_id if request.approval_status == "approved" else None,
            restore_version=request.restore_version,
            commit=False,
        )
        payload = _production_graph_event_payload(event)
        if event.approval_status == "approved":
            payload["impact"] = await mark_production_graph_artifact_impact(
                db,
                user_id=user_id,
                novel=novel,
                event=event,
                commit=False,
            )
        await db.commit()
        await db.refresh(event)
        return payload
    except Exception:
        await db.rollback()
        raise


@router.get("/production-graph/events", response_model=Dict[str, Any])
async def list_production_graph_events(
    novel_id: str = Query(...),
    episode_index: Optional[int] = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel = await _get_novel_or_404(db, novel_id, user_id)
    query = select(ProductionStateEvent).where(
        ProductionStateEvent.user_id == user_id,
        ProductionStateEvent.novel_id == novel_id,
    )
    if episode_index is not None:
        query = query.where(ProductionStateEvent.episode_index == episode_index)
    result = await db.execute(query.order_by(ProductionStateEvent.production_version.asc()))
    items = [_production_graph_event_payload(event) for event in result.scalars().all()]
    return {"novel_id": novel_id, "items": items, "count": len(items)}


@router.get("/production-graph/project", response_model=Dict[str, Any])
async def get_production_graph_projection(
    novel_id: str = Query(...),
    max_version: Optional[int] = Query(None, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel = await _get_novel_or_404(db, novel_id, user_id)
    return await project_story_state(
        db,
        user_id=user_id,
        novel_id=novel_id,
        max_version=max_version,
    )


@router.get("/production-graph/events/{event_id}/impact", response_model=Dict[str, Any])
async def get_production_graph_event_impact(
    event_id: str,
    novel_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel = await _get_novel_or_404(db, novel_id, user_id)
    try:
        event = await db.get(ProductionStateEvent, event_id)
        if event is None or event.user_id != user_id or event.novel_id != novel_id:
            raise ValueError("Production state event does not exist")
        return await resolve_production_graph_artifact_impact(db, user_id=user_id, novel=novel, event=event)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
    query = select(StoryEntity).where(StoryEntity.user_id == user_id)
    query = _apply_story_entity_scope_filters(
        query,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        scope=scope,
    )
    result = await db.execute(query)
    return StoryEntityStatsResponse(**production_entity_counts(result.scalars().all(), ENTITY_TYPES))


@router.get("/entities/production-pack/{novel_id}", response_model=ProductionPackResponse)
async def get_story_production_pack(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await _get_novel_or_404(db, novel_id, user_id)
    entities = await query_story_entities_for_production(
        db,
        user_id=user_id,
        novel_id=novel_id,
    )
    entities = sorted(entities, key=lambda entity: (entity.entity_type or "", str(entity.updated_at or "")))
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


@router.get("/production-bible/{novel_id}/summary", response_model=ProductionBibleSummaryResponse)
async def get_production_bible_summary(
    novel_id: str,
    story_bible_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    summary = await build_production_bible_summary(
        db,
        user_id,
        novel_id,
        story_bible_id=story_bible_id,
    )
    return ProductionBibleSummaryResponse(summary=summary)


@router.get("/novel/{novel_id}/production-bible/review", response_model=Dict[str, Any])
async def review_production_bible(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    summary = await build_production_bible_summary(db, user_id, novel_id)
    return {
        "sections": ["style", "characters", "scenes", "props", "events", "voices"],
        "approval_state": infer_approval_state(summary),
        "summary": summary,
    }


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


@router.post("/entities/bulk-action", response_model=EntityBulkActionResponse)
async def bulk_action_story_entities(
    request: EntityBulkActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if request.action not in {"delete", "approve", "set_scope", "set_tags"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的实体批量动作")

    updated_entities: list[StoryEntity] = []
    deleted_count = 0
    skipped: list[BulkSkippedItem] = []
    warnings: list[str] = []
    allow_test_override = request.allow_test_override and is_dev_mode()
    if request.allow_test_override and not allow_test_override:
        warnings.append("生产模式不允许使用测试跳过开关，请先解除锁定资产或切换到测试环境")

    for entity_id in request.entity_ids:
        try:
            entity = await _get_story_entity_or_404(db, entity_id, user_id)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                skipped.append(BulkSkippedItem(id=entity_id, reason="实体不存在", repair_action="刷新实体库后重新选择"))
                continue
            raise

        if request.action == "delete":
            assets_result = await db.execute(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.entity_id == entity.id,
                    Asset.is_active == True,
                )
            )
            entity_assets = list(assets_result.scalars().all())
            blocked_assets = [asset for asset in entity_assets if asset.is_locked or asset.is_final]
            if blocked_assets and not allow_test_override:
                for asset in blocked_assets:
                    skipped.append(
                        BulkSkippedItem(
                            id=asset.id,
                            reason="关联资产已锁定或定稿",
                            repair_action="先在资产库解锁该实体资产，或使用测试模式确认跳过",
                        )
                    )
                continue
            for asset in entity_assets:
                if (asset.is_locked or asset.is_final) and allow_test_override:
                    warnings.append(f"测试模式已跳过「{asset.name}」的锁定资产限制")
                asset.is_active = False
                asset.updated_at = utc_now()
            await db.delete(entity)
            deleted_count += 1
            continue

        if request.action == "approve":
            should_approve = request.approved if request.approved is not None else True
            if should_approve and await entity_has_duplicate_risk(db, user_id=user_id, entity=entity):
                skipped.append(
                    BulkSkippedItem(
                        id=entity.id,
                        reason="存在高重复风险，不能批量定稿",
                        repair_action="先查看合并建议并执行合并或单条确认",
                    )
                )
                continue
            try:
                reviewed = (
                    await approve_review_entity(db, user_id=user_id, entity_id=entity.id, reason="bulk approve")
                    if should_approve
                    else await reject_review_entity(db, user_id=user_id, entity_id=entity.id, reason="bulk reject")
                )
            except EntityApprovalEvidenceError as exc:
                skipped.append(
                    BulkSkippedItem(
                        id=entity.id,
                        reason=str(exc),
                        repair_action="补充原文证据后再定稿",
                    )
                )
                continue
            updated_entities.append(reviewed)
            continue

        if request.action == "set_tags":
            entity.tags = request.tags or []
            entity.updated_at = utc_now()
            updated_entities.append(entity)
            continue

        if request.action == "set_scope":
            if request.scope not in {"global", "novel", "chapter", "script"}:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的实体作用域")
            if request.scope == "global":
                resolved = {"novel_id": None, "chapter_id": None, "script_id": None}
            else:
                ensure_entity_scope_payload(request.scope, request)
                resolved = await _resolve_entity_scope(
                    db,
                    user_id,
                    novel_id=request.novel_id,
                    chapter_id=request.chapter_id if request.scope in {"chapter", "script"} else None,
                    script_id=request.script_id if request.scope == "script" else None,
                )
            entity.novel_id = resolved["novel_id"]
            entity.chapter_id = resolved["chapter_id"]
            entity.script_id = resolved["script_id"]
            entity.updated_at = utc_now()
            updated_entities.append(entity)

    await db.commit()
    for entity in updated_entities:
        await db.refresh(entity)

    return EntityBulkActionResponse(
        updated_count=len(updated_entities),
        deleted_count=deleted_count,
        skipped=skipped,
        warnings=warnings,
        entities=[build_story_entity_response(entity) for entity in updated_entities],
    )


@router.post("/entities/reextract", response_model=EntityBulkActionResponse)
async def reextract_story_entities(
    request: EntityReextractRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    novel_id, chapter_id, script_id, text = await _resolve_extraction_text(
        db, user_id, request.novel_id, request.chapter_id, request.script_id, request.text
    )
    try:
        extracted = await _extract_story_entities_with_optional_ai(
            db,
            user_id,
            text,
            request.entity_types,
            request.model_config_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    query = select(StoryEntity).where(StoryEntity.user_id == user_id)
    if novel_id:
        query = query.where(StoryEntity.novel_id == novel_id)
    if chapter_id:
        query = query.where(StoryEntity.chapter_id == chapter_id)
    if script_id:
        query = query.where(StoryEntity.script_id == script_id)
    query = query.where(StoryEntity.entity_type.in_(request.entity_types))
    existing_entities = list((await db.execute(query)).scalars().all())
    existing_by_key = {
        _entity_match_key(entity.entity_type, entity.name, entity.canonical_name): entity
        for entity in existing_entities
    }

    deleted_count = 0
    skipped: list[BulkSkippedItem] = []
    warnings: list[str] = []
    allow_test_override = request.allow_test_override and is_dev_mode()
    if request.allow_test_override and not allow_test_override:
        warnings.append("生产模式不允许使用测试跳过开关，请先解除锁定资产或切换到测试环境")

    if request.mode == "delete_then_extract":
        for entity in existing_entities:
            assets_result = await db.execute(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.entity_id == entity.id,
                    Asset.is_active == True,
                )
            )
            entity_assets = list(assets_result.scalars().all())
            blocked_assets = [asset for asset in entity_assets if asset.is_locked or asset.is_final]
            if blocked_assets and not allow_test_override:
                for asset in blocked_assets:
                    skipped.append(
                        BulkSkippedItem(
                            id=asset.id,
                            reason="关联资产已锁定或定稿",
                            repair_action="先解锁资产，或改用覆盖更新模式保留实体ID",
                        )
                    )
                continue
            for asset in entity_assets:
                if (asset.is_locked or asset.is_final) and allow_test_override:
                    warnings.append(f"测试模式已跳过「{asset.name}」的锁定资产限制")
                asset.is_active = False
                asset.updated_at = utc_now()
            await db.delete(entity)
            deleted_count += 1
        existing_by_key = {}

    requested_types = set(request.entity_types)
    candidate_items: list[dict[str, Any]] = []
    for item in extracted:
        if item["entity_type"] not in requested_types:
            continue
        key = _entity_match_key(item["entity_type"], item.get("name"))
        existing = existing_by_key.get(key)
        if existing and request.mode == "append":
            skipped.append(BulkSkippedItem(id=existing.id, reason="同名实体已存在", repair_action="如需刷新内容，请使用覆盖更新模式"))
            continue
        candidate_items.append(item)

    if deleted_count:
        await db.commit()

    extraction = await run_candidate_entity_extraction(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        source_type="script" if script_id else ("chapter" if chapter_id else "novel"),
        source_id=script_id or chapter_id or novel_id,
        text=text,
        entity_types=request.entity_types,
        model_config_id=request.model_config_id,
        persist=True,
        candidate_items=candidate_items,
    )
    resulting_entities = extraction["entities"]

    assets: list[Asset] = []
    if request.create_assets and resulting_entities:
        assets = await _create_assets_for_entities(db, user_id, resulting_entities, request.asset_scope)

    return EntityBulkActionResponse(
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        updated_count=extraction["stats"]["updated"],
        deleted_count=deleted_count,
        created_count=extraction["stats"]["created"],
        skipped=skipped,
        warnings=warnings,
        entities=[build_story_entity_response(entity) for entity in resulting_entities],
        assets=[_build_extracted_asset_response(asset) for asset in assets],
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
    entity_data["source"] = "manual"
    entity = StoryEntity(id=str(uuid4()), user_id=user_id, **entity_data)
    set_entity_review_status(entity, APPROVED, changed_by=user_id, reason="manual create")
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return build_story_entity_response(entity)


@router.post("/entities/{entity_id}/approve", response_model=Dict[str, Any])
async def approve_entity(
    entity_id: str,
    request: EntityApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await approve_story_entity(db, user_id, entity_id, request.approved, request.approval_note)


@router.post("/entities/{entity_id}/promote", response_model=Dict[str, Any])
async def promote_entity_candidate(
    entity_id: str,
    request: EntityReviewActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        entity = await approve_review_entity(db, user_id=user_id, entity_id=entity_id, reason=request.reason)
    except EntityApprovalEvidenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"entity": build_story_entity_response(entity), "review_status": get_entity_review_status(entity)}


@router.post("/entities/{entity_id}/reject", response_model=Dict[str, Any])
async def reject_entity_candidate(
    entity_id: str,
    request: EntityReviewActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        entity = await reject_review_entity(db, user_id=user_id, entity_id=entity_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"entity": build_story_entity_response(entity), "review_status": get_entity_review_status(entity)}


@router.get("/entities/{entity_id}/impact", response_model=Dict[str, Any])
async def get_story_entity_impact(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await analyze_entity_change_impact(db, user_id, entity_id)


@router.post("/entities/{entity_id}/impact/review-plan", response_model=Dict[str, Any])
async def create_story_entity_impact_review_plan(
    entity_id: str,
    request: EntityImpactReviewPlanRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await mark_entity_change_impact_for_review(
        db,
        user_id,
        entity_id,
        episode_index=request.episode_index,
        change_note=request.change_note,
    )


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
        ensure_entity_scope_payload(request.scope, request)
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
    skipped: List[BulkSkippedItem] = Field(default_factory=list)


@router.post("/entities/bulk-approve", response_model=EntityBulkApproveResponse)
async def bulk_approve_story_entities(
    request: EntityBulkApproveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    updated_entities: List[StoryEntity] = []
    skipped: List[BulkSkippedItem] = []

    for entity_id in request.entity_ids:
        try:
            entity = await _get_story_entity_or_404(db, entity_id, user_id)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                skipped.append(BulkSkippedItem(id=entity_id, reason="实体不存在", repair_action="刷新实体库后重新选择"))
                continue
            raise
        if request.approved and await entity_has_duplicate_risk(db, user_id=user_id, entity=entity):
            skipped.append(
                BulkSkippedItem(
                    id=entity.id,
                    reason="存在高重复风险，不能批量定稿",
                    repair_action="先查看合并建议并执行合并或单条确认",
                )
            )
            continue
        try:
            reviewed = (
                await approve_review_entity(db, user_id=user_id, entity_id=entity.id, reason="bulk approve")
                if request.approved
                else await reject_review_entity(db, user_id=user_id, entity_id=entity.id, reason="bulk reject")
            )
        except EntityApprovalEvidenceError as exc:
            skipped.append(
                BulkSkippedItem(id=entity.id, reason=str(exc), repair_action="补充原文证据后再定稿")
            )
            continue
        updated_entities.append(reviewed)

    await db.commit()
    for entity in updated_entities:
        await db.refresh(entity)

    return EntityBulkApproveResponse(
        updated_count=len(updated_entities),
        approved_entities=[build_story_entity_response(e) for e in updated_entities],
        skipped=skipped,
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
    production_entities = await query_story_entities_for_production(
        db,
        user_id=user_id,
        novel_id=novel_id,
    )
    sections = build_story_bible_sections(_entity_dicts(production_entities))
    story_bible = StoryBible(
        id=str(uuid4()),
        user_id=user_id,
        project_id=request.project_id,
        novel_id=novel.id,
        title=request.title or f"{novel.title} Story Bible",
        style=request.style or novel.genre or "anime",
        worldview=(novel.description or "")[:1000] or None,
        character_rules=sections["character_rules"],
        scene_rules=sections["scene_rules"],
        prop_rules=sections["prop_rules"],
        event_timeline=sections["event_timeline"],
        negative_prompt=request.negative_prompt,
        extra_data={
            "generated_from": "novel",
            "entity_count": len(production_entities),
            "candidate_count": sum(not is_entity_production_visible(entity) for entity in entities),
        },
    )
    db.add(story_bible)
    await db.commit()
    await db.refresh(story_bible)

    chapter_count_result = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.user_id == user_id, Chapter.novel_id == novel.id)
    )
    if int(chapter_count_result.scalar_one() or 0) > 0:
        await build_story_state_machine(
            db,
            user_id,
            story_bible_id=story_bible.id,
            novel_id=novel.id,
            persist=True,
        )
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
    production_entities = await query_story_entities_for_production(
        db,
        user_id=user_id,
        novel_id=chapter.novel_id,
        chapter_id=chapter.id,
    )
    sections = build_story_bible_sections(_entity_dicts(production_entities))

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
    extra_data["last_sync_entity_count"] = len(production_entities)
    extra_data["last_sync_candidate_count"] = sum(
        not is_entity_production_visible(entity) for entity in entities
    )
    existing_conflicts = extra_data.get("conflicts", [])
    extra_data["conflicts"] = existing_conflicts + conflicts
    story_bible.extra_data = extra_data
    flag_modified(story_bible, "extra_data")

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
    issue_entries: list[tuple[ConsistencyIssue, Dict[str, Any]]] = []

    def add_issue(
        *,
        entity_type: str,
        name: str,
        severity: str,
        message: str,
        evidence: Optional[str] = None,
        suggested_action: Optional[str] = None,
        incoming_rule: Optional[Dict[str, Any]] = None,
    ) -> None:
        code = _consistency_issue_code(entity_type, name, message)
        if any(existing_issue.code == code for existing_issue, _ in issue_entries):
            return
        issue = ConsistencyIssue(
            code=code,
            entity_type=entity_type,
            name=name,
            severity=severity,
            message=message,
            evidence=evidence,
            suggested_action=suggested_action,
        )
        issue_entries.append(
            (
                issue,
                {
                    "rule": incoming_rule,
                    "novel_id": novel_id,
                    "chapter_id": chapter_id,
                    "script_id": script_id,
                },
            )
        )

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
            message = f"{_story_bible_entity_label(entity_type)} 未收录在 Story Bible 中"
            add_issue(
                entity_type=entity_type,
                name=entity.name,
                severity="warning",
                message=message,
                evidence=entity.evidence,
                suggested_action="收录到 Story Bible",
                incoming_rule=_rule_from_story_entity(entity),
            )

        # 2. 检测外观冲突（角色）
        if entity_type == "character" and entity.appearance:
            for rule in (story_bible.character_rules or []):
                if rule.get("name") == entity.name and rule.get("appearance"):
                    if entity.appearance != rule.get("appearance"):
                        add_issue(
                            entity_type="character",
                            name=entity.name,
                            severity="error",
                            message="角色外观描述与 Story Bible 记录不一致",
                            evidence=f"Story Bible: {rule.get('appearance')[:100]}... 新检测: {entity.appearance[:100]}...",
                            suggested_action="更新角色外观",
                            incoming_rule=_rule_from_story_entity(entity),
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
                            message = f"道具状态从 '{existing_state}' 变为 '{state}'"
                            add_issue(
                                entity_type="prop",
                                name=entity.name,
                                severity="warning",
                                message=message,
                                evidence=entity.evidence,
                                suggested_action="更新道具状态",
                                incoming_rule=_rule_from_story_entity(entity, {"state": state}),
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
                            message = f"场景时间从 '{rule_attrs.get('time')}' 变为 '{time}'"
                            add_issue(
                                entity_type="scene",
                                name=entity.name,
                                severity="warning",
                                message=message,
                                evidence=entity.evidence,
                                suggested_action="更新场景时间",
                                incoming_rule=_rule_from_story_entity(entity, {"time": time}),
                            )
                        if weather and rule_attrs.get("weather") and weather != rule_attrs.get("weather"):
                            message = f"场景天气从 '{rule_attrs.get('weather')}' 变为 '{weather}'"
                            add_issue(
                                entity_type="scene",
                                name=entity.name,
                                severity="warning",
                                message=message,
                                evidence=entity.evidence,
                                suggested_action="更新场景天气",
                                incoming_rule=_rule_from_story_entity(entity, {"weather": weather}),
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
                            message = f"事件序号从 {rule_seq} 变为 {sequence}，可能存在顺序矛盾"
                            add_issue(
                                entity_type="event",
                                name=entity.name,
                                severity="warning",
                                message=message,
                                evidence=entity.evidence,
                                suggested_action="更新事件顺序",
                                incoming_rule=_rule_from_story_entity(entity, {"sequence": sequence}),
                            )

    checked_at = utc_now().isoformat()
    issue_by_code = {issue.code: (issue, incoming_data) for issue, incoming_data in issue_entries}
    active_resolved_codes: set[str] = set()

    extra_data = dict(story_bible.extra_data or {})
    existing_conflicts = extra_data.get("conflicts") or []
    updated_conflicts: list[Dict[str, Any]] = []
    seen_codes: set[str] = set()

    for existing in existing_conflicts:
        if not isinstance(existing, dict):
            updated_conflicts.append(existing)
            continue

        code = existing.get("code")
        if code not in issue_by_code:
            updated_conflicts.append(existing)
            continue

        issue, incoming_data = issue_by_code[code]
        updated = dict(existing)
        updated.update(
            {
                "code": issue.code,
                "entity_type": issue.entity_type,
                "name": issue.name,
                "severity": issue.severity,
                "message": issue.message,
                "evidence": issue.evidence,
                "source": "consistency_check",
                "suggested_action": issue.suggested_action,
                "incoming_data": incoming_data,
                "last_seen_at": checked_at,
            }
        )
        updated.setdefault("detected_at", checked_at)
        updated.setdefault("resolved", False)
        if updated.get("resolved"):
            active_resolved_codes.add(code)
        updated_conflicts.append(updated)
        seen_codes.add(code)

    for code, (issue, incoming_data) in issue_by_code.items():
        if code in seen_codes:
            continue
        updated_conflicts.append(
            {
                "code": issue.code,
                "entity_type": issue.entity_type,
                "name": issue.name,
                "severity": issue.severity,
                "message": issue.message,
                "evidence": issue.evidence,
                "source": "consistency_check",
                "suggested_action": issue.suggested_action,
                "incoming_data": incoming_data,
                "resolved": False,
                "detected_at": checked_at,
                "last_seen_at": checked_at,
            }
        )

    issues = [issue for issue, _ in issue_entries if issue.code not in active_resolved_codes]
    extra_data["conflicts"] = updated_conflicts
    extra_data["last_consistency_check"] = {
        "checked_at": checked_at,
        "checked_entity_count": len(entities),
        "pending_count": len(issues),
        "resolved_count": len(active_resolved_codes),
    }
    story_bible.extra_data = extra_data
    flag_modified(story_bible, "extra_data")
    story_bible.updated_at = utc_now()
    await db.commit()
    await db.refresh(story_bible)

    return ConsistencyCheckResponse(
        story_bible_id=story_bible.id,
        checked_entity_count=len(entities),
        issue_count=len(issues),
        pending_count=len(issues),
        resolved_count=len(active_resolved_codes),
        last_checked_at=checked_at,
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
    conflicts = [dict(c) if isinstance(c, dict) else c for c in (extra_data.get("conflicts") or [])]
    conflict = next((c for c in conflicts if isinstance(c, dict) and c.get("code") == request.issue_code), None)

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

    _apply_story_bible_conflict_resolution(story_bible, conflict, request)

    # 保存更新后的 extra_data
    extra_data["conflicts"] = conflicts
    story_bible.extra_data = extra_data
    flag_modified(story_bible, "extra_data")
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


@router.get("/continuity-review-tasks", response_model=ContinuityReviewTasksResponse)
async def list_continuity_review_tasks(
    workflow_id: Optional[str] = Query(None),
    novel_id: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    episode_index: Optional[int] = Query(None, ge=1),
    review_state: Optional[str] = Query(None),
    status_filter: str = Query("open", alias="status", pattern="^(open|resolved|all)$"),
    sort: str = Query("updated_desc", pattern="^(updated_desc|updated_asc|episode_desc|episode_asc|entity_desc|entity_asc)$"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ContinuityReviewTasksResponse:
    payload = await list_continuity_review_tasks_payload(
        db,
        user_id,
        workflow_id=workflow_id,
        novel_id=novel_id,
        entity_id=entity_id,
        episode_index=episode_index,
        review_state=review_state,
        task_status=status_filter,
        sort=sort,
        limit=limit,
    )
    return ContinuityReviewTasksResponse(**payload)


@router.post("/continuity-review-tasks/resolve-batch", response_model=ContinuityReviewBatchResolveResponse)
async def resolve_continuity_review_tasks(
    request: ContinuityReviewBatchResolveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ContinuityReviewBatchResolveResponse:
    payload = await resolve_continuity_review_tasks_batch(
        db,
        user_id,
        request.shot_ids,
        resolution_note=request.resolution_note,
    )
    return ContinuityReviewBatchResolveResponse(**payload)


@router.post("/continuity-review-tasks/{shot_id}/resolve", response_model=ContinuityReviewResolveResponse)
async def resolve_continuity_review_task(
    shot_id: str,
    request: ContinuityReviewResolveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ContinuityReviewResolveResponse:
    payload = await resolve_continuity_review_task_payload(
        db,
        user_id,
        shot_id,
        resolution_note=request.resolution_note,
    )
    return ContinuityReviewResolveResponse(**payload)


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
