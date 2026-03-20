"""
镜头管理 API 端点
"""
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from pydantic import BaseModel, Field

from app.core.database import get_db, Base
from app.core.security import get_current_user_id

router = APIRouter(tags=["镜头管理"])


# ============== 数据库模型 ==============

class Shot(Base):
    """镜头模型"""
    __tablename__ = "shots"
    
    id = Column(String(36), primary_key=True)
    storyboard_id = Column(String(36), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    shot_number = Column(Integer, nullable=False, default=1)
    duration = Column(Integer, default=4)  # 镜头时长（秒）
    prompt = Column(Text)  # 视频生成Prompt
    dialogue = Column(Text)  # 台词
    visual_description = Column(Text)  # 视觉描述
    camera_angle = Column(String(50))  # 镜头角度
    video_url = Column(String(500))  # 生成视频URL
    audio_url = Column(String(500))  # 语音URL
    video_status = Column(String(20), default="pending")  # pending, generating, completed, failed
    audio_status = Column(String(20), default="pending")  # pending, generating, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============== Pydantic 模型 ==============

class ShotCreate(BaseModel):
    """创建镜头请求"""
    storyboard_id: str = Field(..., description="所属分镜ID")
    shot_number: int = Field(..., description="镜头序号")
    duration: Optional[int] = Field(4, description="镜头时长（秒）")
    prompt: str = Field(..., description="视频生成Prompt")
    dialogue: Optional[str] = Field(None, description="台词")
    visual_description: Optional[str] = Field(None, description="视觉描述")
    camera_angle: Optional[str] = Field(None, description="镜头角度")


class ShotUpdate(BaseModel):
    """更新镜头请求"""
    shot_number: Optional[int] = None
    duration: Optional[int] = None
    prompt: Optional[str] = None
    dialogue: Optional[str] = None
    visual_description: Optional[str] = None
    camera_angle: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    video_status: Optional[str] = None
    audio_status: Optional[str] = None


class ShotResponse(BaseModel):
    """镜头响应"""
    id: str
    storyboard_id: str
    user_id: str
    shot_number: int
    duration: int
    prompt: Optional[str] = None
    dialogue: Optional[str] = None
    visual_description: Optional[str] = None
    camera_angle: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    video_status: str
    audio_status: str
    created_at: str
    updated_at: str


# ============== API 端点 ==============

@router.get("/storyboard/{storyboard_id}", response_model=List[ShotResponse])
async def list_shots_by_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取指定分镜的所有镜头"""
    result = await db.execute(
        select(Shot)
        .where(and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id))
        .order_by(Shot.shot_number)
    )
    shots = result.scalars().all()
    
    return [
        ShotResponse(
            id=str(s.id),
            storyboard_id=str(s.storyboard_id),
            user_id=str(s.user_id),
            shot_number=s.shot_number or 1,
            duration=s.duration or 4,
            prompt=s.prompt,
            dialogue=s.dialogue,
            visual_description=s.visual_description,
            camera_angle=s.camera_angle,
            video_url=s.video_url,
            audio_url=s.audio_url,
            video_status=s.video_status or "pending",
            audio_status=s.audio_status or "pending",
            created_at=str(s.created_at),
            updated_at=str(s.updated_at)
        )
        for s in shots
    ]


@router.get("/{shot_id}", response_model=ShotResponse)
async def get_shot(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个镜头"""
    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    shot = result.scalar_one_or_none()
    
    if not shot:
        raise HTTPException(status_code=404, detail="镜头不存在")
    
    return ShotResponse(
        id=str(shot.id),
        storyboard_id=str(shot.storyboard_id),
        user_id=str(shot.user_id),
        shot_number=shot.shot_number or 1,
        duration=shot.duration or 4,
        prompt=shot.prompt,
        dialogue=shot.dialogue,
        visual_description=shot.visual_description,
        camera_angle=shot.camera_angle,
        video_url=shot.video_url,
        audio_url=shot.audio_url,
        video_status=shot.video_status or "pending",
        audio_status=shot.audio_status or "pending",
        created_at=str(shot.created_at),
        updated_at=str(shot.updated_at)
    )


@router.post("", response_model=ShotResponse, status_code=status.HTTP_201_CREATED)
async def create_shot(
    shot: ShotCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建镜头"""
    shot_id = str(uuid.uuid4())
    
    db_shot = Shot(
        id=shot_id,
        storyboard_id=shot.storyboard_id,
        user_id=user_id,
        shot_number=shot.shot_number,
        duration=shot.duration or 4,
        prompt=shot.prompt,
        dialogue=shot.dialogue,
        visual_description=shot.visual_description,
        camera_angle=shot.camera_angle,
        video_status="pending",
        audio_status="pending"
    )
    
    db.add(db_shot)
    await db.commit()
    await db.refresh(db_shot)
    
    return ShotResponse(
        id=str(db_shot.id),
        storyboard_id=str(db_shot.storyboard_id),
        user_id=str(db_shot.user_id),
        shot_number=db_shot.shot_number or 1,
        duration=db_shot.duration or 4,
        prompt=db_shot.prompt,
        dialogue=db_shot.dialogue,
        visual_description=db_shot.visual_description,
        camera_angle=db_shot.camera_angle,
        video_url=db_shot.video_url,
        audio_url=db_shot.audio_url,
        video_status=db_shot.video_status or "pending",
        audio_status=db_shot.audio_status or "pending",
        created_at=str(db_shot.created_at),
        updated_at=str(db_shot.updated_at)
    )


@router.put("/{shot_id}", response_model=ShotResponse)
async def update_shot(
    shot_id: str,
    shot_update: ShotUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新镜头"""
    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    db_shot = result.scalar_one_or_none()
    
    if not db_shot:
        raise HTTPException(status_code=404, detail="镜头不存在")
    
    # 更新字段
    update_data = shot_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_shot, key, value)
    
    await db.commit()
    await db.refresh(db_shot)
    
    return ShotResponse(
        id=str(db_shot.id),
        storyboard_id=str(db_shot.storyboard_id),
        user_id=str(db_shot.user_id),
        shot_number=db_shot.shot_number or 1,
        duration=db_shot.duration or 4,
        prompt=db_shot.prompt,
        dialogue=db_shot.dialogue,
        visual_description=db_shot.visual_description,
        camera_angle=db_shot.camera_angle,
        video_url=db_shot.video_url,
        audio_url=db_shot.audio_url,
        video_status=db_shot.video_status or "pending",
        audio_status=db_shot.audio_status or "pending",
        created_at=str(db_shot.created_at),
        updated_at=str(db_shot.updated_at)
    )


@router.delete("/{shot_id}")
async def delete_shot(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除镜头"""
    result = await db.execute(
        select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id))
    )
    db_shot = result.scalar_one_or_none()
    
    if not db_shot:
        raise HTTPException(status_code=404, detail="镜头不存在")
    
    await db.delete(db_shot)
    await db.commit()
    
    return {"message": "镜头已删除"}


@router.post("/batch", response_model=List[ShotResponse], status_code=status.HTTP_201_CREATED)
async def create_shots_batch(
    storyboard_id: str,
    shots_data: List[ShotCreate],
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """批量创建镜头"""
    created_shots = []
    
    for shot_data in shots_data:
        shot_id = str(uuid.uuid4())
        db_shot = Shot(
            id=shot_id,
            storyboard_id=storyboard_id,
            user_id=user_id,
            shot_number=shot_data.shot_number,
            duration=shot_data.duration or 4,
            prompt=shot_data.prompt,
            dialogue=shot_data.dialogue,
            visual_description=shot_data.visual_description,
            camera_angle=shot_data.camera_angle,
            video_status="pending",
            audio_status="pending"
        )
        db.add(db_shot)
        created_shots.append(db_shot)
    
    await db.commit()
    
    return [
        ShotResponse(
            id=str(s.id),
            storyboard_id=str(s.storyboard_id),
            user_id=str(s.user_id),
            shot_number=s.shot_number or 1,
            duration=s.duration or 4,
            prompt=s.prompt,
            dialogue=s.dialogue,
            visual_description=s.visual_description,
            camera_angle=s.camera_angle,
            video_url=s.video_url,
            audio_url=s.audio_url,
            video_status=s.video_status or "pending",
            audio_status=s.audio_status or "pending",
            created_at=str(s.created_at),
            updated_at=str(s.updated_at)
        )
        for s in created_shots
    ]
