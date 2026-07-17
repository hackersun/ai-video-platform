"""
图像生成API端点 - 火山引擎Doubao-Seedream
"""

from app.core.time_utils import utc_now
import json
from uuid import uuid4
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete

from app.core.database import get_db
from app.core.api_key_utils import (
    create_image_generation_service,
    get_user_image_model_config,
)
from app.core.dev_generation import dev_image_url, is_dev_mode
from app.core.security import get_current_user_id
from app.services.consistency_context import build_consistency_prompt
from app.services.consistency_preflight import build_generation_context_package, preflight_failure_detail
from app.services.asset_generation_service import style_keywords_for
from app.services.image_generation_pipeline import (
    call_image_generation_provider,
    missing_image_result_message,
    provider_task_id,
)
from app.services.image_prompt_policy import append_global_image_constraints
from app.services.image_result_parser import extract_image_urls_from_provider_result
from app.services.media_persistence import persist_remote_media_url
from app.models import Character, ImageJob, Novel, Shot, StoryBible
from app.models.series_production_run import SeriesProductionRun
from app.features.workflow_media.public import prepare_live_provider_attempt, resolve_live_series_run_for_shot
from app.api.v1.workflow_media_transport import workflow_media_result
from app.services.live_canary_budget import link_provider_attempt
from app.services.live_canary_budget import bind_provider_operation_for_reservation
from app.services.live_canary_budget import settle_synchronous_provider_operation

router = APIRouter(tags=["图像生成"])


# ============== 请求/响应模型 ==============

class ImageGenerateRequest(BaseModel):
    """图像生成请求"""
    prompt: str = Field(..., description="图片描述")
    model: str = Field("Doubao-Seedream-5.0-lite", description="模型ID，默认 Doubao-Seedream-5.0-lite")
    size: str = Field("2K", description="图片尺寸: 2K, 4K")
    num: int = Field(1, ge=1, le=4, description="生成数量")
    style: Optional[str] = Field(None, description="风格: anime, realistic, etc.")
    shot_id: Optional[str] = Field(None, description="关联的镜头ID")
    character_id: Optional[str] = Field(None, description="关联的角色ID")
    story_bible_id: Optional[str] = Field(None, description="用于一致性约束的 Story Bible ID")
    project_id: Optional[str] = Field(None, description="项目ID，用于注入项目全局风格")
    novel_id: Optional[str] = Field(None, description="小说ID，用于自动匹配 Story Bible")
    character_ids: List[str] = Field(default_factory=list, description="需要注入一致性设定的角色ID列表")
    use_consistency_context: bool = Field(True, description="是否自动注入 Story Bible/项目/镜头/角色一致性上下文")
    unsafe_skip_consistency_preflight: bool = Field(False, description="仅用于明确的生产降级调试：跳过一致性预检")
    model_config_id: Optional[str] = Field(None, description="已保存的图像模型配置ID")


class ImageGenerateResponse(BaseModel):
    """图像生成响应"""
    job_id: str
    task_id: Optional[str] = None
    image_urls: list[str]
    status: str
    message: str


class ImageJobResponse(BaseModel):
    """图像任务响应"""
    id: str
    task_id: Optional[str] = None
    prompt: str
    model: str
    size: Optional[str] = None
    num: int
    style: Optional[str] = None
    shot_id: Optional[str] = None
    character_id: Optional[str] = None
    status: str
    image_urls: list[str]
    error_message: Optional[str] = None
    cost: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class ImageStatusResponse(BaseModel):
    """图像状态响应"""
    task_id: str
    job_id: Optional[str] = None
    status: str
    image_urls: list[str]
    message: str


