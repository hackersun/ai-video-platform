"""
API Key 查找工具

提供统一的函数用于从用户的 LLMConfig 中获取（解密后的）API 密钥和 base_url。
"""

from typing import Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from fastapi import HTTPException, status

from app.features.model_drivers.text_execution import (
    TextGenerationServiceAdapter,
    create_text_generation_service,
    extract_chat_content,
    get_user_text_generation_service,
    normalize_provider_base_url,
    sanitize_chat_response,
    strip_thinking_blocks,
)


TEXT_PROVIDER_ALIASES = ("dashscope", "qianlian", "qwen", "minimax", "volcano", "volcano_agent_plan", "openai", "baidu")
TEXT_MODEL_TYPES = ("chat", "completion", "text-generation", "text_generation", "llm")
TEXT_CAPABILITIES = ("chat", "completion", "text_generation", "text-generation", "json_mode", "structured_output")
IMAGE_PROVIDER_ALIASES = ("volcano", "volcano_agent_plan", "minimax", "openai")
IMAGE_MODEL_TYPES = ("image-generation", "image_generation", "image")
IMAGE_CAPABILITIES = (
    "text-to-image",
    "text_to_image",
    "image-edit",
    "image_edit",
    "variation",
    "inpainting",
    "outpainting",
    "character_reference",
    "scene_reference",
)
VISION_PROVIDER_ALIASES = ("dashscope", "qianlian", "qwen", "minimax", "volcano", "volcano_agent_plan", "openai", "baidu")
VISION_MODEL_TYPES = ("vision",)
VISION_CAPABILITIES = ("vision", "multimodal", "image_understanding")



def _provider_key(provider: Any) -> str:
    """Return the stable provider identifier used by service factories."""
    return (getattr(provider, "name", None) or getattr(provider, "id", "") or "").lower()


def _model_supports_any(
    model: Any,
    model_types: tuple[str, ...],
    capabilities: tuple[str, ...],
) -> bool:
    model_type = (getattr(model, "model_type", "") or "").lower()
    if model_type in model_types:
        return True

    model_capabilities = getattr(model, "capabilities", None) or []
    if isinstance(model_capabilities, str):
        import json

        try:
            model_capabilities = json.loads(model_capabilities)
        except Exception:
            model_capabilities = [model_capabilities]

    normalized = {str(item).lower() for item in model_capabilities}
    return bool(normalized.intersection(capabilities))


def _model_supports_text(model: Any) -> bool:
    return _model_supports_any(model, TEXT_MODEL_TYPES, TEXT_CAPABILITIES)


def _model_supports_image(model: Any) -> bool:
    return _model_supports_any(model, IMAGE_MODEL_TYPES, IMAGE_CAPABILITIES)


def _row_api_key(row: Any) -> str:
    config = row[0]
    try:
        return config.get_api_key_decrypted()
    except Exception:
        return ""


def _row_base_url(row: Any, api_key: str = "") -> Optional[str]:
    config, model, provider = row
    extra = config.extra_params or {}
    provider_name = _provider_key(provider)
    explicit_base_url = extra.get("base_url")
    if explicit_base_url:
        return normalize_provider_base_url(provider_name, explicit_base_url)
    if provider_name == "minimax":
        from app.core.minimax_config import get_minimax_base_url

        return normalize_provider_base_url(provider_name, get_minimax_base_url(api_key))
    base_url = model.base_url or provider.base_url
    return normalize_provider_base_url(provider_name, base_url)




def create_image_generation_service(
    api_key: str,
    provider_name: str,
    base_url: Optional[str],
) -> Any:
    """Create the correct image-generation service for a saved provider config."""
    base_url = normalize_provider_base_url(provider_name, base_url)
    if provider_name == "volcano":
        from app.services.volcano_service import VolcanoService

        return VolcanoService(api_key, base_url)
    if provider_name == "volcano_agent_plan":
        from app.services.volcano_service import VolcanoService

        return VolcanoService(api_key, base_url)
    if provider_name == "minimax":
        from app.services.minimax_service import MiniMaxService

        return MiniMaxService(api_key, base_url)
    if provider_name == "openai":
        from app.services.openai_service import OpenAIService

        return OpenAIService(api_key, base_url)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"不支持的图像模型服务商: {provider_name}",
    )



