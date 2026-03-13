"""
视频相关端点
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.novel import Video


router = APIRouter()


class VideoCreateRequest(BaseModel):
    title: str
    script_id: Optional[str] = None
    settings: dict = {}


class VideoResponse(BaseModel):
    id: str
    title: str
    status: str
    video_url: Optional[str] = None
    settings: dict = {}

    class Config:
        from_attributes = True


@router.get("/")
async def list_videos(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取当前用户的视频列表"""
    query = select(Video).where(Video.user_id == user_id).offset(skip).limit(limit)
    result = await db.execute(query)
    videos = result.scalars().all()

    count_query = (
        select(func.count()).select_from(Video).where(Video.user_id == user_id)
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return {
        "items": [
            VideoResponse(
                id=v.id,
                title=v.title,
                status=v.status,
                video_url=v.video_url,
                settings=v.settings or {},
            )
            for v in videos
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{video_id}")
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取视频详情"""
    query = select(Video).where(Video.id == video_id, Video.user_id == user_id)
    result = await db.execute(query)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    return VideoResponse(
        id=video.id,
        title=video.title,
        status=video.status,
        video_url=video.video_url,
        settings=video.settings or {},
    )


@router.post("/")
async def create_video(
    request: VideoCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建视频"""
    video = Video(
        id=str(uuid.uuid4()),
        user_id=user_id,
        script_id=request.script_id,
        title=request.title,
        settings=request.settings,
        status="pending",
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    return {
        "id": video.id,
        "title": video.title,
        "status": video.status,
    }


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除视频"""
    query = select(Video).where(Video.id == video_id, Video.user_id == user_id)
    result = await db.execute(query)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    await db.delete(video)
    await db.commit()

    return {"message": "删除成功"}


@router.post("/{video_id}/generate")
async def generate_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """AI生成视频"""
    query = select(Video).where(Video.id == video_id, Video.user_id == user_id)
    result = await db.execute(query)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    video.status = "generating"
    await db.commit()

    return {"id": video.id, "status": "generating", "message": "视频生成已开始"}


@router.get("/{video_id}/status")
async def get_video_status(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取视频生成状态"""
    query = select(Video).where(Video.id == video_id, Video.user_id == user_id)
    result = await db.execute(query)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    return {
        "id": video.id,
        "status": video.status,
        "progress": 50
        if video.status == "generating"
        else (100 if video.status == "completed" else 0),
        "message": "视频生成中..."
        if video.status == "generating"
        else ("完成" if video.status == "completed" else "等待中"),
    }
