"""Provider-neutral validation for configurable video model capabilities."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


REFERENCE_LIMIT_KEYS = ("reference_images", "reference_videos", "reference_audios")


def _error(code: str, message: str, field: str) -> dict[str, str]:
    return {"code": code, "message": message, "field": field}


def validate_video_capability_contract(
    capabilities: Sequence[str],
    input_contract: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> list[dict[str, str]]:
    if "video_generation" not in capabilities:
        return []
    errors: list[dict[str, str]] = []
    minimum = limits.get("duration_min")
    maximum = limits.get("duration_max")
    if minimum is not None and (not isinstance(minimum, int) or minimum <= 0):
        errors.append(_error("duration_range_invalid", "最小时长必须是正整数。", "limits.duration_min"))
    elif maximum is not None and (not isinstance(maximum, int) or maximum <= 0):
        errors.append(_error("duration_range_invalid", "最大时长必须是正整数。", "limits.duration_max"))
    elif minimum is not None and maximum is not None and minimum > maximum:
        errors.append(_error("duration_range_invalid", "最小时长不能大于最大时长。", "limits.duration_max"))
    if any(not isinstance(limits.get(key), int) or limits.get(key) < 0 for key in REFERENCE_LIMIT_KEYS if key in limits):
        errors.append(_error("reference_limit_invalid", "参考素材数量必须是非负整数。", "limits"))
    resolutions = limits.get("resolutions")
    if resolutions is not None and (
        not isinstance(resolutions, list)
        or not resolutions
        or any(not isinstance(item, str) or not item.strip() for item in resolutions)
    ):
        errors.append(_error("resolution_list_invalid", "分辨率必须是非空字符串列表。", "limits.resolutions"))
    family = str(input_contract.get("family") or "").strip()
    if family == "seedance_2_5":
        errors.append(_error(
            "model_family_not_available",
            "官方模型目录尚未发布 Seedance 2.5；可保留兼容草稿，但不能实模验证、发布或设为默认。",
            "input_contract.family",
        ))
    if family == "seedance_2_5" and input_contract.get("verification_status") != "experimental":
        errors.append(_error(
            "seedance_25_experimental_required",
            "Seedance 2.5 在完成官方契约与实模认证前只能保存为实验模型。",
            "input_contract.verification_status",
        ))
    return errors


__all__ = ["validate_video_capability_contract"]
