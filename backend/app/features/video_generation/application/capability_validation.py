"""Validate request parameters against the selected persisted video contract."""

from collections.abc import Mapping
from typing import Any

from app.features.video_generation.errors import VideoGenerationError


def reference_limits_from_contract(
    limits: Mapping[str, Any], fallback: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(fallback)
    for source, target in (
        ("reference_images", "images"),
        ("reference_videos", "videos"),
        ("reference_audios", "audios"),
        ("native_audio", "native_audio"),
    ):
        if source in limits:
            result[target] = limits[source]
    return result


def validate_video_generation_parameters(
    *, duration: int, resolution: str, limits: Mapping[str, Any],
) -> None:
    durations = limits.get("durations")
    minimum = limits.get("duration_min")
    maximum = limits.get("duration_max")
    if isinstance(durations, list) and durations and duration not in durations:
        supported = "、".join(str(value) for value in durations)
        raise VideoGenerationError(422, f"当前模型仅支持 {supported} 秒时长。")
    if isinstance(minimum, int) and isinstance(maximum, int) and not minimum <= duration <= maximum:
        raise VideoGenerationError(422, f"当前模型支持 {minimum}–{maximum} 秒时长。")
    resolutions = limits.get("resolutions")
    if isinstance(resolutions, list) and resolutions and resolution not in resolutions:
        supported = "、".join(str(value) for value in resolutions)
        raise VideoGenerationError(422, f"当前模型仅支持 {supported} 分辨率。")


__all__ = ["reference_limits_from_contract", "validate_video_generation_parameters"]
