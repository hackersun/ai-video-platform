"""
API Key 查找工具

提供统一的函数用于从用户的 LLMConfig 中获取（解密后的）API 密钥和 base_url。
"""

from typing import Any, Optional, Tuple
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from fastapi import HTTPException, status


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


def normalize_provider_base_url(provider_name: str, base_url: Optional[str]) -> Optional[str]:
    """Normalize legacy provider URLs before constructing service clients."""
    if not base_url:
        return base_url
    normalized = base_url.rstrip("/")
    if provider_name == "qianlian" and normalized.endswith("/apps/anthropic"):
        return f"{normalized}/v1"
    return normalized


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


def strip_thinking_blocks(content: str) -> str:
    """Remove model reasoning blocks from user-facing text."""
    if not content:
        return content
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    if cleaned.lstrip().lower().startswith("<think>"):
        marker = "</think>"
        end = cleaned.lower().find(marker)
        if end >= 0:
            cleaned = cleaned[end + len(marker):]
    return cleaned.strip()


def sanitize_chat_response(response: dict) -> dict:
    """Strip reasoning markers from OpenAI-compatible chat responses."""
    try:
        for choice in response.get("choices", []):
            message = choice.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = strip_thinking_blocks(content)
    except AttributeError:
        return response
    return response


class TextGenerationServiceAdapter:
    """Small compatibility layer for text-generation services.

    Some provider clients only expose `chat_completion`, while text endpoints also
    need safe generation and planning helpers. This adapter keeps endpoint code
    provider-agnostic without forcing every service class to implement the same
    convenience methods.
    """

    def __init__(self, service: Any):
        self._service = service

    def __getattr__(self, name: str) -> Any:
        return getattr(self._service, name)

    async def chat_completion(self, *args: Any, **kwargs: Any) -> dict:
        return sanitize_chat_response(await self._service.chat_completion(*args, **kwargs))

    async def safe_chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_context_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> dict:
        provider_safe = getattr(self._service, "safe_chat_completion", None)
        if callable(provider_safe):
            return sanitize_chat_response(
                await provider_safe(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_context_tokens=max_context_tokens,
                    **kwargs,
                )
            )

        from app.services.ai_service_base import parse_api_error, truncate_context

        output_tokens = max_tokens or 4000
        context_window = 32000
        get_context_window = getattr(self._service, "get_context_window", None)
        if callable(get_context_window):
            context_window = get_context_window(model)
        max_input = max(500, context_window - output_tokens - 200)
        if max_context_tokens:
            max_input = min(max_input, max_context_tokens)

        system_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
                break

        prepared = truncate_context(
            messages,
            max_tokens=max_input,
            preserve_system=True,
            system_prompt=system_prompt,
        )

        try:
            return sanitize_chat_response(
                await self._service.chat_completion(
                    model=model,
                    messages=prepared,
                    temperature=temperature,
                    max_tokens=output_tokens,
                    **kwargs,
                )
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=parse_api_error(exc))

    def calculate_request_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        provider_cost = getattr(self._service, "calculate_request_cost", None)
        if callable(provider_cost):
            return provider_cost(model, input_tokens, output_tokens)
        provider_cost = getattr(self._service, "calculate_cost", None)
        if callable(provider_cost):
            return provider_cost(model, input_tokens, output_tokens)
        return 0.0

    async def understand_dialogue(
        self,
        user_input: str,
        context: Optional[list[dict]] = None,
        model: str = "",
    ) -> dict:
        provider_method = getattr(self._service, "understand_dialogue", None)
        if callable(provider_method):
            return await provider_method(user_input=user_input, context=context, model=model)

        messages = [
            {
                "role": "system",
                "content": (
                    "你是专业的需求理解助手。请分析用户输入，提取创作目标、题材、"
                    "关键约束、需要补充的信息，并用中文结构化输出。"
                ),
            },
            {"role": "user", "content": user_input},
        ]
        if context:
            messages.insert(1, {"role": "user", "content": f"历史上下文：{context}"})
        return await self.safe_chat_completion(model=model, messages=messages, temperature=0.4, max_tokens=1200)

    async def generate_coding_plan(
        self,
        requirement: str,
        model: str,
        context: Optional[str] = None,
        language: Optional[str] = None,
    ) -> dict:
        provider_method = getattr(self._service, "generate_coding_plan", None)
        if callable(provider_method):
            return await provider_method(requirement=requirement, model=model, context=context, language=language)

        prompt = f"需求描述：\n{requirement}\n\n"
        if language:
            prompt += f"目标语言：{language}\n\n"
        if context:
            prompt += f"额外上下文：\n{context}\n\n"
        prompt += "请生成结构清晰、可执行的 Coding Plan。"
        return await self.safe_chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "你是专业的技术架构师和代码规划专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )

    async def generate_novel_with_plan(self, prompt: str, model: str, max_tokens: int = 8000) -> dict:
        provider_method = getattr(self._service, "generate_novel_with_plan", None)
        if callable(provider_method):
            return await provider_method(prompt=prompt, model=model, max_tokens=max_tokens)

        plan_response = await self.safe_chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "你是专业的小说创作规划师，擅长设计完整故事架构。"},
                {
                    "role": "user",
                    "content": (
                        f"请为以下小说主题生成创作规划：\n{prompt}\n\n"
                        "包含故事大纲、主要角色、关键情节点、章节节奏和风格建议。"
                    ),
                },
            ],
            temperature=0.8,
            max_tokens=2000,
        )
        plan = plan_response["choices"][0]["message"]["content"]
        content_response = await self.safe_chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "你是专业的中文小说作家，擅长将规划转化为故事正文。"},
                {"role": "user", "content": f"基于以下规划创作第一章正文：\n\n{plan}\n\n原始主题：{prompt}"},
            ],
            temperature=0.8,
            max_tokens=max_tokens,
        )
        return {
            "plan": plan,
            "content": content_response["choices"][0]["message"]["content"],
            "usage": content_response.get("usage", {}),
        }

    async def generate_technical_storyboard(
        self,
        scene_description: str,
        model: str,
        technical_requirements: Optional[str] = None,
    ) -> dict:
        provider_method = getattr(self._service, "generate_technical_storyboard", None)
        if callable(provider_method):
            return await provider_method(
                scene_description=scene_description,
                technical_requirements=technical_requirements,
                model=model,
            )

        prompt = f"场景描述：\n{scene_description}\n\n"
        if technical_requirements:
            prompt += f"技术要求：\n{technical_requirements}\n\n"
        prompt += "请生成包含镜头、画面、技术实现、资源需求和风险点的分镜方案。"
        return await self.safe_chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "你是专业的技术分镜师和视觉开发专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
        )


