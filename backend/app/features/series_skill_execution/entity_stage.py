"""Model-first candidate selection kept outside the legacy entity hotspot."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from .model_pipeline import execute_skill_model_or_fallback
from .stage_contracts import validate_entity_candidates


async def resolve_entity_candidates(
    db: AsyncSession, *, user_id: str, rendered_prompt: str, source_text: str,
    requested_types: set[str], supplied: list[dict[str, Any]] | None,
    fallback: Callable[[], list[dict[str, Any]]], model_config_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if supplied is not None:
        values = [dict(item) for item in supplied if item.get("entity_type") in requested_types]
        return values, {
            "execution_mode": "supplied_candidates", "validation_status": "caller_owned",
            "fallback_reason": None,
            "input_sha256": sha256(rendered_prompt.encode("utf-8")).hexdigest(),
        }
    result = await execute_skill_model_or_fallback(
        db, user_id=user_id, rendered_prompt=rendered_prompt, output_contract="json_array",
        validator=lambda value: validate_entity_candidates(
            value, source_text=source_text, requested_types=requested_types,
        ), fallback=fallback, explicit_config_id=model_config_id,
    )
    return result.value, result.evidence


__all__ = ["resolve_entity_candidates"]
