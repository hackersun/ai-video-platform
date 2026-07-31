"""Volcano Ark image driver delegating to VolcanoService."""

from app.features.model_drivers.adapters._shared import completed_output, connection_test, unsupported_poll
from app.features.model_drivers.domain import ImageCommand


class VolcanoArkImageDriver:
    key = "volcano_ark_image_v3"
    capabilities = frozenset({"image_generation"})

    async def test_connection(self, context):
        return await connection_test(
            lambda: self.submit(ImageCommand(prompt="模型中心连接测试"), context),
            "火山 Ark 图像模型连接成功",
        )

    async def submit(self, command, context):
        from app.services.volcano_service import VolcanoService

        result = await VolcanoService(context.api_key, context.base_url).generate_image(
            command.prompt, model=context.profile.api_model_id,
            **({"image": list(command.reference_images)} if command.reference_images else {}),
            **dict(command.params),
        )
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            image_urls = [
                str(item["url"]) for item in result["data"]
                if isinstance(item, dict) and item.get("url")
            ]
            if image_urls:
                result = {**result, "image_urls": image_urls}
        return completed_output(result)

    poll = staticmethod(unsupported_poll)
