"""Public facade for provider-neutral driver execution contracts."""

from app.features.model_drivers.domain import (
    CapabilityDriver,
    Command,
    DriverCapabilityError,
    DriverContext,
    DriverError,
    DriverLimitError,
    DriverParameterError,
    DriverRegistrationError,
    DriverResultError,
    DriverSchemaError,
    DriverSubmission,
    DriverTestResult,
    DriverUnavailableError,
    ImageCommand,
    SpeechCommand,
    TextCommand,
    VideoCommand,
)
from app.features.model_drivers.executor import execute_connection_test, execute_generation
from app.features.model_drivers.registry import DriverRegistry

__all__ = [
    "CapabilityDriver", "Command", "DriverCapabilityError", "DriverContext", "DriverError",
    "DriverLimitError", "DriverParameterError", "DriverRegistrationError", "DriverRegistry",
    "DriverResultError", "DriverSchemaError", "DriverSubmission", "DriverTestResult",
    "DriverUnavailableError", "ImageCommand", "SpeechCommand", "TextCommand", "VideoCommand",
    "execute_connection_test", "execute_generation",
]
