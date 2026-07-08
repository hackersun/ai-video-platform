"""生产策略到视频模型配置的真实路由。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig, LLMModel, LLMProvider


STRATEGY_VIDEO_MODEL_PREFERENCE: dict[str, list[str]] = {
    "draft_fast": [
        "doubao-seedance-2-0-fast-260128",
        "doubao-seedance-1-5-pro-251215",
        "doubao-seedance-2.0-fast",
        "Doubao-Seedance-1.0-pro-fast",
    ],
    "final_quality": [
        "doubao-seedance-2-0-260128",
        "doubao-seedance-2.0",
        "doubao-seedance-1-5-pro-251215",
        "doubao-seedance-2-0-fast-260128",
    ],
    "low_cost": [
        "doubao-seedance-2-0-fast-260128",
        "doubao-seedance-1-5-pro-251215",
        "Doubao-Seedance-1.0-pro-fast",
    ],
}

_VIDEO_PROVIDER_NAMES = {"volcano", "volcano_agent_plan"}


def _is_video_model(model: LLMModel) -> bool:
    model_type = (model.model_type or "").lower()
    capabilities = [str(item).lower() for item in (model.capabilities or [])]
    return model_type in {"video", "video-generation", "video_generation"} or any("video" in item for item in capabilities)


async def resolve_strategy_video_config_id(
    db: AsyncSession,
    user_id: str,
    production_strategy: Optional[str],
    explicit_config_id: Optional[str],
) -> dict[str, Any]:
    candidates = STRATEGY_VIDEO_MODEL_PREFERENCE.get(production_strategy or "", [])
    if explicit_config_id:
        return {
            "model_config_id": explicit_config_id,
            "routing": "explicit",
            "strategy_model_candidates": candidates,
            "matched_api_model_id": None,
        }
    if not candidates:
        return {
            "model_config_id": None,
            "routing": "fallback",
            "strategy_model_candidates": candidates,
            "matched_api_model_id": None,
        }

    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            LLMConfig.user_id == user_id,
            LLMConfig.is_active == True,
            LLMConfig.test_status == "success",
            LLMModel.is_active == True,
            LLMModel.model_id.in_(candidates),
            LLMProvider.is_active == True,
            or_(LLMProvider.name.in_(_VIDEO_PROVIDER_NAMES), LLMProvider.id.in_(_VIDEO_PROVIDER_NAMES)),
        )
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.updated_at), desc(LLMConfig.created_at))
    )
    rows = [row for row in result.all() if _is_video_model(row[1])]
    for api_model_id in candidates:
        for config, model, _provider in rows:
            if model.model_id == api_model_id:
                return {
                    "model_config_id": config.id,
                    "routing": "strategy",
                    "strategy_model_candidates": candidates,
                    "matched_api_model_id": model.model_id,
                }

    return {
        "model_config_id": None,
        "routing": "fallback",
        "strategy_model_candidates": candidates,
        "matched_api_model_id": None,
    }
