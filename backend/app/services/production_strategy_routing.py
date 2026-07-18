"""生产策略到模型绑定别名的兼容路由。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.public import resolve_legacy_strategy_config_id


STRATEGY_BINDING_KEYS = {
    "draft_fast": "video.draft_fast",
    "final_quality": "video.final_quality",
    "low_cost": "video.low_cost",
    "direct_av_first": "video.direct_av",
    "separate_video_tts": "video.separate_tts",
}


async def resolve_strategy_video_config_id(
    db: AsyncSession,
    user_id: str,
    production_strategy: Optional[str],
    explicit_config_id: Optional[str],
) -> dict[str, Any]:
    return await resolve_legacy_strategy_config_id(
        db,
        user_id=user_id,
        binding_key=STRATEGY_BINDING_KEYS.get(production_strategy or ""),
        explicit_config_id=explicit_config_id,
    )
