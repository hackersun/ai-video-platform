"""
小说管理 API 端点
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON
from pydantic import BaseModel, Field

from app.core.database import get_db, Base
from app.core.security import get_current_user_id

router = APIRouter(tags=["小说管理"])


# ============== 数据库模型 ==============

class Novel(Base):
    """小说模型"""
    __tablename__ = "novels"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    genre = Column(String(50))  # 玄幻、都市、仙侠等
    status = Column(String(20), default="draft")  # draft, writing, completed
    word_count = Column(Integer, default=0)
    tags = Column(JSON, default=list)
    cover_url = Column(String(500))
    source = Column(String(20), default="manual")  # manual, ai_generated
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============== Pydantic 模型 ==============

class NovelCreate(BaseModel):
    """创建小说"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    genre: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    cover_url: Optional[str] = None


class NovelUpdate(BaseModel):
    """更新小说"""
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    word_count: Optional[int] = None
    tags: Optional[List[str]] = None
    cover_url: Optional[str] = None


class NovelResponse(BaseModel):
    """小说响应"""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    genre: Optional[str]
    status: str
    word_count: int
    tags: List[str]
    cover_url: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime


# ============== 数据库初始化 ==============

async def init_novels_table(db: AsyncSession):
    """确保表存在"""
    from sqlalchemy import text
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS novels (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            genre TEXT,
            status TEXT DEFAULT 'draft',
            word_count INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            cover_url TEXT,
            source TEXT DEFAULT 'manual',
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await db.commit()


# ============== API 端点 ==============

@router.get("", response_model=List[NovelResponse])
async def list_novels(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有小说"""
    await init_novels_table(db)
    
    result = await db.execute(
        select(Novel)
        .where(Novel.user_id == user_id)
        .order_by(desc(Novel.updated_at))
    )
    novels = result.scalars().all()
    
    return [
        NovelResponse(
            id=n.id,
            user_id=n.user_id,
            title=n.title,
            description=n.description,
            genre=n.genre,
            status=n.status or "draft",
            word_count=n.word_count or 0,
            tags=n.tags or [],
            cover_url=n.cover_url,
            source=n.source or "manual",
            created_at=n.created_at,
            updated_at=n.updated_at
        )
        for n in novels
    ]


@router.get("/{novel_id}", response_model=NovelResponse)
async def get_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个小说"""
    await init_novels_table(db)
    
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    
    return NovelResponse(
        id=novel.id,
        user_id=novel.user_id,
        title=novel.title,
        description=novel.description,
        genre=novel.genre,
        status=novel.status or "draft",
        word_count=novel.word_count or 0,
        tags=novel.tags or [],
        cover_url=novel.cover_url,
        source=novel.source or "manual",
        created_at=novel.created_at,
        updated_at=novel.updated_at
    )


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
async def create_novel(
    novel: NovelCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建小说"""
    await init_novels_table(db)
    
    db_novel = Novel(
        id=str(uuid4()),
        user_id=user_id,
        title=novel.title,
        description=novel.description,
        genre=novel.genre,
        tags=novel.tags or [],
        cover_url=novel.cover_url,
        status="draft"
    )
    db.add(db_novel)
    await db.commit()
    await db.refresh(db_novel)
    
    return NovelResponse(
        id=db_novel.id,
        user_id=db_novel.user_id,
        title=db_novel.title,
        description=db_novel.description,
        genre=db_novel.genre,
        status=db_novel.status or "draft",
        word_count=db_novel.word_count or 0,
        tags=db_novel.tags or [],
        cover_url=db_novel.cover_url,
        source=db_novel.source or "manual",
        created_at=db_novel.created_at,
        updated_at=db_novel.updated_at
    )


@router.put("/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: str,
    novel_update: NovelUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新小说"""
    await init_novels_table(db)
    
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    db_novel = result.scalar_one_or_none()
    
    if not db_novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    
    # 更新字段
    update_data = novel_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_novel, key, value)
    
    await db.commit()
    await db.refresh(db_novel)
    
    return NovelResponse(
        id=db_novel.id,
        user_id=db_novel.user_id,
        title=db_novel.title,
        description=db_novel.description,
        genre=db_novel.genre,
        status=db_novel.status or "draft",
        word_count=db_novel.word_count or 0,
        tags=db_novel.tags or [],
        cover_url=db_novel.cover_url,
        source=db_novel.source or "manual",
        created_at=db_novel.created_at,
        updated_at=db_novel.updated_at
    )


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除小说"""
    await init_novels_table(db)
    
    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    db_novel = result.scalar_one_or_none()
    
    if not db_novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    
    await db.delete(db_novel)
    await db.commit()
    
    return {"message": "小说已删除"}
