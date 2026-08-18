"""Stable compatibility driver over the production text service factory."""

from app.features.model_drivers.adapters._shared import connection_test, unsupported_poll
from app.features.model_drivers.domain import DriverSubmission, TextCommand


_SUCCESS_MESSAGES = {
    "baidu": "百度API连接成功！", "dashscope": "千问API连接成功！", "deepseek": "DeepSeek 官方 API 连接成功！",
    "openai": "OpenAI API连接成功！", "qianlian": "千链API连接成功！",
    "qwen": "千问API连接成功！", "volcano": "火山引擎API连接成功！",
    "volcano_agent_plan": "火山方舟 API 连接成功！",
}
_STRUCTURED_OUTPUT_CONTRACTS = frozenset({"json", "json_array", "json_object", "json_schema"})
_STRUCTURED_OUTPUT_MAX_TOKENS = 12000


class LegacyTextDriver:
    key = "legacy_text_v1"
    capabilities = frozenset({"text_generation"})

    async def test_connection(self, context):
        provider = str(context.connection_params.get("provider_name") or context.profile.provider_id)
        prompt = str(context.connection_params.get("test_message") or "模型中心连接测试")
        return await connection_test(
            lambda: self.submit(TextCommand(prompt=prompt), context),
            _SUCCESS_MESSAGES.get(provider, "API 连接成功！"),
        )

    async def submit(self, command, context):
        from app.features.model_drivers.text_execution import create_text_generation_service, extract_chat_content

        provider = str(context.connection_params.get("provider_name") or context.profile.provider_id)
        service = create_text_generation_service(context.api_key, provider, context.base_url)
        structured_options = (
            {"max_tokens": _STRUCTURED_OUTPUT_MAX_TOKENS}
            if command.output_contract in _STRUCTURED_OUTPUT_CONTRACTS else {}
        )
        if provider == "deepseek" and structured_options:
            structured_options["thinking"] = {"type": "disabled"}
        response = await service.safe_chat_completion(
            model=context.profile.api_model_id,
            messages=[{"role": "user", "content": command.prompt}],
            **structured_options,
            **dict(command.params),
        )
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        return DriverSubmission(
            "completed", None,
            {"text": extract_chat_content(response), "usage_count": usage.get("total_tokens", 0)},
        )

    poll = staticmethod(unsupported_poll)
