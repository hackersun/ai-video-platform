"""
剧本数据模型（Pydantic）
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ==================== 基础模型 ====================

class ScriptBase(BaseModel):
    """剧本基础模型"""
    title: str = Field(..., min_length=1, max_length=255)
    format: str = Field("standard", pattern="^(standard|screenplay)$")
    
    model_config = ConfigDict(from_attributes=True)


class ScriptCreate(ScriptBase):
    """剧本创建模型"""
    novel_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None
    content: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)


class ScriptUpdate(BaseModel):
    """剧本更新模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[Dict[str, Any]] = None
    format: Optional[str] = Field(None, pattern="^(standard|screenplay)$")
    status: Optional[str] = Field(None, pattern="^(draft|published|generating)$")
    
    model_config = ConfigDict(from_attributes=True)


class ScriptResponse(ScriptBase):
    """剧本响应模型"""
    id: UUID
    novel_id: Optional[UUID]
    chapter_id: Optional[UUID]
    status: str
    ai_generated: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ScriptDetail(ScriptResponse):
    """剧本详情"""
    content: Optional[Dict[str, Any]]
    scenes: List["SceneResponse"] = []
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 场景模型 ====================

class SceneBase(BaseModel):
    """场景基础模型"""
    scene_number: int = Field(..., ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)
    time_of_day: Optional[str] = Field(None, max_length=50)
    characters: Optional[List[UUID]] = None
    props: Optional[List[str]] = None
    action_description: Optional[str] = None
    camera_direction: Optional[str] = None
    dialogue: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)


class SceneCreate(SceneBase):
    """场景创建模型"""
    model_config = ConfigDict(from_attributes=True)


class SceneUpdate(BaseModel):
    """场景更新模型"""
    scene_number: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)
    time_of_day: Optional[str] = Field(None, max_length=50)
    characters: Optional[List[UUID]] = None
    props: Optional[List[str]] = None
    action_description: Optional[str] = None
    camera_direction: Optional[str] = None
    dialogue: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)


class SceneResponse(SceneBase):
    """场景响应模型"""
    id: UUID
    script_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SceneDetail(SceneResponse):
    """场景详情"""
    generated_images: Optional[List[str]] = None
    generated_video: Optional[str] = None
    generated_audio: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 列表和分页模型 ====================

class ScriptListResponse(BaseModel):
    """剧本列表响应"""
    items: List[ScriptResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


class SceneListResponse(BaseModel):
    """场景列表响应"""
    items: List[SceneResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


# ==================== AI生成相关 ====================

class ScriptGenerateRequest(BaseModel):
    """剧本生成请求"""
    novel_id: UUID
    chapter_id: Optional[UUID] = None
    style: str = Field("standard", pattern="^(standard|cinematic|dramatic|comedy)$")
    scene_count: int = Field(5, ge=1, le=20)
    include_dialogue: bool = True
    include_camera_directions: bool = True
    
    model_config = ConfigDict(from_attributes=True)


class SceneGenerateRequest(BaseModel):
    """场景生成请求"""
    script_id: UUID
    scene_number: int
    description: str
    characters: List[UUID]
    location: str
    time_of_day: str
    
    model_config = ConfigDict(from_attributes=True)


class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    scene_id: UUID
    style: str = Field("anime", pattern="^(anime|realistic|3d|pixel)$")
    duration: int = Field(5, ge=3, le=10)
    include_audio: bool = True
    
    model_config = ConfigDict(from_attributes=True)


class GenerationResult(BaseModel):
    """生成结果"""
    task_id: str
    status: str
    progress: int
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
