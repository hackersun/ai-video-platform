"""Pure Prompt Profile value objects and rendering rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@dataclass(frozen=True)
class PromptSelection:
    profile_id: str
    profile_version_id: str
    profile_key: str
    profile_name: str
    version: int
    stage: str | None
    prompt: str
    routing_reason: str
    fallback_reason: str | None
    output_contract: str | None
    checksum: str
    routing: Mapping[str, Any]


@dataclass(frozen=True)
class PromptRouteQuery:
    user_id: str
    task: str
    provider_id: str = ""
    model_id: str = ""
    capabilities: frozenset[str] = field(default_factory=frozenset)
    output_contract: str | None = None
    stage: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)


def render_prompt(content: str, variables: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    values = _SafeFormatDict({**dict(variables), **dict(context)})
    try:
        return (content or "").format_map(values).strip()
    except ValueError:
        return (content or "").strip()


def stable_prompt_checksum(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()
