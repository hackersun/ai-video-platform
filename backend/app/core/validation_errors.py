"""Credential-aware sanitizing for request validation errors."""

from typing import Any, Iterable, Mapping


_CREDENTIAL_FIELDS = frozenset({"api_key", "api_secret"})
_REDACTED = "<redacted>"


def _redact_credential_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _REDACTED if key in _CREDENTIAL_FIELDS else _redact_credential_keys(nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_redact_credential_keys(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_credential_keys(item) for item in value)
    return value


def redact_credential_validation_errors(
    errors: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve FastAPI's error shape while hiding invalid credential input."""
    sanitized: list[dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        location = item.get("loc", ())
        sensitive_location = any(part in _CREDENTIAL_FIELDS for part in location)
        for field in ("input", "ctx"):
            if field not in item:
                continue
            item[field] = _REDACTED if sensitive_location else _redact_credential_keys(item[field])
        sanitized.append(item)
    return sanitized
