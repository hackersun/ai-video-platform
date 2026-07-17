"""MiniMax image driver delegating request and response ownership."""

from app.features.model_drivers.adapters._shared import connection_test, unsupported_poll
from app.features.model_drivers.domain import DriverSubmission, ImageCommand


class MiniMaxImageDriver:
    key = "minimax_image_v1"
    capabilities = frozenset({"image_generation"})

    async def test_connection(self, context):
        return await connection_test(
            lambda: self.submit(ImageCommand(prompt="模型中心连接测试"), context),
            "MiniMax 图像模型连接成功",
        )

    async def submit(self, command, context):
        from app.services.image_provider_response_contract import classify_image_provider_response
        from app.services.minimax_service import MiniMaxService

        result = await MiniMaxService(context.api_key, context.base_url).generate_image(
            command.prompt, model=context.profile.api_model_id, **dict(command.params)
        )
        classified = classify_image_provider_response(result, "minimax")
        return DriverSubmission(
            classified["status"],
            classified["provider_task_id"],
            {"image_urls": classified["image_urls"], "evidence": classified["evidence"]},
        )

    poll = staticmethod(unsupported_poll)
