"""Model-first execution with a deterministic, auditable fallback."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Callable, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.generation_context import resolve_generation_context
from app.features.model_drivers.public import (
    TextCommand,
    build_builtin_driver_registry,
    execute_generation,
)


T = TypeVar("T")


@dataclass(frozen=True)
class SeriesStageModelResult(Generic[T]):
    value: T
    evidence: dict[str, Any]


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        return json.loads(cleaned)
    except (TypeError, json.JSONDecodeError) as error:
        starts = [position for position in (cleaned.find("["), cleaned.find("{")) if position >= 0]
        if not starts:
            raise ValueError("model_output_invalid") from error
        start = min(starts)
        closing = "]" if cleaned[start] == "[" else "}"
        end = cleaned.rfind(closing)
        if end < start:
            raise ValueError("model_output_invalid") from error
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as nested:
            raise ValueError("model_output_invalid") from nested


def _binding_evidence(context: Any) -> dict[str, Any]:
    binding = context.binding
    profile = binding.profile
    return {
        "binding_id": getattr(binding, "binding_id", None),
        "connection_id": getattr(binding, "connection_id", None),
        "provider_id": getattr(profile, "provider_id", None),
        "api_model_id": getattr(profile, "api_model_id", None),
    }


def _fallback_result(
    fallback: Callable[[], T], *, input_hash: str, reason: str,
    binding: dict[str, Any] | None = None,
) -> SeriesStageModelResult[T]:
    return SeriesStageModelResult(
        value=fallback(),
        evidence={
            "execution_mode": "deterministic_fallback",
            "validation_status": "fallback",
            "fallback_reason": reason,
            "input_sha256": input_hash,
            **(binding or {}),
        },
    )


async def execute_skill_model_or_fallback(
    db: AsyncSession,
    *,
    user_id: str,
    rendered_prompt: str,
    output_contract: str,
    validator: Callable[[Any], T],
    fallback: Callable[[], T],
    project_id: str | None = None,
    series_id: str | None = None,
    explicit_config_id: str | None = None,
) -> SeriesStageModelResult[T]:
    """Execute the selected text model and admit only validated structured output."""
    input_hash = _hash(rendered_prompt)
    try:
        context = await resolve_generation_context(
            db, user_id=user_id, stage="text", explicit_config_id=explicit_config_id,
            project_id=project_id, series_id=series_id, prefer_canonical_binding=True,
        )
    except Exception:
        return _fallback_result(fallback, input_hash=input_hash, reason="model_unavailable")

    binding = _binding_evidence(context)
    try:
        submission = await execute_generation(
            build_builtin_driver_registry(),
            TextCommand(prompt=rendered_prompt, output_contract=output_contract),
            context.driver_context,
        )
        raw = submission.output.get("text")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("model_output_invalid")
        parsed = _parse_json(raw)
    except ValueError:
        return _fallback_result(
            fallback, input_hash=input_hash, reason="model_output_invalid", binding=binding,
        )
    except Exception:
        return _fallback_result(
            fallback, input_hash=input_hash, reason="model_execution_failed", binding=binding,
        )

    try:
        value = validator(parsed)
    except (TypeError, ValueError, KeyError):
        return _fallback_result(
            fallback, input_hash=input_hash, reason="model_output_rejected", binding=binding,
        )
    return SeriesStageModelResult(
        value=value,
        evidence={
            "execution_mode": "provider_model", "validation_status": "passed",
            "fallback_reason": None, "input_sha256": input_hash,
            "output_sha256": _hash(raw), **binding,
        },
    )


__all__ = ["SeriesStageModelResult", "execute_skill_model_or_fallback"]
