"""Provider-neutral command and driver contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, TypeAlias

from app.features.model_config import ModelProfileContract


@dataclass(frozen=True)
class TextCommand:
    capability: Literal["text_generation"] = "text_generation"
    prompt: str = ""
    output_contract: str = "plain_text"
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageCommand:
    capability: Literal["image_generation"] = "image_generation"
    prompt: str = ""
    reference_images: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeechCommand:
    capability: Literal["speech_generation"] = "speech_generation"
    text: str = ""
    voice_id: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoCommand:
    capability: Literal["video_generation"] = "video_generation"
    prompt: str = ""
    reference_images: tuple[str, ...] = ()
    reference_videos: tuple[str, ...] = ()
    reference_audios: tuple[str, ...] = ()
    native_audio: bool = False
    dialogue_contract: Mapping[str, Any] | None = None
    params: Mapping[str, Any] = field(default_factory=dict)


Command: TypeAlias = TextCommand | ImageCommand | SpeechCommand | VideoCommand


@dataclass(frozen=True)
class DriverContext:
    profile: ModelProfileContract
    driver_key: str
    connection_id: str | None
    secrets: Mapping[str, str] = field(default_factory=dict, repr=False)
    execution_snapshot_id: str | None = None


@dataclass(frozen=True)
class DriverTestResult:
    status: str
    message: str
    sanitized_evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DriverSubmission:
    status: str
    provider_task_id: str | None
    output: Mapping[str, Any] = field(default_factory=dict)


class CapabilityDriver(Protocol):
    key: str
    capabilities: frozenset[str]

    async def test_connection(self, context: DriverContext) -> DriverTestResult: ...

    async def submit(self, command: Command, context: DriverContext) -> DriverSubmission: ...

    async def poll(self, provider_task_id: str, context: DriverContext) -> DriverSubmission: ...


class DriverError(RuntimeError):
    """Base error for safe, provider-neutral driver execution failures."""


class DriverUnavailableError(DriverError):
    def __init__(self, key: str):
        super().__init__(f"driver '{key}' is not installed")


class DriverRegistrationError(DriverError):
    pass


class DriverCapabilityError(DriverError):
    def __init__(self, driver_key: str, capability: str):
        super().__init__(f"driver '{driver_key}' does not support capability '{capability}'")


class DriverParameterError(DriverError):
    pass


class DriverSchemaError(DriverError):
    pass


class DriverLimitError(DriverError):
    pass


class DriverResultError(DriverError):
    pass


__all__ = [
    "CapabilityDriver",
    "Command",
    "DriverCapabilityError",
    "DriverContext",
    "DriverError",
    "DriverLimitError",
    "DriverParameterError",
    "DriverRegistrationError",
    "DriverResultError",
    "DriverSchemaError",
    "DriverSubmission",
    "DriverTestResult",
    "DriverUnavailableError",
    "ImageCommand",
    "SpeechCommand",
    "TextCommand",
    "VideoCommand",
]
