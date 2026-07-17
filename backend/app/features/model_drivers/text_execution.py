"""Legacy text execution compatibility over current provider services."""

from typing import Any, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_drivers.text_response import (
    extract_chat_content,
    normalize_provider_base_url,
    sanitize_chat_response,
    strip_thinking_blocks,
)

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


async def get_user_text_generation_service(
    db: AsyncSession,
    user_id: str,
) -> Tuple[Any, str, str, Optional[str]]:
    """Return (service, provider_name, model_id, base_url) for the default text config."""
    from app.core.api_key_utils import get_user_text_model_config

    api_key, provider_name, model_id, base_url = await get_user_text_model_config(db, user_id)
    service = create_text_generation_service(api_key or "", provider_name or "", base_url)
    return service, provider_name or "", model_id or "", base_url