async def _sync_generated_image_links(
    db: AsyncSession,
    user_id: str,
    request: ImageGenerateRequest,
    image_urls: list[str],
) -> None:
    """Write the first generated image back to linked production records."""
    if not image_urls:
        return

    primary_url = image_urls[0]
    if request.shot_id:
        shot_result = await db.execute(
            select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if shot:
            shot.image_url = primary_url
            shot.image_status = "succeeded"
            shot.updated_at = utc_now()

    if request.character_id:
        char_result = await db.execute(
            select(Character).where(Character.id == request.character_id, Character.user_id == user_id)
        )
        character = char_result.scalar_one_or_none()
        if character:
            character.avatar = primary_url
            character.updated_at = utc_now()


# ============== API 端点 ==============

@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image(
    request: ImageGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    生成图片 - 使用火山引擎Doubao-Seedream模型

    支持模型:
    - Doubao-Seedream-4.5
    - Doubao-Seedream-5.0-lite
    - doubao-seedream-5-0-260128（Seedream 5.0 Pro）

    会创建ImageJob记录并返回job_id用于后续查询。
    """
    shot = None
    character = None
    # 验证 shot_id 关联（如果提供）
    if request.shot_id:
        shot_result = await db.execute(
            select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if shot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="镜头不存在"
            )

    # Load every server-owned association before resolving live membership.
    requested_character_ids = {str(value) for value in request.character_ids}
    if request.character_id:
        requested_character_ids.add(request.character_id)
    characters = list((await db.scalars(select(Character).where(
        Character.id.in_(requested_character_ids), Character.user_id == user_id,
    ))).all()) if requested_character_ids else []
    if request.character_id:
        character = next((item for item in characters if item.id == request.character_id), None)
        if character is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    if not request.shot_id:
        related_novel_ids: set[str] = set()
        if request.novel_id:
            owned_novel = await db.scalar(select(Novel.id).where(Novel.id == request.novel_id, Novel.user_id == user_id))
            if owned_novel:
                related_novel_ids.add(str(owned_novel))
        related_novel_ids.update(str(item.novel_id) for item in characters if item.novel_id)
        if request.story_bible_id:
            bible = await db.scalar(select(StoryBible).where(
                StoryBible.id == request.story_bible_id, StoryBible.user_id == user_id,
            ))
            if bible and bible.novel_id:
                related_novel_ids.add(str(bible.novel_id))
        if request.project_id:
            project_novels = list((await db.scalars(select(Novel.id).where(
                Novel.project_id == request.project_id, Novel.user_id == user_id,
            ))).all())
            related_novel_ids.update(str(value) for value in project_novels)
            project_bibles = list((await db.scalars(select(StoryBible).where(
                StoryBible.project_id == request.project_id, StoryBible.user_id == user_id,
            ))).all())
            related_novel_ids.update(str(item.novel_id) for item in project_bibles if item.novel_id)
            project_characters = list((await db.scalars(select(Character).where(
                Character.project_id == request.project_id, Character.user_id == user_id,
            ))).all())
            related_novel_ids.update(str(item.novel_id) for item in project_characters if item.novel_id)
        active_runs = list((await db.scalars(select(SeriesProductionRun).where(
            SeriesProductionRun.user_id == user_id,
            SeriesProductionRun.novel_id.in_(related_novel_ids),
            SeriesProductionRun.status == "media_running",
        ))).all()) if related_novel_ids else []
        live_runs = [row for row in active_runs if (row.budget_policy or {}).get("live_canary") is True]
        if len(live_runs) > 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                "code": "live_canary_image_context_ambiguous",
                "message": "image associations resolve to multiple active live runs",
            })
        if live_runs:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                "code": "live_canary_shot_context_required",
                "message": "live series image generation must be bound to a canonical shot",
            })

    if not is_dev_mode() and not request.use_consistency_context and not request.unsafe_skip_consistency_preflight:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="生产模式不能跳过一致性预检；如需降级调试，请显式开启 unsafe_skip_consistency_preflight 并记录原因。",
        )

    style_prompt = style_keywords_for(request.style) if request.style else ""
    final_prompt = request.prompt
    consistency_metadata = {}
    if request.use_consistency_context:
        context = await build_consistency_prompt(
            db,
            user_id,
            task="character_image" if request.character_id else "scene_reference_image",
            base_prompt=request.prompt,
            story_bible_id=request.story_bible_id,
            project_id=request.project_id,
            novel_id=request.novel_id,
            shot_id=request.shot_id,
            character_ids=request.character_ids,
            fallback_character_id=request.character_id,
            extra_context={"图片风格": style_prompt or request.style, "图片尺寸": request.size},
        )
        final_prompt = context["prompt"]
        consistency_metadata = context["metadata"]
    if style_prompt and style_prompt not in final_prompt:
        final_prompt = f"{final_prompt}\n\n画面风格要求：{style_prompt}"
    final_prompt = append_global_image_constraints(final_prompt)

    if not is_dev_mode() and not request.unsafe_skip_consistency_preflight:
        preflight_package = await build_generation_context_package(
            db,
            user_id,
            task_type="image_generation",
            model_config_id=request.model_config_id,
            production_mode=True,
            novel_id=request.novel_id,
            shot_id=request.shot_id,
        )
        if not preflight_package.get("ready"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=preflight_failure_detail(preflight_package),
            )

    # 先创建 ImageJob 记录（pending状态）
    job_id = str(uuid4())
    job = ImageJob(
        id=job_id,
        user_id=user_id,
        prompt=final_prompt,
        model=request.model,
        size=request.size,
        num=request.num,
        style=request.style,
        shot_id=request.shot_id,
        character_id=request.character_id,
        status="pending",
        image_urls=[],
    )
    db.add(job)
    await db.commit()

    try:
        try:
            api_key, provider_name, model_id, base_url = await get_user_image_model_config(
                db,
                user_id,
                config_id=request.model_config_id,
            )
            service = create_image_generation_service(api_key or "", provider_name or "", base_url)
        except HTTPException:
            if request.model_config_id or not is_dev_mode():
                raise
            image_urls = [dev_image_url(f"{job_id}-{index}", request.style or "anime") for index in range(request.num)]
            job.status = "succeeded"
            job.task_id = f"dev-image-{job_id}"
            job.image_urls = image_urls
            job.cost = "0"
            job.error_message = None
            job.completed_at = utc_now()

            await _sync_generated_image_links(db, user_id, request, image_urls)

            await db.commit()
            return ImageGenerateResponse(
                job_id=job_id,
                task_id=job.task_id,
                image_urls=image_urls,
                status="succeeded",
                message="DEV_MODE 本地图片任务已完成，未调用云端图像模型"
            )
        job.model = model_id

        live_run = await workflow_media_result(
            resolve_live_series_run_for_shot(db, user_id=user_id, shot=shot)
        ) if shot else None
        live_reservation = await workflow_media_result(prepare_live_provider_attempt(
            db, live_run, capability="image",
            reservation_id=f"{job.id}:image:{uuid4()}",
            job_type="image_job", job_id=job.id,
        ))
        result = await call_image_generation_provider(
            service,
            provider_name=provider_name,
            model_id=model_id,
            prompt=final_prompt,
            num=request.num,
            size=request.size,
            aspect_ratio="1:1",
            openai_size="1024x1024", db=db, user_id=user_id, config_id=request.model_config_id,
        )

        # 解析返回结果：兼容 data:[{url}]、data:{image_urls:[]}、images/local_urls 等结构
        job.task_id = provider_task_id(result, provider_name=provider_name)
        returned_image_urls = extract_image_urls_from_provider_result(result)
        if live_reservation and not job.task_id and returned_image_urls:
            operation_id = live_run.cost_summary["reservations"][live_reservation].get("operation_id")
            job.task_id = f"sync:{operation_id}"
        image_operation = None
        if live_reservation and job.task_id:
            image_operation = await bind_provider_operation_for_reservation(
                db, live_run, reservation_id=live_reservation, provider_task_id=job.task_id
            )
        if live_reservation:
            linkage = {
                "series_run_id": live_run.id, "reservation_id": live_reservation,
                "provider_task_id": job.task_id, "capability": "image",
                "operation_id": (live_run.cost_summary["reservations"][live_reservation]).get("operation_id"),
            }
            job.cost = json.dumps(linkage, sort_keys=True)
            await link_provider_attempt(
                db, live_run, reservation_id=live_reservation,
                provider_task_id=job.task_id, job_id=job.id, capability="image",
            )
        image_urls = returned_image_urls
        if image_operation and image_urls:
            await settle_synchronous_provider_operation(
                db, image_operation,
                provider_actual_rmb=result.get("actual_cost_rmb", result.get("cost_rmb")) if isinstance(result, dict) else None,
            )

        if not image_urls:
            # 更新job为失败状态
            error_message = missing_image_result_message(provider_name, job.task_id)
            job.status = "failed"
            job.error_message = error_message
            job.completed_at = utc_now()
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"图像生成失败: {error_message}"
            )

        persisted_urls = []
        persistence_errors = []
        for index, image_url in enumerate(image_urls):
            try:
                persisted_urls.append(
                    await persist_remote_media_url(
                        image_url,
                        media_type="image",
                        subdir="images",
                        prefix=f"image-{job_id[:8]}-{index}",
                        max_bytes=20 * 1024 * 1024,
                    ) or image_url
                )
            except Exception as exc:
                persisted_urls.append(image_url)
                persistence_errors.append(str(exc))

        # 更新job为成功状态
        job.status = "succeeded"
        job.image_urls = persisted_urls
        if persistence_errors:
            job.error_message = f"图片已生成，但本地持久化失败: {'; '.join(persistence_errors[:2])}"
        job.completed_at = utc_now()
        await _sync_generated_image_links(db, user_id, request, persisted_urls)
        await db.commit()

        return ImageGenerateResponse(
            job_id=job_id,
            task_id=job.task_id,
            image_urls=persisted_urls,
            status="succeeded",
            message=f"成功生成 {len(image_urls)} 张图片"
        )

    except HTTPException:
        raise
    except Exception as e:
        # 更新job为失败状态
        job.status = "failed"
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"图像生成失败: {str(e)}"
        )


@router.get("/models")
async def list_image_models():
    """获取支持的图像生成模型列表"""
    return {
        "models": [
            {
                "id": "Doubao-Seedream-4.5",
                "name": "豆包-图片-4.5",
                "description": "基础图片生成模型"
            },
            {
                "id": "Doubao-Seedream-5.0-lite",
                "name": "豆包-图片-5.0-lite",
                "description": "轻量级图片生成模型，速度更快"
            },
            {
                "id": "doubao-seedream-5-0-260128",
                "name": "豆包 Seedream 5.0 Pro",
                "description": "非 Lite 旗舰生图模型，支持多参考图和组图生成"
            }
        ]
    }


@router.get("/jobs", response_model=List[ImageJobResponse])
async def list_image_jobs(
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    status: Optional[str] = Query(None, description="状态过滤: pending, running, succeeded, failed"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取用户的图像任务历史列表，支持分页和状态过滤。
    """
    query = select(ImageJob).where(ImageJob.user_id == user_id)
    if status:
        query = query.where(ImageJob.status == status)
    query = query.order_by(desc(ImageJob.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        ImageJobResponse(
            id=job.id,
            task_id=job.task_id,
            prompt=job.prompt,
            model=job.model,
            size=job.size,
            num=job.num,
            style=job.style,
            shot_id=job.shot_id,
            character_id=job.character_id,
            status=job.status,
            image_urls=job.image_urls or [],
            error_message=job.error_message,
            cost=job.cost,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=ImageJobResponse)
async def get_image_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取单个图像任务详情。
    """
    result = await db.execute(
        select(ImageJob).where(
            ImageJob.id == job_id,
            ImageJob.user_id == user_id
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    return ImageJobResponse(
        id=job.id,
        task_id=job.task_id,
        prompt=job.prompt,
        model=job.model,
        size=job.size,
        num=job.num,
        style=job.style,
        shot_id=job.shot_id,
        character_id=job.character_id,
        status=job.status,
        image_urls=job.image_urls or [],
        error_message=job.error_message,
        cost=job.cost,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.get("/status/{task_id}", response_model=ImageStatusResponse)
async def get_image_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    根据task_id查询图像生成任务状态。

    注意: 火山引擎图像生成API为同步模式，通常立即返回结果。
    此接口尝试从数据库中查找对应job，或通过API查询。
    """
    # 先尝试从数据库查找
    result = await db.execute(
        select(ImageJob).where(
            ImageJob.task_id == task_id,
            ImageJob.user_id == user_id
        )
    )
    job = result.scalar_one_or_none()

    if job:
        return ImageStatusResponse(
            task_id=task_id,
            job_id=job.id,
            status=job.status,
            image_urls=job.image_urls or [],
            message={
                "pending": "任务等待中",
                "running": "图像生成中",
                "succeeded": f"成功生成 {len(job.image_urls or [])} 张图片",
                "failed": f"生成失败: {job.error_message}"
            }.get(job.status, f"未知状态: {job.status}")
        )

    # 如果数据库中没有找到，返回未知状态
    return ImageStatusResponse(
        task_id=task_id,
        job_id=None,
        status="unknown",
        image_urls=[],
        message=f"未找到task_id={task_id}的任务记录"
    )


@router.delete("/jobs/{job_id}")
async def delete_image_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    删除指定的图像生成任务。
    """
    result = await db.execute(
        select(ImageJob).where(
            ImageJob.id == job_id,
            ImageJob.user_id == user_id
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    await db.execute(
        delete(ImageJob).where(ImageJob.id == job_id)
    )
    await db.commit()

    return {"message": "任务已删除", "job_id": job_id}
