"""Public facade for provider-neutral driver execution contracts."""

from app.features.model_drivers.domain import (
    CapabilityDriver,
    Command,
    DriverCapabilityError,
    DriverContext,
    DriverContextError,
    DriverError,
    DriverExecutionError,
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
from app.features.model_drivers.executor import execute_connection_test, execute_generation, execute_poll
from app.features.model_drivers.registry import DriverRegistry, build_builtin_driver_registry
from app.features.model_drivers.adapters.connection_callable import (
    execute_external_connection_test,
    execute_legacy_connection_test,
)

__all__ = [
    "CapabilityDriver", "Command", "DriverCapabilityError", "DriverContext", "DriverContextError", "DriverError",
    "DriverExecutionError",
    "DriverLimitError", "DriverParameterError", "DriverRegistrationError", "DriverRegistry",
    "DriverResultError", "DriverSchemaError", "DriverSubmission", "DriverTestResult",
    "DriverUnavailableError", "ImageCommand", "SpeechCommand", "TextCommand", "VideoCommand",
    "build_builtin_driver_registry", "execute_connection_test", "execute_external_connection_test",
    "execute_generation", "execute_legacy_connection_test", "execute_poll",
]
