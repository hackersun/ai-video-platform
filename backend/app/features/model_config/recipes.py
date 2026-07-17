"""Pure anime production recipe contracts and validation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, TypedDict

from app.features.model_config.domain import (
    VERIFIED_CONNECTION_STATUSES,
    RecipeBindingContract,
    is_safe_model_binding_scope,
)


class RecipeStage(TypedDict, total=False):
    binding_id: str
    required: bool
    params: dict[str, Any]


class ProductionRecipeSpec(TypedDict):
    text: RecipeStage
    vision: RecipeStage
    image: RecipeStage
    video: RecipeStage
    audio: dict[str, Any]
    subtitle: dict[str, Any]
    render: RecipeStage
    storage: RecipeStage


@dataclass(frozen=True)
class RecipeError:
    code: str
    message: str
    stage: str | None = None
    binding_id: str | None = None


class RecipeValidationError(ValueError):
    def __init__(self, errors: list[RecipeError]):
        self.errors = tuple(errors)
        super().__init__(", ".join(error.code for error in errors))


STAGE_REQUIREMENTS = {
    "text": ("script_generation", "text_generation"),
    "vision": ("shot_vision", "vision_analysis"),
    "image": ("shot_image", "image_generation"),
    "video": ("shot_video", "video_generation"),
    "audio": ("shot_speech", "speech_generation"),
    "subtitle": ("shot_subtitle", "subtitle_generation"),
    "render": ("workflow_render", "media_render"),
    "storage": ("workflow_storage", "object_storage"),
}
SUBTITLE_SOURCE_BY_AUDIO_MODE = {
    "video_native_audio": "video_dialogue_timeline",
    "separate_tts": "tts_timeline",
}


def stable_recipe_checksum(spec: Mapping[str, Any]) -> str:
    payload = json.dumps(
        spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _stage(spec: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = spec.get(name, {})
    return value if isinstance(value, Mapping) else {}


def recipe_binding_references(spec: Mapping[str, Any]) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    for stage in ("text", "vision", "image", "video", "render", "storage"):
        binding_id = _stage(spec, stage).get("binding_id")
        if isinstance(binding_id, str) and binding_id:
            references.append((stage, binding_id))
    audio = _stage(spec, "audio")
    if audio.get("mode") == "separate_tts" and audio.get("binding_id"):
        references.append(("audio", str(audio["binding_id"])))
    subtitle = _stage(spec, "subtitle")
    if subtitle.get("binding_id"):
        references.append(("subtitle", str(subtitle["binding_id"])))
    return references


def _basic_errors(spec: Mapping[str, Any]) -> list[RecipeError]:
    errors: list[RecipeError] = []
    for stage in ("text", "vision", "image", "video", "render", "storage"):
        values = _stage(spec, stage)
        required = stage in {"video", "render", "storage"} or values.get("required") is True
        if required and not values.get("binding_id"):
            errors.append(RecipeError(f"{stage}_binding_required", "缺少必需的阶段绑定", stage))
    audio = _stage(spec, "audio")
    mode = audio.get("mode")
    if mode == "video_native_audio":
        if audio.get("binding_id"):
            errors.append(RecipeError(
                "tts_binding_forbidden_for_native_audio", "原生音频方案不能同时绑定 TTS", "audio",
            ))
    elif mode == "separate_tts":
        if not audio.get("binding_id"):
            errors.append(RecipeError(
                "tts_binding_required", "独立配音方案必须绑定声音模型", "audio",
            ))
    else:
        errors.append(RecipeError(
            "audio_mode_invalid", "声音方案必须选择原生音频或独立 TTS", "audio",
        ))
    subtitle_source = _stage(spec, "subtitle").get("source")
    if not subtitle_source:
        errors.append(RecipeError(
            "subtitle_source_required", "生产方案必须声明字幕来源", "subtitle",
        ))
    elif mode in SUBTITLE_SOURCE_BY_AUDIO_MODE and subtitle_source != SUBTITLE_SOURCE_BY_AUDIO_MODE[mode]:
        errors.append(RecipeError(
            "subtitle_source_invalid_for_audio_mode", "字幕来源与声音方案不匹配", "subtitle",
        ))
    return errors


def _binding_errors(
    spec: Mapping[str, Any],
    bindings: Mapping[str, RecipeBindingContract],
    user_id: str | None,
) -> list[RecipeError]:
    errors: list[RecipeError] = []
    for stage, binding_id in recipe_binding_references(spec):
        binding = bindings.get(binding_id)
        if binding is None:
            errors.append(RecipeError("binding_missing", "引用的绑定不存在", stage, binding_id))
            continue
        expected_task, expected_capability = STAGE_REQUIREMENTS[stage]
        if binding.task != expected_task:
            errors.append(RecipeError(
                "binding_task_mismatch", "绑定任务与生产阶段不匹配", stage, binding_id,
            ))
        if (
            binding.capability != expected_capability
            or expected_capability not in binding.profile_capabilities
        ):
            errors.append(RecipeError(
                "binding_capability_mismatch", "绑定能力与生产阶段不匹配", stage, binding_id,
            ))
        if not binding.is_active:
            errors.append(RecipeError("binding_inactive", "绑定未启用", stage, binding_id))
        if binding.profile_status != "published":
            errors.append(RecipeError(
                "binding_profile_not_published", "绑定的模型版本未发布", stage, binding_id,
            ))
        if not binding.model_enabled or not binding.provider_enabled:
            errors.append(RecipeError(
                "binding_owner_disabled", "绑定的模型或供应商已停用", stage, binding_id,
            ))
        if binding.connection_status not in VERIFIED_CONNECTION_STATUSES:
            errors.append(RecipeError(
                "binding_connection_not_verified", "绑定连接未验证", stage, binding_id,
            ))
        safe_scope = is_safe_model_binding_scope(
            scope_type=binding.scope_type,
            owner_id=binding.owner_id,
            scope_id=binding.scope_id,
        )
        if not safe_scope:
            errors.append(RecipeError(
                "binding_scope_invalid", "绑定作用域不安全或不属于其所有者", stage, binding_id,
            ))
        is_system_scope = binding.scope_type == "system"
        trusted_system = is_system_scope and safe_scope
        if user_id and binding.owner_id != user_id and not trusted_system and not is_system_scope:
            errors.append(RecipeError(
                "binding_owner_mismatch", "绑定不属于当前用户", stage, binding_id,
            ))
        if binding.connection_owner_id != binding.owner_id:
            errors.append(RecipeError(
                "binding_owner_mismatch", "连接与绑定归属不一致", stage, binding_id,
            ))
        if not binding.connection_matches_profile:
            errors.append(RecipeError(
                "binding_connection_mismatch", "连接供应商与模型不匹配", stage, binding_id,
            ))
    video_binding_id = _stage(spec, "video").get("binding_id")
    video = bindings.get(str(video_binding_id)) if video_binding_id else None
    if _stage(spec, "audio").get("mode") == "video_native_audio" and (
        video is None or "native_audio" not in video.profile_capabilities
    ):
        errors.append(RecipeError(
            "native_audio_capability_required", "当前视频模型不支持原生音频", "video",
            str(video_binding_id) if video_binding_id else None,
        ))
    return errors


def validate_recipe(
    spec: Mapping[str, Any],
    resolved_bindings: Mapping[str, RecipeBindingContract] | None = None,
    *,
    user_id: str | None = None,
) -> list[RecipeError]:
    errors = _basic_errors(spec)
    if resolved_bindings is not None:
        errors.extend(_binding_errors(spec, resolved_bindings, user_id))
    elif _stage(spec, "audio").get("mode") == "video_native_audio":
        declared = _stage(spec, "video").get("capabilities")
        if declared is not None and "native_audio" not in declared:
            errors.append(RecipeError(
                "native_audio_capability_required", "当前视频模型不支持原生音频", "video",
            ))
    return errors


__all__ = [
    "ProductionRecipeSpec",
    "RecipeBindingContract",
    "RecipeError",
    "RecipeStage",
    "RecipeValidationError",
    "stable_recipe_checksum",
    "validate_recipe",
]
