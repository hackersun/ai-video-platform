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
    MediaRenderCommand,
    ObjectStorageCommand,
    SpeechCommand,
    TextCommand,
    VideoCommand,
)
from app.features.model_drivers.executor import execute_connection_test, execute_generation, execute_poll
from app.features.model_drivers.registry import (
    DriverRegistry,
    build_builtin_driver_registry,
    describe_installed_drivers,
)
from app.features.model_drivers.adapters.connection_callable import (
    execute_external_connection_test,
)
from app.features.model_drivers.configuration_testing import (
    execute_llm_connection_test,
    resolve_published_driver_key,
    select_llm_connection_driver_key,
)
from app.features.model_drivers.adapters.legacy_minimax_config import test_minimax_api
from app.features.model_drivers.adapters.legacy_volcano_config import (
    test_volcano_agent_plan_api,
    test_volcano_api,
)

__all__ = [
    "CapabilityDriver", "Command", "DriverCapabilityError", "DriverContext", "DriverContextError", "DriverError",
    "DriverExecutionError",
    "DriverLimitError", "DriverParameterError", "DriverRegistrationError", "DriverRegistry",
    "DriverResultError", "DriverSchemaError", "DriverSubmission", "DriverTestResult",
    "DriverUnavailableError", "ImageCommand", "MediaRenderCommand", "ObjectStorageCommand",
    "SpeechCommand", "TextCommand", "VideoCommand",
    "build_builtin_driver_registry", "describe_installed_drivers", "execute_connection_test", "execute_external_connection_test",
    "execute_generation", "execute_llm_connection_test", "execute_poll",
    "resolve_published_driver_key", "select_llm_connection_driver_key",
    "test_minimax_api", "test_volcano_agent_plan_api", "test_volcano_api",
]
