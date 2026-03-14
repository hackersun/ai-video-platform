"""
分镜数据模型（Pydantic）
用于API请求和响应的数据验证
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class StoryboardBase(BaseModel):
    """分镜基础模型"""
    title: str = Field(..., min_length=1, max_length=200, description="分镜标题")
    script_id: str = Field(..., description="关联剧本ID")
    scene_id: Optional[str] = Field(None, description="关联场景ID")
    description: Optional[str] = Field(None, max_length=1000, description="分镜描述")
    
    model_config = ConfigDict(from_attributes=True)


class StoryboardCreate(StoryboardBase):
    """创建分镜模型"""
    model_config = ConfigDict(from_attributes=True)


class StoryboardResponse(StoryboardBase):
    """分镜响应模型"""
    id: str
    status: str = Field(..., description="分镜状态: draft, in_progress, completed")
    shot_count: int = Field(0, description="镜头数量")
    created_at: datetime
    updated_at: datetime
    user_id: str
    
    model_config = ConfigDict(from_attributes=True)


class StoryboardListResponse(BaseModel):
    """分镜列表响应"""
    items: List[StoryboardResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 镜头(Shot)模型 ====================

class ShotBase(BaseModel):
    """镜头基础模型"""
    title: str = Field(..., min_length=1, max_length=200, description="镜头标题")
    description: Optional[str] = Field(None, max_length=1000, description="镜头描述")
    prompt: str = Field(..., min_length=1, description="AI生成提示词")
    negative_prompt: Optional[str] = Field(None, description="负面提示词")
    camera_movement: str = Field("static", description="镜头运动: static, pan, tilt, zoom, dolly, truck")
    camera_angle: str = Field("eye_level", description="镜头角度: eye_level, high_angle, low_angle, bird_eye, worm_eye")
    shot_type: str = Field("medium_shot", description="镜头类型: extreme_close_up, close_up, medium_shot, full_shot, wide_shot")
    duration: int = Field(5, ge=1, le=60, description="镜头时长(秒)")
    sequence_number: int = Field(..., ge=1, description="镜头顺序")
    characters: List[str] = Field(default_factory=list, description="出场角色")
    location: Optional[str] = Field(None, description="拍摄地点")
    time_of_day: Optional[str] = Field(None, description="时间: morning, afternoon, evening, night")
    dialogue: Optional[str] = Field(None, description="对白内容")
    notes: Optional[str] = Field(None, description="备注")
    
    model_config = ConfigDict(from_attributes=True)


class ShotCreate(ShotBase):
    """创建镜头模型"""
    model_config = ConfigDict(from_attributes=True)


class ShotResponse(ShotBase):
    """镜头响应模型"""
    id: str
    storyboard_id: str
    image_url: Optional[str] = Field(None, description="生成的图片URL")
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ShotListResponse(BaseModel):
    """镜头列表响应"""
    items: List[ShotResponse]
    total: int
    page: int
    page_size: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 导出选项 ====================

class StoryboardExportOptions(BaseModel):
    """分镜导出选项"""
    format: str = Field(..., description="导出格式: pdf, images, both")
    include_prompt: bool = Field(True, description="是否包含提示词")
    include_camera_info: bool = Field(True, description="是否包含镜头信息")
    image_quality: str = Field("medium", description="图片质量: low, medium, high")
    
    model_config = ConfigDict(from_attributes=True)


# ==================== AI生成相关 ====================

class ShotGenerationRequest(BaseModel):
    """镜头生成请求"""
    scene_description: str = Field(..., description="场景描述")
    num_shots: int = Field(5, ge=1, le=20, description="生成镜头数量")
    style: Optional[str] = Field("anime", description="画面风格")
    aspect_ratio: Optional[str] = Field("16:9", description="画面比例")
    include_camera_movement: bool = Field(True, description="是否包含镜头运动")
    
    model_config = ConfigDict(from_attributes=True)


class PromptConversionRequest(BaseModel):
    """提示词转换请求"""
    scene_description: str = Field(..., description="场景描述")
    camera_movement: Optional[str] = Field(None, description="镜头运动")
    camera_angle: Optional[str] = Field(None, description="镜头角度")
    shot_type: Optional[str] = Field(None, description="镜头类型")
    style: Optional[str] = Field("anime", description="画面风格")
    
    model_config = ConfigDict(from_attributes=True)
