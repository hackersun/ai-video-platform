"""Credential-aware sanitizing for request validation errors."""

from typing import Any, Iterable, Mapping


_CREDENTIAL_FIELDS = frozenset({"api_key", "api_secret"})
_CREDENTIAL_MARKERS = ("apikey", "apisecret", "authorization", "token", "password", "secret", "credential", "header")
_REDACTED = "<redacted>"


def _redact_credential_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _REDACTED if _is_credential_key(key) else _redact_credential_keys(nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_redact_credential_keys(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_credential_keys(item) for item in value)
    return value


def _is_credential_key(value: object) -> bool:
    normalized = "".join(character for character in str(value).lower() if character.isalnum())
    return normalized in _CREDENTIAL_FIELDS or any(marker in normalized for marker in _CREDENTIAL_MARKERS)


def redact_credential_validation_errors(
    errors: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve FastAPI's error shape while hiding invalid credential input."""
    sanitized: list[dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        location = item.get("loc", ())
        sensitive_location = any(_is_credential_key(part) for part in location)
        for field in ("input", "ctx"):
            if field not in item:
                continue
            item[field] = _REDACTED if sensitive_location else _redact_credential_keys(item[field])
        sanitized.append(item)
    return sanitized
