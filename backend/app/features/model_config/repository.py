"""Read-only canonical model catalog repository."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.catalog import (
    ProductCatalog,
    ProductCatalogItem,
    is_product_visible_model,
    is_product_visible_provider,
)
from app.features.model_config.domain import ModelProfileContract, normalize_capabilities
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import (
    ModelCertificationRun,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
)


class ModelConfigurationError(ValueError):
    """Raised when a requested canonical or legacy model cannot be resolved."""


async def load_published_profile(db: AsyncSession, profile_version_id: str) -> ModelProfileVersion | None:
    result = await db.execute(
        select(ModelProfileVersion).where(
            ModelProfileVersion.id == profile_version_id,
            ModelProfileVersion.status == "published",
        )
    )
    return result.scalar_one_or_none()


async def _provider_id_for_profile(db: AsyncSession, profile: ModelProfileVersion) -> str | None:
    model_profile = await db.get(ModelProfile, profile.model_id)
    if model_profile is not None:
        return model_profile.provider_id
    legacy_model = await db.get(LLMModel, profile.model_id)
    return legacy_model.provider_id if legacy_model is not None else None


async def _profile_contract(db: AsyncSession, profile: ModelProfileVersion) -> ModelProfileContract:
    provider_id = await _provider_id_for_profile(db, profile)
    if provider_id is None:
        raise ModelConfigurationError("model_provider_missing")
    return ModelProfileContract(
        profile_version_id=profile.id,
        provider_id=provider_id,
        api_model_id=profile.api_model_id,
        driver_key=profile.driver_key,
        capabilities=frozenset(normalize_capabilities(None, profile.capabilities or [])),
        input_contract=profile.input_contract or {},
        output_contract=profile.output_contract or {},
        parameter_schema=profile.parameter_schema or {},
        default_params=profile.default_params or {},
        limits=profile.limits or {},
        pricing=profile.pricing or {},
        prompt_profile_key=profile.prompt_profile_key,
        contract_version=profile.contract_version,
    )


async def build_legacy_profile_contract(db: AsyncSession, legacy_model_id: str) -> ModelProfileContract:
    model = await db.get(LLMModel, legacy_model_id)
    if model is None:
        raise ModelConfigurationError("legacy_model_not_found")
    return ModelProfileContract(
        profile_version_id=f"legacy:{model.id}",
        provider_id=model.provider_id,
        api_model_id=model.model_id,
        driver_key=f"legacy:{model.provider_id}",
        capabilities=frozenset(normalize_capabilities(model.model_type, model.capabilities or [])),
        input_contract={},
        output_contract={},
        parameter_schema={},
        default_params={},
        limits={"context_window": model.context_window, "max_tokens": model.max_tokens},
        pricing={"input_cost_per_1k": model.input_cost_per_1k, "output_cost_per_1k": model.output_cost_per_1k},
        prompt_profile_key=None,
        contract_version="legacy-single-reference-v1",
    )


async def resolve_profile_version(
    db: AsyncSession,
    *,
    profile_version_id: str | None = None,
    legacy_model_id: str | None = None,
) -> ModelProfileContract:
    if profile_version_id:
        profile = await load_published_profile(db, profile_version_id)
        if profile is None:
            raise ModelConfigurationError("model_profile_not_published")
        return await _profile_contract(db, profile)
    if legacy_model_id:
        return await build_legacy_profile_contract(db, legacy_model_id)
    raise ModelConfigurationError("model_profile_required")


def _primary_config(configs: list[LLMConfig]) -> LLMConfig | None:
    return next((config for config in configs if config.test_status == "success"), configs[0] if configs else None)


async def _certification_status(
    db: AsyncSession,
    user_id: str,
    profile_version_id: str | None,
    config: LLMConfig | None,
) -> str:
    if config is not None and config.test_status == "success":
        return "connection_verified"
    if profile_version_id is None:
        return "unverified"
    result = await db.execute(
        select(ModelCertificationRun.level).where(
            ModelCertificationRun.user_id == user_id,
            ModelCertificationRun.profile_version_id == profile_version_id,
            ModelCertificationRun.status == "success",
        )
    )
    levels = set(result.scalars().all())
    if "live" in levels:
        return "live_verified"
    if "contract" in levels:
        return "contract_verified"
    return "connection_verified" if "connection" in levels else "unverified"


async def list_product_catalog(db: AsyncSession, user_id: str) -> ProductCatalog:
    """Return a canonical-first catalog without mutating legacy or canonical rows."""
    providers = {item.id: item for item in (await db.scalars(select(LLMProvider))).all()}
    models = list((await db.scalars(select(LLMModel).where(LLMModel.is_active == True))).all())
    configs = list((await db.scalars(select(LLMConfig).where(LLMConfig.user_id == user_id, LLMConfig.is_active == True))).all())
    profiles = list((await db.scalars(select(ModelProfileVersion).where(ModelProfileVersion.status == "published"))).all())
    configs_by_model: dict[str, list[LLMConfig]] = defaultdict(list)
    for config in configs:
        configs_by_model[config.model_id].append(config)
    profiles_by_model: dict[str, ModelProfileVersion] = {}
    for profile in profiles:
        current = profiles_by_model.get(profile.model_id)
        if current is None or profile.version > current.version:
            profiles_by_model[profile.model_id] = profile
    items: dict[tuple[str, str], ProductCatalogItem] = {}
    legacy_ids = {model.id for model in models}
    for model in models:
        provider = providers.get(model.provider_id)
        if provider is None or not provider.is_active or not is_product_visible_provider(provider.id, provider.name, provider.name_cn, provider.name_en):
            continue
        if not is_product_visible_model(model.id, model.model_id, model.model_name, model.model_name_cn):
            continue
        profile = profiles_by_model.get(model.id)
        config = _primary_config(configs_by_model.get(model.id, []))
        api_model_id = profile.api_model_id if profile is not None else model.model_id
        item = ProductCatalogItem(
            provider_id=model.provider_id,
            api_model_id=api_model_id,
            profile_version_id=profile.id if profile is not None else None,
            legacy_model_id=model.id,
            legacy_config_id=config.id if config is not None else None,
            certification_status=await _certification_status(db, user_id, profile.id if profile else None, config),
            capabilities=frozenset(normalize_capabilities(model.model_type, profile.capabilities if profile else model.capabilities or [])),
        )
        items[(item.provider_id, item.api_model_id)] = item
    canonical_providers = {item.id: item for item in (await db.scalars(select(ModelProvider).where(ModelProvider.enabled == True))).all()}
    for profile in profiles:
        if profile.model_id in legacy_ids or not is_product_visible_model(profile.api_model_id):
            continue
        provider_id = await _provider_id_for_profile(db, profile)
        provider = canonical_providers.get(provider_id or "")
        if provider_id is None or provider is None or not is_product_visible_provider(provider.code, provider.display_name):
            continue
        key = (provider_id, profile.api_model_id)
        items[key] = ProductCatalogItem(
            provider_id=provider_id,
            api_model_id=profile.api_model_id,
            profile_version_id=profile.id,
            legacy_model_id=None,
            legacy_config_id=None,
            certification_status=await _certification_status(db, user_id, profile.id, None),
            capabilities=frozenset(normalize_capabilities(None, profile.capabilities or [])),
        )
    return ProductCatalog(models=tuple(sorted(items.values(), key=lambda item: (item.provider_id, item.api_model_id))))


__all__ = [
    "ModelConfigurationError",
    "build_legacy_profile_contract",
    "list_product_catalog",
    "load_published_profile",
    "resolve_profile_version",
]
