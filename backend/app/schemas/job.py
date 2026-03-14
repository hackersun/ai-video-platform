"""
任务队列数据模型（Pydantic）
用于API请求和响应的数据验证
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class JobBase(BaseModel):
    """任务基础模型"""
    type: str = Field(..., description="任务类型: video_generation, image_generation, tts, script_generation")
    input_params: Dict[str, Any] = Field(default_factory=dict, description="输入参数")
    
    model_config = ConfigDict(from_attributes=True)


class JobCreate(JobBase):
    """创建任务模型"""
    model_config = ConfigDict(from_attributes=True)


class JobResponse(JobBase):
    """任务响应模型"""
    id: str
    status: str = Field(..., description="任务状态: pending, processing, completed, failed, cancelled")
    output_url: Optional[str] = Field(None, description="输出结果URL")
    error_message: Optional[str] = Field(None, description="错误信息")
    progress: int = Field(0, ge=0, le=100, description="进度百分比")
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    user_id: str
    
    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """任务列表响应"""
    items: List[JobResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


class JobStats(BaseModel):
    """任务统计"""
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    cancelled: int
    
    model_config = ConfigDict(from_attributes=True)


class JobStatus:
    """任务状态常量"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType:
    """任务类型常量"""
    VIDEO_GENERATION = "video_generation"
    IMAGE_GENERATION = "image_generation"
    TTS = "tts"
    SCRIPT_GENERATION = "script_generation"
    MUSIC_GENERATION = "music_generation"
    STORYBOARD_GENERATION = "storyboard_generation"
