"""
章节管理 API 端点
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

router = APIRouter(tags=["章节管理"])


# ============== 数据库模型 ==============

class Chapter(Base):
    """章节模型"""
    __tablename__ = "chapters"
    
    id = Column(String(36), primary_key=True)
    novel_id = Column(String(36), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    chapter_number = Column(Integer, nullable=False, default=1)
    word_count = Column(Integer, default=0)
    status = Column(String(20), default="draft")  # draft, writing, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============== Pydantic 模型 ==============

class ChapterCreate(BaseModel):
    """创建章节请求"""
    novel_id: str = Field(..., description="所属小说ID")
    title: str = Field(..., min_length=1, max_length=200, description="章节标题")
    content: Optional[str] = Field(None, description="章节内容")
    chapter_number: Optional[int] = Field(1, description="章节序号")


class ChapterUpdate(BaseModel):
    """更新章节请求"""
    title: Optional[str] = None
    content: Optional[str] = None
    chapter_number: Optional[int] = None
    status: Optional[str] = None


class ChapterResponse(BaseModel):
    """章节响应"""
    id: str
    novel_id: str
    user_id: str
    title: str
    content: Optional[str] = None
    chapter_number: int
    word_count: int
    status: str
    created_at: str
    updated_at: str


# ============== API 端点 ==============

@router.get("/novel/{novel_id}", response_model=List[ChapterResponse])
async def list_chapters_by_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取指定小说的所有章节"""
    result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()
    
    return [
        ChapterResponse(
            id=str(c.id),
            novel_id=str(c.novel_id),
            user_id=str(c.user_id),
            title=c.title,
            content=c.content,
            chapter_number=c.chapter_number or 1,
            word_count=c.word_count or 0,
            status=c.status or "draft",
            created_at=str(c.created_at),
            updated_at=str(c.updated_at)
        )
        for c in chapters
    ]


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个章节"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    
    return ChapterResponse(
        id=str(chapter.id),
        novel_id=str(chapter.novel_id),
        user_id=str(chapter.user_id),
        title=chapter.title,
        content=chapter.content,
        chapter_number=chapter.chapter_number or 1,
        word_count=chapter.word_count or 0,
        status=chapter.status or "draft",
        created_at=str(chapter.created_at),
        updated_at=str(chapter.updated_at)
    )


@router.post("", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    chapter: ChapterCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建章节"""
    chapter_id = str(uuid.uuid4())
    
    # 计算字数
    word_count = len(chapter.content or "")
    
    db_chapter = Chapter(
        id=chapter_id,
        novel_id=chapter.novel_id,
        user_id=user_id,
        title=chapter.title,
        content=chapter.content,
        chapter_number=chapter.chapter_number or 1,
        word_count=word_count,
        status="draft"
    )
    
    db.add(db_chapter)
    await db.commit()
    await db.refresh(db_chapter)
    
    return ChapterResponse(
        id=str(db_chapter.id),
        novel_id=str(db_chapter.novel_id),
        user_id=str(db_chapter.user_id),
        title=db_chapter.title,
        content=db_chapter.content,
        chapter_number=db_chapter.chapter_number or 1,
        word_count=db_chapter.word_count or 0,
        status=db_chapter.status or "draft",
        created_at=str(db_chapter.created_at),
        updated_at=str(db_chapter.updated_at)
    )


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: str,
    chapter_update: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新章节"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    db_chapter = result.scalar_one_or_none()
    
    if not db_chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    
    # 更新字段
    update_data = chapter_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "content" and value:
            setattr(db_chapter, "word_count", len(value))
        else:
            setattr(db_chapter, key, value)
    
    await db.commit()
    await db.refresh(db_chapter)
    
    return ChapterResponse(
        id=str(db_chapter.id),
        novel_id=str(db_chapter.novel_id),
        user_id=str(db_chapter.user_id),
        title=db_chapter.title,
        content=db_chapter.content,
        chapter_number=db_chapter.chapter_number or 1,
        word_count=db_chapter.word_count or 0,
        status=db_chapter.status or "draft",
        created_at=str(db_chapter.created_at),
        updated_at=str(db_chapter.updated_at)
    )


@router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除章节"""
    result = await db.execute(
        select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id))
    )
    db_chapter = result.scalar_one_or_none()
    
    if not db_chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    
    await db.delete(db_chapter)
    await db.commit()
    
    return {"message": "章节已删除"}
