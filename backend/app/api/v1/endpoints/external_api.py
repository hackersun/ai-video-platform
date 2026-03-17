"""
外部API管理端点
支持Midjourney、Runway、Suno、阿里千问等
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.qwen_config import QWEN_MODELS, get_qwen_model, calculate_cost
from app.models.external_api import ExternalAPIProvider, ExternalAPIConfig, ExternalAPIUsageLog

router = APIRouter(tags=["外部API"])


# ============== 请求/响应模型 ==============

class ExternalAPIProviderResponse(BaseModel):
    """提供商响应"""
    id: str
    name: str
    name_cn: Optional[str]
    api_type: str
    base_url: str
    is_active: bool
    description: Optional[str]
    supported_models: List[dict]


class ExternalAPIConfigCreateRequest(BaseModel):
    """创建配置请求"""
    provider_id: str = Field(..., description="提供商ID")
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    api_key: str = Field(..., description="API密钥")
    api_secret: Optional[str] = Field(None, description="API Secret")
    custom_base_url: Optional[str] = Field(None, description="自定义基础URL")
    description: Optional[str] = Field(None, description="描述")
    is_default: bool = Field(False, description="设为默认")


class ExternalAPIConfigResponse(BaseModel):
    """配置响应"""
    id: str
    provider_id: str
    provider_name: str
    name: str
    api_type: str
    is_active: bool
    is_default: bool
    test_status: Optional[str]
    usage_count: int
    created_at: datetime


class QwenModelResponse(BaseModel):
    """千问模型响应"""
    id: str
    name: str
    name_cn: str
    type: str
    capabilities: List[str]
    context_window: int
    max_tokens: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    description: str
    use_case: str


class QwenChatRequest(BaseModel):
    """千问对话请求"""
    model: str = Field("qwen-plus", description="模型ID")
    messages: List[dict] = Field(..., description="对话消息")
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1, le=8192)
    stream: bool = Field(False, description="是否流式输出")


class QwenChatResponse(BaseModel):
    """千问对话响应"""
    content: str
    model: str
    usage: dict
    cost: float


# ============== 预设数据 ==============

DEFAULT_PROVIDERS = [
    {
        "id": "midjourney",
        "name": "midjourney",
        "name_cn": "Midjourney",
        "api_type": "image",
        "base_url": "https://api.imagineapi.com/v1",
        "auth_type": "bearer",
        "description": "高质量AI图像生成",
        "supported_models": [{"id": "midjourney-v6", "name": "Midjourney V6"}]
    },
    {
        "id": "runway",
        "name": "runway",
        "name_cn": "Runway",
        "api_type": "video",
        "base_url": "https://api.runwayml.com/v1",
        "auth_type": "bearer",
        "description": "AI视频生成",
        "supported_models": [{"id": "gen-3", "name": "Gen-3 Alpha"}]
    },
    {
        "id": "suno",
        "name": "suno",
        "name_cn": "Suno",
        "api_type": "audio",
        "base_url": "https://api.suno.ai/v1",
        "auth_type": "bearer",
        "description": "AI音乐生成",
        "supported_models": [{"id": "suno-v3", "name": "Suno V3"}]
    },
    {
        "id": "qwen",
        "name": "qwen",
        "name_cn": "阿里千问",
        "api_type": "text",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "auth_type": "bearer",
        "description": "阿里通义千问大模型",
        "supported_models": [{"id": m["id"], "name": m["name_cn"]} for m in QWEN_MODELS]
    }
]


# ============== API端点 ==============

@router.get("/providers", response_model=List[ExternalAPIProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db)
):
    """获取外部API提供商列表"""
    result = await db.execute(
        select(ExternalAPIProvider).where(ExternalAPIProvider.is_active == True)
    )
    providers = result.scalars().all()
    
    if not providers:
        # 初始化预设数据
        for provider_data in DEFAULT_PROVIDERS:
            provider = ExternalAPIProvider(**provider_data)
            db.add(provider)
        await db.commit()
        
        # 重新查询
        result = await db.execute(
            select(ExternalAPIProvider).where(ExternalAPIProvider.is_active == True)
        )
        providers = result.scalars().all()
    
    return providers


@router.get("/qwen/models", response_model=List[QwenModelResponse])
async def list_qwen_models():
    """获取阿里千问模型列表"""
    return QWEN_MODELS


@router.get("/configs", response_model=List[ExternalAPIConfigResponse])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的外部API配置列表"""
    result = await db.execute(
        select(ExternalAPIConfig, ExternalAPIProvider)
        .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
        .where(
            and_(
                ExternalAPIConfig.user_id == user_id,
                ExternalAPIConfig.is_active == True
            )
        )
        .order_by(desc(ExternalAPIConfig.is_default), desc(ExternalAPIConfig.created_at))
    )
    
    configs = []
    for row in result.all():
        config, provider = row
        configs.append({
            "id": config.id,
            "provider_id": config.provider_id,
            "provider_name": provider.name_cn or provider.name,
            "name": config.name,
            "api_type": provider.api_type,
            "is_active": config.is_active,
            "is_default": config.is_default,
            "test_status": config.test_status,
            "usage_count": config.usage_count,
            "created_at": config.created_at
        })
    
    return configs


@router.post("/configs", response_model=ExternalAPIConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    request: ExternalAPIConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建外部API配置"""
    # 验证提供商
    result = await db.execute(
        select(ExternalAPIProvider).where(ExternalAPIProvider.id == request.provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提供商不存在"
        )
    
    # 如果设为默认，取消其他默认配置
    if request.is_default:
        await db.execute(
            select(ExternalAPIConfig)
            .where(and_(ExternalAPIConfig.user_id == user_id, ExternalAPIConfig.is_default == True))
            .update({"is_default": False})
        )
    
    # TODO: 加密存储API密钥
    config = ExternalAPIConfig(
        id=str(uuid4()),
        user_id=user_id,
        provider_id=request.provider_id,
        name=request.name,
        api_key=request.api_key,
        api_secret=request.api_secret,
        custom_base_url=request.custom_base_url,
        description=request.description,
        is_default=request.is_default,
        test_status="pending"
    )
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    return {
        "id": config.id,
        "provider_id": config.provider_id,
        "provider_name": provider.name_cn or provider.name,
        "name": config.name,
        "api_type": provider.api_type,
        "is_active": config.is_active,
        "is_default": config.is_default,
        "test_status": config.test_status,
        "created_at": config.created_at
    }
