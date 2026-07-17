"""Volcano Ark video driver delegating to the production content/submission boundary."""

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
        params = dict(command.params)
        from app.features.video_generation.adapters import ark
        from app.features.video_generation.constants import PROVIDER_VIDEO_WATERMARK_ENABLED
        from app.services.video_reference_adapter import build_video_provider_content

        duration = int(params.pop("duration", 5))
        resolution = str(params.pop("resolution", "720p"))
        camera_fixed = bool(params.pop("camera_fixed", False))
        watermark = bool(params.pop("watermark", PROVIDER_VIDEO_WATERMARK_ENABLED))
        seed = params.pop("seed", None)
        reference_package = {
            "images": [{"url": url} for url in command.reference_images],
            "videos": [{"url": url} for url in command.reference_videos],
            "audios": [{"url": url} for url in command.reference_audios],
        }
        content = build_video_provider_content(
            final_prompt=command.prompt, duration=duration, resolution=resolution,
            reference_package=reference_package, model_limits=dict(context.profile.limits),
            model_id=context.profile.api_model_id, provider=context.profile.provider_id,
            camera_fixed=camera_fixed, watermark=watermark,
        )
        create_kwargs = ark.build_ark_video_create_kwargs(
            model=context.profile.api_model_id, content=content["content"], duration=duration,
            resolution=resolution, camera_fixed=camera_fixed, watermark=watermark,
            generate_audio=command.native_audio, seed=seed,
        )
        result = ark.submit_ark_video_task(
            api_key=context.api_key, base_url=context.base_url, create_kwargs=create_kwargs,
        )
        task_id = getattr(result, "id", None) or (result.get("id") if isinstance(result, dict) else None)
        return completed_output({
            "task_id": task_id, "provider_metadata": content["metadata"],
            "dialogue_contract": command.dialogue_contract,
        })

    async def poll(self, provider_task_id, context):
        from app.services.volcano_service import VolcanoService

        result = await VolcanoService(context.api_key, context.base_url).get_video_status(
            provider_task_id, model=context.profile.api_model_id
        )
        return completed_output(result)
