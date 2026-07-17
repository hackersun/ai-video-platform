from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.model_config.public import (
    ModelBindingError,
    resolve_legacy_strategy_config_id,
    resolve_model_binding,
)
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from tests.model_binding_test_support import (
    db_session as db_session,
    make_binding,
    seed_profile,
)


@pytest.fixture(autouse=True)
def _canonical_binding_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_CENTER_READ_MODE", "canonical")


@pytest.mark.asyncio
async def test_projection_matches_old_public_result_for_broad_video_capability(
    db_session: AsyncSession,
) -> None:
    provider = LLMProvider(id="volcano", name="Volcano", is_active=True)
    model = LLMModel(
        id="multimodal-seedance",
        provider_id=provider.id,
        model_id="doubao-seedance-2-0-fast-260128",
        model_name="Multimodal Seedance",
        model_type="multimodal",
        capabilities=["audio-video-generation"],
        is_active=True,
    )
    config = LLMConfig(
        id="multimodal-seedance-config",
        user_id="user-1",
        model_id=model.id,
        name="Multimodal Seedance",
        is_active=True,
        is_default=True,
        test_status="success",
        tested_at=utc_now(),
    )
    db_session.add_all([provider, model, config])
    await db_session.commit()

    old_public_result = {
        "model_config_id": config.id,
        "routing": "strategy",
        "strategy_model_candidates": [
            "doubao-seedance-2-0-fast-260128",
            "doubao-seedance-1-5-pro-251215",
            "doubao-seedance-2.0-fast",
            "Doubao-Seedance-1.0-pro-fast",
        ],
        "matched_api_model_id": model.model_id,
    }

    projected = await resolve_legacy_strategy_config_id(
        db_session,
        user_id="user-1",
        binding_key="video.draft_fast",
        explicit_config_id=None,
    )

    assert projected == old_public_result


@pytest.mark.asyncio
async def test_canonical_binding_does_not_broaden_video_capability_matching(
    db_session: AsyncSession,
) -> None:
    profile, connection = await seed_profile(
        db_session,
        "canonical-multimodal",
        capabilities=("audio-video-generation",),
    )
    db_session.add(
        make_binding(
            "canonical-multimodal",
            profile,
            connection,
            scope_type="user",
            scope_id="user-1",
        )
    )
    await db_session.commit()

    with pytest.raises(ModelBindingError, match="capability_mismatch"):
        await resolve_model_binding(
            db_session,
            user_id="user-1",
            task="shot_video",
            capability="video_generation",
        )
