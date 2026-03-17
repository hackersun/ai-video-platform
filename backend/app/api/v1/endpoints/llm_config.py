"""
大模型配置API
支持多模型接入配置管理
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
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig, LLMUsageLog

router = APIRouter(tags=["大模型配置"])


# ============== 请求/响应模型 ==============

class LLMProviderResponse(BaseModel):
    """提供商响应"""
    id: str
    name: str
    name_cn: str
    name_en: str
    provider_type: str
    base_url: str
    is_active: bool
    description: Optional[str]
    icon_url: Optional[str]


class LLMModelResponse(BaseModel):
    """模型响应"""
    id: str
    provider_id: str
    model_id: str
    model_name: str
    model_name_cn: Optional[str]
    model_type: str
    capabilities: List[str]
    context_window: int
    max_tokens: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    is_active: bool
    is_recommended: bool
    description: Optional[str]


class LLMConfigCreateRequest(BaseModel):
    """创建配置请求"""
    model_id: str = Field(..., description="模型ID")
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    api_key: str = Field(..., description="API密钥")
    api_secret: Optional[str] = Field(None, description="API Secret")
    temperature: float = Field(0.7, ge=0, le=2)
    top_p: float = Field(0.9, ge=0, le=1)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    extra_params: Optional[dict] = Field({}, description="额外参数")
    is_default: bool = Field(False, description="设为默认")


class LLMConfigResponse(BaseModel):
    """配置响应"""
    id: str
    user_id: str
    model_id: str
    model_name: str
    provider_name: str
    name: str
    temperature: float
    top_p: float
    max_tokens: Optional[int]
    is_active: bool
    is_default: bool
    test_status: Optional[str]
    test_message: Optional[str]
    usage_count: int
    created_at: datetime
    updated_at: datetime


class LLMTestRequest(BaseModel):
    """测试请求"""
    message: str = Field("你好，请介绍一下自己", description="测试消息")


class LLMTestResponse(BaseModel):
    """测试响应"""
    success: bool
    message: str
    response: Optional[str]
    response_time_ms: Optional[int]
    tokens_used: Optional[int]


# ============== 预设数据 ==============

DEFAULT_PROVIDERS = [
    {
        "id": "volcano",
        "name": "volcano",
        "name_cn": "火山引擎",
        "name_en": "Volcano Engine",
        "provider_type": "cloud",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "auth_type": "bearer",
        "description": "字节跳动旗下云服务平台，提供豆包大模型",
        "icon_url": "/icons/volcano.svg",
        "website_url": "https://www.volcengine.com",
        "doc_url": "https://www.volcengine.com/docs/82379"
    }
]

DEFAULT_MODELS = [
    {
        "id": "doubao-seed-1-8",
        "provider_id": "volcano",
        "model_id": "doubao-seed-1-8-251228",
        "model_name": "Doubao-Seed-1.8",
        "model_name_cn": "豆包Seed-1.8",
        "model_type": "chat",
        "capabilities": ["chat", "completion", "function_calling", "json_mode"],
        "context_window": 4096,
        "max_tokens": 2048,
        "input_cost_per_1k": 0.005,
        "output_cost_per_1k": 0.009,
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "is_active": True,
        "is_recommended": True,
        "description": "豆包最新轻量级模型，性价比高",
        "version": "1.8",
        "release_date": "2024-12-28"
    }
]


# ============== API端点 ==============

@router.get("/providers", response_model=List[LLMProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db)
):
    """获取大模型提供商列表"""
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.is_active == True)
    )
    providers = result.scalars().all()
    
    if not providers:
        # 初始化预设数据
        for provider_data in DEFAULT_PROVIDERS:
            provider = LLMProvider(**provider_data)
            db.add(provider)
        await db.commit()
        
        # 重新查询
        result = await db.execute(
            select(LLMProvider).where(LLMProvider.is_active == True)
        )
        providers = result.scalars().all()
    
    return providers


@router.get("/models", response_model=List[LLMModelResponse])
async def list_models(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取大模型列表"""
    from datetime import datetime
    
    query = select(LLMModel).where(LLMModel.is_active == True)
    
    if provider:
        query = query.where(LLMModel.provider_id == provider)
    
    result = await db.execute(query)
    models = result.scalars().all()
    
    if not models:
        # 初始化预设模型
        for model_data in DEFAULT_MODELS:
            # 转换 release_date 字符串为 datetime 对象
            model_copy = model_data.copy()
            if 'release_date' in model_copy and model_copy['release_date']:
                try:
                    model_copy['release_date'] = datetime.fromisoformat(model_copy['release_date'])
                except:
                    model_copy['release_date'] = None
            model = LLMModel(**model_copy)
            db.add(model)
        await db.commit()
        
        # 重新查询
        result = await db.execute(query)
        models = result.scalars().all()
    
    return models


