"""
剧本管理 API 端点
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Boolean
from pydantic import BaseModel, Field

from app.core.database import get_db, Base
from app.core.security import get_current_user_id

router = APIRouter(tags=["剧本管理"])


# ============== 数据库模型 ==============

class Script(Base):
    """剧本模型"""
    __tablename__ = "scripts"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    novel_id = Column(String(36), ForeignKey("novels.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    content = Column(Text)  # 剧本正文
    genre = Column(String(50))
    style = Column(String(50))  # 风格：写实、浪漫、悬疑等
    duration = Column(Integer)  # 时长（分钟）
    status = Column(String(20), default="draft")  # draft, writing, completed
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============== Pydantic 模型 ==============

class ScriptCreate(BaseModel):
    """创建剧本"""
    novel_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    content: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    duration: Optional[int] = None


class ScriptUpdate(BaseModel):
    """更新剧本"""
    novel_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    duration: Optional[int] = None
    status: Optional[str] = None


class ScriptResponse(BaseModel):
    """剧本响应"""
    id: str
    user_id: str
    novel_id: Optional[str]
    title: str
    description: Optional[str]
    content: Optional[str]
    genre: Optional[str]
    style: Optional[str]
    duration: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime


# ============== 数据库初始化 ==============

async def init_scripts_table(db: AsyncSession):
    """确保表存在"""
    from sqlalchemy import text
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS scripts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            novel_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            content TEXT,
            genre TEXT,
            style TEXT,
            duration INTEGER,
            status TEXT DEFAULT 'draft',
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await db.commit()


# ============== API 端点 ==============

@router.get("", response_model=List[ScriptResponse])
async def list_scripts(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有剧本"""
    await init_scripts_table(db)
    
    result = await db.execute(
        select(Script)
        .where(Script.user_id == user_id)
        .order_by(desc(Script.updated_at))
    )
    scripts = result.scalars().all()
    
    return [
        ScriptResponse(
            id=s.id,
            user_id=s.user_id,
            novel_id=s.novel_id,
            title=s.title,
            description=s.description,
            content=s.content,
            genre=s.genre,
            style=s.style,
            duration=s.duration,
            status=s.status or "draft",
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        for s in scripts
    ]


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个剧本"""
    await init_scripts_table(db)
    
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()
    
    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    
    return ScriptResponse(
        id=script.id,
        user_id=script.user_id,
        novel_id=script.novel_id,
        title=script.title,
        description=script.description,
        content=script.content,
        genre=script.genre,
        style=script.style,
        duration=script.duration,
        status=script.status or "draft",
        created_at=script.created_at,
        updated_at=script.updated_at
    )


@router.post("", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    script: ScriptCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建剧本"""
    await init_scripts_table(db)
    
    db_script = Script(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=script.novel_id,
        title=script.title,
        description=script.description,
        content=script.content,
        genre=script.genre,
        style=script.style,
        duration=script.duration,
        status="draft"
    )
    db.add(db_script)
    await db.commit()
    await db.refresh(db_script)
    
    return ScriptResponse(
        id=db_script.id,
        user_id=db_script.user_id,
        novel_id=db_script.novel_id,
        title=db_script.title,
        description=db_script.description,
        content=db_script.content,
        genre=db_script.genre,
        style=db_script.style,
        duration=db_script.duration,
        status=db_script.status or "draft",
        created_at=db_script.created_at,
        updated_at=db_script.updated_at
    )


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    script_update: ScriptUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新剧本"""
    await init_scripts_table(db)
    
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    db_script = result.scalar_one_or_none()
    
    if not db_script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    
    # 更新字段
    update_data = script_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_script, key, value)
    
    await db.commit()
    await db.refresh(db_script)
    
    return ScriptResponse(
        id=db_script.id,
        user_id=db_script.user_id,
        novel_id=db_script.novel_id,
        title=db_script.title,
        description=db_script.description,
        content=db_script.content,
        genre=db_script.genre,
        style=db_script.style,
        duration=db_script.duration,
        status=db_script.status or "draft",
        created_at=db_script.created_at,
        updated_at=db_script.updated_at
    )


@router.delete("/{script_id}")
async def delete_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除剧本"""
    await init_scripts_table(db)
    
    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    db_script = result.scalar_one_or_none()
    
    if not db_script:
        raise HTTPException(status_code=404, detail="剧本不存在")
    
    await db.delete(db_script)
    await db.commit()
    
    return {"message": "剧本已删除"}
