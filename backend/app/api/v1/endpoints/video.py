"""
视频生成 API 端点
支持火山引擎豆包视频模型

使用官方SDK: volcengine-python-sdk[ark]
模型: doubao-seedance-1-5-pro-251215 (Doubao-Seedance-1.5-pro)

完整异步流程:
1. POST /video/generate -> 提交任务，返回 task_id
2. GET /video/status/{task_id} -> 查询任务状态
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id

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
    status: str
    message: str


class VideoStatusResponse(BaseModel):
    """视频状态响应"""
    task_id: str
    status: str  # pending, running, succeeded, failed
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    message: str
    progress: Optional[int] = Field(None, description="进度百分比")
    duration: Optional[int] = None
    resolution: Optional[str] = None


class VideoQueryResponse(BaseModel):
    """视频列表响应"""
    videos: List[dict]


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
    db: AsyncSession = Depends(get_db)
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
        
        prompt_text = f"{request.prompt} {duration_arg} --camerafixed {camerafixed} --watermark {watermark} {resolution_arg}"
        
        content.append({
            "type": "text",
            "text": prompt_text
        })
        
        # 调用SDK创建任务
        create_result = client.content_generation.tasks.create(
            model=request.model,
            content=content
        )
        
        return VideoGenerateResponse(
            task_id=create_result.id,
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
    api_key: str
):
    """
    查询视频生成状态
    
    使用task_id轮询任务状态
    """
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
        
        if task_status == "succeeded" and hasattr(get_result, 'output'):
            output = get_result.output
            if output:
                video_url = getattr(output, 'video_url', None)
                cover_url = getattr(output, 'last_frame_url', None)
        
        if hasattr(get_result, 'duration'):
            duration = get_result.duration
        if hasattr(get_result, 'resolution'):
            resolution = get_result.resolution
        
        # 进度百分比估算
        progress = None
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


@router.post("/generate/sync")
async def generate_video_sync(
    request: VideoGenerateRequest
):
    """
    同步生成视频 - 轮询等待完成
    
    适用于短时生成场景（测试用）
    """
    try:
        client = _create_ark_client(request.api_key)
        
        # 构建content
        content = []
        
        if request.image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": request.image_url}
            })
        
        duration_arg = f"--duration {request.duration}"
        prompt_text = f"{request.prompt} {duration_arg} --camerafixed false --watermark true"
        
        content.append({
            "type": "text",
            "text": prompt_text
        })
        
        # 创建任务
        create_result = client.content_generation.tasks.create(
            model=request.model,
            content=content
        )
        
        task_id = create_result.id
        
        # 轮询等待完成
        max_wait = 120  # 最多等待120秒
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            get_result = client.content_generation.tasks.get(task_id=task_id)
            task_status = get_result.status
            
            if task_status == "succeeded":
                output = get_result.output
                video_url = getattr(output, 'video_url', None) if output else None
                cover_url = getattr(output, 'last_frame_url', None) if output else None
                
                return {
                    "task_id": task_id,
                    "status": "succeeded",
                    "video_url": video_url,
                    "cover_url": cover_url,
                    "duration": getattr(get_result, 'duration', None),
                    "resolution": getattr(get_result, 'resolution', None),
                    "message": "视频生成完成"
                }
            
            elif task_status == "failed":
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(getattr(get_result, 'error', 'Unknown error')),
                    "message": "视频生成失败"
                }
            
            # 等待3秒后继续轮询
            time.sleep(3)
        
        # 超时
        return {
            "task_id": task_id,
            "status": "timeout",
            "message": "生成超时，请稍后使用task_id查询"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"视频生成失败: {str(e)}"
        )


@router.get("/jobs")
async def list_video_jobs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取用户的视频任务列表
    
    TODO: 从数据库查询历史任务
    """
    # TODO: 实现从数据库查询历史任务
    return {"videos": [], "message": "历史任务查询待实现"}


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
