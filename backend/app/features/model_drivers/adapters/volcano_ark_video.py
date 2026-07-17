"""Volcano Ark video driver delegating to VolcanoService."""

from app.features.model_drivers.adapters._shared import completed_output, connection_test
from app.features.model_drivers.domain import VideoCommand


class VolcanoArkVideoDriver:
    key = "volcano_ark_video_v3"
    capabilities = frozenset({"video_generation"})

    async def test_connection(self, context):
        return await connection_test(
            lambda: self.submit(VideoCommand(prompt="模型中心连接测试"), context),
            "火山 Ark 视频模型连接成功",
        )

    async def submit(self, command, context):
        from app.services.volcano_service import VolcanoService

        params = dict(command.params)
        image_url = command.reference_images[0] if command.reference_images else None
        result = await VolcanoService(context.api_key, context.base_url).generate_video(
            prompt=command.prompt,
            model=context.profile.api_model_id,
            image_url=image_url,
            **params,
        )
        return completed_output(result)

    async def poll(self, provider_task_id, context):
        from app.services.volcano_service import VolcanoService

        result = await VolcanoService(context.api_key, context.base_url).get_video_status(
            provider_task_id, model=context.profile.api_model_id
        )
        return completed_output(result)
