"""Check-first, idempotent backfill from legacy model configuration records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_encryption import validate_fernet_ciphertext
from app.features.model_config.domain import normalize_capabilities
from app.features.model_drivers.public import select_llm_connection_driver_key
from app.features.workflow_media.public import production_strategy_metadata
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import (
    ModelBinding,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion
from app.models.prompt_skill import PromptSkill


_TASK_BY_CAPABILITY = {
    "text_generation": "script_generation",
    "image_generation": "shot_image",
    "video_generation": "shot_video",
    "speech_generation": "shot_speech",
}
_BACKFILL_NAMESPACE = UUID("5e3fcb40-f894-5ebb-8a7a-6ed2e5f0b4ad")
_LEGACY_PRODUCTION_STRATEGIES = (
    "draft_fast", "final_quality", "low_cost", "separate_video_tts", "direct_av_first",
)


def _checksum(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(body.encode("utf-8")).hexdigest()


def _canonical_id(kind: str, legacy_id: str) -> str:
    return str(uuid5(_BACKFILL_NAMESPACE, f"{kind}:{legacy_id}"))


def _provider_code(provider: LLMProvider) -> str:
    return "-".join(part for part in provider.name.lower().strip().replace("_", "-").split("-") if part)


def _connection_name(config: LLMConfig) -> str:
    return f"legacy:{config.id}"


def _profile_key(provider: LLMProvider, model: LLMModel, capabilities: list[str]) -> str:
    contract = {
        "driver_key": select_llm_connection_driver_key(provider.name, model.model_type),
        "limits": {"context_window": model.context_window, "max_tokens": model.max_tokens},
        "pricing": {"input_cost_per_1k": model.input_cost_per_1k, "output_cost_per_1k": model.output_cost_per_1k},
    }
    return (
        f"legacy:{_provider_code(provider)}:{model.model_id}:"
        f"{_checksum(capabilities)[:12]}:{_checksum(contract)[:12]}"
    )


def _backfill_credentials(config: LLMConfig) -> tuple[str, str | None, bool]:
    """Copy only credentials decryptable by the current Fernet key."""
    api_key = config.api_key or ""
    api_secret = config.api_secret
    reentry_required = False
    for value in (api_key, api_secret):
        if not value:
            continue
        try:
            validate_fernet_ciphertext(value)
        except ValueError:
            reentry_required = True
    if reentry_required:
        return "", None, True
    return api_key, api_secret, False


def _matches_legacy_profile_version(
    version: ModelProfileVersion, payload: dict[str, object], profile_id: str,
) -> bool:
    return (
        version.status == "published"
        and version.model_id == profile_id
        and version.api_model_id == payload["api_model_id"]
        and version.driver_key == payload["driver_key"]
        and sorted(version.capabilities or []) == payload["capabilities"]
        and dict(version.input_contract or {}) == {}
        and dict(version.output_contract or {}) == {}
        and dict(version.parameter_schema or {}) == {}
        and dict(version.default_params or {}) == {}
        and dict(version.limits or {}) == payload["limits"]
        and dict(version.pricing or {}) == payload["pricing"]
        and version.prompt_profile_key is None
        and version.contract_version == "legacy-backfill-v1"
    )


@dataclass
class BackfillReport:
    providers_created: int = 0
    profiles_created: int = 0
    profile_versions_created: int = 0
    connections_created: int = 0
    bindings_created: int = 0
    recipes_created: int = 0
    prompt_profiles_created: int = 0
    prompt_versions_created: int = 0
    planned_total: int = 0
    updated_total: int = 0

    @property
    def created_total(self) -> int:
        return sum(
            value for key, value in asdict(self).items()
            if key.endswith("_created")
        )

    def sanitized_dict(self) -> dict[str, int]:
        return {
            "providers_created": self.providers_created,
            "profiles_created": self.profiles_created,
            "profile_versions_created": self.profile_versions_created,
            "connections_created": self.connections_created,
            "bindings_created": self.bindings_created,
            "recipes_created": self.recipes_created,
            "prompt_profiles_created": self.prompt_profiles_created,
            "prompt_versions_created": self.prompt_versions_created,
            "planned_total": self.planned_total,
            "created_total": self.created_total,
            "updated_total": self.updated_total,
        }


def _plan(report: BackfillReport, field: str, *, apply: bool) -> None:
    report.planned_total += 1
    if apply:
        setattr(report, field, getattr(report, field) + 1)


async def _legacy_rows(
    db: AsyncSession, user_id: str | None
) -> tuple[list[LLMProvider], list[LLMModel], list[LLMConfig], list[PromptSkill]]:
    providers = list((await db.scalars(select(LLMProvider))).all())
    models = list((await db.scalars(select(LLMModel))).all())
    config_statement = select(LLMConfig)
    prompt_statement = select(PromptSkill).where(PromptSkill.is_active == True)
    if user_id:
        config_statement = config_statement.where(LLMConfig.user_id == user_id)
        prompt_statement = prompt_statement.where(PromptSkill.user_id == user_id)
    configs = list((await db.scalars(config_statement)).all())
    prompts = list((await db.scalars(prompt_statement)).all())
    return providers, models, configs, prompts


async def _backfill_provider(
    db: AsyncSession, provider: LLMProvider, report: BackfillReport, apply: bool
) -> str:
    provider_id = _canonical_id("provider", provider.id)
    existing = await db.get(ModelProvider, provider_id)
    if existing is None:
        existing = await db.scalar(select(ModelProvider).where(ModelProvider.code == _provider_code(provider)))
    if existing is not None:
        return existing.id
    _plan(report, "providers_created", apply=apply)
    if apply:
        db.add(ModelProvider(
            id=provider_id, code=_provider_code(provider), display_name=provider.name_cn or provider.name,
            provider_family=provider.provider_type or "legacy", is_builtin=bool(provider.is_builtin),
            enabled=bool(provider.is_active),
        ))
    return provider_id


async def _backfill_model(
    db: AsyncSession,
    model: LLMModel,
    provider: LLMProvider,
    canonical_provider_id: str,
    report: BackfillReport,
    apply: bool,
    pending_profile_versions: dict[tuple[str, str], tuple[str, str, str]],
) -> str:
    capabilities = sorted(normalize_capabilities(model.model_type, model.capabilities or []))
    profile_key = _profile_key(provider, model, capabilities)
    profile_identity = (canonical_provider_id, profile_key)
    profile_id = _canonical_id("profile", model.id)
    cached = pending_profile_versions.get(profile_identity)
    if cached is not None:
        cached_profile_id, cached_version_id, cached_checksum = cached
        payload = {
            "model_id": cached_profile_id, "api_model_id": model.model_id,
            "driver_key": select_llm_connection_driver_key(provider.name, model.model_type),
            "capabilities": capabilities,
            "limits": {"context_window": model.context_window, "max_tokens": model.max_tokens},
            "pricing": {"input_cost_per_1k": model.input_cost_per_1k, "output_cost_per_1k": model.output_cost_per_1k},
        }
        if _checksum(payload) != cached_checksum:
            raise ValueError("legacy_profile_version_conflict")
        return cached_version_id

    profile = await db.get(ModelProfile, profile_id)
    if profile is None:
        profile = await db.scalar(select(ModelProfile).where(
            ModelProfile.provider_id == canonical_provider_id,
            ModelProfile.profile_key == profile_key,
        ))
    if profile is not None:
        profile_id = profile.id
    if profile is None:
        _plan(report, "profiles_created", apply=apply)
        if apply:
            db.add(ModelProfile(
                id=profile_id, provider_id=canonical_provider_id,
                profile_key=profile_key,
                display_name=model.model_name_cn or model.model_name,
                enabled=bool(model.is_active),
            ))
    payload = {
        "model_id": profile_id, "api_model_id": model.model_id,
        "driver_key": select_llm_connection_driver_key(provider.name, model.model_type),
        "capabilities": capabilities,
        "limits": {"context_window": model.context_window, "max_tokens": model.max_tokens},
        "pricing": {"input_cost_per_1k": model.input_cost_per_1k, "output_cost_per_1k": model.output_cost_per_1k},
    }
    version_id = _canonical_id("profile-version", model.id)
    version = await db.get(ModelProfileVersion, version_id)
    if version is None:
        version = await db.scalar(select(ModelProfileVersion).where(
            ModelProfileVersion.model_id == profile_id,
            ModelProfileVersion.version == 1,
        ))
    if version is not None:
        if not _matches_legacy_profile_version(version, payload, profile_id):
            raise ValueError("legacy_profile_version_conflict")
        pending_profile_versions[profile_identity] = (profile_id, version.id, _checksum(payload))
        return version.id
    _plan(report, "profile_versions_created", apply=apply)
    if apply:
        db.add(ModelProfileVersion(
            id=version_id, version=1, input_contract={}, output_contract={},
            parameter_schema={}, default_params={}, prompt_profile_key=None,
            contract_version="legacy-backfill-v1", status="published",
            checksum=_checksum(payload), **payload,
        ))
    pending_profile_versions[profile_identity] = (profile_id, version_id, _checksum(payload))
    return version_id


async def _backfill_connection(
    db: AsyncSession,
    config: LLMConfig,
    provider_id: str,
    legacy_provider_id: str,
    report: BackfillReport,
    apply: bool,
) -> None:
    connection_id = _canonical_id("connection", config.id)
    if await db.get(ModelConnection, connection_id) is not None:
        return
    api_key, api_secret, credential_reentry_required = _backfill_credentials(config)
    _plan(report, "connections_created", apply=apply)
    if apply:
        db.add(ModelConnection(
            id=connection_id, user_id=config.user_id, provider_id=provider_id,
            name=_connection_name(config), api_key=api_key, api_secret=api_secret,
            endpoint_overrides={},
            connection_params={
                "legacy_config_id": config.id, "legacy_model_id": config.model_id,
                "legacy_provider_id": legacy_provider_id,
                "credential_reentry_required": credential_reentry_required,
            },
            status="verified" if config.test_status == "success" and not credential_reentry_required else "draft",
            tested_at=config.tested_at if not credential_reentry_required else None,
        ))


async def _backfill_default_bindings(
    db: AsyncSession,
    config: LLMConfig,
    model: LLMModel,
    profile_version_id: str,
    report: BackfillReport,
    apply: bool,
    pending_binding_keys: set[tuple[str, str, str, str, str]],
) -> None:
    if not config.is_default or config.test_status != "success" or not config.is_active:
        return
    for capability in sorted(normalize_capabilities(model.model_type, model.capabilities or [])):
        task = _TASK_BY_CAPABILITY.get(capability)
        if task is None:
            continue
        binding_key = (config.user_id, "user", config.user_id, task, capability)
        if binding_key in pending_binding_keys:
            continue
        existing = await db.scalar(select(ModelBinding).where(
            ModelBinding.user_id == config.user_id, ModelBinding.scope_type == "user",
            ModelBinding.scope_id == config.user_id, ModelBinding.task == task,
            ModelBinding.capability == capability, ModelBinding.is_active == True,
        ))
        if existing is not None:
            continue
        pending_binding_keys.add(binding_key)
        _plan(report, "bindings_created", apply=apply)
        if apply:
            db.add(ModelBinding(
                id=_canonical_id("binding", f"{config.id}:{capability}"), user_id=config.user_id,
                scope_type="user", scope_id=config.user_id, task=task, capability=capability,
                profile_version_id=profile_version_id,
                connection_id=_canonical_id("connection", config.id),
                priority=100, route_policy="single", fallback_profile_version_ids=[],
                version=1, is_active=True,
            ))


async def _backfill_prompt(
    db: AsyncSession, prompt: PromptSkill, report: BackfillReport, apply: bool
) -> None:
    profile_id = _canonical_id("prompt-profile", prompt.id)
    profile = await db.get(PromptProfile, profile_id)
    if profile is None:
        _plan(report, "prompt_profiles_created", apply=apply)
        if apply:
            db.add(PromptProfile(
                id=profile_id, user_id=prompt.user_id, key=f"legacy:{prompt.id}",
                name=prompt.name, task=prompt.task,
            ))
    version_id = _canonical_id("prompt-version", prompt.id)
    version = await db.get(PromptProfileVersion, version_id)
    if version is not None:
        return
    _plan(report, "prompt_versions_created", apply=apply)
    if apply:
        body = {
            "task": prompt.task, "stage": prompt.stage, "content": prompt.content,
            "variables": prompt.variables or {}, "tags": prompt.tags or [],
        }
        db.add(PromptProfileVersion(
            id=version_id, profile_id=profile_id, version=1, stage=prompt.stage,
            content=prompt.content, variables=prompt.variables or {}, routing={}, output_contract=None,
            evaluation={}, status="published", checksum=_checksum(body),
        ))


async def _backfill_production_strategies(
    db: AsyncSession,
    *,
    user_ids: set[str],
    report: BackfillReport,
    apply: bool,
) -> None:
    for user_id in sorted(user_ids):
        for strategy in _LEGACY_PRODUCTION_STRATEGIES:
            recipe_key = f"legacy.strategy.{strategy}"
            existing = await db.scalar(select(ProductionRecipeVersion).where(
                ProductionRecipeVersion.user_id == user_id,
                ProductionRecipeVersion.recipe_key == recipe_key,
                ProductionRecipeVersion.version == 1,
            ))
            if existing is not None:
                continue
            _plan(report, "recipes_created", apply=apply)
            if apply:
                spec = {
                    "schema_version": "legacy-production-strategy-v1",
                    "production_strategy": strategy,
                    "metadata": production_strategy_metadata(strategy),
                }
                db.add(ProductionRecipeVersion(
                    id=_canonical_id("recipe", f"{user_id}:{strategy}"), user_id=user_id,
                    recipe_key=recipe_key, name=f"Legacy {strategy}", version=1,
                    status="published", spec=spec, checksum=_checksum(spec),
                ))


async def backfill_model_center(
    db: AsyncSession, *, apply: bool = False, user_id: str | None = None
) -> BackfillReport:
    """Plan or apply an additive legacy projection without decrypting any secret."""
    report = BackfillReport()
    providers, models, configs, prompts = await _legacy_rows(db, user_id)
    provider_by_id = {provider.id: provider for provider in providers}
    canonical_provider_ids: dict[str, str] = {}
    model_by_id = {model.id: model for model in models}
    for provider in providers:
        canonical_provider_ids[provider.id] = await _backfill_provider(db, provider, report, apply)
    profile_versions: dict[str, str] = {}
    pending_profile_versions: dict[tuple[str, str], tuple[str, str, str]] = {}
    pending_binding_keys: set[tuple[str, str, str, str, str]] = set()
    for model in models:
        provider = provider_by_id.get(model.provider_id)
        if provider is not None:
            profile_versions[model.id] = await _backfill_model(
                db, model, provider, canonical_provider_ids[provider.id], report, apply,
                pending_profile_versions,
            )
    for config in configs:
        model = model_by_id.get(config.model_id)
        if model is None or model.provider_id not in provider_by_id:
            continue
        await _backfill_connection(
            db, config, canonical_provider_ids[model.provider_id], model.provider_id, report, apply,
        )
        profile_version_id = profile_versions.get(model.id)
        if profile_version_id is not None:
            await _backfill_default_bindings(
                db, config, model, profile_version_id, report, apply, pending_binding_keys,
            )
    for prompt in prompts:
        await _backfill_prompt(db, prompt, report, apply)
    await _backfill_production_strategies(
        db, user_ids={config.user_id for config in configs}, report=report, apply=apply,
    )
    if apply:
        await db.flush()
    return report


async def get_connection_for_legacy_config(
    db: AsyncSession, legacy_config_id: str
) -> ModelConnection | None:
    rows: Iterable[ModelConnection] = (await db.scalars(select(ModelConnection))).all()
    return next(
        (row for row in rows if (row.connection_params or {}).get("legacy_config_id") == legacy_config_id),
        None,
    )


__all__ = ["BackfillReport", "backfill_model_center", "get_connection_for_legacy_config"]
