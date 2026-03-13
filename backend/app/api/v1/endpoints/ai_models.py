"""
AI模型配置 API 端点
"""

import time
import httpx
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.crypto import crypto_util
from app.models.ai_model import AIModel, ModelConfig, ModelUsageLog, CostSettings
from app.schemas.ai_model import (
    AIModelCreate,
    AIModelUpdate,
    AIModelResponse,
    AIModelListResponse,
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelConfigListResponse,
    ProviderAPIKeyUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
    CostSettingsCreate,
    CostSettingsUpdate,
    CostSettingsResponse,
    UsageLogResponse,
    UsageStatsResponse,
    ModelCategoriesResponse,
)

router = APIRouter(prefix="/models", tags=["ai-models"])


async def get_current_user_id_required(
    user_id: str = Depends(get_current_user_id),
) -> UUID:
    """获取当前用户ID（必需）"""
    return UUID(user_id)


@router.get("", response_model=AIModelListResponse)
async def list_models(
    category: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """获取模型列表"""
    query = select(AIModel)
    count_query = select(func.count()).select_from(AIModel)

    if category:
        query = query.where(AIModel.category == category)
        count_query = count_query.where(AIModel.category == category)
    if provider:
        query = query.where(AIModel.provider == provider)
        count_query = count_query.where(AIModel.provider == provider)
    if status:
        query = query.where(AIModel.status == status)
        count_query = count_query.where(AIModel.status == status)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (AIModel.name.ilike(search_filter))
            | (AIModel.display_name.ilike(search_filter))
        )
        count_query = count_query.where(
            (AIModel.name.ilike(search_filter))
            | (AIModel.display_name.ilike(search_filter))
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    skip = (page - 1) * page_size
    query = query.order_by(desc(AIModel.created_at)).offset(skip).limit(page_size)

    result = await db.execute(query)
    models = result.scalars().all()

    return AIModelListResponse(
        items=[AIModelResponse.model_validate(m) for m in models],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/categories", response_model=ModelCategoriesResponse)
async def get_model_categories(db: AsyncSession = Depends(get_db)):
    """获取模型分类"""
    result = await db.execute(
        select(AIModel.provider, func.count(AIModel.id).label("count")).group_by(
            AIModel.provider
        )
    )
    provider_counts = {r.provider: r.count for r in result.all()}

    categories = [
        CategoryInfo(
            id="text_generation",
            name="文本生成",
            icon="file-text",
            description="LLM文字生成",
        ),
        CategoryInfo(
            id="image_generation", name="图像生成", icon="image", description="AI绘图"
        ),
        CategoryInfo(
            id="video_generation",
            name="视频生成",
            icon="video",
            description="AI视频生成",
        ),
        CategoryInfo(
            id="voice_synthesis", name="语音合成", icon="mic", description="文字转语音"
        ),
        CategoryInfo(
            id="music_generation",
            name="音乐生成",
            icon="music",
            description="AI音乐创作",
        ),
        CategoryInfo(
            id="image_understanding",
            name="图像理解",
            icon="eye",
            description="多模态理解",
        ),
    ]

    providers = [
        ProviderInfo(
            id="openai",
            name="OpenAI",
            logo="",
            models_count=provider_counts.get("openai", 0),
        ),
        ProviderInfo(
            id="anthropic",
            name="Anthropic",
            logo="",
            models_count=provider_counts.get("anthropic", 0),
        ),
        ProviderInfo(
            id="volcengine",
            name="火山引擎",
            logo="",
            models_count=provider_counts.get("volcengine", 0),
        ),
        ProviderInfo(
            id="midjourney",
            name="Midjourney",
            logo="",
            models_count=provider_counts.get("midjourney", 0),
        ),
        ProviderInfo(
            id="runway",
            name="Runway",
            logo="",
            models_count=provider_counts.get("runway", 0),
        ),
        ProviderInfo(
            id="elevenlabs",
            name="ElevenLabs",
            logo="",
            models_count=provider_counts.get("elevenlabs", 0),
        ),
        ProviderInfo(
            id="suno", name="Suno", logo="", models_count=provider_counts.get("suno", 0)
        ),
    ]

    return ModelCategoriesResponse(categories=categories, providers=providers)


@router.get("/providers")
async def get_providers(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """获取模型提供商"""
    result = await db.execute(
        select(AIModel.provider, func.count(AIModel.id).label("count")).group_by(
            AIModel.provider
        )
    )
    return [
        {"id": r.provider, "name": r.provider.title(), "models_count": r.count}
        for r in result.all()
    ]


@router.get("/{model_id}", response_model=AIModelResponse)
async def get_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """获取模型详情"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return AIModelResponse.model_validate(model)


@router.post("", response_model=AIModelResponse)
async def create_model(
    model_data: AIModelCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """创建AI模型"""
    model = AIModel(**model_data.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return AIModelResponse.model_validate(model)


@router.put("/{model_id}", response_model=AIModelResponse)
async def update_model(
    model_id: UUID,
    model_data: AIModelUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """更新AI模型"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    update_data = model_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(model, field, value)

    await db.commit()
    await db.refresh(model)
    return AIModelResponse.model_validate(model)


@router.delete("/{model_id}")
async def delete_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """删除AI模型"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    await db.delete(model)
    await db.commit()
    return {"message": "Model deleted successfully"}


@router.post("/{model_id}/api-key")
async def update_provider_api_key(
    model_id: UUID,
    key_data: ProviderAPIKeyUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """更新提供商API Key（加密存储）"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    encrypted_key = crypto_util.encrypt(key_data.api_key)
    model.api_key_env = encrypted_key
    await db.commit()

    await _log_usage(
        db, user_id, model_id, "api_key_update", status="success", latency_ms=0
    )

    return {"message": "API key updated successfully"}


@router.post("/{model_id}/test", response_model=TestConnectionResponse)
async def test_model_connection(
    model_id: UUID,
    request: TestConnectionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """测试模型连接"""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    start_time = time.time()
    error_msg = None

    try:
        api_key = request.api_key
        if not api_key and model.api_key_env:
            api_key = crypto_util.decrypt(model.api_key_env)

        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {api_key}"}
            base_url = model.base_url or "https://api.openai.com/v1"

            if model.provider == "openai":
                response = await client.get(
                    f"{base_url}/models/{model.model_id}", headers=headers
                )
            elif model.provider == "anthropic":
                response = await client.get(
                    f"{base_url}/messages",
                    headers={**headers, "anthropic-version": "2023-06-01"},
                )
            else:
                response = await client.get(base_url, headers=headers)

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code < 400:
                await _log_usage(
                    db,
                    user_id,
                    model_id,
                    "test_connection",
                    status="success",
                    latency_ms=latency_ms,
                )
                return TestConnectionResponse(
                    success=True, latency_ms=latency_ms, message="Connection successful"
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"

    except httpx.TimeoutException:
        error_msg = "Connection timeout"
    except Exception as e:
        error_msg = str(e)

    latency_ms = int((time.time() - start_time) * 1000)
    await _log_usage(
        db,
        user_id,
        model_id,
        "test_connection",
        status="failed",
        latency_ms=latency_ms,
        error=error_msg,
    )

    return TestConnectionResponse(
        success=False,
        latency_ms=latency_ms,
        message="Connection failed",
        error=error_msg,
    )


@router.get("/user/config", response_model=ModelConfigListResponse)
async def get_user_model_config(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """获取用户模型配置"""
    result = await db.execute(
        select(ModelConfig)
        .options(selectinload(ModelConfig.model))
        .where(ModelConfig.user_id == user_id)
        .order_by(ModelConfig.priority.desc())
    )
    configs = result.scalars().all()

    default_models = {}
    for config in configs:
        if config.model:
            category = config.model.category
            if category not in default_models or config.is_enabled:
                default_models[category] = config.model.name

    return ModelConfigListResponse(
        items=[ModelConfigResponse.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.put("/user/config", response_model=ModelConfigListResponse)
async def update_user_model_config(
    default_models: dict,
    custom_configs: List[dict] = [],
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """更新用户模型配置"""
    for category, model_name in default_models.items():
        result = await db.execute(
            select(AIModel).where(
                AIModel.category == category, AIModel.name == model_name
            )
        )
        model = result.scalar_one_or_none()
        if model:
            existing = await db.execute(
                select(ModelConfig).where(
                    ModelConfig.user_id == user_id, ModelConfig.model_id == model.id
                )
            )
            config = existing.scalar_one_or_none()
            if not config:
                config = ModelConfig(
                    user_id=user_id, model_id=model.id, is_enabled=True, priority=1
                )
                db.add(config)

    await db.commit()

    result = await db.execute(
        select(ModelConfig)
        .options(selectinload(ModelConfig.model))
        .where(ModelConfig.user_id == user_id)
    )
    configs = result.scalars().all()

    return ModelConfigListResponse(
        items=[ModelConfigResponse.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.post("/user/config", response_model=ModelConfigResponse)
async def create_user_model_config(
    config_data: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """创建用户模型配置"""
    config = ModelConfig(user_id=user_id, **config_data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return ModelConfigResponse.model_validate(config)


@router.delete("/user/config/{config_id}")
async def delete_user_model_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """删除用户模型配置"""
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == config_id, ModelConfig.user_id == user_id
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    await db.delete(config)
    await db.commit()
    return {"message": "Config deleted successfully"}


@router.get("/usage/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    period: str = Query("day"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """获取使用统计"""
    if period == "day":
        start_date = datetime.utcnow() - timedelta(days=1)
    elif period == "week":
        start_date = datetime.utcnow() - timedelta(days=7)
    else:
        start_date = datetime.utcnow() - timedelta(days=30)

    result = await db.execute(
        select(ModelUsageLog).where(
            ModelUsageLog.user_id == user_id, ModelUsageLog.created_at >= start_date
        )
    )
    logs = result.scalars().all()

    total_requests = len(logs)
    total_tokens = sum(log.total_tokens for log in logs)
    total_cost = sum(log.cost for log in logs)

    by_category = {}
    by_provider = {}

    for log in logs:
        result = await db.execute(select(AIModel).where(AIModel.id == log.model_id))
        model = result.scalar_one_or_none()
        if model:
            if model.category not in by_category:
                by_category[model.category] = {"requests": 0, "cost": 0}
            by_category[model.category]["requests"] += 1
            by_category[model.category]["cost"] += log.cost

            if model.provider not in by_provider:
                by_provider[model.provider] = {"requests": 0, "cost": 0}
            by_provider[model.provider]["requests"] += 1
            by_provider[model.provider]["cost"] += log.cost

    return UsageStatsResponse(
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_cost=total_cost,
        by_category=by_category,
        by_provider=by_provider,
    )


@router.get("/cost/settings", response_model=CostSettingsResponse)
async def get_cost_settings(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """获取成本设置"""
    result = await db.execute(
        select(CostSettings).where(CostSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = CostSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return CostSettingsResponse.model_validate(settings)


@router.put("/cost/settings", response_model=CostSettingsResponse)
async def update_cost_settings(
    settings_data: CostSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id_required),
):
    """更新成本设置"""
    result = await db.execute(
        select(CostSettings).where(CostSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = CostSettings(user_id=user_id)
        db.add(settings)

    update_data = settings_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)
    return CostSettingsResponse.model_validate(settings)


async def _log_usage(
    db: AsyncSession,
    user_id: UUID,
    model_id: UUID,
    request_type: str,
    status: str,
    latency_ms: int,
    error: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float = 0,
):
    """记录使用日志"""
    log = ModelUsageLog(
        user_id=user_id,
        model_id=model_id,
        request_type=request_type,
        status=status,
        latency_ms=latency_ms,
        error_message=error,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost=cost,
    )
    db.add(log)
    await db.commit()
