"""Provider-facing prompt and metadata rules."""

from typing import Any, Optional

from app.features.video_generation.constants import PROVIDER_VIDEO_WATERMARK_ENABLED
from app.features.video_generation.schemas import VideoGenerateRequest


def provider_image_url_error_message(exc: Exception, provider_image_url: Optional[str]) -> Optional[str]:
    error_text = str(exc)
    if "image_url" not in error_text:
        return None
    if not any(marker in error_text for marker in ("InvalidParameter", "not valid", "BadRequest")):
        return None
    if provider_image_url:
        return (
            "参考图地址已提交给云端视频模型，但模型拒绝了该图片 URL。请确认图片是可公网访问、未过期的 http(s) 地址，"
            f"或改用无参考图模式后重试。原始错误：{error_text}"
        )
    return (
        "参考图不是可公网访问的 URL，已不应传给云端视频模型；请重新生成/上传公网可访问参考图，"
        f"或使用无参考图模式后重试。原始错误：{error_text}"
    )


def append_provider_image_note(prompt: str, omission_reason: Optional[str]) -> str:
    if not omission_reason:
        return prompt
    return (
        f"{prompt}\n\n参考图接入说明：{omission_reason}，本次云端调用不传 image_url；"
        "请依据上文角色视觉DNA、场景、道具、风格锁和剧情连续性生成，保持人物形象与分镜逻辑一致。"
    )


def video_prompt_parameters(
    request: VideoGenerateRequest,
    seed: Optional[int],
    provider_image_url: Optional[str] = None,
    image_url_omitted_reason: Optional[str] = None,
    image_delivery: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    parameters = {
        "duration": request.duration, "resolution": request.resolution,
        "camera_fixed": False, "watermark": PROVIDER_VIDEO_WATERMARK_ENABLED, "seed": seed,
        "image_url": request.image_url, "provider_image_url": provider_image_url,
        "image_url_sent": bool(provider_image_url), "model_config_id": request.model_config_id,
    }
    if request.image_url and image_url_omitted_reason:
        parameters["image_url_omitted_reason"] = image_url_omitted_reason
    if image_delivery:
        parameters.update(
            image_delivery_method=image_delivery.get("delivery_method"),
            image_delivery_config_id=image_delivery.get("storage_config_id"),
            image_delivery_provider=image_delivery.get("storage_provider_name"),
        )
    return parameters


def video_model_metadata(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_id": config.get("provider_id"), "provider_name": config.get("provider_name"),
        "model_config_id": config.get("model_config_id"), "config_model_id": config.get("config_model_id"),
        "api_model_id": config.get("api_model_id"), "model_endpoint_id": config.get("model_endpoint_id"),
        "model_type": config.get("model_type"), "model_test_status": config.get("test_status"),
        "model_capabilities": config.get("capabilities") or [],
    }
