"""
TTS (文本转语音) API 端点
支持火山引擎豆包语音合成
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.tts_job import TTSJob

router = APIRouter(tags=["语音合成"])


# ============== 请求/响应模型 ==============

class TTSGenerateRequest(BaseModel):
    """TTS生成请求"""
    text_content: str = Field(..., description="要转换的文本")
    title: Optional[str] = Field(None, description="任务标题")
    voice_model: str = Field("default", description="语音模型")
    api_provider: str = Field("volcano", description="API提供商: volcano, azure")
    script_id: Optional[str] = Field(None, description="关联的剧本ID")
    shot_id: Optional[str] = Field(None, description="关联的镜头ID")


class TTSJobResponse(BaseModel):
    """TTS任务响应"""
    id: str
    user_id: str
    script_id: Optional[str] = None
    shot_id: Optional[str] = None
    title: Optional[str] = None
    text_content: Optional[str] = None
    voice_model: Optional[str] = None
    api_provider: Optional[str] = None
    status: str
    progress: int
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    cost: Optional[int] = 0
    error_message: Optional[str] = None
    extra_data: Optional[str] = '{}'
    is_active: Optional[int] = 1
    created_at: datetime
    updated_at: datetime


# ============== API 端点 ==============

@router.post("/generate", response_model=TTSJobResponse)
async def generate_tts(
    request: TTSGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建TTS任务"""
    job_id = str(uuid4())
    
    job = TTSJob(
        id=job_id,
        user_id=user_id,
        title=request.title or f"TTS任务_{job_id[:8]}",
        text_content=request.text_content,
        voice_model=request.voice_model,
        api_provider=request.api_provider,
        script_id=request.script_id,
        shot_id=request.shot_id,
        status="pending",
        progress=0
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # TODO: 实际调用TTS API生成音频
    # 目前返回成功，实际异步生成由后台任务处理
    
    return job


@router.get("/jobs", response_model=List[TTSJobResponse])
async def list_tts_jobs(
    limit: int = 50,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的TTS任务列表"""
    query = select(TTSJob).where(TTSJob.user_id == user_id)
    
    if status_filter:
        query = query.where(TTSJob.status == status_filter)
    
    query = query.order_by(desc(TTSJob.created_at)).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return jobs


@router.get("/jobs/{job_id}", response_model=TTSJobResponse)
async def get_tts_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取TTS任务详情"""
    query = select(TTSJob).where(
        TTSJob.id == job_id,
        TTSJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return job


@router.put("/jobs/{job_id}", response_model=TTSJobResponse)
async def update_tts_job(
    job_id: str,
    status_update: str = None,
    progress: int = None,
    audio_url: str = None,
    duration: float = None,
    error_message: str = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新TTS任务状态"""
    query = select(TTSJob).where(
        TTSJob.id == job_id,
        TTSJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if status_update:
        job.status = status_update
    if progress is not None:
        job.progress = progress
    if audio_url:
        job.audio_url = audio_url
    if duration is not None:
        job.duration = duration
    if error_message:
        job.error_message = error_message
    
    await db.commit()
    await db.refresh(job)
    
    return job


@router.delete("/jobs/{job_id}")
async def delete_tts_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除TTS任务"""
    query = select(TTSJob).where(
        TTSJob.id == job_id,
        TTSJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    await db.delete(job)
    await db.commit()
    
    return {"message": "删除成功"}
