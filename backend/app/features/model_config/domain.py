"""Provider-neutral model configuration domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Mapping, Sequence


ModelCapability = Literal[
    "text_generation",
    "vision_analysis",
    "image_generation",
    "speech_generation",
    "video_generation",
    "subtitle_generation",
    "media_render",
    "object_storage",
]


class ProfileStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class CertificationLevel(str, Enum):
    NONE = "none"
    CONNECTION = "connection"
    CONTRACT = "contract"
    LIVE = "live"


class BindingScope(str, Enum):
    REQUEST = "request"
    SERIES = "series"
    PROJECT = "project"
    USER = "user"
    SYSTEM = "system"


CAPABILITY_ALIASES: dict[str, ModelCapability] = {
    "chat": "text_generation",
    "completion": "text_generation",
    "text-generation": "text_generation",
    "vision": "vision_analysis",
    "vision-analysis": "vision_analysis",
    "image-understanding": "vision_analysis",
    "image": "image_generation",
    "image-generation": "image_generation",
    "text-to-image": "image_generation",
    "tts": "speech_generation",
    "audio": "speech_generation",
    "speech-generation": "speech_generation",
    "text-to-speech": "speech_generation",
    "video": "video_generation",
    "video-generation": "video_generation",
    "text-to-video": "video_generation",
    "image-to-video": "video_generation",
    "subtitle-generation": "subtitle_generation",
    "render": "media_render",
    "media-render": "media_render",
    "storage": "object_storage",
    "object-storage": "object_storage",
}


def normalize_capabilities(model_type: str | None, capabilities: Sequence[str]) -> set[ModelCapability]:
    values = [str(model_type or "").lower(), *(str(item).lower() for item in capabilities)]
    return {
        CAPABILITY_ALIASES[value.replace("_", "-")]
        for value in values
        if value.replace("_", "-") in CAPABILITY_ALIASES
    }


@dataclass(frozen=True)
class ModelProfileContract:
    profile_version_id: str
    provider_id: str
    api_model_id: str
    driver_key: str
    capabilities: frozenset[ModelCapability]
    input_contract: Mapping[str, Any]
    output_contract: Mapping[str, Any]
    parameter_schema: Mapping[str, Any]
    default_params: Mapping[str, Any]
    limits: Mapping[str, Any]
    pricing: Mapping[str, Any]
    prompt_profile_key: str | None
    contract_version: str


@dataclass(frozen=True)
class ResolvedModelBinding:
    task: str
    capability: ModelCapability
    profile: ModelProfileContract
    connection_id: str | None
    binding_version: int
    source_scope: Literal["request", "series", "project", "user", "system", "legacy"]


__all__ = [
    "BindingScope",
    "CAPABILITY_ALIASES",
    "CertificationLevel",
    "ModelCapability",
    "ModelProfileContract",
    "ProfileStatus",
    "ResolvedModelBinding",
    "normalize_capabilities",
]
