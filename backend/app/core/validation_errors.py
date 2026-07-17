"""Credential-aware sanitizing for request validation errors."""

from typing import Any, Iterable, Mapping


_CREDENTIAL_FIELDS = frozenset({"api_key", "api_secret"})
_REDACTED = "<redacted>"


def redact_credential_validation_errors(
    errors: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve FastAPI's error shape while hiding invalid credential input."""
    sanitized: list[dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        location = item.get("loc", ())
        if any(part in _CREDENTIAL_FIELDS for part in location):
            if "input" in item:
                item["input"] = _REDACTED
            if "ctx" in item:
                item["ctx"] = _REDACTED
        sanitized.append(item)
    return sanitized
