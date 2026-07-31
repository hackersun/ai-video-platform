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
    return await validate_required_model_bindings(
        db, run, bindings, required_tested_at=required_tested_at,
        freshness_seconds=freshness_seconds, persist=persist,
    )


async def validate_required_model_bindings(
    db: AsyncSession,
    run: SeriesProductionRun,
    bindings: dict[str, str],
    *,
    required_tested_at: datetime,
    freshness_seconds: int = 900,
    persist: bool = False,
) -> dict[str, dict[str, str]]:
    if not bindings or not set(bindings).issubset(CAPABILITIES):
        raise BindingValidationError("one or more known model bindings are required")
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
        for capability in bindings
    }
    if persist:
        previous = (run.model_bindings or {}).get("capabilities") or {}
        merged = {**previous, **snapshot}
        video = merged.get("video") or {}
        run.model_bindings = {
            "capabilities": merged,
            "provider_id": video.get("provider_id"),
            "model_id": video.get("api_model_id"),
        }
        flag_modified(run, "model_bindings")
        await db.commit()
    return snapshot


async def validate_persisted_model_bindings(
    db: AsyncSession, run: SeriesProductionRun, *, required_capabilities: set[str],
    persist_missing: bool = False,
) -> dict[str, dict[str, str]]:
    """Revalidate immutable run snapshots without restarting the rolling test clock."""
    persisted = (run.model_bindings or {}).get("capabilities") or {}
    if not required_capabilities or not required_capabilities.issubset(CAPABILITIES):
        raise BindingValidationError("one or more known model bindings are required")
    verified: dict[str, dict[str, str]] = {}
    for capability in required_capabilities:
        expected = persisted.get(capability) or {}
        config_id = str(expected.get("config_id") or "")
        stable_keys = (
            "config_id", "db_model_id", "api_model_id", "provider_id",
            "tested_at", "contract_version", "prompt_profile", "verification_status",
        )
        has_snapshot = all(expected.get(key) is not None for key in stable_keys)
        rolling_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=900)
        current = await _binding_snapshot(
            db, run, capability=capability, config_id=config_id,
            minimum_tested_at=(datetime.min if has_snapshot else max(
                required_tested_at_for_run(run), rolling_cutoff,
            )),
        )
        changed = has_snapshot and any(
            str(current.get(key) or "") != str(expected.get(key) or "") for key in stable_keys
        )
        if changed and not persist_missing:
            raise BindingValidationError(f"{capability} persisted binding snapshot has changed")
        if changed:
            current = await _binding_snapshot(
                db, run, capability=capability, config_id=config_id,
                minimum_tested_at=max(required_tested_at_for_run(run), rolling_cutoff),
            )
        verified[capability] = dict(current if changed or not has_snapshot else expected)
    if persist_missing:
        merged = {**persisted, **verified}
        video = merged.get("video") or {}
        run.model_bindings = {
            "capabilities": merged,
            "provider_id": video.get("provider_id"),
            "model_id": video.get("api_model_id"),
        }
        flag_modified(run, "model_bindings")
        await db.commit()
    return verified
