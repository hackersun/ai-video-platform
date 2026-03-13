"""
AI模型配置Pydantic Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class AIModelBase(BaseModel):
    """AI模型基础配置"""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    provider: str = Field(..., max_length=50)
    category: str = Field(..., max_length=50)
    model_id: Optional[str] = Field(None, max_length=100)
    version: Optional[str] = Field(None, max_length=20)
    capabilities: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    input_price: float = Field(0, ge=0)
    output_price: float = Field(0, ge=0)
    supported_params: Optional[Dict[str, Any]] = None
    default_params: Optional[Dict[str, Any]] = None
    status: str = Field("active", pattern="^(active|inactive|maintenance|beta)$")
    is_default: bool = False
    base_url: Optional[str] = Field(None, max_length=500)
    rate_limit_rpm: int = Field(60, ge=1)
    rate_limit_tpm: int = Field(150000, ge=1)
    concurrent_limit: int = Field(10, ge=1)
    icon_url: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(from_attributes=True)


class AIModelCreate(AIModelBase):
    """AI模型创建"""

    pass


class AIModelUpdate(BaseModel):
    """AI模型更新"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    model_id: Optional[str] = Field(None, max_length=100)
    version: Optional[str] = Field(None, max_length=20)
    capabilities: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    input_price: Optional[float] = Field(None, ge=0)
    output_price: Optional[float] = Field(None, ge=0)
    supported_params: Optional[Dict[str, Any]] = None
    default_params: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|maintenance|beta)$")
    is_default: Optional[bool] = None
    base_url: Optional[str] = Field(None, max_length=500)
    rate_limit_rpm: Optional[int] = Field(None, ge=1)
    rate_limit_tpm: Optional[int] = Field(None, ge=1)
    concurrent_limit: Optional[int] = Field(None, ge=1)
    icon_url: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(from_attributes=True)


class AIModelResponse(AIModelBase):
    """AI模型响应"""

    id: UUID
    api_key_env: Optional[str] = None
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIModelListResponse(BaseModel):
    """AI模型列表响应"""

    items: List[AIModelResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ModelConfigBase(BaseModel):
    """用户/团队模型配置基础"""

    model_id: UUID
    is_enabled: bool = True
    priority: int = Field(0, ge=0)
    custom_params: Optional[Dict[str, Any]] = None
    custom_prompts: Optional[Dict[str, Any]] = None
    daily_limit: int = Field(0, ge=0)
    monthly_limit: int = Field(0, ge=0)

    model_config = ConfigDict(from_attributes=True)


class ModelConfigCreate(ModelConfigBase):
    """用户模型配置创建"""

    pass


class ModelConfigUpdate(BaseModel):
    """用户模型配置更新"""

    is_enabled: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0)
    custom_params: Optional[Dict[str, Any]] = None
    custom_prompts: Optional[Dict[str, Any]] = None
    daily_limit: Optional[int] = Field(None, ge=0)
    monthly_limit: Optional[int] = Field(None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class ModelConfigResponse(ModelConfigBase):
    """用户模型配置响应"""

    id: UUID
    user_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    today_usage: int = 0
    month_usage: int = 0
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelConfigListResponse(BaseModel):
    """用户模型配置列表响应"""

    items: List[ModelConfigResponse]
    total: int


class ProviderAPIKeyUpdate(BaseModel):
    """提供商API Key更新"""

    api_key: str = Field(..., min_length=1)

    model_config = ConfigDict(from_attributes=True)


class TestConnectionRequest(BaseModel):
    """测试连接请求"""

    model_id: UUID
    api_key: Optional[str] = None


class TestConnectionResponse(BaseModel):
    """测试连接响应"""

    success: bool
    latency_ms: Optional[int] = None
    message: str
    error: Optional[str] = None


class CostSettingsBase(BaseModel):
    """成本设置基础"""

    routing_strategy: str = Field(
        "balanced", pattern="^(balanced|quality_first|cost_first|speed_first)$"
    )
    daily_budget: float = Field(0, ge=0)
    monthly_budget: float = Field(0, ge=0)
    alert_threshold: float = Field(0.8, ge=0, le=1)
    auto_failover: bool = True
    fallback_to_free: bool = True

    model_config = ConfigDict(from_attributes=True)


class CostSettingsCreate(CostSettingsBase):
    """成本设置创建"""

    pass


class CostSettingsUpdate(BaseModel):
    """成本设置更新"""

    routing_strategy: Optional[str] = Field(
        None, pattern="^(balanced|quality_first|cost_first|speed_first)$"
    )
    daily_budget: Optional[float] = Field(None, ge=0)
    monthly_budget: Optional[float] = Field(None, ge=0)
    alert_threshold: Optional[float] = Field(None, ge=0, le=1)
    auto_failover: Optional[bool] = None
    fallback_to_free: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class CostSettingsResponse(CostSettingsBase):
    """成本设置响应"""

    id: UUID
    user_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsageLogResponse(BaseModel):
    """使用日志响应"""

    id: UUID
    user_id: UUID
    team_id: Optional[UUID] = None
    model_id: UUID
    config_id: Optional[UUID] = None
    request_type: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0
    status: str
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsageStatsResponse(BaseModel):
    """使用统计响应"""

    total_requests: int
    total_tokens: int
    total_cost: float
    by_category: Dict[str, Dict[str, Any]]
    by_provider: Dict[str, Dict[str, Any]]


class CategoryInfo(BaseModel):
    """模型分类信息"""

    id: str
    name: str
    icon: str
    description: str


class ProviderInfo(BaseModel):
    """提供商信息"""

    id: str
    name: str
    logo: Optional[str] = None
    models_count: int = 0


class ModelCategoriesResponse(BaseModel):
    """模型分类响应"""

    categories: List[CategoryInfo]
    providers: List[ProviderInfo]
