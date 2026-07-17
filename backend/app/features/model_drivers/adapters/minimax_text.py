"""MiniMax text driver delegating to the legacy text service factory."""

from app.features.model_drivers.adapters._shared import connection_test, unsupported_poll
from app.features.model_drivers.domain import DriverSubmission, TextCommand


class MiniMaxTextDriver:
    key = "minimax_text_v2"
    capabilities = frozenset({"text_generation"})

    async def test_connection(self, context):
        return await connection_test(
            lambda: self.submit(TextCommand(prompt="模型中心连接测试"), context),
            "MiniMax 文本模型连接成功",
        )

    async def submit(self, command, context):
        from app.features.model_drivers.text_execution import create_text_generation_service, extract_chat_content

        service = create_text_generation_service(context.api_key, "minimax", context.base_url)
        response = await service.safe_chat_completion(
            model=context.profile.api_model_id,
            messages=[{"role": "user", "content": command.prompt}],
            **dict(command.params),
        )
        return DriverSubmission("completed", None, {"text": extract_chat_content(response), "response": response})

    poll = staticmethod(unsupported_poll)
