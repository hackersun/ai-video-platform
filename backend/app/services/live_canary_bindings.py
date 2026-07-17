"""Fail-closed model-binding freshness validation for live canaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.series_production_run import SeriesProductionRun
from app.features.model_execution_contract import resolve_model_execution_contract
from app.services.live_canary_staging_proof import PROOF_KEY, validate_staging_proof


CAPABILITIES = {
    "text": {"chat", "completion", "text"},
    "image": {"text-to-image", "image", "image-generation"},
    "tts": {"text-to-speech", "tts", "speech"},
    "video": {"text-to-video", "image-to-video", "video", "video-generation"},
}


class BindingValidationError(ValueError):
    pass


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def required_tested_at_for_run(run: SeriesProductionRun) -> datetime:
    raw = (run.run_metadata or {}).get("canary_staging_required_at")
    try:
        staging_at = datetime.fromisoformat(raw) if raw else None
    except (TypeError, ValueError) as error:
        raise BindingValidationError(
            "invalid canary staging requirement timestamp"
        ) from error
    values = [
        _naive_utc(value)
        for value in (run.created_at, staging_at)
        if value is not None
    ]
    if not values:
        raise BindingValidationError(
            "live canary run has no trusted requirement timestamp"
        )
    return max(values)


async def _binding_snapshot(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    capability: str,
    config_id: str,
    minimum_tested_at: datetime,
) -> dict[str, str]:
    row = (
        await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMModel.id == LLMConfig.model_id)
            .join(LLMProvider, LLMProvider.id == LLMModel.provider_id)
            .where(LLMConfig.id == config_id, LLMConfig.user_id == run.user_id)
        )
    ).one_or_none()
    if row is None:
        raise BindingValidationError(f"{capability} binding is missing or not owned")
    config, model, provider = row
    tags = {
        str(tag).lower().replace("_", "-") for tag in (model.capabilities or [])
    }
    tags.add(str(model.model_type or "").lower().replace("_", "-"))
    tested_at = _naive_utc(config.tested_at) if config.tested_at else None
    if (
        not config.is_active
        or config.test_status != "success"
        or tested_at is None
    ):
        raise BindingValidationError(
            f"{capability} binding lacks a successful historical server test"
        )
    if (
        not model.is_active
        or not provider.is_active
        or not tags.intersection(CAPABILITIES[capability])
    ):
        raise BindingValidationError(
            f"{capability} binding does not match an active model capability"
        )
    proof_kind = "fresh_server_test"
    if tested_at < minimum_tested_at:
        policy = run.budget_policy or {}
        isolated = (
            policy.get("profile") == "isolated_live_canary"
            and policy.get("live_canary") is True
        )
        if not isolated:
            raise BindingValidationError(
                f"{capability} binding lacks a fresh successful server test"
            )
        try:
            validate_staging_proof(
                (config.extra_params or {}).get(PROOF_KEY),
                config_id=config.id, model_id=model.id, provider_id=provider.id,
                target_user_id=run.user_id, test_status=config.test_status,
                tested_at=config.tested_at, max_age_seconds=900,
            )
        except (TypeError, ValueError) as error:
            raise BindingValidationError(
                f"{capability} isolated staging proof is invalid or expired"
            ) from error
        proof_kind = "isolated_staging"
    contract = resolve_model_execution_contract(provider.id, model.model_id, capability)
    return {
        "config_id": config.id,
        "db_model_id": model.id,
        "api_model_id": model.model_id,
        "provider_id": provider.id,
        "tested_at": tested_at.isoformat(),
        "proof_kind": proof_kind,
        "contract_version": contract.contract_version,
        "prompt_profile": contract.prompt_profile,
        "verification_status": contract.verification_status,
    }


async def validate_model_bindings(
    db: AsyncSession,
    run: SeriesProductionRun,
    bindings: dict[str, str],
    *,
    required_tested_at: datetime,
    freshness_seconds: int = 900,
    persist: bool = True,
) -> dict[str, dict[str, str]]:
    if set(bindings) != set(CAPABILITIES):
        raise BindingValidationError("exact text/image/tts/video bindings are required")
    if not 1 <= freshness_seconds <= 900:
        raise BindingValidationError("server freshness must be within 900 seconds")
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        seconds=freshness_seconds
    )
    minimum_tested_at = max(_naive_utc(required_tested_at), cutoff)
    snapshot = {
        capability: await _binding_snapshot(
            db,
            run,
            capability=capability,
            config_id=bindings[capability],
            minimum_tested_at=minimum_tested_at,
        )
        for capability in CAPABILITIES
    }
    if persist:
        run.model_bindings = {
            "capabilities": snapshot,
            "provider_id": snapshot["video"]["provider_id"],
            "model_id": snapshot["video"]["api_model_id"],
        }
        flag_modified(run, "model_bindings")
        await db.commit()
    return snapshot
