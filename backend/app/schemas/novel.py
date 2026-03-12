"""
小说数据模型（Pydantic）
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ==================== 基础模型 ====================

class NovelBase(BaseModel):
    """小说基础模型"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    genre: Optional[str] = Field(None, max_length=50)
    cover_image: Optional[str] = Field(None, max_length=500)
    
    model_config = ConfigDict(from_attributes=True)


class NovelCreate(NovelBase):
    """小说创建模型"""
    model_config = ConfigDict(from_attributes=True)


class NovelUpdate(BaseModel):
    """小说更新模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    genre: Optional[str] = Field(None, max_length=50)
    cover_image: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, pattern="^(draft|published|archived)$")
    
    model_config = ConfigDict(from_attributes=True)


class NovelInDB(NovelBase):
    """数据库中的小说模型"""
    id: UUID
    author_id: UUID
    status: str = "draft"
    word_count: int = 0
    ai_generated: bool = False
    ai_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class NovelResponse(NovelBase):
    """小说响应模型"""
    id: UUID
    author_id: UUID
    status: str
    word_count: int
    cover_image: Optional[str]
    ai_generated: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class NovelDetail(NovelResponse):
    """小说详情（包含章节）"""
    chapter_count: int = 0
    chapters: List[dict] = []  # 简化，避免循环引用
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 章节模型 ====================

class ChapterBase(BaseModel):
    """章节基础模型"""
    title: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    chapter_number: int = Field(..., ge=1)
    
    model_config = ConfigDict(from_attributes=True)


class ChapterCreate(ChapterBase):
    """章节创建模型"""
    model_config = ConfigDict(from_attributes=True)


class ChapterUpdate(BaseModel):
    """章节更新模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    chapter_number: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, pattern="^(draft|published)$")
    
    model_config = ConfigDict(from_attributes=True)


class ChapterResponse(ChapterBase):
    """章节响应模型"""
    id: UUID
    novel_id: UUID
    status: str
    word_count: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ChapterDetail(ChapterResponse):
    """章节详情"""
    scripts: List[dict] = []  # 简化，避免循环引用
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 列表和分页模型 ====================

class NovelListResponse(BaseModel):
    """小说列表响应"""
    items: List[NovelResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


class ChapterListResponse(BaseModel):
    """章节列表响应"""
    items: List[ChapterResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


# ==================== AI生成相关 ====================

class NovelGenerateRequest(BaseModel):
    """小说生成请求"""
    prompt: str = Field(..., min_length=10, max_length=2000)
    genre: Optional[str] = None
    word_count: int = Field(5000, ge=500, le=50000)
    style: Optional[str] = "modern"
    
    model_config = ConfigDict(from_attributes=True)


class ChapterGenerateRequest(BaseModel):
    """章节生成请求"""
    novel_id: UUID
    chapter_number: int
    prompt: Optional[str] = None
    previous_chapter_id: Optional[UUID] = None
    
    model_config = ConfigDict(from_attributes=True)


class GenerationStatus(BaseModel):
    """生成状态"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# 重建模型以解决前向引用问题
NovelDetail.model_rebuild()
ChapterDetail.model_rebuild()
