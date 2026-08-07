"""Execute an already-built video request through its selected model driver."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.features.model_drivers.public import (
    DriverError,
    DriverUnavailableError,
    VideoCommand,
    VideoReference,
    build_builtin_driver_registry,
    execute_generation,
)
from app.features.model_config.public import ExecutionSnapshotCommand, create_execution_snapshot
from app.features.video_generation.adapters.ark import submit_ark_video_task
from app.features.video_generation.errors import VideoGenerationError


@dataclass(frozen=True)
class SubmittedVideoTask:
    id: str


def _references(content: list[dict[str, Any]]) -> tuple[VideoReference, ...]:
    references: list[VideoReference] = []
    media_types = {"image_url": "image", "video_url": "video", "audio_url": "audio"}
    for item in content:
        item_type = item.get("type") if isinstance(item, dict) else None
        value = item.get(item_type) if item_type in media_types else None
        url = value.get("url") if isinstance(value, dict) else None
        if isinstance(url, str) and url:
            media_type = media_types[item_type]
            references.append(VideoReference(
                media_type,
                url,
                str(item.get("role") or f"reference_{media_type}"),
            ))
    return tuple(references)


def build_video_command(
    *, prompt: str, content: list[dict[str, Any]], params: dict[str, Any], native_audio: bool = False,
) -> VideoCommand:
    references = _references(content)
    return VideoCommand(
        prompt=prompt,
        reference_images=tuple(item.url for item in references if item.media_type == "image"),
        reference_videos=tuple(item.url for item in references if item.media_type == "video"),
        reference_audios=tuple(item.url for item in references if item.media_type == "audio"),
        references=references,
        native_audio=native_audio,
        params=params,
    )


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
    execution_snapshot_id: str | None = None,
) -> Any:
    if generation_context is None:
        return submit_ark_video_task(create_kwargs=create_kwargs, client=client)
    params = {
        **dict(generation_context.profile.default_params),
        **{key: create_kwargs[key] for key in ("duration", "resolution", "ratio", "camera_fixed", "watermark", "seed") if key in create_kwargs},
    }
    try:
        submission = await execute_generation(
            build_builtin_driver_registry(),
            build_video_command(
                prompt=prompt,
                content=create_kwargs.get("content") or [],
                params=params,
                native_audio=bool(create_kwargs.get("generate_audio")),
            ),
            replace(generation_context.driver_context, execution_snapshot_id=execution_snapshot_id)
            if execution_snapshot_id else generation_context.driver_context,
        )
    except DriverError as error:
        raise VideoGenerationError(422, str(error)) from error
    if not submission.provider_task_id:
        raise VideoGenerationError(422, "视频驱动未返回可轮询的任务标识")
    return SubmittedVideoTask(submission.provider_task_id)


async def create_bound_video_execution_snapshot(
    db: Any, *, user_id: str, generation_context: Any, job_id: str,
    create_kwargs: dict[str, Any],
) -> str | None:
    if generation_context is None:
        return None
    references = _references(create_kwargs.get("content") or [])
    images = [item for item in references if item.media_type == "image"]
    videos = [item for item in references if item.media_type == "video"]
    audios = [item for item in references if item.media_type == "audio"]
    snapshot = await create_execution_snapshot(
        db,
        ExecutionSnapshotCommand(
            user_id=user_id, run_id=None, job_id=job_id,
            task=generation_context.binding.task,
            capability=generation_context.binding.capability,
            binding=generation_context.binding,
            recipe_version_id=getattr(generation_context, "recipe_version_id", None),
            prompt_profile_version_id=getattr(generation_context, "prompt_profile_version_id", None),
            sanitized_params={
                "duration": create_kwargs.get("duration"),
                "resolution": create_kwargs.get("resolution"),
                "native_audio": bool(create_kwargs.get("generate_audio")),
                "reference_image_count": len(images),
                "reference_video_count": len(videos),
                "reference_audio_count": len(audios),
                "seed": create_kwargs.get("seed"),
            },
        ),
    )
    return snapshot.id


__all__ = [
    "SubmittedVideoTask", "build_video_command", "create_bound_video_execution_snapshot",
    "has_video_generation_driver", "submit_bound_video_task",
]
