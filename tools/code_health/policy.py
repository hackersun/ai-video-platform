"""Validated machine-readable policy for repository health checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PolicyError(ValueError):
    """Raised when the policy cannot be enforced safely."""


@dataclass(frozen=True)
class Limits:
    new_file_lines: int
    function_lines: int
    route_lines: int
    react_page_lines: int
    react_component_lines: int
    endpoint_routes: int


@dataclass(frozen=True)
class BoundaryRule:
    source_glob: str
    forbidden_module_prefix: str
    code: str


@dataclass(frozen=True)
class ExceptionRule:
    path: str
    max_file_lines: int | None
    reason: str
    owner: str
    remove_when: str


@dataclass(frozen=True)
class Policy:
    version: int
    roots: tuple[str, ...]
    exclude: tuple[str, ...]
    limits: Limits
    boundaries: tuple[BoundaryRule, ...]
    exceptions: tuple[ExceptionRule, ...]


LIMIT_FIELDS = tuple(Limits.__dataclass_fields__)


def _require_string(raw: dict[str, Any], field: str, *, context: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{context} requires non-empty {field}")
    return value.strip()


def _load_limits(raw: Any) -> Limits:
    if not isinstance(raw, dict):
        raise PolicyError("limits must be an object")
    values: dict[str, int] = {}
    for field in LIMIT_FIELDS:
        value = raw.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise PolicyError(f"limit {field} must be a positive integer")
        values[field] = value
    return Limits(**values)


def _load_boundaries(raw: Any) -> tuple[BoundaryRule, ...]:
    if not isinstance(raw, list):
        raise PolicyError("boundaries must be an array")
    return tuple(
        BoundaryRule(
            source_glob=_require_string(item, "source_glob", context="boundary"),
            forbidden_module_prefix=_require_string(item, "forbidden_module_prefix", context="boundary"),
            code=_require_string(item, "code", context="boundary"),
        )
        for item in raw
        if isinstance(item, dict)
    )


def _load_exceptions(raw: Any) -> tuple[ExceptionRule, ...]:
    if not isinstance(raw, list):
        raise PolicyError("exceptions must be an array")
    exceptions = []
    for item in raw:
        if not isinstance(item, dict):
            raise PolicyError("each exception must be an object")
        missing = [field for field in ("reason", "owner", "remove_when") if not str(item.get(field) or "").strip()]
        if missing:
            raise PolicyError("exception requires reason, owner and remove_when")
        maximum = item.get("max_file_lines")
        if maximum is not None and (not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0):
            raise PolicyError("exception max_file_lines must be a positive integer")
        exceptions.append(ExceptionRule(
            path=_require_string(item, "path", context="exception"),
            max_file_lines=maximum,
            reason=str(item["reason"]).strip(),
            owner=str(item["owner"]).strip(),
            remove_when=str(item["remove_when"]).strip(),
        ))
    return tuple(exceptions)


def _load_string_array(raw: Any, field: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(raw, list) or (not allow_empty and not raw):
        raise PolicyError(f"{field} must be a{' non-empty' if not allow_empty else 'n'} array")
    if any(not isinstance(value, str) or not value.strip() for value in raw):
        raise PolicyError(f"{field} values must be non-empty strings")
    return tuple(value.strip() for value in raw)


def load_policy(path: Path) -> Policy:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"cannot load policy: {error}") from error
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise PolicyError("policy version must be 1")
    boundaries = _load_boundaries(raw.get("boundaries"))
    if len(boundaries) != len(raw.get("boundaries", [])):
        raise PolicyError("each boundary must be an object")
    return Policy(
        version=1,
        roots=_load_string_array(raw.get("roots"), "roots", allow_empty=False),
        exclude=_load_string_array(raw.get("exclude"), "exclude", allow_empty=True),
        limits=_load_limits(raw.get("limits")),
        boundaries=boundaries,
        exceptions=_load_exceptions(raw.get("exceptions")),
    )


__all__ = [
    "BoundaryRule",
    "ExceptionRule",
    "Limits",
    "Policy",
    "PolicyError",
    "load_policy",
]
