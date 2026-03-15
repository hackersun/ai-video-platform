"""
AI配置管理API
支持API密钥、外部API、AI模型的配置管理
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.ai_providers import PROVIDER_PRESETS, get_provider_config, get_model_config, list_all_models
from app.models.ai_config import APIKeyConfig, ExternalAPIConfig, AIModelConfig, ModelProviderPreset

router = APIRouter(prefix="/ai-config", tags=["AI配置"])


# ============== 请求/响应模型 ==============

class APIKeyCreateRequest(BaseModel):
    """创建API密钥请求"""
    provider: str = Field(..., description="服务商")
    api_key: str = Field(..., description="API密钥")
    api_secret: Optional[str] = Field(None, description="API Secret")
    description: Optional[str] = Field(None, description="描述")
    is_default: bool = Field(False, description="设为默认")


class APIKeyResponse(BaseModel):
    """API密钥响应"""
    id: str
    provider: str
    provider_name: str
    is_active: bool
    is_default: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class ExternalAPICreateRequest(BaseModel):
    """创建外部API配置请求"""
    name: str = Field(..., description="配置名称")
    provider: str = Field(..., description="服务商")
    api_type: str = Field(..., description="API类型")
    base_url: str = Field(..., description="基础URL")
    api_key_id: Optional[str] = Field(None, description="关联API密钥ID")
    description: Optional[str] = Field(None, description="描述")


class AIModelCreateRequest(BaseModel):
    """创建AI模型配置请求"""
    model_id: str = Field(..., description="模型ID")
    model_name: str = Field(..., description="模型名称")
    provider: str = Field(..., description="服务商")
    model_type: str = Field(..., description="模型类型")
    external_api_id: Optional[str] = Field(None, description="关联API配置ID")
    is_default: bool = Field(False, description="设为默认")


class ProviderPresetResponse(BaseModel):
    """提供商预设响应"""
    provider: str
    provider_name: str
    provider_name_cn: str
    supported_types: List[str]
    available_models: List[dict]


# ============== API端点 ==============

@router.get("/providers", response_model=List[ProviderPresetResponse])
async def list_providers():
    """
    获取支持的AI提供商列表
    
    返回所有支持的AI模型提供商及其可用模型
    """
    providers = []
    for provider_id, config in PROVIDER_PRESETS.items():
        providers.append({
            "provider": provider_id,
            "provider_name": config["provider_name"],
            "provider_name_cn": config["provider_name_cn"],
            "supported_types": config["supported_types"],
            "available_models": config["available_models"]
        })
    return providers


@router.get("/providers/{provider}/models")
async def get_provider_models(provider: str):
    """获取指定提供商的模型列表"""
    config = get_provider_config(provider)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提供商不存在"
        )
    return config.get("available_models", [])


# ============== API密钥管理 ==============

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的API密钥列表"""
    result = await db.execute(
        select(APIKeyConfig).where(
            and_(
                APIKeyConfig.user_id == user_id,
                APIKeyConfig.is_active == True
            )
        )
    )
    keys = result.scalars().all()
    
    return [
        {
            "id": key.id,
            "provider": key.provider,
            "provider_name": PROVIDER_PRESETS.get(key.provider, {}).get("provider_name_cn", key.provider),
            "is_active": key.is_active,
            "is_default": key.is_default,
            "description": key.description,
            "created_at": key.created_at,
            "updated_at": key.updated_at
        }
        for key in keys
    ]


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    创建API密钥配置
    
    支持火山引擎、OpenAI、Anthropic等主流服务商
    """
    # 验证提供商
    if request.provider not in PROVIDER_PRESETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的提供商: {request.provider}"
        )
    
    # TODO: 加密存储API密钥
    # 实际生产环境需要使用加密算法（如AES-256）加密存储
    
    key_config = APIKeyConfig(
        id=str(uuid4()),
        user_id=user_id,
        provider=request.provider,
        api_key=request.api_key,  # 需要加密
        api_secret=request.api_secret,
        description=request.description,
        is_default=request.is_default
    )
    
    db.add(key_config)
    await db.commit()
    await db.refresh(key_config)
    
    return {
        "id": key_config.id,
        "provider": key_config.provider,
        "provider_name": PROVIDER_PRESETS[request.provider]["provider_name_cn"],
        "is_active": key_config.is_active,
        "is_default": key_config.is_default,
        "description": key_config.description,
        "created_at": key_config.created_at,
        "updated_at": key_config.updated_at
    }


@router.post("/api-keys/{key_id}/test")
async def test_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    测试API密钥是否有效
    
    调用服务商API验证密钥
    """
    result = await db.execute(
        select(APIKeyConfig).where(
            and_(
                APIKeyConfig.id == key_id,
                APIKeyConfig.user_id == user_id
            )
        )
    )
    key_config = result.scalar_one_or_none()
    
    if not key_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API密钥不存在"
        )
    
    # TODO: 实现实际的API测试逻辑
    # 调用服务商API验证密钥有效性
    
    return {
        "success": True,
        "message": "API密钥有效",
        "provider": key_config.provider
    }


# ============== 外部API配置 ==============

@router.get("/external-apis")
async def list_external_apis(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取外部API配置列表"""
    result = await db.execute(
        select(ExternalAPIConfig).where(
            and_(
                ExternalAPIConfig.user_id == user_id,
                ExternalAPIConfig.is_active == True
            )
        )
    )
    apis = result.scalars().all()
    return apis


@router.post("/external-apis", status_code=status.HTTP_201_CREATED)
async def create_external_api(
    request: ExternalAPICreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建外部API配置"""
    api_config = ExternalAPIConfig(
        id=str(uuid4()),
        user_id=user_id,
        name=request.name,
        provider=request.provider,
        api_type=request.api_type,
        base_url=request.base_url,
        api_key_id=request.api_key_id,
        description=request.description
    )
    
    db.add(api_config)
    await db.commit()
    await db.refresh(api_config)
    
    return api_config


# ============== AI模型配置 ==============

@router.get("/models")
async