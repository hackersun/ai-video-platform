"""
视频生成 API 端点
支持火山引擎豆包视频模型

使用官方SDK: volcengine-python-sdk[ark]
模型: doubao-seedance-1-5-pro-251215 (Doubao-Seedance-1.5-pro)

完整异步流程:
1. POST /video/generate -> 提交任务，返回 task_id
2. GET /video/status/{task_id} -> 查询任务状态
3. GET /video/jobs -> 获取历史任务
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, Field

from app.core.api_key_utils import get_user_api_key
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.video_job import VideoJob
from app.api.v1.endpoints.dashboard import log_activity

router = APIRouter(tags=["视频生成"])


# ============== 常量配置 ==============

VIDEO_MODEL_ID = "Doubao-Seedance-1.0-pro-fast"  # 已验证的快速视频模型

# 所有可选视频模型（按VOLCANO_MODELS配置）
VIDEO_MODEL_OPTIONS = [
    {"id": "Doubao-Seedance-1.0-pro-fast", "label": "豆包Seedance-1.0-pro-fast", "desc": "快速版，速度快，支持文生视频/图生视频"},
    {"id": "Doubao-Seedance-1.5-pro",        "label": "豆包Seedance-1.5-pro",        "desc": "Pro版，高质量（注：需账户有对应额度）"},
]


# ============== 请求/响应模型 ==============

class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    prompt: str = Field(..., description="视频描述")
    model: str = Field(VIDEO_MODEL_ID, description="模型ID，可选 Doubao-Seedance-1.0-pro-fast / Doubao-Seedance-1.5-pro")
    duration: int = Field(5, ge=4, le=10, description="视频时长（秒），支持4/5/8/10秒")
    resolution: str = Field("720p", description="分辨率: 480p, 720p, 1080p")
    api_key: Optional[str] = Field(None, description="火山引擎API Key（可选，默认使用用户在LLM配置中的密钥）")
    image_url: Optional[str] = Field(None, description="参考图片URL，用于图生视频")
    seed: Optional[int] = Field(None, description="随机种子")
    shot_id: Optional[str] = Field(None, description="来源镜头ID")
    storyboard_id: Optional[str] = Field(None, description="来源分镜ID")
    script_id: Optional[str] = Field(None, description="来源剧本ID")
    novel_id: Optional[str] = Field(None, description="来源小说ID")


class VideoGenerateResponse(BaseModel):
    """视频生成响应"""
    task_id: str
    job_id: str  # 新增：数据库job ID
    status: str
    message: str


class VideoStatusResponse(BaseModel):
    """视频状态响应"""
    task_id: str
    job_id: Optional[str] = None
    status: str  # pending, running, succeeded, failed
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    message: str
    progress: Optional[int] = Field(None, description="进度百分比")
    duration: Optional[int] = None
    resolution: Optional[str] = None


class VideoJobResponse(BaseModel):
    """视频任务响应"""
    id: str
    task_id: Optional[str] = None
    title: Optional[str] = None
    prompt: Optional[str] = None
    shot_id: Optional[str] = None
    shot_number: Optional[int] = None
    storyboard_id: Optional[str] = None
    storyboard_title: Optional[str] = None
    script_id: Optional[str] = None
    script_title: Optional[str] = None
    novel_id: Optional[str] = None
    novel_title: Optional[str] = None
    model_name: Optional[str] = None
    status: str
    progress: int
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    error_message: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    created_at: datetime
    updated_at: datetime


def _create_ark_client(api_key: str, base_url: Optional[str] = None):
    """创建ARK客户端"""
    from volcenginesdkarkruntime import Ark
    return Ark(
        base_url=base_url or "https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key,
    )


def _get_volcano_model_name(model_id: str) -> str:
    """根据模型ID获取模型名称"""
    from app.core.volcano_config import VOLCANO_MODELS
    for m in VOLCANO_MODELS:
        if m["id"] == model_id:
            return m.get("name_cn", m.get("name", model_id))
    # 未知模型，返回ID本身
    return model_id


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(
    request: VideoGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    生成视频 - 异步提交任务

    使用火山引擎官方SDK调用视频生成API
    """
    lineage_shot_id = request.shot_id
    lineage_storyboard_id = request.storyboard_id
    lineage_script_id = request.script_id

    if request.shot_id:
        from app.models import Shot, Storyboard

        shot_result = await db.execute(
            select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if shot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

        storyboard_result = await db.execute(
            select(Storyboard).where(Storyboard.id == shot.storyboard_id, Storyboard.user_id == user_id)
        )
        storyboard = storyboard_result.scalar_one_or_none()
        if storyboard is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分镜不存在")

        lineage_storyboard_id = str(storyboard.id)
        lineage_script_id = storyboard.script_id

        if request.storyboard_id and request.storyboard_id != lineage_storyboard_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="shot_id 与 storyboard_id 不匹配")
        if request.script_id and request.script_id != lineage_script_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="shot_id 与 script_id 不匹配")
    elif request.storyboard_id:
        from app.models import Storyboard

        storyboard_result = await db.execute(
            select(Storyboard).where(Storyboard.id == request.storyboard_id, Storyboard.user_id == user_id)
        )
        storyboard = storyboard_result.scalar_one_or_none()
        if storyboard is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分镜不存在")

        lineage_script_id = storyboard.script_id

        if request.script_id and request.script_id != lineage_script_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="storyboard_id 与 script_id 不匹配")
    elif request.script_id:
        from app.models import Script

        script_result = await db.execute(
            select(Script).where(Script.id == request.script_id, Script.user_id == user_id)
        )
        script = script_result.scalar_one_or_none()
        if script is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="剧本不存在")

    try:
        # 使用请求提供的 API key 或从用户的 LLMConfig 中获取
        if request.api_key:
            resolved_api_key = request.api_key
            resolved_base_url = None
        else:
            resolved_api_key, resolved_base_url = await get_user_api_key(db, user_id, "volcano")
        client = _create_ark_client(resolved_api_key, resolved_base_url)

        # 构建content
        content = []

        # 如果有参考图片，添加图片
        if request.image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": request.image_url}
            })

        # 构建提示词，包含参数
        duration_arg = f"--duration {request.duration}"
        camerafixed = "false"  # 相机运动
        watermark = "true"
        resolution_arg = f"--resolution {request.resolution}"

        prompt_text = f"{request.prompt} {duration_arg} --camerafixed {camerafixed} --watermark {watermark}"

        content.append({
            "type": "text",
            "text": prompt_text
        })

        # 视频模型需要 endpoint_id，不是模型名
        from app.core.volcano_config import get_endpoint_id
        video_model = get_endpoint_id(request.model)

        # 调用SDK创建任务
        create_result = client.content_generation.tasks.create(
            model=video_model,
            content=content
        )

        # 构建关联数据（ID + 标题）
        from app.models import Novel, Script, Storyboard, Shot
        extra_data = {}
        if request.novel_id:
            novel = await db.get(Novel, request.novel_id)
            extra_data["novel_id"] = request.novel_id
            extra_data["novel_title"] = novel.title if novel else None
        if request.script_id:
            script = await db.get(Script, request.script_id)
            extra_data["script_id"] = request.script_id
            extra_data["script_title"] = script.title if script else None
        if request.storyboard_id:
            storyboard = await db.get(Storyboard, request.storyboard_id)
            extra_data["storyboard_id"] = request.storyboard_id
            extra_data["storyboard_title"] = storyboard.title if storyboard else None
        if request.shot_id:
            shot = await db.get(Shot, request.shot_id)
            extra_data["shot_id"] = request.shot_id
            extra_data["shot_number"] = shot.shot_number if shot else None

        # 创建数据库记录
        job = VideoJob(
            id=str(uuid4()),
            user_id=user_id,
            task_id=create_result.id,
            title=request.prompt[:50] if len(request.prompt) > 50 else request.prompt,
            prompt=request.prompt,
            model_id=request.model,
            model_name=_get_volcano_model_name(request.model),
            duration=request.duration,
            resolution=request.resolution,
            image_url=request.image_url,
            status="pending",
            progress=10,
            extra_data=extra_data,
        )
        db.add(job)
        await db.commit()

        await log_activity(
            db=db,
            user_id=user_id,
            activity_type="created",
            entity_type="video",
            entity_id=job.id,
            title=f"提交视频生成: {job.title}",
        )
        await db.commit()

        return VideoGenerateResponse(
            task_id=create_result.id,
            job_id=job.id,
            status="pending",
            message="视频生成任务已提交，请使用task_id查询状态"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"视频生成失败: {str(e)}"
        )


