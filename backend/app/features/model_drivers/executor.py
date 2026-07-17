"""Fail-closed execution kernel shared by connection tests and generation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from app.features.model_drivers.domain import (
    Command,
    DriverCapabilityError,
    DriverContext,
    DriverLimitError,
    DriverParameterError,
    DriverResultError,
    DriverSchemaError,
    DriverSubmission,
    DriverTestResult,
    ImageCommand,
    SpeechCommand,
    TextCommand,
    VideoCommand,
)
from app.features.model_drivers.registry import DriverRegistry


_SENSITIVE_KEY_PARTS = ("authorization", "password", "secret", "token", "api_key", "apikey")
_SCHEMA_KEYS = frozenset({"type", "properties", "required", "additionalProperties"})
_PROPERTY_SCHEMA_KEYS = frozenset({"type", "enum", "minimum", "maximum"})
_TYPE_CHECKS = {
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "array": lambda value: isinstance(value, list),
}


async def execute_connection_test(
    registry: DriverRegistry, driver_key: str, context: DriverContext
) -> DriverTestResult:
    result = await registry.require(driver_key).test_connection(context)
    if not isinstance(result, DriverTestResult) or not isinstance(result.sanitized_evidence, Mapping):
        raise DriverResultError("driver returned an invalid connection test result")
    return replace(
        result,
        message=_sanitize_text(result.message, context.secrets),
        sanitized_evidence=_sanitize_evidence(result.sanitized_evidence, context.secrets),
    )


async def execute_generation(
    registry: DriverRegistry, command: Command, context: DriverContext
) -> DriverSubmission:
    driver = registry.require(context.driver_key)
    capability = command.capability
    if capability not in driver.capabilities or capability not in context.profile.capabilities:
        raise DriverCapabilityError(context.driver_key, capability)
    validate_params(context.profile.parameter_schema, command.params)
    validate_command_limits(command, context.profile.limits)
    result = await driver.submit(command, context)
    if not isinstance(result, DriverSubmission):
        raise DriverResultError("driver returned an invalid generation result")
    return result


def validate_params(schema: Mapping[str, Any], params: Mapping[str, Any]) -> None:
    if not isinstance(schema, Mapping) or not isinstance(params, Mapping):
        raise DriverSchemaError("parameter schema and params must be mappings")
    if not schema:
        if params:
            raise DriverParameterError("parameters are not declared by the profile")
        return
    _validate_root_schema(schema)
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    for name in required:
        if name not in params:
            raise DriverParameterError("a required parameter is missing")
    for name, value in params.items():
        property_schema = properties.get(name)
        if property_schema is None:
            raise DriverParameterError("a parameter is not declared by the profile")
        _validate_parameter_value(property_schema, value)


def validate_command_limits(command: Command, limits: Mapping[str, Any]) -> None:
    measured = _command_limit_values(command)
    if not isinstance(limits, Mapping) or set(limits) != set(measured):
        raise DriverLimitError("profile limits do not exactly describe this command capability")
    for name, value in limits.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise DriverLimitError("profile limits must be non-negative integers")
        if measured[name] > value:
            raise DriverLimitError("command exceeds a profile limit")


def _validate_root_schema(schema: Mapping[str, Any]) -> None:
    if set(schema) - _SCHEMA_KEYS or schema.get("type") != "object":
        raise DriverSchemaError("unsupported parameter schema")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, Mapping) or not isinstance(required, (list, tuple)):
        raise DriverSchemaError("invalid parameter schema")
    if schema.get("additionalProperties", False) is not False:
        raise DriverSchemaError("additional parameters are not supported")
    if any(not isinstance(name, str) or name not in properties for name in required):
        raise DriverSchemaError("invalid required parameter declaration")
    for property_schema in properties.values():
        _validate_property_schema(property_schema)


def _validate_property_schema(schema: Any) -> None:
    if not isinstance(schema, Mapping) or set(schema) - _PROPERTY_SCHEMA_KEYS:
        raise DriverSchemaError("unsupported parameter property schema")
    value_type = schema.get("type")
    if value_type not in _TYPE_CHECKS:
        raise DriverSchemaError("unsupported parameter type")
    for key in ("minimum", "maximum"):
        if key in schema and (not isinstance(schema[key], (int, float)) or isinstance(schema[key], bool)):
            raise DriverSchemaError("parameter bounds must be numeric")
    if "minimum" in schema and "maximum" in schema and schema["minimum"] > schema["maximum"]:
        raise DriverSchemaError("parameter bounds are invalid")
    if "enum" in schema and not isinstance(schema["enum"], (list, tuple)):
        raise DriverSchemaError("parameter enum must be a list")


def _validate_parameter_value(schema: Mapping[str, Any], value: Any) -> None:
    value_type = schema["type"]
    if not _TYPE_CHECKS[value_type](value):
        raise DriverParameterError("parameter type does not match the profile")
    if "enum" in schema and value not in schema["enum"]:
        raise DriverParameterError("parameter is outside the declared enum")
    if "minimum" in schema and value < schema["minimum"]:
        raise DriverParameterError("parameter is below the declared minimum")
    if "maximum" in schema and value > schema["maximum"]:
        raise DriverParameterError("parameter is above the declared maximum")


def _command_limit_values(command: Command) -> dict[str, int]:
    if isinstance(command, TextCommand):
        return {"max_prompt_chars": len(command.prompt)}
    if isinstance(command, ImageCommand):
        return {"max_prompt_chars": len(command.prompt), "max_reference_images": len(command.reference_images)}
    if isinstance(command, SpeechCommand):
        return {"max_text_chars": len(command.text)}
    if isinstance(command, VideoCommand):
        return {
            "max_prompt_chars": len(command.prompt),
            "max_reference_images": len(command.reference_images),
            "max_reference_videos": len(command.reference_videos),
            "max_reference_audios": len(command.reference_audios),
        }
    raise DriverCapabilityError("unknown", str(getattr(command, "capability", "unknown")))


def _sanitize_evidence(value: Any, secrets: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "***" if _is_sensitive_key(key) else _sanitize_evidence(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_evidence(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_evidence(item, secrets) for item in value)
    return _sanitize_text(value, secrets) if isinstance(value, str) else value


def _sanitize_text(value: str, secrets: Mapping[str, str]) -> str:
    sanitized = value
    for secret in sorted((item for item in secrets.values() if item), key=len, reverse=True):
        sanitized = sanitized.replace(secret, "***")
    return sanitized


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


__all__ = ["execute_connection_test", "execute_generation", "validate_command_limits", "validate_params"]
