"""Resolve a user-facing video model selection to its runtime contract."""

from typing import Any, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_utils import get_user_api_key
from app.core.model_registry import find_model, get_provider
from app.core.volcano_agent_plan_config import find_volcano_agent_plan_model
from app.core.volcano_config import VOLCANO_MODELS, get_endpoint_id
from app.features.video_generation.constants import VIDEO_MODEL_ID
from app.features.video_generation.errors import VideoGenerationError
from app.features.model_config.public import (
    GenerationContext,
    ModelBindingError,
    resolve_generation_context,
)
from app.models import LLMConfig, LLMModel, LLMProvider


_LEGACY_FALLBACK_ERRORS = {"legacy_config_not_verified", "model_binding_not_found"}

def get_video_model_name(model_id: str) -> str:
    model = next((item for item in VOLCANO_MODELS if item["id"] == model_id), None)
    return model.get("name_cn", model.get("name", model_id)) if model else model_id


def _validate_video_model(model: LLMModel, *, broad_capability_check: bool) -> None:
    model_type = (model.model_type or "").lower()
    capabilities = [str(item).lower() for item in (model.capabilities or [])]
    valid_types = {"video", "video-generation", "video_generation"} if broad_capability_check else {
        "video", "video-generation"
    }
    if model_type not in valid_types and not (broad_capability_check and any("video" in item for item in capabilities)):
        raise VideoGenerationError(422, f"所选模型不是视频生成模型：{model.model_name}")


def _database_payload(
    model: LLMModel,
    provider: LLMProvider,
    config: Optional[LLMConfig],
) -> dict[str, Any]:
    provider_id = provider.name or provider.id
    extra = config.extra_params or {} if config else {}
    registry_model = find_model(model.id) or find_model(model.model_id)
    endpoint_id = get_endpoint_id(model.model_id) if provider_id == "volcano" else model.model_id
    return {
        "provider_id": provider_id,
        "provider_name": provider.name_cn or provider.name,
        "api_model_id": model.model_id,
        "config_model_id": model.id,
        "model_config_id": config.id if config else None,
        "model_name": model.model_name_cn or model.model_name,
        "model_type": (model.model_type or "").lower(),
        "base_url": extra.get("base_url") or model.base_url or provider.base_url,
        "api_key": config.get_api_key_decrypted() if config else None,
        "test_status": config.test_status if config else None,
        "model_endpoint_id": endpoint_id,
        "capabilities": model.capabilities or [],
        "limits": (registry_model.get("limits") if registry_model else {}) or {},
        "protocol": extra.get("protocol") or ((registry_model.get("protocol") if registry_model else {}) or {}),
        "routing": (registry_model.get("routing") if registry_model else {}) or {},
    }


async def _explicit_config(db: AsyncSession, user_id: str, config_id: str) -> dict[str, Any]:
    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(and_(
            LLMConfig.id == config_id, LLMConfig.user_id == user_id,
            LLMConfig.is_active.is_(True), LLMModel.is_active.is_(True), LLMProvider.is_active.is_(True),
        )).limit(1)
    )
    row = result.first()
    if not row:
        raise VideoGenerationError(404, "所选视频模型配置不存在或已停用")
    config, model, provider = row
    _validate_video_model(model, broad_capability_check=True)
    return _database_payload(model, provider, config)


async def _database_model(
    db: AsyncSession, user_id: str, model_key: str,
) -> Optional[dict[str, Any]]:
    result = await db.execute(
        select(LLMModel, LLMProvider).join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(and_(
            LLMModel.is_active.is_(True), LLMProvider.is_active.is_(True),
            or_(LLMModel.id == model_key, LLMModel.model_id == model_key),
        )).limit(1)
    )
    row = result.first()
    if not row:
        return None
    model, provider = row
    _validate_video_model(model, broad_capability_check=False)
    config = await db.scalar(
        select(LLMConfig).where(and_(
            LLMConfig.user_id == user_id, LLMConfig.model_id == model.id, LLMConfig.is_active.is_(True),
        )).order_by(desc(LLMConfig.is_default), desc(LLMConfig.updated_at), desc(LLMConfig.created_at)).limit(1)
    )
    return _database_payload(model, provider, config)


