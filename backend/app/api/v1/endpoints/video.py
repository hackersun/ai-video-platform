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

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.video_job import VideoJob

router = APIRouter(tags=["视频生成"])


# ============== 常量配置 ==============

# 视频模型ID - 使用Doubao-Seedance-1.5-pro
VIDEO_MODEL_ID = "doubao-seedance-1-5-pro-251215"


# ============== 请求/响应模型 ==============

class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    prompt: str = Field(..., description="视频描述")
    model: str = Field(VIDEO_MODEL_ID, description="模型ID，默认 doubao-seedance-1-5-pro-251215")
    duration: int = Field(5, ge=4, le=10, description="视频时长（秒），支持4/8/10秒")
    resolution: str = Field("720p", description="分辨率: 480p, 720p, 1080p")
    api_key: str = Field(..., description="火山引擎API Key")
    image_url: Optional[str] = Field(None, description="参考图片URL，用于图生视频")
    seed: Optional[int] = Field(None, description="随机种子")


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


def _create_ark_client(api_key: str):
    """创建ARK客户端"""
    from volcenginesdkarkruntime import Ark
    return Ark(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key,
    )


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
    try:
        client = _create_ark_client(request.api_key)
        
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
        
        # 调用SDK创建任务
        create_result = client.content_generation.tasks.create(
            model=request.model,
            content=content
        )
        
        # 创建数据库记录
        job = VideoJob(
            id=str(uuid4()),
            user_id=user_id,
            task_id=create_result.id,
            title=request.prompt[:50] if len(request.prompt) > 50 else request.prompt,
            prompt=request.prompt,
            model_id=request.model,
            model_name="Doubao-Seedance-1.5-pro",
            duration=request.duration,
            resolution=request.resolution,
            image_url=request.image_url,
            status="pending",
            progress=10
        )
        db.add(job)
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
    job_id: Optional[str] = None,
    api_key: Optional[str] = None
):
    """
    查询视频生成状态
    
    使用task_id轮询任务状态，同时更新数据库
    """
    # 如果没有提供api_key，使用默认的
    if not api_key:
        api_key = "be8feb9d-6b08-406e-8447-b22b87cd907a"
    
    try:
        client = _create_ark_client(api_key)
        
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
        client = _create_ark_client(job.extra_data.get("api_key", ""))
        
        get_result = client.content_generation.tasks.get(task_id=job.task_id)
        task_status = get_result.status
        
        # 更新状态
        job.status = task_status
        
        if task_status == "succeeded":
            job.progress = 100
            if hasattr(get_result, 'output') and get_result.output:
                job.video_url = getattr(get_result.output, 'video_url', None)
                job.cover_url = getattr(get_result.output, 'last_frame_url', None)
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
    """旧版视频生成接口，保持向后兼容"""
    new_request = VideoGenerateRequest(
        prompt=request.prompt,
        duration=request.duration,
        api_key=request.api_key,
        image_url=request.image_url
    )
    return await generate_video(new_request)