async def get_user_task_model_config(
    db: AsyncSession,
    user_id: str,
    provider_ids: tuple[str, ...] | list[str],
    raise_if_missing: bool = True,
    model_types: tuple[str, ...] = TEXT_MODEL_TYPES,
    capabilities: tuple[str, ...] = TEXT_CAPABILITIES,
    missing_detail: str = "请先配置千问/百炼大模型API密钥（LLM配置页面）",
    config_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    获取某类任务可用的默认模型配置。

    Returns:
        (api_key, provider_id, api_model_id, base_url)
    """
    from app.models.llm_config import LLMConfig, LLMModel, LLMProvider

    provider_ids = tuple(provider_ids)
    provider_id_set = {item.lower() for item in provider_ids}
    model_filter = or_(
        LLMModel.model_type.in_(model_types),
        *[LLMModel.capabilities.contains([capability]) for capability in capabilities],
    )
    if config_id:
        result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.id == config_id,
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMModel.is_active == True,
                    LLMProvider.is_active == True,
                )
            )
            .limit(1)
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="所选模型配置不存在或已停用")

        config, model, provider = row
        provider_key = _provider_key(provider)
        if (
            provider_key not in provider_id_set
            and (provider.id or "").lower() not in provider_id_set
            and (model.provider_id or "").lower() not in provider_id_set
        ):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="所选模型配置的提供者不支持当前能力")
        if not _model_supports_any(model, model_types, capabilities):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="所选模型配置不支持当前能力")

        api_key = config.get_api_key_decrypted()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="所选模型配置的 API Key 为空或无法解密，请在 AI 模型配置页面重新保存并验证该配置",
            )
        return api_key, provider_key, model.model_id, _row_base_url(row, api_key)

    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMModel.is_active == True,
                LLMProvider.is_active == True,
                or_(LLMProvider.name.in_(provider_ids), LLMProvider.id.in_(provider_ids)),
                model_filter,
                LLMConfig.is_default == True,
            )
        )
        .limit(1)
    )
    row = result.first()

    if not row:
        result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMModel.is_active == True,
                    LLMProvider.is_active == True,
                    or_(LLMProvider.name.in_(provider_ids), LLMProvider.id.in_(provider_ids)),
                    model_filter,
                )
            )
            .order_by(desc(LLMConfig.is_default), desc(LLMConfig.last_used_at), desc(LLMConfig.created_at))
            .limit(1)
        )
        row = result.first()

    if not row:
        result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMModel.is_active == True,
                    LLMProvider.is_active == True,
                )
            )
            .order_by(desc(LLMConfig.is_default), desc(LLMConfig.last_used_at), desc(LLMConfig.created_at))
        )
        row = next(
            (
                candidate
                for candidate in result.all()
                if _provider_key(candidate[2]) in provider_ids
                and _model_supports_any(candidate[1], model_types, capabilities)
            ),
            None,
        )

    if not row:
        if raise_if_missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=missing_detail,
            )
        return None, None, None, None

    config, model, provider = row
    api_key = _row_api_key(row)
    if not api_key:
        fallback_result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMConfig.id != config.id,
                    LLMModel.is_active == True,
                    LLMProvider.is_active == True,
                    or_(LLMProvider.name.in_(provider_ids), LLMProvider.id.in_(provider_ids)),
                    model_filter,
                )
            )
            .order_by(desc(LLMConfig.test_status == "success"), desc(LLMConfig.last_used_at), desc(LLMConfig.updated_at), desc(LLMConfig.created_at))
        )
        for fallback_row in fallback_result.all():
            fallback_key = _row_api_key(fallback_row)
            if fallback_key:
                fallback_config, fallback_model, fallback_provider = fallback_row
                fallback_provider_name = _provider_key(fallback_provider)
                return fallback_key, fallback_provider_name, fallback_model.model_id, _row_base_url(fallback_row, fallback_key)

        if raise_if_missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"默认模型配置“{config.name}”的 API Key 为空或无法解密，请在 AI 模型配置页面重新保存并验证该配置",
            )
        provider_name = _provider_key(provider)
        return None, provider_name, model.model_id, model.base_url or provider.base_url

    provider_name = _provider_key(provider)
    return api_key, provider_name, model.model_id, _row_base_url(row, api_key)


async def get_user_text_model_config(
    db: AsyncSession,
    user_id: str,
    raise_if_missing: bool = True,
    config_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """获取文本生成默认配置（千问/DashScope/百炼优先）。"""
    return await get_user_task_model_config(
        db=db,
        user_id=user_id,
        provider_ids=TEXT_PROVIDER_ALIASES,
        raise_if_missing=raise_if_missing,
        model_types=TEXT_MODEL_TYPES,
        capabilities=TEXT_CAPABILITIES,
        missing_detail="请先配置千问/百炼大模型API密钥（LLM配置页面）",
        config_id=config_id,
    )


async def get_user_image_model_config(
    db: AsyncSession,
    user_id: str,
    raise_if_missing: bool = True,
    config_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """获取图像生成默认配置。"""
    return await get_user_task_model_config(
        db=db,
        user_id=user_id,
        provider_ids=IMAGE_PROVIDER_ALIASES,
        raise_if_missing=raise_if_missing,
        model_types=IMAGE_MODEL_TYPES,
        capabilities=IMAGE_CAPABILITIES,
        missing_detail="请先配置图像生成模型API密钥（LLM配置页面）",
        config_id=config_id,
    )


async def get_user_vision_model_config(
    db: AsyncSession,
    user_id: str,
    raise_if_missing: bool = True,
    config_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """获取视觉理解/多模态默认配置，不用于直接文生图。"""
    return await get_user_task_model_config(
        db=db,
        user_id=user_id,
        provider_ids=VISION_PROVIDER_ALIASES,
        raise_if_missing=raise_if_missing,
        model_types=VISION_MODEL_TYPES,
        capabilities=VISION_CAPABILITIES,
        missing_detail="请先配置视觉多模态模型API密钥（LLM配置页面）",
        config_id=config_id,
    )


async def get_user_api_key(
    db: AsyncSession,
    user_id: str,
    provider_id: str,
    raise_if_missing: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """
    获取用户配置的 API 密钥和 base_url（解密后）。

    查找逻辑：
    1. 优先查找用户的默认配置（is_default=True）
    2. 其次查找任意活跃的配置
    3. 找不到时根据 raise_if_missing 决定是否抛出错误

    Returns:
        Tuple[api_key, base_url]

    Raises:
        HTTPException: 用户未配置且 raise_if_missing=True。
    """
    from app.models.llm_config import LLMConfig, LLMModel, LLMProvider

    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMConfig.is_default == True,
                or_(LLMModel.provider_id == provider_id, LLMProvider.name == provider_id, LLMProvider.id == provider_id),
            )
        )
        .limit(1)
    )
    row = result.first()

    if not row:
        result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    or_(LLMModel.provider_id == provider_id, LLMProvider.name == provider_id, LLMProvider.id == provider_id),
                )
            )
            .order_by(LLMConfig.created_at.desc())
            .limit(1)
        )
        row = result.first()

    if not row:
        if raise_if_missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"未找到 {provider_id} API Key 配置。"
                    "请前往【LLM 配置】页面添加 API Key 后重试。"
                ),
            )
        return None, None

    config, model, provider = row
    api_key = config.get_api_key_decrypted()
    # base_url: 优先用户配置的 extra_params 中的 base_url，其次用模型定义的 base_url
    extra = config.extra_params or {}
    provider_name = _provider_key(provider) or provider_id
    base_url = extra.get("base_url") or getattr(model, "base_url", None) or getattr(provider, "base_url", None)
    return api_key, normalize_provider_base_url(provider_name, base_url)


# ========== 各 Provider 便捷函数 ==========

async def get_user_volcano_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的火山引擎 API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "volcano")
    return api_key


async def get_user_minimax_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的 MiniMax API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "minimax")
    return api_key


async def get_user_openai_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的 OpenAI API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "openai")
    return api_key


async def get_user_qianlian_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的阿里百炼 API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "qianlian")
    return api_key


async def get_user_dashscope_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户配置的千问 API 密钥（解密后）"""
    api_key, _ = await get_user_api_key(db, user_id, "dashscope")
    return api_key
