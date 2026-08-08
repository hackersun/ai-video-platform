"""Official MiniMax H3 video-generation capability contract."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


MINIMAX_H3_MODEL_ID = "MiniMax-H3"
MINIMAX_H3_DRIVER_KEY = "minimax_h3_video_v2"
MINIMAX_H3_RESOLUTIONS = ("768P", "2K")
MINIMAX_H3_RATIOS = ("adaptive", "16:9", "9:16", "1:1", "4:3", "3:4")


def h3_reference_limits() -> dict[str, int]:
    return {"images": 9, "videos": 3, "audios": 3, "total": 12}


def h3_parameter_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "duration": {"type": "integer", "minimum": 4, "maximum": 15},
            "resolution": {"type": "string", "enum": list(MINIMAX_H3_RESOLUTIONS)},
            "ratio": {"type": "string", "enum": list(MINIMAX_H3_RATIOS)},
        },
        "required": ["duration", "resolution", "ratio"],
        "additionalProperties": False,
    }


def _issue(code: str, message: str, field: str) -> dict[str, str]:
    return {"code": code, "message": message, "field": field}


def validate_h3_generation(
    *,
    prompt: str,
    duration: int,
    resolution: str,
    ratio: str,
    references: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if len(prompt) > 7000:
        issues.append(_issue("prompt_too_long", "提示词不能超过 7000 个字符。", "prompt"))
    if not isinstance(duration, int) or isinstance(duration, bool) or not 4 <= duration <= 15:
        issues.append(_issue("duration_out_of_range", "MiniMax H3 时长必须是 4–15 秒的整数。", "duration"))
    if resolution not in MINIMAX_H3_RESOLUTIONS:
        issues.append(_issue("resolution_not_supported", "MiniMax H3 分辨率仅支持 768P、2K。", "resolution"))
    if ratio not in MINIMAX_H3_RATIOS:
        issues.append(_issue("ratio_not_supported", "MiniMax H3 不支持当前宽高比。", "ratio"))

    counts = Counter(str(item.get("media_type") or "") for item in references)
    limits = h3_reference_limits()
    for media_type, key, label in (
        ("image", "images", "图片"),
        ("video", "videos", "视频"),
        ("audio", "audios", "音频"),
    ):
        if counts[media_type] > limits[key]:
            issues.append(_issue(
                f"reference_{key}_exceeded",
                f"MiniMax H3 最多支持 {limits[key]} 个{label}参考。",
                f"reference_{key}",
            ))
    if len(references) > limits["total"]:
        issues.append(_issue(
            "reference_total_exceeded",
            "MiniMax H3 图片、视频和音频参考合计不能超过 12 个。",
            "references",
        ))
    return issues


__all__ = [
    "MINIMAX_H3_DRIVER_KEY",
    "MINIMAX_H3_MODEL_ID",
    "MINIMAX_H3_RATIOS",
    "MINIMAX_H3_RESOLUTIONS",
    "h3_parameter_schema",
    "h3_reference_limits",
    "validate_h3_generation",
]
