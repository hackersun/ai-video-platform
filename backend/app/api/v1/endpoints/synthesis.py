"""
音视频合成 API 端点
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_utils import get_user_volcano_api_key
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.synthesis_job import SynthesisJob
from app.services.volcano_service import VolcanoService

router = APIRouter(tags=["音视频合成"])


class SynthesisGenerateRequest(BaseModel):
    video_url: str = Field(..., min_length=1, description="原始视频URL")
    audio_url: str = Field(..., min_length=1, description="要合成的音频URL")
    title: Optional[str] = Field(None, description="任务标题")
    api_key: Optional[str] = Field(None, description="火山引擎 API Key（可选，不填则自动使用用户配置的 Key）")
    video_job_id: Optional[str] = Field(None, description="来源视频任务ID")
    tts_job_id: Optional[str] = Field(None, description="来源TTS任务ID")

    @field_validator("video_url", "audio_url")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("video_url", "audio_url")
    @classmethod
    def validate_urls(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be a valid http or https URL")
        return value


class SynthesisGenerateResponse(BaseModel):
    task_id: str
    job_id: str
    status: str
    message: str


class SynthesisJobResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    title: Optional[str] = None
    model_name: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    video_job_id: Optional[str] = None
    tts_job_id: Optional[str] = None
    status: str
    progress: int
    output_url: Optional[str] = None
    cover_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@router.post("/generate", response_model=SynthesisGenerateResponse)
async def generate_synthesis(
    request: SynthesisGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    resolved_api_key = request.api_key or await get_user_volcano_api_key(db, user_id)
    service = VolcanoService(resolved_api_key)
    try:
        result = await service.video_voice_synthesis(
            video_url=request.video_url,
            audio_url=request.audio_url,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Synthesis service request failed",
        ) from exc

    job_status = result.get("status", "succeeded")

    job = SynthesisJob(
        id=str(uuid4()),
        user_id=user_id,
        task_id=result.get("task_id"),
        title=request.title or "音视频合成",
        model_id="volcano-synthesis",
        model_name="volcano-synthesis",
        video_url=request.video_url,
        audio_url=request.audio_url,
        status=job_status,
        progress=100 if job_status == "succeeded" else 0,
        output_url=result.get("output_url"),
        duration_seconds=result.get("duration"),
        cost=0,
        extra_data={
            "video_job_id": request.video_job_id,
            "tts_job_id": request.tts_job_id,
        },
    )
    db.add(job)
    await db.commit()

    return SynthesisGenerateResponse(
        task_id=result.get("task_id", job.id),
        job_id=job.id,
        status=job.status,
        message=result.get("message", "合成任务已完成"),
    )


@router.get("/jobs", response_model=List[SynthesisJobResponse])
async def list_synthesis_jobs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(SynthesisJob)
        .where(SynthesisJob.user_id == user_id, SynthesisJob.is_active == True)
        .order_by(desc(SynthesisJob.created_at))
        .limit(50)
    )
    jobs = result.scalars().all()
    return [
        SynthesisJobResponse(
            id=job.id,
            task_id=job.task_id,
            title=job.title,
            model_name=job.model_name,
            video_url=job.video_url,
            audio_url=job.audio_url,
            video_job_id=(job.extra_data or {}).get("video_job_id") if isinstance(job.extra_data, dict) else None,
            tts_job_id=(job.extra_data or {}).get("tts_job_id") if isinstance(job.extra_data, dict) else None,
            status=job.status,
            progress=job.progress,
            output_url=job.output_url,
            cover_url=job.cover_url,
            duration_seconds=job.duration_seconds,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        for job in jobs
    ]
