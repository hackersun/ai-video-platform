"""Provider-neutral command and driver contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, TypeAlias


@dataclass(frozen=True)
class TextCommand:
    capability: Literal["text_generation"] = field(default="text_generation", init=False)
    prompt: str = ""
    output_contract: str = "plain_text"
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageCommand:
    capability: Literal["image_generation"] = field(default="image_generation", init=False)
    prompt: str = ""
    reference_images: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeechCommand:
    capability: Literal["speech_generation"] = field(default="speech_generation", init=False)
    text: str = ""
    voice_id: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoCommand:
    capability: Literal["video_generation"] = field(default="video_generation", init=False)
    prompt: str = ""
    reference_images: tuple[str, ...] = ()
    reference_videos: tuple[str, ...] = ()
    reference_audios: tuple[str, ...] = ()
    native_audio: bool = False
    dialogue_contract: Mapping[str, Any] | None = None
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaRenderCommand:
    capability: Literal["media_render"] = field(default="media_render", init=False)
    manifest: Mapping[str, Any] = field(default_factory=dict)
    output_dir: str = ""
    burn_subtitles: bool = False
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectStorageCommand:
    capability: Literal["object_storage"] = field(default="object_storage", init=False)
    source_url: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)


Command: TypeAlias = TextCommand | ImageCommand | SpeechCommand | VideoCommand | MediaRenderCommand | ObjectStorageCommand


class DriverProfile(Protocol):
    driver_key: str
    capabilities: frozenset[str]
    parameter_schema: Mapping[str, Any]
    limits: Mapping[str, Any]
    provider_id: str
    api_model_id: str


@dataclass(frozen=True)
class DriverContext:
    profile: DriverProfile
    driver_key: str
    connection_id: str | None
    secrets: Mapping[str, str] = field(default_factory=dict, repr=False)
    base_url: str | None = None
    connection_params: Mapping[str, Any] = field(default_factory=dict, repr=False)
    execution_snapshot_id: str | None = None

    @property
    def api_key(self) -> str:
        return self.secrets.get("api_key", "")

    @property
    def api_secret(self) -> str:
        return self.secrets.get("api_secret", "")


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


class DriverContextError(DriverError):
    def __init__(self):
        super().__init__("driver keys in the request context do not agree")


class DriverExecutionError(DriverError):
    def __init__(self, operation: str, sanitized_evidence: Mapping[str, Any]):
        super().__init__(f"driver {operation} failed")
        self.sanitized_evidence = sanitized_evidence


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
    "DriverContextError",
    "DriverError",
    "DriverExecutionError",
    "DriverLimitError",
    "DriverParameterError",
    "DriverProfile",
    "DriverRegistrationError",
    "DriverResultError",
    "DriverSchemaError",
    "DriverSubmission",
    "DriverTestResult",
    "DriverUnavailableError",
    "ImageCommand",
    "MediaRenderCommand",
    "ObjectStorageCommand",
    "SpeechCommand",
    "TextCommand",
    "VideoCommand",
]
