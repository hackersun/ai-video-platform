"""
小说管理 API 端点
"""

from app.core.time_utils import utc_now
import json
from typing import Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.api_key_utils import (
    create_image_generation_service,
    create_text_generation_service,
    get_user_image_model_config,
    get_user_text_model_config,
)
from app.core.security import get_current_user_id
from app.models import Character, Novel, Chapter, NovelImportJob, StoryEntity
from app.api.v1.endpoints.dashboard import log_activity
from app.services.image_generation_pipeline import (
    call_image_generation_provider,
    missing_image_result_message,
    provider_task_id,
)
from app.services.image_result_parser import extract_image_urls_from_provider_result
from app.services.asset_generation_service import style_keywords_for
from app.services.image_prompt_policy import append_global_image_constraints
from app.services.media_persistence import persist_remote_media_url
from app.services.novel_import_service import parse_novel_import, validate_import_filename
from app.services.novel_production_entry import build_novel_production_entries, build_novel_production_entry
from app.services.prompt_skill_service import apply_active_prompt_skill_template
from app.services.series_production import build_series_plan, get_series_plan
from app.services.story_prompt_context import build_cover_prompt, load_story_prompt_context

router = APIRouter(tags=["小说管理"])


# ============== Pydantic 模型 ==============

class NovelCreate(BaseModel):
    """创建小说"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    genre: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    cover_url: Optional[str] = None


class NovelUpdate(BaseModel):
    """更新小说"""
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    word_count: Optional[int] = None
    tags: Optional[List[str]] = None
    cover_url: Optional[str] = None


class NovelResponse(BaseModel):
    """小说响应"""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    genre: Optional[str]
    status: str
    word_count: int
    tags: List[str]
    cover_url: Optional[str]
    source: str
    chapter_count: int = 0
    total_chapters: int = 0
    legacy_character_count: int = 0
    production_character_count: int = 0
    character_count: int = 0
    story_entity_counts: Dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class NovelGenerateRequest(BaseModel):
    """AI生成小说请求"""
    prompt: str = Field(..., min_length=1, description="创作主题/提示词")
    genre: str = Field(..., description="小说类型（玄幻、都市、仙侠、科幻等）")
    chapter_count: int = Field(default=3, ge=1, le=20, description="章节数量")
    style: Optional[str] = Field(None, description="写作风格（可选）")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class NovelIntroGenerateRequest(BaseModel):
    """AI生成小说简介请求"""
    title: str = Field(..., min_length=1, max_length=200, description="小说标题")
    genre: str = Field(..., min_length=1, description="小说类型")
    style: Optional[str] = Field(None, description="写作风格")
    description: Optional[str] = Field(None, description="创作说明")
    model_config_id: Optional[str] = Field(None, description="已保存的文本模型配置ID")


class NovelIntroGenerateResponse(BaseModel):
    """AI生成小说简介响应"""
    intro: str
    provider: str
    model: str


class ChapterBriefResponse(BaseModel):
    """章节简要响应（嵌套在小说生成响应中）"""
    id: str
    title: str
    chapter_number: int
    content: Optional[str]
    word_count: int


class NovelGenerateResponse(BaseModel):
    """AI生成小说响应"""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    genre: Optional[str]
    status: str
    word_count: int
    tags: List[str]
    cover_url: Optional[str]
    source: str
    chapters: List[ChapterBriefResponse]
    created_at: datetime
    updated_at: datetime


class NovelCoverGenerateRequest(BaseModel):
    """生成小说封面请求"""
    prompt: Optional[str] = Field(None, description="封面生成提示词")
    title: Optional[str] = Field(None, description="小说标题（未创建小说时使用）")
    genre: Optional[str] = Field(None, description="小说题材（未创建小说时使用）")
    description: Optional[str] = Field(None, description="小说简介或创作说明")
    style: str = Field("anime", description="封面风格")
    model_config_id: Optional[str] = Field(None, description="已保存的图像模型配置ID")


class NovelCoverGenerateResponse(BaseModel):
    """生成小说封面响应"""
    novel_id: Optional[str] = None
    cover_url: str
    job_id: Optional[str] = None
    status: str
    message: str


class NovelSeriesPlanRequest(BaseModel):
    """整书多集生产计划请求"""
    target_episode_count: Optional[int] = Field(None, ge=1, le=100, description="目标集数")
    chapters_per_episode: Optional[int] = Field(None, ge=1, le=50, description="每集覆盖章节数")
    target_duration_seconds: int = Field(60, ge=30, le=180, description="单集目标时长")
    aspect_ratio: str = Field("9:16", description="画幅比例")
    style: Optional[str] = Field(None, description="动漫/短剧风格")
    persist: bool = Field(True, description="是否保存到小说生产计划")


class ImportChapterPreview(BaseModel):
    title: str
    chapter_number: int
    word_count: int
    preview: str


class NovelImportJobResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    content_type: Optional[str]
    status: str
    title: str
    description: Optional[str]
    chapter_count: int
    word_count: int
    metadata: dict
    chapters: List[ImportChapterPreview]
    novel_id: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class NovelImportConfirmRequest(BaseModel):
    job_id: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    genre: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class NovelImportJobUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, description="导入任务状态")
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    error_message: Optional[str] = None


# ============== LLM API Key 辅助函数 ==============

async def get_user_qwen_api_key(db: AsyncSession, user_id: str) -> tuple[str, str, str, Optional[str]]:
    """获取用户默认文本模型配置。"""
    api_key, provider_name, model_id, base_url = await get_user_text_model_config(db, user_id)
    return api_key or "", provider_name or "", model_id or "", base_url


async def get_user_text_api_key(
    db: AsyncSession,
    user_id: str,
    model_config_id: Optional[str] = None,
) -> tuple[str, str, str, Optional[str]]:
    """获取默认或用户指定的文本模型配置。"""
    api_key, provider_name, model_id, base_url = await get_user_text_model_config(
        db,
        user_id,
        config_id=model_config_id,
    )
    return api_key or "", provider_name or "", model_id or "", base_url


def build_novel_response(
    novel: Novel,
    *,
    chapter_count: int = 0,
    legacy_character_count: int = 0,
    story_entity_counts: Optional[Dict[str, int]] = None,
) -> NovelResponse:
    counts = story_entity_counts or {}
    production_character_count = int(counts.get("character") or 0)
    return NovelResponse(
        id=novel.id,
        user_id=novel.user_id,
        title=novel.title,
        description=novel.description,
        genre=novel.genre,
        status=novel.status or "draft",
        word_count=novel.word_count or 0,
        tags=novel.tags or [],
        cover_url=novel.cover_url,
        source=novel.source or "manual",
        chapter_count=chapter_count,
        total_chapters=chapter_count,
        legacy_character_count=legacy_character_count,
        production_character_count=production_character_count,
        character_count=legacy_character_count + production_character_count,
        story_entity_counts=counts,
        created_at=novel.created_at,
        updated_at=novel.updated_at,
    )


async def load_novel_counts(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
) -> tuple[int, int, Dict[str, int]]:
    chapter_result = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.user_id == user_id, Chapter.novel_id == novel_id)
    )
    legacy_result = await db.execute(
        select(func.count(Character.id)).where(Character.user_id == user_id, Character.novel_id == novel_id)
    )
    entity_result = await db.execute(
        select(
            StoryEntity.entity_type,
            func.count(func.distinct(func.coalesce(StoryEntity.canonical_name, StoryEntity.name))),
        )
        .where(StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id)
        .group_by(StoryEntity.entity_type)
    )
    return (
        int(chapter_result.scalar_one() or 0),
        int(legacy_result.scalar_one() or 0),
        {str(entity_type): int(count or 0) for entity_type, count in entity_result.all()},
    )


def build_import_job_response(job: NovelImportJob) -> NovelImportJobResponse:
    return NovelImportJobResponse(
        id=job.id,
        user_id=job.user_id,
        filename=job.filename,
        content_type=job.content_type,
        status=job.status,
        title=job.title,
        description=job.description,
        chapter_count=job.chapter_count or 0,
        word_count=job.word_count or 0,
        metadata=job.metadata_json or {},
        chapters=[
            ImportChapterPreview(
                title=chapter.get("title", f"第{idx + 1}章"),
                chapter_number=chapter.get("chapter_number", idx + 1),
                word_count=chapter.get("word_count", 0),
                preview=chapter.get("preview", ""),
            )
            for idx, chapter in enumerate(job.chapters_preview or [])
        ],
        novel_id=job.novel_id,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def extract_intro_from_response(content: str) -> str:
    """Extract a short intro from plain text or a small JSON response."""
    text = content.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            text = str(parsed.get("intro") or parsed.get("description") or parsed.get("summary") or "").strip()
    except json.JSONDecodeError:
        pass

    return text.strip().strip('"').strip()


async def generate_cover_image_for_user(
    db: AsyncSession,
    user_id: str,
    prompt: str,
    style: str,
    label: str,
    model_config_id: Optional[str] = None,
) -> tuple[str, str, Optional[str], str, str]:
    """Generate a novel cover image and persist an ImageJob."""
    from app.core.dev_generation import dev_image_url, is_dev_mode
    from app.models.image_job import ImageJob

    job_id = str(uuid4())
    image_url = None
    status_value = "succeeded"
    message = "封面生成成功"
    task_id = None
    model_id = ""
    provider_name = "dev_mode"

    try:
        api_key, provider_name, model_id, base_url = await get_user_image_model_config(
            db,
            user_id,
            config_id=model_config_id,
        )
        service = create_image_generation_service(api_key or "", provider_name or "", base_url)
        style_prompt = style_keywords_for(style) if style else ""
        final_prompt = prompt
        if style_prompt and style_prompt not in final_prompt:
            final_prompt = f"{final_prompt}\n\n封面画风要求：{style_prompt}"
        final_prompt = append_global_image_constraints(final_prompt)
        result_img = await call_image_generation_provider(
            service,
            provider_name=provider_name or "",
            model_id=model_id or "",
            prompt=final_prompt,
            num=1,
            size="2K",
            aspect_ratio="3:4",
            openai_size="1024x1792", db=db, user_id=user_id, config_id=model_config_id, job_id=job_id,
        )
        task_id = provider_task_id(result_img, provider_name=provider_name)
        image_urls = extract_image_urls_from_provider_result(result_img)
        image_url = image_urls[0] if image_urls else None
    except HTTPException:
        if not is_dev_mode():
            raise
        image_url = dev_image_url(job_id, label)
        task_id = f"dev-cover-{job_id}"
        model_id = "dev-placeholder"
        message = "DEV_MODE 本地封面已生成，未调用云端图像模型"

    if not image_url:
        raise HTTPException(status_code=500, detail=f"封面生成失败：{missing_image_result_message(provider_name, task_id)}")

    original_image_url = image_url
    persistence_error = None
    try:
        image_url = await persist_remote_media_url(
            image_url,
            media_type="image",
            subdir="images",
            prefix=f"novel-cover-{job_id[:8]}",
            max_bytes=20 * 1024 * 1024,
        ) or image_url
        if image_url != original_image_url:
            message = f"{message}，已保存为本地持久封面"
    except Exception as exc:
        persistence_error = str(exc)
        message = f"{message}，但本地持久化失败，将暂用供应商图片地址"

    image_job = ImageJob(
        id=job_id,
        user_id=user_id,
        task_id=task_id,
        prompt=prompt,
        model=model_id,
        size="2K",
        num=1,
        style=style,
        status=status_value,
        image_urls=[image_url],
        error_message=persistence_error,
        completed_at=utc_now(),
    )
    db.add(image_job)
    return job_id, image_url, task_id, status_value, message


# ============== API 端点 ==============

@router.post("/import/preview", response_model=NovelImportJobResponse, status_code=status.HTTP_201_CREATED)
async def preview_import_novel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """上传 txt/md/markdown 文件并创建可确认的导入预览任务。"""
    try:
        validate_import_filename(file.filename or "")
        parsed = parse_novel_import(file.filename or "novel.txt", await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    job = NovelImportJob(
        id=str(uuid4()),
        user_id=user_id,
        filename=file.filename or "novel.txt",
        content_type=file.content_type,
        status="previewed",
        title=parsed.title,
        description=parsed.description,
        chapter_count=len(parsed.chapters),
        word_count=parsed.word_count,
        metadata_json=parsed.metadata,
        chapters_preview=[
            {
                "title": chapter.title,
                "content": chapter.content,
                "chapter_number": chapter.chapter_number,
                "word_count": chapter.word_count,
                "preview": chapter.preview,
            }
            for chapter in parsed.chapters
        ],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return build_import_job_response(job)


@router.post("/import/confirm", response_model=NovelGenerateResponse, status_code=status.HTTP_201_CREATED)
async def confirm_import_novel(
    request: NovelImportConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """确认导入预览并创建 Novel 与 Chapter 记录。"""
    result = await db.execute(
        select(NovelImportJob).where(and_(NovelImportJob.id == request.job_id, NovelImportJob.user_id == user_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入任务不存在")
    if job.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="导入任务已完成")
    if job.status != "previewed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="导入任务状态不可确认")

    chapters_data = job.chapters_preview or []
    if not chapters_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="导入任务没有可创建章节")

    novel_id = str(uuid4())
    db_novel = Novel(
        id=novel_id,
        user_id=user_id,
        title=request.title or job.title,
        description=request.description if request.description is not None else job.description,
        genre=request.genre,
        tags=request.tags or [],
        source="imported",
        status="completed",
        word_count=job.word_count or 0,
        extra_data={"import_job_id": job.id, **(job.metadata_json or {})},
    )
    db.add(db_novel)

    created_chapters = []
    for idx, chapter in enumerate(chapters_data):
        content = chapter.get("content") or ""
        word_count = chapter.get("word_count") or len(content)
        chapter_number = chapter.get("chapter_number") or idx + 1
        db_chapter = Chapter(
            id=str(uuid4()),
            novel_id=novel_id,
            user_id=user_id,
            title=chapter.get("title") or f"第{chapter_number}章",
            content=content,
            chapter_number=chapter_number,
            word_count=word_count,
            status="completed",
        )
        db.add(db_chapter)
        created_chapters.append(
            {
                "id": db_chapter.id,
                "title": db_chapter.title,
                "chapter_number": db_chapter.chapter_number,
                "content": db_chapter.content,
                "word_count": db_chapter.word_count,
            }
        )

    job.status = "completed"
    job.novel_id = novel_id
    await db.commit()
    await db.refresh(db_novel)
    await db.refresh(job)

    return NovelGenerateResponse(
        id=db_novel.id,
        user_id=db_novel.user_id,
        title=db_novel.title,
        description=db_novel.description,
        genre=db_novel.genre,
        status=db_novel.status,
        word_count=db_novel.word_count or 0,
        tags=db_novel.tags or [],
        cover_url=db_novel.cover_url,
        source=db_novel.source or "imported",
        chapters=[ChapterBriefResponse(**chapter) for chapter in created_chapters],
        created_at=db_novel.created_at,
        updated_at=db_novel.updated_at,
    )


@router.get("/import/jobs", response_model=List[NovelImportJobResponse])
async def list_import_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """列出当前用户的小说导入任务。"""
    query = select(NovelImportJob).where(NovelImportJob.user_id == user_id)
    if status_filter:
        query = query.where(NovelImportJob.status == status_filter)
    query = query.order_by(desc(NovelImportJob.created_at)).limit(limit)
    result = await db.execute(query)
    return [build_import_job_response(job) for job in result.scalars().all()]


@router.get("/import/jobs/{job_id}", response_model=NovelImportJobResponse)
async def get_import_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取导入任务详情。"""
    result = await db.execute(
        select(NovelImportJob).where(and_(NovelImportJob.id == job_id, NovelImportJob.user_id == user_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入任务不存在")
    return build_import_job_response(job)


@router.put("/import/jobs/{job_id}", response_model=NovelImportJobResponse)
async def update_import_job(
    job_id: str,
    request: NovelImportJobUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """更新导入任务元数据或状态。"""
    result = await db.execute(
        select(NovelImportJob).where(and_(NovelImportJob.id == job_id, NovelImportJob.user_id == user_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入任务不存在")

    if request.status is not None:
        if request.status not in {"previewed", "completed", "failed", "cancelled", "archived"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的导入任务状态")
        job.status = request.status
    if request.title is not None:
        job.title = request.title
    if request.description is not None:
        job.description = request.description
    if request.error_message is not None:
        job.error_message = request.error_message
    job.updated_at = utc_now()

    await db.commit()
    await db.refresh(job)
    return build_import_job_response(job)


@router.post("/import/jobs/{job_id}/retry", response_model=NovelImportJobResponse)
async def retry_import_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """将失败/取消/归档的导入任务恢复为可确认的预览状态。"""
    result = await db.execute(
        select(NovelImportJob).where(and_(NovelImportJob.id == job_id, NovelImportJob.user_id == user_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入任务不存在")
    if job.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已完成导入任务不能重试")

    job.status = "previewed"
    job.error_message = None
    job.updated_at = utc_now()
    await db.commit()
    await db.refresh(job)
    return build_import_job_response(job)


@router.delete("/import/jobs/{job_id}")
async def delete_import_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """归档导入任务，保留导入审计记录。"""
    result = await db.execute(
        select(NovelImportJob).where(and_(NovelImportJob.id == job_id, NovelImportJob.user_id == user_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入任务不存在")

    job.status = "archived"
    job.updated_at = utc_now()
    await db.commit()
    return {"message": "导入任务已归档", "job_id": job_id}


@router.get("", response_model=List[NovelResponse])
async def list_novels(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有小说"""
    result = await db.execute(
        select(Novel)
        .where(Novel.user_id == user_id)
        .order_by(desc(Novel.updated_at))
    )
    novels = list(result.scalars().all())
    novel_ids = [novel.id for novel in novels]
    chapter_counts: Dict[str, int] = {}
    legacy_character_counts: Dict[str, int] = {}
    story_entity_counts: Dict[str, Dict[str, int]] = {}

    if novel_ids:
        chapter_result = await db.execute(
            select(Chapter.novel_id, func.count(Chapter.id))
            .where(Chapter.user_id == user_id, Chapter.novel_id.in_(novel_ids))
            .group_by(Chapter.novel_id)
        )
        chapter_counts = {novel_id: int(count or 0) for novel_id, count in chapter_result.all()}

        legacy_result = await db.execute(
            select(Character.novel_id, func.count(Character.id))
            .where(Character.user_id == user_id, Character.novel_id.in_(novel_ids))
            .group_by(Character.novel_id)
        )
        legacy_character_counts = {novel_id: int(count or 0) for novel_id, count in legacy_result.all()}

        entity_result = await db.execute(
            select(
                StoryEntity.novel_id,
                StoryEntity.entity_type,
                func.count(func.distinct(func.coalesce(StoryEntity.canonical_name, StoryEntity.name))),
            )
            .where(StoryEntity.user_id == user_id, StoryEntity.novel_id.in_(novel_ids))
            .group_by(StoryEntity.novel_id, StoryEntity.entity_type)
        )
        for novel_id, entity_type, count in entity_result.all():
            story_entity_counts.setdefault(str(novel_id), {})[str(entity_type)] = int(count or 0)

    return [
        build_novel_response(
            novel,
            chapter_count=chapter_counts.get(novel.id, 0),
            legacy_character_count=legacy_character_counts.get(novel.id, 0),
            story_entity_counts=story_entity_counts.get(novel.id, {}),
        )
        for novel in novels
    ]


@router.get("/production-entries", response_model=dict)
async def read_novel_production_entries(
    novel_ids: str = Query("", description="逗号分隔的小说 ID 列表"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    ids = [item.strip() for item in novel_ids.split(",") if item.strip()]
    return await build_novel_production_entries(db, user_id, ids)


@router.get("/{novel_id}/production-entry", response_model=dict)
async def read_novel_production_entry(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await build_novel_production_entry(db, user_id, novel_id)


@router.get("/{novel_id}", response_model=NovelResponse)
async def get_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个小说"""
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    chapter_count, legacy_character_count, story_entity_counts = await load_novel_counts(db, user_id, novel.id)
    return build_novel_response(
        novel,
        chapter_count=chapter_count,
        legacy_character_count=legacy_character_count,
        story_entity_counts=story_entity_counts,
    )


@router.get("/{novel_id}/series-plan", response_model=dict)
async def read_novel_series_plan(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """读取已保存的整书多集生产计划。"""
    return await get_series_plan(db, user_id, novel_id)


@router.post("/{novel_id}/series-plan", response_model=dict)
async def generate_novel_series_plan(
    novel_id: str,
    request: NovelSeriesPlanRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """按章节顺序生成并保存整书多集动漫生产计划。"""
    return await build_series_plan(
        db,
        user_id,
        novel_id=novel_id,
        target_episode_count=request.target_episode_count,
        chapters_per_episode=request.chapters_per_episode,
        target_duration_seconds=request.target_duration_seconds,
        aspect_ratio=request.aspect_ratio,
        style=request.style,
        persist=request.persist,
    )


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
async def create_novel(
    novel: NovelCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建小说"""
    db_novel = Novel(
        id=str(uuid4()),
        user_id=user_id,
        title=novel.title,
        description=novel.description,
        genre=novel.genre,
        tags=novel.tags or [],
        cover_url=novel.cover_url,
        status="draft"
    )
    db.add(db_novel)
    await db.commit()
    await db.refresh(db_novel)

    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="created",
        entity_type="novel",
        entity_id=db_novel.id,
        title=f"创建小说: {db_novel.title}",
    )
    await db.commit()

    return build_novel_response(db_novel)


@router.put("/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: str,
    novel_update: NovelUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新小说"""
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    db_novel = result.scalar_one_or_none()

    if not db_novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    # 更新字段
    update_data = novel_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_novel, key, value)

    await db.commit()
    await db.refresh(db_novel)

    chapter_count, legacy_character_count, story_entity_counts = await load_novel_counts(db, user_id, db_novel.id)
    return build_novel_response(
        db_novel,
        chapter_count=chapter_count,
        legacy_character_count=legacy_character_count,
        story_entity_counts=story_entity_counts,
    )


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除小说"""
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    db_novel = result.scalar_one_or_none()

    if not db_novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    await db.delete(db_novel)
    await db.commit()

    return {"message": "小说已删除"}


@router.post("/generate-cover", response_model=NovelCoverGenerateResponse)
async def generate_standalone_novel_cover(
    request: NovelCoverGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """为创建中的小说生成封面图，不创建小说记录。"""
    if not request.prompt and not request.title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先填写小说标题或封面提示词")

    title = (request.title or "未命名小说").strip()
    context = await load_story_prompt_context(
        db,
        user_id,
        title=title,
        genre=(request.genre or "通用").strip(),
        description=request.description,
        style=request.style,
        limit_chapters=0,
    )
    prompt = build_cover_prompt(context, user_prompt=request.prompt, style=request.style)
    prompt_result = await apply_active_prompt_skill_template(
        db,
        user_id,
        task="novel_cover",
        internal_prompt=prompt,
        context={
            "title": context.get("title") or title,
            "genre": context.get("genre") or request.genre or "通用",
            "style": request.style,
            "description": context.get("description") or request.description or "",
            "prompt": request.prompt or "",
            "user_prompt": request.prompt or "",
        },
    )
    prompt = prompt_result["prompt"]

    try:
        job_id, image_url, _task_id, status_value, message = await generate_cover_image_for_user(
            db=db,
            user_id=user_id,
            prompt=prompt,
            style=request.style,
            label=title,
            model_config_id=request.model_config_id,
        )
        await db.commit()
        return NovelCoverGenerateResponse(
            novel_id=None,
            cover_url=image_url,
            job_id=job_id,
            status=status_value,
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"封面生成失败: {str(e)}")


@router.post("/{novel_id}/generate-cover", response_model=NovelCoverGenerateResponse)
async def generate_novel_cover(
    novel_id: str,
    request: NovelCoverGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """为小说生成封面图并回写 cover_url。"""
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    db_novel = result.scalar_one_or_none()
    if not db_novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=db_novel.id,
        style=request.style,
    )
    prompt = build_cover_prompt(context, user_prompt=request.prompt, style=request.style)
    prompt_result = await apply_active_prompt_skill_template(
        db,
        user_id,
        task="novel_cover",
        internal_prompt=prompt,
        context={
            "title": context.get("title") or db_novel.title,
            "genre": context.get("genre") or db_novel.genre or "通用",
            "style": request.style,
            "description": context.get("description") or db_novel.description or "",
            "prompt": request.prompt or "",
            "user_prompt": request.prompt or "",
        },
    )
    prompt = prompt_result["prompt"]

    try:
        job_id, image_url, _task_id, status_value, message = await generate_cover_image_for_user(
            db=db,
            prompt=prompt,
            user_id=user_id,
            style=request.style,
            label=db_novel.title,
            model_config_id=request.model_config_id,
        )
        db_novel.cover_url = image_url
        await db.commit()
        await db.refresh(db_novel)

        return NovelCoverGenerateResponse(
            novel_id=db_novel.id,
            cover_url=image_url,
            job_id=job_id,
            status=status_value,
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"封面生成失败: {str(e)}")


@router.post("/generate-intro", response_model=NovelIntroGenerateResponse)
async def generate_novel_intro(
    request: NovelIntroGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """AI生成小说简介，不创建小说或章节记录。"""
    api_key, provider_name, model_id, base_url = await get_user_text_api_key(
        db,
        user_id,
        request.model_config_id,
    )
    service = create_text_generation_service(api_key, provider_name, base_url)

    style_hint = f"风格：{request.style}。" if request.style else ""
    description_hint = f"\n创作说明：{request.description}" if request.description else ""
    prompt = f"""请为一部小说生成可直接用于作品管理页的简介。

标题：《{request.title}》
题材：{request.genre}
{style_hint}{description_hint}

要求：
1. 120-180字，中文输出
2. 交代主角处境、核心冲突、故事钩子
3. 不要输出章节正文、标题、Markdown 或解释
4. 只输出简介正文"""
    prompt_result = await apply_active_prompt_skill_template(
        db,
        user_id,
        task="novel_generation",
        internal_prompt=prompt,
        context={
            "title": request.title,
            "genre": request.genre,
            "style": request.style or "",
            "description": request.description or "",
            "prompt": request.description or request.title,
            "主题": request.description or request.title,
        },
    )
    prompt = prompt_result["prompt"]

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是专业的中文小说策划编辑，擅长写清晰、有钩子的作品简介。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        intro = extract_intro_from_response(response["choices"][0]["message"]["content"])
        if not intro:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 简介生成接口未返回简介内容")
        return NovelIntroGenerateResponse(intro=intro, provider=provider_name, model=model_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI简介生成失败: {str(e)}")


@router.post("/generate", response_model=NovelGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_novel(
    request: NovelGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成小说 - 根据主题和类型生成完整小说结构及章节内容"""
    # 获取用户的API密钥
    api_key, provider_name, model_id, base_url = await get_user_text_api_key(
        db,
        user_id,
        request.model_config_id,
    )

    service = create_text_generation_service(api_key, provider_name, base_url)

    # 构建创作提示词
    style_hint = f"写作风格：{request.style}。" if request.style else ""
    generation_prompt = f"""请根据以下要求创作一部{request.genre}类型的小说：

主题：{request.prompt}
类型：{request.genre}
{style_hint}
章节数量：{request.chapter_count}章

请生成：
1. 小说标题（简洁有吸引力）
2. 小说简介（100字以内）
3. 每个章节的标题和内容（每章约1500-2000字）

请确保：
- 情节连贯，人物性格鲜明
- 每章有独立的小高潮
- 适当埋设伏笔和悬念
- 遵循{request.genre}类型的典型叙事结构

请以JSON格式输出，格式如下：
{{
    "title": "小说标题",
    "description": "简介",
    "chapters": [
        {{"title": "第一章标题", "content": "第一章内容"}},
        {{"title": "第二章标题", "content": "第二章内容"}}
    ]
}}"""
    prompt_result = await apply_active_prompt_skill_template(
        db,
        user_id,
        task="novel_generation",
        internal_prompt=generation_prompt,
        context={
            "prompt": request.prompt,
            "主题": request.prompt,
            "genre": request.genre,
            "style": request.style or "",
            "chapter_count": request.chapter_count,
            "章节数量": request.chapter_count,
        },
    )
    generation_prompt = prompt_result["prompt"]

    # 调用LLM生成小说
    try:
        response = await service.chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是一个专业的小说作家，擅长创作各种类型的小说。请严格按照JSON格式输出，不要包含其他内容。"},
                {"role": "user", "content": generation_prompt}
            ],
            temperature=0.8,
            max_tokens=16000
        )

        content = response["choices"][0]["message"]["content"]

        # 尝试解析JSON
        # 提取JSON部分（处理可能的markdown代码块）
        json_str = content.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        novel_data = json.loads(json_str)

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI返回内容解析失败: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成失败: {str(e)}"
        )

    # 创建小说记录
    novel_id = str(uuid4())
    db_novel = Novel(
        id=novel_id,
        user_id=user_id,
        title=novel_data.get("title", request.prompt[:50]),
        description=novel_data.get("description", ""),
        genre=request.genre,
        tags=[request.genre],
        source="ai_generated",
        status="writing"
    )
    db.add(db_novel)

    # 创建章节记录
    created_chapters = []
    chapters_data = novel_data.get("chapters", [])

    for idx, chapter_data in enumerate(chapters_data):
        chapter_id = str(uuid4())
        chapter_content = chapter_data.get("content", "")
        word_count = len(chapter_content)
        chapter_title = chapter_data.get("title", f"第{idx + 1}章")

        db_chapter = Chapter(
            id=chapter_id,
            novel_id=novel_id,
            user_id=user_id,
            title=chapter_title,
            content=chapter_content,
            chapter_number=idx + 1,
            word_count=word_count,
            status="completed"
        )
        db.add(db_chapter)
        created_chapters.append({
            "id": chapter_id,
            "title": chapter_title,
            "chapter_number": idx + 1,
            "content": chapter_content,
            "word_count": word_count
        })

    # 更新小说的总字数
    total_word_count = sum(c["word_count"] for c in created_chapters)
    db_novel.word_count = total_word_count

    # 如果所有章节都创建了，将小说状态设为completed
    if len(created_chapters) >= request.chapter_count:
        db_novel.status = "completed"

    await db.commit()
    await db.refresh(db_novel)

    return NovelGenerateResponse(
        id=db_novel.id,
        user_id=db_novel.user_id,
        title=db_novel.title,
        description=db_novel.description,
        genre=db_novel.genre,
        status=db_novel.status,
        word_count=db_novel.word_count,
        tags=db_novel.tags or [],
        cover_url=db_novel.cover_url,
        source=db_novel.source or "ai_generated",
        chapters=[ChapterBriefResponse(**c) for c in created_chapters],
        created_at=db_novel.created_at,
        updated_at=db_novel.updated_at
    )