def _registry_payload(model_key: str) -> Optional[dict[str, Any]]:
    model = find_model(model_key)
    if not model or model.get("modality") != "video":
        return None
    provider_id = model.get("provider_id") or "volcano"
    provider = get_provider(provider_id) or {}
    api_model_id = model.get("api_model_id") or model_key
    return {
        "provider_id": provider_id, "provider_name": provider.get("display_name") or provider_id,
        "api_model_id": api_model_id, "config_model_id": model.get("id"), "model_config_id": None,
        "model_name": model.get("display_name") or api_model_id, "model_type": "video-generation",
        "base_url": provider.get("base_url"), "api_key": None, "test_status": None,
        "model_endpoint_id": get_endpoint_id(api_model_id) if provider_id == "volcano" else api_model_id,
        "capabilities": model.get("capabilities") or [], "limits": model.get("limits") or {},
        "protocol": model.get("protocol") or {}, "routing": model.get("routing") or {},
    }


def _fallback_payload(model_key: str) -> dict[str, Any]:
    model = find_volcano_agent_plan_model(model_key)
    return {
        "provider_id": model["provider_id"] if model else "volcano",
        "provider_name": "火山方舟 Agent Plan" if model else "火山引擎",
        "api_model_id": model["model_id"] if model else model_key,
        "config_model_id": model["id"] if model else None,
        "model_name": model["model_name_cn"] if model else get_video_model_name(model_key),
        "model_type": "video-generation", "base_url": model["base_url"] if model else None,
        "api_key": None, "test_status": None,
        "model_endpoint_id": model["model_id"] if model else get_endpoint_id(model_key),
        "capabilities": model["capabilities"] if model else ["text-to-video", "image-to-video"],
    }


async def _legacy_video_model_config(
    db: AsyncSession,
    user_id: str,
    requested_model: Optional[str],
    config_id: Optional[str] = None,
) -> dict[str, Any]:
    if config_id:
        return await _explicit_config(db, user_id, config_id)
    model_key = requested_model or VIDEO_MODEL_ID
    database = await _database_model(db, user_id, model_key)
    return database or _registry_payload(model_key) or _fallback_payload(model_key)


def _generation_context_payload(context: GenerationContext) -> dict[str, Any]:
    profile = context.profile
    provider_name = context.connection_params.get("provider_name") or profile.provider_id
    return {
        "provider_id": provider_name,
        "provider_name": provider_name,
        "api_model_id": profile.api_model_id,
        "config_model_id": profile.profile_version_id,
        "model_config_id": context.binding.connection_id,
        "model_name": profile.api_model_id,
        "model_type": "video-generation",
        "base_url": context.base_url,
        "api_key": context.api_key,
        "test_status": "success",
        "model_endpoint_id": profile.api_model_id,
        "capabilities": list(profile.capabilities),
        "limits": dict(profile.limits),
        "protocol": dict(profile.input_contract),
        "routing": {"route_policy": dict(context.route_policy)},
        "generation_context": context,
    }


async def resolve_video_model_config(
    db: AsyncSession,
    user_id: str,
    requested_model: Optional[str],
    config_id: Optional[str] = None,
) -> dict[str, Any]:
    try:
        context = await resolve_generation_context(
            db, user_id=user_id, stage="video", explicit_config_id=config_id,
        )
    except ModelBindingError as error:
        if str(error) in _LEGACY_FALLBACK_ERRORS:
            return await _legacy_video_model_config(db, user_id, requested_model, config_id)
        raise VideoGenerationError(422, str(error)) from error
    if context.binding.binding_version == 0 and not config_id:
        return await _legacy_video_model_config(db, user_id, requested_model, config_id)
    return _generation_context_payload(context)


async def resolve_video_job_client_config(
    db: AsyncSession,
    user_id: str,
    job: Any,
) -> tuple[str, Optional[str]]:
    extra = job.extra_data if isinstance(job.extra_data, dict) else {}
    config_id = str(extra.get("model_config_id") or "").strip() or None
    if config_id:
        resolved = await resolve_video_model_config(
            db, user_id, job.model_id, config_id,
        )
        api_key = resolved.get("api_key")
        if not api_key:
            raise VideoGenerationError(422, "视频任务绑定的模型配置缺少 API Key")
        return api_key, resolved.get("base_url")
    provider_id = str(extra.get("provider_id") or "volcano")
    api_key, base_url = await get_user_api_key(db, user_id, provider_id)
    return api_key, base_url