@router.get("/status/{task_id}", response_model=VideoStatusResponse)
async def get_video_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    api_key: Optional[str] = None
):
    """
    查询视频生成状态。

    使用 task_id 轮询任务状态。API Key 优先使用请求参数，
    否则从用户的 LLMConfig 中获取。
    """
    if api_key:
        resolved_api_key = api_key
        resolved_base_url = None
    else:
        resolved_api_key, resolved_base_url = await get_user_api_key(db, user_id, "volcano")

    try:
        client = _create_ark_client(resolved_api_key, resolved_base_url)
        
        get_result = client.content_generation.tasks.get(task_id=task_id)
        task_status = get_result.status
        
        # 状态映射
        status_map = {
            "pending": "pending",
            "running": "running", 
            "succeeded": "succeeded",
            "failed": "failed"
        }
        
        mapped_status = status_map.get(task_status, task_status)
        
        # 获取输出信息
        video_url = None
        cover_url = None
        duration = None
        resolution = None
        progress = None
        
        # 视频URL在 content 字段中
        if task_status == "succeeded" and hasattr(get_result, 'content'):
            content = get_result.content
            if content:
                video_url = getattr(content, 'video_url', None)
                # 封面图取最后一帧
                cover_url = getattr(content, 'last_frame_url', None)
        
        if hasattr(get_result, 'duration'):
            duration = get_result.duration
        if hasattr(get_result, 'resolution'):
            resolution = get_result.resolution
        
        # 进度百分比估算
        if task_status == "pending":
            progress = 10
        elif task_status == "running":
            progress = 50
        elif task_status == "succeeded":
            progress = 100
        
        message = {
            "pending": "任务等待中",
            "running": "视频生成中，请稍候",
            "succeeded": "视频生成完成",
            "failed": f"生成失败: {getattr(get_result, 'error', 'Unknown error')}"
        }.get(task_status, f"未知状态: {task_status}")
        
        job = await db.execute(
            select(VideoJob).where(VideoJob.task_id == task_id)
        )
        job_record = job.scalar_one_or_none()
        job_id = job_record.id if job_record else None

        return VideoStatusResponse(
            task_id=task_id,
            job_id=job_id,
            status=mapped_status,
            video_url=video_url,
            cover_url=cover_url,
            message=message,
            progress=progress,
            duration=duration,
            resolution=resolution
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询状态失败: {str(e)}"
        )