@router.get("/configs", response_model=List[LLMConfigResponse])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的大模型配置列表"""
    result = await db.execute(
        select(LLMConfig, LLMModel)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True
            )
        )
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.created_at))
    )
    
    configs = []
    for row in result.all():
        config, model = row
        configs.append({
            "id": config.id,
            "user_id": config.user_id,
            "model_id": config.model_id,
            "model_name": model.model_name,
            "provider_name": "火山引擎",  # TODO: 从provider表获取
            "name": config.name,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
            "is_active": config.is_active,
            "is_default": config.is_default,
            "test_status": config.test_status,
            "test_message": config.test_message,
            "usage_count": config.usage_count,
            "created_at": config.created_at,
            "updated_at": config.updated_at
        })
    
    return configs


@router.post("/configs", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    request: LLMConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建大模型配置"""
    # 验证模型是否存在
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == request.model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型不存在"
        )
    
    # 如果设为默认，取消其他默认配置
    if request.is_default:
        await db.execute(
            select(LLMConfig)
            .where(and_(LLMConfig.user_id == user_id, LLMConfig.is_default == True))
            .update({"is_default": False})
        )
    
    # TODO: 加密存储API密钥
    config = LLMConfig(
        id=str(uuid4()),
        user_id=user_id,
        model_id=request.model_id,
        name=request.name,
        api_key=request.api_key,  # 需要加密
        api_secret=request.api_secret,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_tokens,
        extra_params=request.extra_params,
        is_default=request.is_default,
        test_status="pending"
    )
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    return {
        "id": config.id,
        "user_id": config.user_id,
        "model_id": config.model_id,
        "model_name": model.model_name,
        "provider_name": "火山引擎",
        "name": config.name,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "is_active": config.is_active,
        "is_default": config.is_default,
        "test_status": config.test_status,
        "test_message": config.test_message,
        "usage_count": config.usage_count,
        "created_at": config.created_at,
        "updated_at": config.updated_at
    }


@router.post("/configs/{config_id}/test", response_model=LLMTestResponse)
async def test_config(
    config_id: str,
    request: LLMTestRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """测试大模型配置"""
    result = await db.execute(
        select(LLMConfig, LLMModel)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    config, model = row
    
    # TODO: 实现实际的API调用测试
    # 这里模拟测试成功
    import asyncio
    start_time = datetime.utcnow()
    await asyncio.sleep(1)  # 模拟API调用
    end_time = datetime.utcnow()
    
    response_time = int((end_time - start_time).total_seconds() * 1000)
    
    # 更新测试状态
    config.test_status = "success"
    config.test_message = "连接成功"
    config.tested_at = datetime.utcnow()
    await db.commit()
    
    return {
        "success": True,
        "message": "测试成功",
        "response": f"你好！我是{model.model_name_cn}，很高兴为你服务。",
        "response_time_ms": response_time,
        "tokens_used": 25
    }


@router.put("/configs/{config_id}", response_model=LLMConfigResponse)
async def update_config(
    config_id: str,
    request: LLMConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新大模型配置"""
    result = await db.execute(
        select(LLMConfig).where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    # 更新字段
    config.name = request.name
    config.api_key = request.api_key  # 需要加密
    config.api_secret = request.api_secret
    config.temperature = request.temperature
    config.top_p = request.top_p
    config.max_tokens = request.max_tokens
    config.extra_params = request.extra_params
    config.is_default = request.is_default
    config.test_status = "pending"  # 重置测试状态
    
    await db.commit()
    await db.refresh(config)
    
    # 获取模型信息
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == config.model_id)
    )
    model = result.scalar_one()
    
    return {
        "id": config.id,
        "user_id": config.user_id,
        "model_id": config.model_id,
        "model_name": model.model_name,
        "provider_name": "火山引擎",
        "name": config.name,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "is_active": config.is_active,
        "is_default": config.is_default,
        "test_status": config.test_status,
        "test_message": config.test_message,
        "usage_count": config.usage_count,
        "created_at": config.created_at,
        "updated_at": config.updated_at
    }


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除大模型配置"""
    result = await db.execute(
        select(LLMConfig).where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    config.is_active = False
    await db.commit()
    
    return {"message": "配置已删除"}


@router.post("/configs/{config_id}/set-default")
async def set_default_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """设为默认配置"""
    # 取消其他默认配置
    await db.execute(
        select(LLMConfig)
        .where(and_(LLMConfig.user_id == user_id, LLMConfig.is_default == True))
        .update({"is_default": False})
    )
    
    # 设置新的默认配置
    result = await db.execute(
        select(LLMConfig).where(
            and_(
                LLMConfig.id == config_id,
                LLMConfig.user_id == user_id
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    config.is_default = True
    await db.commit()
    
    return {"message": "已设为默认配置"}
