"""
图像生成API端点 - 火山引擎Doubao-Seedream
"""

from app.core.time_utils import utc_now
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
    get_user_volcano_api_key,
)
from app.core.dev_generation import dev_image_url, is_dev_mode
from app.core.security import get_current_user_id
from app.services.consistency_context import build_consistency_prompt
from app.services.media_persistence import persist_remote_media_url
from app.services.volcano_service import VolcanoService
from app.models.image_job import ImageJob

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

    会创建ImageJob记录并返回job_id用于后续查询。
    """
    # 验证 shot_id 关联（如果提供）
    if request.shot_id:
        from app.models import Shot
        shot_result = await db.execute(
            select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if shot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="镜头不存在"
            )

    # 验证 character_id 关联（如果提供）
    if request.character_id:
        from app.models import Character
        char_result = await db.execute(
            select(Character).where(Character.id == request.character_id, Character.user_id == user_id)
        )
        character = char_result.scalar_one_or_none()
        if character is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="角色不存在"
            )

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
            extra_context={"图片风格": request.style, "图片尺寸": request.size},
        )
        final_prompt = context["prompt"]
        consistency_metadata = context["metadata"]

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
        provider_name = "volcano"
        model_id = request.model
        if request.model_config_id:
            api_key, provider_name, model_id, base_url = await get_user_image_model_config(
                db,
                user_id,
                config_id=request.model_config_id,
            )
            service = create_image_generation_service(api_key or "", provider_name or "", base_url)
        else:
            try:
                api_key = await get_user_volcano_api_key(db, user_id)
            except HTTPException:
                if not is_dev_mode():
                    raise
                image_urls = [dev_image_url(f"{job_id}-{index}", request.style or "anime") for index in range(request.num)]
                job.status = "succeeded"
                job.task_id = f"dev-image-{job_id}"
                job.image_urls = image_urls
                job.cost = "0"
                job.error_message = None
                job.completed_at = utc_now()

                if request.shot_id:
                    from app.models import Shot

                    shot_result = await db.execute(
                        select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id)
                    )
                    shot = shot_result.scalar_one_or_none()
                    if shot:
                        shot.image_url = image_urls[0]
                        shot.image_status = "succeeded"

                await db.commit()
                return ImageGenerateResponse(
                    job_id=job_id,
                    task_id=job.task_id,
                    image_urls=image_urls,
                    status="succeeded",
                    message="DEV_MODE 本地图片任务已完成，未调用云端图像模型"
                )
            service = VolcanoService(api_key)
        job.model = model_id

        # 构建提示词
        prompt = final_prompt
        if request.style:
            prompt = f"{request.style} style, {prompt}"

        if provider_name in ("volcano", "volcano_agent_plan"):
            result = await service.generate_image(
                prompt=prompt,
                model=model_id,
                size=request.size,
                num=request.num
            )
        elif provider_name == "minimax":
            result = await service.generate_image(
                prompt=prompt,
                model=model_id,
                aspect_ratio="1:1",
                n=request.num,
                response_format="url",
            )
        elif provider_name == "openai":
            result = await service.generate_image(
                prompt=prompt,
                model=model_id,
                size="1024x1024",
                n=request.num,
                save_local=False,
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的图像模型服务商: {provider_name}")

        # 解析返回结果
        image_urls = []
        if "data" in result:
            for item in result["data"]:
                if isinstance(item, dict) and "url" in item:
                    image_urls.append(item["url"])
        if not image_urls:
            items = result.get("images") or result.get("image_urls") or []
            if isinstance(items, dict):
                items = items.get("items") or items.get("images") or items.get("image_urls") or []
            for item in items:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("image_url")
                    if url:
                        image_urls.append(url)
                elif isinstance(item, str):
                    image_urls.append(item)
        if not image_urls and result.get("local_urls"):
            image_urls = result["local_urls"]

        if not image_urls:
            # 更新job为失败状态
            job.status = "failed"
            job.error_message = "未获取到图片URL"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"图像生成失败: 未获取到图片URL"
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
        job.task_id = result.get("id") or result.get("task_id")
        if persistence_errors:
            job.error_message = f"图片已生成，但本地持久化失败: {'; '.join(persistence_errors[:2])}"
        job.completed_at = utc_now()
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
