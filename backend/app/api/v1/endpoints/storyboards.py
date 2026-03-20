"""
分镜管理 API 端点
"""
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON
from pydantic import BaseModel, Field

from app.core.database import get_db, Base
from app.core.security import get_current_user_id

router = APIRouter(tags=["分镜管理"])


# ============== 数据库模型 ==============

class Storyboard(Base):
    """分镜模型"""
    __tablename__ = "storyboards"
    
    id = Column(String(36), primary_key=True)
    script_id = Column(String(36), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    content = Column(JSON)  # 分镜内容（结构化）
    shot_count = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)  # 总时长（秒）
    status = Column(String(20), default="draft")  # draft, generating, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============== Pydantic 模型 ==============

class StoryboardCreate(BaseModel):
    """创建分镜请求"""
    script_id: str = Field(..., description="所属剧本ID")
    title: str = Field(..., min_length=1, max_length=200, description="分镜标题")
    description: Optional[str] = Field(None, description="分镜描述")
    content: Optional[dict] = Field(None, description="分镜内容")


class StoryboardUpdate(BaseModel):
    """更新分镜请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: Optional[int] = None
    total_duration: Optional[int] = None
    status: Optional[str] = None


class StoryboardResponse(BaseModel):
    """分镜响应"""
    id: str
    script_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: int
    total_duration: int
    status: str
    created_at: str
    updated_at: str


# ============== API 端点 ==============

@router.get("/script/{script_id}", response_model=List[StoryboardResponse])
async def list_storyboards_by_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取指定剧本的所有分镜"""
    result = await db.execute(
        select(Storyboard)
        .where(and_(Storyboard.script_id == script_id, Storyboard.user_id == user_id))
        .order_by(desc(Storyboard.created_at))
    )
    storyboards = result.scalars().all()
    
    return [
        StoryboardResponse(
            id=str(s.id),
            script_id=str(s.script_id),
            user_id=str(s.user_id),
            title=s.title,
            description=s.description,
            content=s.content,
            shot_count=s.shot_count or 0,
            total_duration=s.total_duration or 0,
            status=s.status or "draft",
            created_at=str(s.created_at),
            updated_at=str(s.updated_at)
        )
        for s in storyboards
    ]


@router.get("/{storyboard_id}", response_model=StoryboardResponse)
async def get_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    return StoryboardResponse(
        id=str(storyboard.id),
        script_id=str(storyboard.script_id),
        user_id=str(storyboard.user_id),
        title=storyboard.title,
        description=storyboard.description,
        content=storyboard.content,
        shot_count=storyboard.shot_count or 0,
        total_duration=storyboard.total_duration or 0,
        status=storyboard.status or "draft",
        created_at=str(storyboard.created_at),
        updated_at=str(storyboard.updated_at)
    )


@router.post("", response_model=StoryboardResponse, status_code=status.HTTP_201_CREATED)
async def create_storyboard(
    storyboard: StoryboardCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建分镜"""
    storyboard_id = str(uuid.uuid4())
    
    db_storyboard = Storyboard(
        id=storyboard_id,
        script_id=storyboard.script_id,
        user_id=user_id,
        title=storyboard.title,
        description=storyboard.description,
        content=storyboard.content or {},
        status="draft"
    )
    
    db.add(db_storyboard)
    await db.commit()
    await db.refresh(db_storyboard)
    
    return StoryboardResponse(
        id=str(db_storyboard.id),
        script_id=str(db_storyboard.script_id),
        user_id=str(db_storyboard.user_id),
        title=db_storyboard.title,
        description=db_storyboard.description,
        content=db_storyboard.content,
        shot_count=db_storyboard.shot_count or 0,
        total_duration=db_storyboard.total_duration or 0,
        status=db_storyboard.status or "draft",
        created_at=str(db_storyboard.created_at),
        updated_at=str(db_storyboard.updated_at)
    )


@router.put("/{storyboard_id}", response_model=StoryboardResponse)
async def update_storyboard(
    storyboard_id: str,
    storyboard_update: StoryboardUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    db_storyboard = result.scalar_one_or_none()
    
    if not db_storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    # 更新字段
    update_data = storyboard_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_storyboard, key, value)
    
    await db.commit()
    await db.refresh(db_storyboard)
    
    return StoryboardResponse(
        id=str(db_storyboard.id),
        script_id=str(db_storyboard.script_id),
        user_id=str(db_storyboard.user_id),
        title=db_storyboard.title,
        description=db_storyboard.description,
        content=db_storyboard.content,
        shot_count=db_storyboard.shot_count or 0,
        total_duration=db_storyboard.total_duration or 0,
        status=db_storyboard.status or "draft",
        created_at=str(db_storyboard.created_at),
        updated_at=str(db_storyboard.updated_at)
    )


@router.delete("/{storyboard_id}")
async def delete_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    db_storyboard = result.scalar_one_or_none()
    
    if not db_storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    await db.delete(db_storyboard)
    await db.commit()
    
    return {"message": "分镜已删除"}
