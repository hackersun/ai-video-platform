"""Read-only canonical model catalog repository."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.catalog import (
    ProductCatalog,
    ProductCatalogItem,
    group_legacy_configs,
    is_product_visible_model,
    is_product_visible_provider,
    provider_model_identity,
    select_primary_legacy_config,
)
from app.features.model_config.domain import (
    BindingScope,
    ModelCapability,
    ModelProfileContract,
    SYSTEM_MODEL_BINDING_OWNER_ID,
    SYSTEM_MODEL_BINDING_SCOPE_ID,
    VERIFIED_CONNECTION_STATUSES,
    normalize_capabilities,
)
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import (
    ModelBinding,
    ModelCertificationRun,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
)


@dataclass(frozen=True)
class BindingCandidate:
    id: str
    user_id: str
    scope_type: str
    scope_id: str
    task: str
    capability: ModelCapability
    profile_version_id: str
    connection_id: str
    priority: int
    route_policy: str
    fallback_profile_version_ids: tuple[str, ...]
    version: int


@dataclass(frozen=True)
class ConnectionRecord:
    id: str
    user_id: str
    provider_id: str
    status: str


@dataclass(frozen=True)
class LegacyConfigCandidate:
    config_id: str
    model_id: str
    api_model_id: str
    provider_id: str
    provider_name: str
    capabilities: frozenset[ModelCapability]
    model_type: str | None
    raw_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class ProfileOwnerState:
    model_exists: bool
    model_enabled: bool
    provider_exists: bool
    provider_enabled: bool


async def load_shadow_connection_identity(
    db: AsyncSession, connection_id: str
) -> dict[str, str]:
    """Return legacy linkage for a migrated connection without exposing secrets."""
    connection = await db.get(ModelConnection, connection_id)
    if connection is None:
        return {}
    params = connection.connection_params or {}
    return {
        key: value for key, value in {
            "provider_id": params.get("legacy_provider_id"),
            "connection_id": params.get("legacy_config_id"),
        }.items() if isinstance(value, str) and value
    }


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


async def load_binding_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: str,
) -> tuple[BindingCandidate, ...]:
    rows = await db.scalars(
        select(ModelBinding).where(
            or_(
                and_(
                    ModelBinding.user_id == user_id,
                    ModelBinding.scope_type != BindingScope.SYSTEM.value,
                ),
                and_(
                    ModelBinding.scope_type == BindingScope.SYSTEM.value,
                    ModelBinding.user_id == SYSTEM_MODEL_BINDING_OWNER_ID,
                    ModelBinding.scope_id == SYSTEM_MODEL_BINDING_SCOPE_ID,
                ),
            ),
            ModelBinding.task == task,
            ModelBinding.capability == capability,
            ModelBinding.is_active == True,
        )
    )
    return tuple(
        BindingCandidate(
            id=row.id,
            user_id=row.user_id,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
            task=row.task,
            capability=row.capability,
            profile_version_id=row.profile_version_id,
            connection_id=row.connection_id,
            priority=row.priority,
            route_policy=row.route_policy,
            fallback_profile_version_ids=tuple(row.fallback_profile_version_ids or []),
            version=row.version,
        )
        for row in rows.all()
    )


def _connection_record(connection: ModelConnection) -> ConnectionRecord:
    return ConnectionRecord(
        id=connection.id,
        user_id=connection.user_id,
        provider_id=connection.provider_id,
        status=connection.status,
    )


async def load_connection(db: AsyncSession, connection_id: str) -> ConnectionRecord | None:
    connection = await db.get(ModelConnection, connection_id)
    return _connection_record(connection) if connection is not None else None


async def load_verified_connections(
    db: AsyncSession,
    *,
    user_id: str,
    provider_id: str,
) -> tuple[ConnectionRecord, ...]:
    rows = await db.scalars(
        select(ModelConnection)
        .where(
            ModelConnection.user_id == user_id,
            ModelConnection.provider_id == provider_id,
            ModelConnection.status.in_(VERIFIED_CONNECTION_STATUSES),
        )
        .order_by(ModelConnection.id)
    )
    return tuple(_connection_record(row) for row in rows.all())


async def load_profile_owner_state(
    db: AsyncSession,
    *,
    profile_version_id: str,
    provider_id: str,
) -> ProfileOwnerState:
    version = await db.get(ModelProfileVersion, profile_version_id)
    if version is None:
        return ProfileOwnerState(False, False, False, False)
    model = await db.get(ModelProfile, version.model_id)
    if model is not None:
        provider = await db.get(ModelProvider, provider_id)
        return ProfileOwnerState(True, model.enabled, provider is not None, bool(provider and provider.enabled))
    legacy_model = await db.get(LLMModel, version.model_id)
    legacy_provider = await db.get(LLMProvider, provider_id)
    return ProfileOwnerState(
        legacy_model is not None,
        bool(legacy_model and legacy_model.is_active),
        legacy_provider is not None,
        bool(legacy_provider and legacy_provider.is_active),
    )


async def load_legacy_config_rows(
    db: AsyncSession,
    *,
    user_id: str,
) -> tuple[LegacyConfigCandidate, ...]:
    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            LLMConfig.user_id == user_id,
            LLMConfig.is_active == True,
            LLMConfig.test_status == "success",
            LLMModel.is_active == True,
            LLMProvider.is_active == True,
        )
        .order_by(
            desc(LLMConfig.is_default),
            desc(LLMConfig.updated_at),
            desc(LLMConfig.created_at),
        )
    )
    return tuple(
        LegacyConfigCandidate(
            config_id=config.id,
            model_id=model.id,
            api_model_id=model.model_id,
            provider_id=provider.id,
            provider_name=provider.name,
            capabilities=frozenset(
                normalize_capabilities(model.model_type, model.capabilities or [])
            ),
            model_type=model.model_type,
            raw_capabilities=tuple(str(item) for item in (model.capabilities or [])),
        )
        for config, model, provider in result.all()
    )


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


def _matches_catalog_filters(
    item: ProductCatalogItem,
    *,
    capability: str | None,
    provider_id: str | None,
    status: str | None,
    query: str | None,
) -> bool:
    keyword = (query or "").strip().casefold()
    searchable = " ".join((
        item.provider_name, item.provider_code, item.model_name, item.api_model_id,
    )).casefold()
    return (
        (not capability or capability in item.capabilities)
        and (not provider_id or provider_id == item.provider_id)
        and (not status or status == item.certification_status)
        and (not keyword or keyword in searchable)
    )


async def list_product_catalog(
    db: AsyncSession,
    user_id: str,
    *,
    capability: str | None = None,
    provider_id: str | None = None,
    status: str | None = None,
    query: str | None = None,
) -> ProductCatalog:
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
            provider_name=provider.name_cn or provider.name_en or provider.name,
            provider_code=provider.name,
            model_name=model.model_name_cn or model.model_name or model.model_id,
            api_model_id=api_model_id,
            profile_version_id=profile.id if profile is not None else None,
            profile_version=profile.version if profile is not None else None,
            driver_key=profile.driver_key if profile is not None else None,
            legacy_model_id=model.id,
            legacy_config_id=config.id if config is not None else None,
            certification_status=_certification_status(profile.id if profile else None, config, certification_levels),
            capabilities=frozenset(normalize_capabilities(model.model_type, profile.capabilities if profile else model.capabilities or [])),
        )
        items[provider_model_identity(provider.name, item.api_model_id)] = item
    for profile in sorted(profiles_by_model.values(), key=lambda item: (item.model_id, -item.version, item.id)):
        if profile.model_id in legacy_ids or not is_product_visible_model(profile):
            continue
        model_profile = model_profiles.get(profile.model_id)
        if model_profile is None or not is_product_visible_model(model_profile):
            continue
        canonical_provider_id = model_profile.provider_id
        provider = canonical_providers.get(canonical_provider_id)
        if provider is None or not is_product_visible_provider(provider):
            continue
        key = provider_model_identity(provider.code, profile.api_model_id)
        items[key] = ProductCatalogItem(
            provider_id=canonical_provider_id,
            provider_name=provider.display_name,
            provider_code=provider.code,
            model_name=model_profile.display_name,
            api_model_id=profile.api_model_id,
            profile_version_id=profile.id,
            profile_version=profile.version,
            driver_key=profile.driver_key,
            legacy_model_id=None,
            legacy_config_id=None,
            certification_status=_certification_status(profile.id, None, certification_levels),
            capabilities=frozenset(normalize_capabilities(None, profile.capabilities or [])),
        )
    filtered = (
        item for item in items.values()
        if _matches_catalog_filters(
            item,
            capability=capability,
            provider_id=provider_id,
            status=status,
            query=query,
        )
    )
    return ProductCatalog(models=tuple(sorted(filtered, key=lambda item: (item.provider_name, item.model_name, item.api_model_id))))


__all__ = [
    "BindingCandidate",
    "ConnectionRecord",
    "LegacyConfigCandidate",
    "ModelConfigurationError",
    "ProfileOwnerState",
    "VERIFIED_CONNECTION_STATUSES",
    "build_legacy_profile_contract",
    "load_binding_candidates",
    "load_connection",
    "load_legacy_config_rows",
    "load_profile_owner_state",
    "load_shadow_connection_identity",
    "load_verified_connections",
    "list_product_catalog",
    "load_published_profile",
    "resolve_profile_version",
]
