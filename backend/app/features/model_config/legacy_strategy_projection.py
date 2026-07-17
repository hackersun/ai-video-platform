"""Legacy model-ID projection for strategy binding aliases."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.bindings import (
    legacy_config_sort_key,
    legacy_model_capabilities,
)
from app.features.model_config.repository import load_legacy_config_rows


_LEGACY_VIDEO_PROVIDERS = frozenset({"volcano", "volcano_agent_plan"})
_LEGACY_STRATEGY_MODELS: dict[str, tuple[str, ...]] = {
    "video.draft_fast": (
        "doubao-seedance-2-0-fast-260128",
        "doubao-seedance-1-5-pro-251215",
        "doubao-seedance-2.0-fast",
        "Doubao-Seedance-1.0-pro-fast",
    ),
    "video.final_quality": (
        "doubao-seedance-2-0-260128",
        "doubao-seedance-2.0",
        "doubao-seedance-1-5-pro-251215",
        "doubao-seedance-2-0-fast-260128",
    ),
    "video.low_cost": (
        "doubao-seedance-2-0-fast-260128",
        "doubao-seedance-1-5-pro-251215",
        "Doubao-Seedance-1.0-pro-fast",
    ),
}


def _strategy_result(
    config_id: str | None,
    routing: str,
    candidates: list[str],
    matched: str | None,
) -> dict[str, Any]:
    return {
        "model_config_id": config_id,
        "routing": routing,
        "strategy_model_candidates": candidates,
        "matched_api_model_id": matched,
    }


async def resolve_legacy_strategy_config_id(
    db: AsyncSession,
    *,
    user_id: str,
    binding_key: str | None,
    explicit_config_id: str | None,
) -> dict[str, Any]:
    candidates = list(_LEGACY_STRATEGY_MODELS.get(binding_key or "", ()))
    if explicit_config_id:
        return _strategy_result(explicit_config_id, "explicit", candidates, None)
    if not candidates:
        return _strategy_result(None, "fallback", candidates, None)
    rows = await load_legacy_config_rows(db, user_id=user_id)
    eligible = [
        row
        for row in rows
        if row[1].model_id in candidates
        and "video_generation" in legacy_model_capabilities(row[1])
        and ({row[2].id, row[2].name} & _LEGACY_VIDEO_PROVIDERS)
    ]
    eligible.sort(key=legacy_config_sort_key)
    for model_id in candidates:
        match = next((row for row in eligible if row[1].model_id == model_id), None)
        if match is not None:
            return _strategy_result(match[0].id, "strategy", candidates, model_id)
    return _strategy_result(None, "fallback", candidates, None)


__all__ = ["resolve_legacy_strategy_config_id"]
