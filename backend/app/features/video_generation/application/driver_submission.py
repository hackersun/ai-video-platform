"""Execute an already-built video request through its selected model driver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.features.model_drivers.public import (
    DriverError,
    DriverUnavailableError,
    VideoCommand,
    build_builtin_driver_registry,
    execute_generation,
)
from app.features.video_generation.adapters.ark import submit_ark_video_task
from app.features.video_generation.errors import VideoGenerationError


@dataclass(frozen=True)
class SubmittedVideoTask:
    id: str


def _references(content: list[dict[str, Any]]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    values = {"image_url": [], "video_url": [], "audio_url": []}
    for item in content:
        item_type = item.get("type") if isinstance(item, dict) else None
        value = item.get(item_type) if item_type in values else None
        url = value.get("url") if isinstance(value, dict) else None
        if isinstance(url, str) and url:
            values[item_type].append(url)
    return tuple(values["image_url"]), tuple(values["video_url"]), tuple(values["audio_url"])


def has_video_generation_driver(generation_context: Any) -> bool:
    if generation_context is None:
        return False
    try:
        build_builtin_driver_registry().require(generation_context.driver_context.driver_key)
    except DriverUnavailableError:
        return False
    return True


async def submit_bound_video_task(
    generation_context: Any, prompt: str, create_kwargs: dict[str, Any], client: Any,
) -> Any:
    if generation_context is None:
        return submit_ark_video_task(create_kwargs=create_kwargs, client=client)
    images, videos, audios = _references(create_kwargs.get("content") or [])
    params = {
        **dict(generation_context.profile.default_params),
        **{key: create_kwargs[key] for key in ("duration", "resolution", "camera_fixed", "watermark", "seed") if key in create_kwargs},
    }
    try:
        submission = await execute_generation(
            build_builtin_driver_registry(),
            VideoCommand(
                prompt=prompt, reference_images=images, reference_videos=videos, reference_audios=audios,
                native_audio=bool(create_kwargs.get("generate_audio")), params=params,
            ),
            generation_context.driver_context,
        )
    except DriverError as error:
        raise VideoGenerationError(422, str(error)) from error
    if not submission.provider_task_id:
        raise VideoGenerationError(422, "视频驱动未返回可轮询的任务标识")
    return SubmittedVideoTask(submission.provider_task_id)


__all__ = ["SubmittedVideoTask", "has_video_generation_driver", "submit_bound_video_task"]
