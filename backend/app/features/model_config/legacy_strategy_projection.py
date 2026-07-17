"""Legacy model-ID projection for strategy binding aliases."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.repository import LegacyConfigCandidate, load_legacy_config_rows


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


def _is_legacy_video_model(candidate: LegacyConfigCandidate) -> bool:
    model_type = (candidate.model_type or "").lower()
    return model_type in {"video", "video-generation", "video_generation"} or any(
        "video" in item.lower() for item in candidate.raw_capabilities
    )


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
        if row.api_model_id in candidates
        and _is_legacy_video_model(row)
        and ({row.provider_id, row.provider_name} & _LEGACY_VIDEO_PROVIDERS)
    ]
    for model_id in candidates:
        match = next((row for row in eligible if row.api_model_id == model_id), None)
        if match is not None:
            return _strategy_result(match.config_id, "strategy", candidates, model_id)
    return _strategy_result(None, "fallback", candidates, None)


__all__ = ["resolve_legacy_strategy_config_id"]
