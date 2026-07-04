"""Translate reference packages into provider content payloads."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


REFERENCE_IMAGE_ROLE = "reference_image"
REFERENCE_VIDEO_ROLE = "reference_video"
REFERENCE_AUDIO_ROLE = "reference_audio"


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _bool_arg(value: bool) -> str:
    return "true" if value else "false"


def _text_content(
    prompt: str,
    *,
    duration: int,
    resolution: str,
    camera_fixed: bool,
    watermark: bool,
) -> Dict[str, Any]:
    return {
        "type": "text",
        "text": (
            f"{prompt} --duration {duration} --resolution {resolution} "
            f"--camerafixed {_bool_arg(camera_fixed)} --watermark {_bool_arg(watermark)}"
        ),
    }


def _content_url(item: Any) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    url = item.get("url")
    return str(url) if url else None


def _model_limit(model_limits: Optional[Dict[str, Any]], key: str, default: int) -> int:
    limits = model_limits if isinstance(model_limits, dict) else {}
    return _positive_int(limits.get(key), default)


def build_video_provider_content(
    *,
    final_prompt: str,
    duration: int,
    resolution: str,
    provider_image_url: Optional[str] = None,
    reference_package: Optional[Dict[str, Any]] = None,
    model_limits: Optional[Dict[str, Any]] = None,
    camera_fixed: bool = False,
    watermark: bool = True,
) -> Dict[str, Any]:
    """Build Ark content while preserving the legacy single-image shape."""
    package = reference_package if isinstance(reference_package, dict) else {}
    image_limit = _model_limit(model_limits, "images", 1)
    video_limit = _model_limit(model_limits, "videos", 0)
    audio_limit = _model_limit(model_limits, "audios", 0)
    package_images = [item for item in package.get("images") or [] if _content_url(item)]
    package_videos = [item for item in package.get("videos") or [] if _content_url(item)]
    package_audios = [item for item in package.get("audios") or [] if _content_url(item)]

    if image_limit <= 0:
        content = [
            _text_content(
                final_prompt,
                duration=duration,
                resolution=resolution,
                camera_fixed=camera_fixed,
                watermark=watermark,
            )
        ]
        return {
            "content": content,
            "mode": "text_only",
            "metadata": {
                "mode": "text_only",
                "image_count": 0,
                "video_count": 0,
                "audio_count": 0,
                "dropped_image_count": len(package_images) + (1 if provider_image_url else 0),
            },
        }

    if image_limit > 1 and package_images:
        images = package_images[:image_limit]
        videos = package_videos[:video_limit] if video_limit > 0 else []
        audios = package_audios[:audio_limit] if audio_limit > 0 else []
        content: List[Dict[str, Any]] = [
            {
                "type": "image_url",
                "image_url": {"url": _content_url(item)},
                "role": REFERENCE_IMAGE_ROLE,
            }
            for item in images
        ]
        content.extend(
            {
                "type": "video_url",
                "video_url": {"url": _content_url(item)},
                "role": REFERENCE_VIDEO_ROLE,
            }
            for item in videos
        )
        content.extend(
            {
                "type": "audio_url",
                "audio_url": {"url": _content_url(item)},
                "role": REFERENCE_AUDIO_ROLE,
            }
            for item in audios
        )
        at_reference_text = package.get("at_reference_text")
        prompt = f"{at_reference_text}\n{final_prompt}" if at_reference_text else final_prompt
        content.append(
            _text_content(
                prompt,
                duration=duration,
                resolution=resolution,
                camera_fixed=camera_fixed,
                watermark=watermark,
            )
        )
        return {
            "content": content,
            "mode": "multimodal",
            "metadata": {
                "mode": "multimodal",
                "image_count": len(images),
                "video_count": len(videos),
                "audio_count": len(audios),
            },
        }

    content = []
    if provider_image_url:
        content.append({"type": "image_url", "image_url": {"url": provider_image_url}})
    content.append(
        _text_content(
            final_prompt,
            duration=duration,
            resolution=resolution,
            camera_fixed=camera_fixed,
            watermark=watermark,
        )
    )
    return {
        "content": content,
        "mode": "single_image",
        "metadata": {
            "mode": "single_image",
            "image_count": 1 if provider_image_url else 0,
            "video_count": 0,
            "audio_count": 0,
        },
    }


def build_reference_package_metadata(
    reference_package: Optional[Dict[str, Any]],
    provider_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Return the compact job metadata persisted with generation tasks."""
    package = reference_package if isinstance(reference_package, dict) else {}
    items: List[Dict[str, Any]] = []
    for item in package.get("images") or []:
        if isinstance(item, dict):
            items.append({"type": "image", **item})
    for item in package.get("videos") or []:
        if isinstance(item, dict):
            items.append({"type": "video", **item})
    for item in package.get("audios") or []:
        if isinstance(item, dict):
            items.append({"type": "audio", **item})

    return {
        **dict(provider_metadata or {}),
        "items": items,
        "dropped": package.get("dropped") or [],
    }


def enrich_prompt_parameters_with_reference_contract(
    parameters: Dict[str, Any],
    provider_metadata: Dict[str, Any],
    model_limits: Optional[Dict[str, Any]] = None,
    model_protocol: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Attach the actual provider reference payload shape to job parameters."""
    params = dict(parameters or {})
    metadata = provider_metadata if isinstance(provider_metadata, dict) else {}
    limits = model_limits if isinstance(model_limits, dict) else {}
    protocol = model_protocol if isinstance(model_protocol, dict) else {}
    image_limit = _model_limit(limits, "images", 1)
    image_count = _positive_int(metadata.get("image_count"), 0)
    video_count = _positive_int(metadata.get("video_count"), 0)
    audio_count = _positive_int(metadata.get("audio_count"), 0)

    params["model_input_mode"] = protocol.get("input_mode") or (
        "text" if image_limit <= 0 else "reference_images_text" if image_limit > 1 else "image_text"
    )
    params["provider_reference_image_count"] = image_count
    params["provider_reference_video_count"] = video_count
    params["provider_reference_audio_count"] = audio_count
    params["reference_image_capacity"] = image_limit
    params["image_url_sent"] = image_count > 0
    if not params["image_url_sent"]:
        params["provider_image_url"] = None
    if metadata.get("dropped_image_count"):
        params["dropped_reference_image_count"] = metadata["dropped_image_count"]
    return params
