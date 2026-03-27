"""
TTS 语音合成 API 端点
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Shot, Storyboard
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.tts_job import TTSJob
from app.services.volcano_service import VolcanoService
from app.core.api_key_utils import get_user_volcano_api_key

router = APIRouter(tags=["TTS语音合成"])


class TTSGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="要转换的文本")
    model: str = Field("doubao-tts", min_length=1, description="TTS 模型ID")
    voice: str = Field("default", min_length=1, description="音色选择")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    title: Optional[str] = Field(None, description="任务标题")
    api_key: Optional[str] = Field(None, description="火山引擎 API Key（可选，不填则自动使用用户配置的 Key）")
    shot_id: Optional[str] = Field(None, description="关联的镜头ID")

    @field_validator("text", "model", "voice")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class TTSGenerateResponse(BaseModel):
    task_id: str
    job_id: str
    status: str
    message: str


class TTSJobResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    model_name: Optional[str] = None
    voice: Optional[str] = None
    speed: Optional[float] = None
    shot_id: Optional[str] = None
    script_id: Optional[str] = None
    status: str
    progress: int
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_tts(
    request: TTSGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    script_id: Optional[str] = None

    if request.shot_id:
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

        script_id = storyboard.script_id

    # api_key: 优先用请求提供的，其次从用户 LLMConfig 中获取
    resolved_api_key = request.api_key or await get_user_volcano_api_key(db, user_id)
    service = VolcanoService(resolved_api_key)
    try:
        result = await service.text_to_speech(
            text=request.text,
            model=request.model,
            voice=request.voice,
            speed=request.speed,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS service request failed",
        ) from exc

    job_status = result.get("status", "succeeded")

    job = TTSJob(
        id=str(uuid4()),
        user_id=user_id,
        task_id=result.get("task_id"),
        title=request.title or (request.text[:50] if len(request.text) > 50 else request.text),
        text=request.text,
        model_id=request.model,
        model_name=result.get("model", request.model),
        voice=request.voice,
        speed=request.speed,
        shot_id=request.shot_id,
        status=job_status,
        progress=100 if job_status == "succeeded" else 0,
        audio_url=result.get("audio_url"),
        duration_seconds=result.get("duration"),
        cost=0,
        extra_data={"script_id": script_id} if script_id else {},
    )
    db.add(job)
    await db.commit()

    return TTSGenerateResponse(
        task_id=result.get("task_id", job.id),
        job_id=job.id,
        status=job.status,
        message=result.get("message", "TTS 任务已完成"),
    )


@router.get("/jobs", response_model=List[TTSJobResponse])
async def list_tts_jobs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(TTSJob)
        .where(TTSJob.user_id == user_id, TTSJob.is_active == True)
        .order_by(desc(TTSJob.created_at))
        .limit(50)
    )
    jobs = result.scalars().all()
    return [
        TTSJobResponse(
            id=job.id,
            task_id=job.task_id,
            title=job.title,
            text=job.text,
            model_name=job.model_name,
            voice=job.voice,
            speed=job.speed,
            shot_id=job.shot_id,
            script_id=(job.extra_data or {}).get("script_id") if isinstance(job.extra_data, dict) else None,
            status=job.status,
            progress=job.progress,
            audio_url=job.audio_url,
            duration_seconds=job.duration_seconds,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        for job in jobs
    ]
