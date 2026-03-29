"""
音视频合成 API 端点
支持将视频与音频合并
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
from app.models.synthesis_job import SynthesisJob

router = APIRouter(tags=["音视频合成"])


# ============== 请求/响应模型 ==============

class SynthesisCreateRequest(BaseModel):
    """创建合成任务请求"""
    video_job_id: Optional[str] = Field(None, description="视频任务ID")
    tts_job_id: Optional[str] = Field(None, description="TTS任务ID")
    title: str = Field(..., description="作品标题")


class SynthesisStatusUpdate(BaseModel):
    """更新合成状态"""
    status: str = Field(..., description="状态: pending, running, succeeded, failed")
    progress: Optional[int] = Field(None, ge=0, le=100, description="进度百分比")
    output_url: Optional[str] = Field(None, description="输出URL")
    error_message: Optional[str] = Field(None, description="错误信息")


class SynthesisJobResponse(BaseModel):
    """合成任务响应"""
    id: str
    user_id: str
    video_job_id: Optional[str] = None
    tts_job_id: Optional[str] = None
    title: Optional[str] = None
    status: str
    progress: int
    output_url: Optional[str] = None
    output_type: Optional[str] = None
    duration: Optional[float] = None
    cost: Optional[int] = 0
    error_message: Optional[str] = None
    extra_data: Optional[str] = '{}'
    is_active: Optional[int] = 1
    created_at: datetime
    updated_at: datetime


# ============== API 端点 ==============

@router.post("/create", response_model=SynthesisJobResponse)
async def create_synthesis(
    request: SynthesisCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建合成任务"""
    job_id = str(uuid4())
    
    job = SynthesisJob(
        id=job_id,
        user_id=user_id,
        video_job_id=request.video_job_id,
        tts_job_id=request.tts_job_id,
        title=request.title,
        status="pending",
        progress=0
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return job


@router.get("/jobs", response_model=List[SynthesisJobResponse])
async def list_synthesis_jobs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的合成任务列表"""
    query = (
        select(SynthesisJob)
        .where(SynthesisJob.user_id == user_id)
        .order_by(desc(SynthesisJob.created_at))
        .limit(limit)
    )
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return jobs


@router.get("/jobs/{job_id}", response_model=SynthesisJobResponse)
async def get_synthesis_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取合成任务详情"""
    query = select(SynthesisJob).where(
        SynthesisJob.id == job_id,
        SynthesisJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return job


@router.put("/jobs/{job_id}", response_model=SynthesisJobResponse)
async def update_synthesis_job(
    job_id: str,
    update: SynthesisStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新合成任务状态"""
    query = select(SynthesisJob).where(
        SynthesisJob.id == job_id,
        SynthesisJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新字段
    if update.status:
        job.status = update.status
    if update.progress is not None:
        job.progress = update.progress
    if update.output_url:
        job.output_url = update.output_url
    if update.error_message:
        job.error_message = update.error_message
    
    await db.commit()
    await db.refresh(job)
    
    return job


@router.delete("/jobs/{job_id}")
async def delete_synthesis_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除合成任务"""
    query = select(SynthesisJob).where(
        SynthesisJob.id == job_id,
        SynthesisJob.user_id == user_id
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    await db.delete(job)
    await db.commit()
    
    return {"message": "删除成功"}