@router.get("/jobs", response_model=List[VideoJobResponse])
async def list_video_jobs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取用户的视频任务历史列表
    """
    result = await db.execute(
        select(VideoJob)
        .where(
            VideoJob.user_id == user_id,
            VideoJob.is_active == True
        )
        .order_by(desc(VideoJob.created_at))
        .limit(50)
    )
    jobs = result.scalars().all()
    
    return [
        VideoJobResponse(
            id=job.id,
            task_id=job.task_id,
            title=job.title,
            prompt=job.prompt,
            shot_id=(job.extra_data or {}).get("shot_id") if isinstance(job.extra_data, dict) else None,
            shot_number=(job.extra_data or {}).get("shot_number") if isinstance(job.extra_data, dict) else None,
            storyboard_id=(job.extra_data or {}).get("storyboard_id") if isinstance(job.extra_data, dict) else None,
            storyboard_title=(job.extra_data or {}).get("storyboard_title") if isinstance(job.extra_data, dict) else None,
            script_id=(job.extra_data or {}).get("script_id") if isinstance(job.extra_data, dict) else None,
            script_title=(job.extra_data or {}).get("script_title") if isinstance(job.extra_data, dict) else None,
            novel_id=(job.extra_data or {}).get("novel_id") if isinstance(job.extra_data, dict) else None,
            novel_title=(job.extra_data or {}).get("novel_title") if isinstance(job.extra_data, dict) else None,
            model_name=job.model_name,
            status=job.status,
            progress=job.progress,
            video_url=job.video_url,
            cover_url=job.cover_url,
            error_message=job.error_message,
            duration=job.duration,
            resolution=job.resolution,
            created_at=job.created_at,
            updated_at=job.updated_at
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=VideoJobResponse)
async def get_video_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取单个视频任务详情
    """
    result = await db.execute(
        select(VideoJob).where(
            VideoJob.id == job_id,
            VideoJob.user_id == user_id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    return VideoJobResponse(
        id=job.id,
        task_id=job.task_id,
        title=job.title,
        prompt=job.prompt,
        shot_id=(job.extra_data or {}).get("shot_id") if isinstance(job.extra_data, dict) else None,
        shot_number=(job.extra_data or {}).get("shot_number") if isinstance(job.extra_data, dict) else None,
        storyboard_id=(job.extra_data or {}).get("storyboard_id") if isinstance(job.extra_data, dict) else None,
        storyboard_title=(job.extra_data or {}).get("storyboard_title") if isinstance(job.extra_data, dict) else None,
        script_id=(job.extra_data or {}).get("script_id") if isinstance(job.extra_data, dict) else None,
        script_title=(job.extra_data or {}).get("script_title") if isinstance(job.extra_data, dict) else None,
        novel_id=(job.extra_data or {}).get("novel_id") if isinstance(job.extra_data, dict) else None,
        novel_title=(job.extra_data or {}).get("novel_title") if isinstance(job.extra_data, dict) else None,
        model_name=job.model_name,
        status=job.status,
        progress=job.progress,
        video_url=job.video_url,
        cover_url=job.cover_url,
        error_message=job.error_message,
        duration=job.duration,
        resolution=job.resolution,
        created_at=job.created_at,
        updated_at=job.updated_at
    )


@router.post("/jobs/{job_id}/refresh")
async def refresh_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    刷新任务状态（从第三方API获取最新状态并更新数据库）
    """
    result = await db.execute(
        select(VideoJob).where(
            VideoJob.id == job_id,
            VideoJob.user_id == user_id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if not job.task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务没有第三方task_id"
        )
    
    try:
        # 从用户的 LLMConfig 获取 API 密钥
        resolved_api_key, resolved_base_url = await get_user_api_key(db, user_id, "volcano")
        client = _create_ark_client(resolved_api_key, resolved_base_url)
        
        get_result = client.content_generation.tasks.get(task_id=job.task_id)
        task_status = get_result.status
        
        # 更新状态
        job.status = task_status
        
        if task_status == "succeeded":
            job.progress = 100
            if hasattr(get_result, 'output') and get_result.output:
                job.video_url = getattr(get_result.output, 'video_url', None)
                job.cover_url = getattr(get_result.output, 'last_frame_url', None)
            # Log completion activity (commit happens below with job update)
            await log_activity(
                db=db,
                user_id=job.user_id,
                activity_type="completed",
                entity_type="video",
                entity_id=job.id,
                title=f"视频生成完成: {job.title}",
                description="视频生成任务已成功完成",
            )
        elif task_status == "running":
            job.progress = 50
        elif task_status == "failed":
            job.error_message = str(getattr(get_result, 'error', 'Unknown error'))
        
        await db.commit()
        
        return {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "video_url": job.video_url,
            "message": "状态已更新"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刷新状态失败: {str(e)}"
        )


# ============== 废弃的旧API（保持向后兼容）==============

class OldVideoGenerateRequest(BaseModel):
    """旧版视频生成请求（兼容）"""
    prompt: str
    api_key: str
    duration: int = 5
    image_url: Optional[str] = None


@router.post("/generate/legacy")
async def generate_video_legacy(
    request: OldVideoGenerateRequest
):
    """
    旧版视频生成接口（已废弃）。

    此接口仅用于向后兼容。不推荐在新代码中使用。
    请使用 /video/generate 接口，并通过用户的 LLMConfig 配置 API Key。
    """
    new_request = VideoGenerateRequest(
        prompt=request.prompt,
        duration=request.duration,
        api_key=request.api_key,
        image_url=request.image_url
    )
    # legacy endpoint 无法获取 user_id，跳过 LLMConfig 查找
    # 仅在明确提供了 api_key 时工作
    if not new_request.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Legacy 接口需要提供 api_key（请改用新版 /video/generate 接口）"
        )
    return await generate_video(new_request)


# ============== 视频下载代理接口 ==============

class VideoDownloadRequest(BaseModel):
    """视频下载请求"""
    video_url: str = Field(..., description="视频URL")
    filename: Optional[str] = Field(None, description="下载文件名")


@router.post("/download")
async def download_video(
    request: VideoDownloadRequest
):
    """
    代理下载视频 - 解决URL特殊字符截断问题
    
    由于火山引擎视频URL包含特殊字符，前端直接打开可能截断
    因此通过后端代理下载
    """
    try:
        import httpx
        import urllib.parse
        
        video_url = request.video_url
        
        # 解析URL确保特殊字符正确处理
        parsed = urllib.parse.urlparse(video_url)
        
        # 使用httpx下载视频
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(video_url)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"下载失败: HTTP {response.status_code}"
                )
            
            # 获取文件名
            filename = request.filename or "video.mp4"
            
            # 返回流式响应
            from fastapi.responses import StreamingResponse
            from starlette.datastructures import Headers
            
            headers = Headers({
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "video/mp4",
            })
            
            return StreamingResponse(
                response.aiter_bytes(),
                media_type="video/mp4",
                headers=headers
            )
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="下载超时，请稍后重试"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载失败: {str(e)}"
        )
