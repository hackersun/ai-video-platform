"""Read-only canonical model catalog repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.catalog import (
    ProductCatalog,
    ProductCatalogItem,
    group_legacy_configs,
    is_product_visible_model,
    is_product_visible_provider,
    select_primary_legacy_config,
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


def _certification_status(
    profile_version_id: str | None,
    config: LLMConfig | None,
    levels_by_profile: dict[str, set[str]],
) -> str:
    if config is not None and config.test_status == "success":
        return "connection_verified"
    if profile_version_id is None:
        return "unverified"
    levels = levels_by_profile.get(profile_version_id, set())
    if "live" in levels:
        return "live_verified"
    if "contract" in levels:
        return "contract_verified"
    return "connection_verified" if "connection" in levels else "unverified"


def _latest_published_profiles(rows: list[ModelProfileVersion]) -> dict[str, ModelProfileVersion]:
    latest: dict[str, ModelProfileVersion] = {}
    for row in rows:
        current = latest.get(row.model_id)
        if current is None or (row.version, row.id) > (current.version, current.id):
            latest[row.model_id] = row
    return latest


async def _load_catalog_rows(db: AsyncSession, user_id: str):
    providers = {item.id: item for item in (await db.scalars(select(LLMProvider))).all()}
    models = list((await db.scalars(select(LLMModel).where(LLMModel.is_active == True))).all())
    configs = list((await db.scalars(select(LLMConfig).where(LLMConfig.user_id == user_id, LLMConfig.is_active == True))).all())
    versions = list((await db.scalars(select(ModelProfileVersion).where(ModelProfileVersion.status == "published"))).all())
    model_ids = {version.model_id for version in versions}
    profiles = {
        item.id: item for item in (
            await db.scalars(select(ModelProfile).where(ModelProfile.id.in_(model_ids), ModelProfile.enabled == True))
        ).all()
    } if model_ids else {}
    canonical_providers = {
        item.id: item for item in (await db.scalars(select(ModelProvider).where(ModelProvider.enabled == True))).all()
    }
    return providers, models, configs, versions, profiles, canonical_providers


async def _load_certification_levels(
    db: AsyncSession, user_id: str, profile_version_ids: set[str]
) -> dict[str, set[str]]:
    if not profile_version_ids:
        return {}
    rows = (
        await db.execute(
            select(ModelCertificationRun.profile_version_id, ModelCertificationRun.level).where(
                ModelCertificationRun.user_id == user_id,
                ModelCertificationRun.profile_version_id.in_(profile_version_ids),
                ModelCertificationRun.status == "success",
            )
        )
    ).all()
    levels: dict[str, set[str]] = {}
    for profile_version_id, level in rows:
        levels.setdefault(profile_version_id, set()).add(level)
    return levels


async def list_product_catalog(db: AsyncSession, user_id: str) -> ProductCatalog:
    """Return a canonical-first catalog without mutating legacy or canonical rows."""
    providers, models, configs, versions, model_profiles, canonical_providers = await _load_catalog_rows(db, user_id)
    configs_by_model = group_legacy_configs(configs)
    profiles_by_model = _latest_published_profiles(versions)
    certification_levels = await _load_certification_levels(
        db, user_id, {profile.id for profile in profiles_by_model.values()}
    )
    items: dict[tuple[str, str], ProductCatalogItem] = {}
    legacy_ids = {model.id for model in models}
    for model in models:
        provider = providers.get(model.provider_id)
        if provider is None or not provider.is_active or not is_product_visible_provider(provider):
            continue
        if not is_product_visible_model(model):
            continue
        profile = profiles_by_model.get(model.id)
        config = select_primary_legacy_config(configs_by_model.get(model.id, []))
        api_model_id = profile.api_model_id if profile is not None else model.model_id
        item = ProductCatalogItem(
            provider_id=model.provider_id,
            api_model_id=api_model_id,
            profile_version_id=profile.id if profile is not None else None,
            legacy_model_id=model.id,
            legacy_config_id=config.id if config is not None else None,
            certification_status=_certification_status(profile.id if profile else None, config, certification_levels),
            capabilities=frozenset(normalize_capabilities(model.model_type, profile.capabilities if profile else model.capabilities or [])),
        )
        items[(item.provider_id, item.api_model_id)] = item
    for profile in sorted(profiles_by_model.values(), key=lambda item: (item.model_id, -item.version, item.id)):
        if profile.model_id in legacy_ids or not is_product_visible_model(profile):
            continue
        model_profile = model_profiles.get(profile.model_id)
        provider_id = model_profile.provider_id if model_profile is not None else None
        provider = canonical_providers.get(provider_id or "")
        if provider_id is None or provider is None or not is_product_visible_provider(provider):
            continue
        key = (provider_id, profile.api_model_id)
        items[key] = ProductCatalogItem(
            provider_id=provider_id,
            api_model_id=profile.api_model_id,
            profile_version_id=profile.id,
            legacy_model_id=None,
            legacy_config_id=None,
            certification_status=_certification_status(profile.id, None, certification_levels),
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