def create_text_generation_service(
    api_key: str,
    provider_name: str,
    base_url: Optional[str],
) -> Any:
    """Create the correct text-generation service for a saved provider config."""
    base_url = normalize_provider_base_url(provider_name, base_url)
    if provider_name == "qianlian":
        from app.services.qianlian_service import QianlianService

        return TextGenerationServiceAdapter(QianlianService(api_key, base_url))
    if provider_name in ("dashscope", "qwen"):
        from app.services.dashscope_service import DashScopeService

        return TextGenerationServiceAdapter(DashScopeService(api_key, base_url))
    if provider_name == "minimax":
        from app.services.minimax_service import MiniMaxService

        return TextGenerationServiceAdapter(MiniMaxService(api_key, base_url))
    if provider_name == "volcano":
        from app.services.volcano_service import VolcanoService

        return TextGenerationServiceAdapter(VolcanoService(api_key, base_url))
    if provider_name == "volcano_agent_plan":
        from app.services.volcano_service import VolcanoService

        return TextGenerationServiceAdapter(VolcanoService(api_key, base_url))
    if provider_name == "openai":
        from app.services.openai_service import OpenAIService

        return TextGenerationServiceAdapter(OpenAIService(api_key, base_url))
    if provider_name == "baidu":
        from app.services.openai_service import OpenAIService

        return TextGenerationServiceAdapter(OpenAIService(api_key, base_url))
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"不支持的文本模型服务商: {provider_name}",
    )


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


async def get_user_text_generation_service(
    db: AsyncSession,
    user_id: str,
) -> Tuple[Any, str, str, Optional[str]]:
    """Return (service, provider_name, model_id, base_url) for the default text config."""
    api_key, provider_name, model_id, base_url = await get_user_text_model_config(db, user_id)
    service = create_text_generation_service(api_key or "", provider_name or "", base_url)
    return service, provider_name or "", model_id or "", base_url


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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选模型配置缺少 API Key，请在大模型配置页面补全")
        extra = config.extra_params or {}
        base_url = extra.get("base_url") or model.base_url or provider.base_url
        return api_key, provider_key, model.model_id, normalize_provider_base_url(provider_key, base_url)

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
    api_key = config.get_api_key_decrypted()
    if not api_key:
        if raise_if_missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="大模型API密钥未设置，请在LLM配置中填入有效的API Key",
            )
        provider_name = _provider_key(provider)
        return None, provider_name, model.model_id, model.base_url or provider.base_url

    extra = config.extra_params or {}
    base_url = extra.get("base_url") or model.base_url or provider.base_url
    provider_name = _provider_key(provider)
    return api_key, provider_name, model.model_id, normalize_provider_base_url(provider_name, base_url)


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
