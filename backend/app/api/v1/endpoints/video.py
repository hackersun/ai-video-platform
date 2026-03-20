"""
视频生成 API 端点
支持火山引擎豆包视频模型

完整异步流程:
1. POST /video/generate -> 提交任务，返回 task_id
2. POST /video/status -> 查询任务状态
3. POST /video/generate/complete -> 同步等待完成（轮询）
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import asyncio
import aiohttp

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id

router = APIRouter(tags=["视频生成"])


# ============== 常量配置 ==============

VIDEO_MODEL_ID = "Doubao-Seed-2.0-pro"
VIDEO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


# ============== 请求/响应模型 ==============

class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    prompt: str = Field(..., description="视频描述")
    model: str = Field(VIDEO_MODEL_ID, description="模型ID，默认 Doubao-Seed-2.0-pro")
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


class VideoStatusRequest(BaseModel):
    """视频状态查询请求"""
    task_id: str
    api_key: str = Field(..., description="火山引擎API Key")


class VideoStatusResponse(BaseModel):
    """视频状态响应"""
    task_id: str
    status: str  # pending, processing, completed, failed
    video_url: Optional[str]
    cover_url: Optional[str]
    message: str
    progress: Optional[int] = Field(None, description="进度百分比")


class VideoQueryResponse(BaseModel):
    """视频列表响应"""
    videos: List[dict]


# ============== API端点 ==============

async def _call_volcano_api(api_key: str, payload: dict) -> dict:
    """调用火山引擎API"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            VIDEO_BASE_URL + "/responses",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=300)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"API调用失败: {error_text}")
            return await response.json()


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(
    request: VideoGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    生成视频 - 异步提交任务
    
    返回 task_id，用于后续查询状态
    """
    try:
        # 构建消息内容
        content = []
        if request.image_url:
            content.append({
                "type": "input_image",
                "image_url": request.image_url
            })
        content.append({
            "type": "input_text",
            "text": f"请生成一段{request.duration}秒的视频：{request.prompt}"
        })
        
        payload = {
            "model": request.model,
            "input": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }
        
        result = await _call_volcano_api(request.api_key, payload)

        # 火山引擎Responses API返回结果
        # output可能是list或dict，需要处理
        task_id = result.get("id") or str(uuid4())

        # 检查返回的内容
        output_data = result.get("output", [])
        if isinstance(output_data, list) and len(output_data) > 0:
            # output是list，找第一个非reasoning项
            for item in output_data:
                if isinstance(item, dict) and item.get("type") == "video":
                    video_url = item.get("url") or item.get("video_url")
                    if video_url:
                        return VideoGenerateResponse(
                            task_id=task_id,
                            status="completed",
                            message="视频生成完成"
                        )

        # 检查是否有错误
        if "error" in result:
            error_msg = result.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"视频生成失败: {error_msg}"
            )

        # 如果没有video数据，说明这是异步任务
        return VideoGenerateResponse(
            task_id=task_id,
            status="pending",
            message="视频生成任务已提交，请使用任务ID查询进度"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"视频生成失败: {str(e)}"
        )


@router.post("/status", response_model=VideoStatusResponse)
async def query_video_status(
    request: VideoStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    查询视频生成状态
    
    火山引擎Responses API是同步的，通常10-30秒完成
    如果之前调用返回了task_id，可以用它来查询
    """
    try:
        # 火山引擎的Responses API是同步的
        # 如果之前的调用还在处理，可以通过task_id查询
        
        payload = {
            "task_id": request.task_id
        }
        
        result = await _call_volcano_api(request.api_key, payload)
        
        # 检查输出
        output_items = result.get("output", {}).get("attachments", [])
        
        video_url = None
        cover_url = None
        status_str = "processing"
        message = "视频生成中..."
        progress = None
        
        for item in output_items:
            if item.get("type") == "video":
                video_url = item.get("url")
                status_str = "completed"
                message = "视频生成完成"
                progress = 100
            elif item.get("type") == "image" and item.get("property", {}).get("type") == "cover":
                cover_url = item.get("url")
        
        return VideoStatusResponse(
            task_id=request.task_id,
            status=status_str,
            video_url=video_url,
            cover_url=cover_url,
            message=message,
            progress=progress
        )
        
    except Exception as e:
        return VideoStatusResponse(
            task_id=request.task_id,
            status="failed",
            video_url=None,
            cover_url=None,
            message=f"查询失败: {str(e)}"
        )


@router.post("/generate/complete", response_model=VideoStatusResponse)
async def generate_video_complete(
    request: VideoGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    生成视频 - 同步等待完成
    
    提交任务后轮询等待完成，返回视频URL
    适用于短等待场景（5-30秒）
    """
    try:
        # 构建消息内容
        content = []
        if request.image_url:
            content.append({
                "type": "input_image",
                "image_url": request.image_url
            })
        content.append({
            "type": "input_text",
            "text": f"请生成一段{request.duration}秒的视频：{request.prompt}"
        })
        
        payload = {
            "model": request.model,
            "input": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }
        
        # 第一次调用
        result = await _call_volcano_api(request.api_key, payload)
        
        task_id = result.get("id") or str(uuid4())
        
        # 检查第一次结果
        output_items = result.get("output", {}).get("attachments", [])
        
        video_url = None
        cover_url = None
        
        for item in output_items:
            if item.get("type") == "video":
                video_url = item.get("url")
            elif item.get("type") == "image" and item.get("property", {}).get("type") == "cover":
                cover_url = item.get("url")
        
        if video_url:
            return VideoStatusResponse(
                task_id=task_id,
                status="completed",
                video_url=video_url,
                cover_url=cover_url,
                message="视频生成完成",
                progress=100
            )
        
        # 如果没完成，轮询等待
        max_polls = 60  # 最多等待5分钟
        poll_interval = 5
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                # 尝试查询状态
                status_payload = {"task_id": task_id}
                status_result = await _call_volcano_api(request.api_key, status_payload)
                
                output_items = status_result.get("output", {}).get("attachments", [])
                
                for item in output_items:
                    if item.get("type") == "video":
                        video_url = item.get("url")
                    elif item.get("type") == "image" and item.get("property", {}).get("type") == "cover":
                        cover_url = item.get("url")
                
                if video_url:
                    return VideoStatusResponse(
                        task_id=task_id,
                        status="completed",
                        video_url=video_url,
                        cover_url=cover_url,
                        message="视频生成完成",
                        progress=100
                    )
                    
            except Exception:
                # 轮询查询失败，继续等待
                pass
            
            # 继续等待
            progress = min(95, (i + 1) * 100 // max_polls)
        
        # 超时
        return VideoStatusResponse(
            task_id=task_id,
            status="processing",
            video_url=None,
            cover_url=None,
            message="视频生成超时，请稍后使用任务ID查询",
            progress=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"视频生成失败: {str(e)}"
        )


@router.get("/models")
async def list_video_models():
    """获取可用的视频生成模型"""
    video_models = [
        {
            "id": "Doubao-Seed-2.0-pro",
            "name": "豆包Seed-2.0-pro",
            "type": "video-generation",
            "capabilities": ["text-to-video", "image-to-video"],
            "durations": [4, 8, 10],
            "resolutions": ["480p", "720p", "1080p"],
            "input_cost_per_1k": 0.5,
            "output_cost_per_1k": 0.5,
            "description": "火山引擎高质量视频生成模型，支持文生视频、图生视频"
        }
    ]
    
    return {
        "models": video_models,
        "default": "Doubao-Seed-2.0-pro"
    }
