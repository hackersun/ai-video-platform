"""Repository reads required to hydrate an executable model binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.repository import BindingCandidate
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import ModelBinding, ModelConnection, ModelProvider


@dataclass(frozen=True)
class RuntimeConnectionRecord:
    provider_name: str
    api_key: str
    api_secret: str
    base_url: str | None
    connection_params: Mapping[str, Any]


@dataclass(frozen=True)
class LegacyRuntimeModelRecord:
    config_id: str
    provider_name: str
    model_id: str
    model_name: str
    model_type: str
    capabilities: tuple[str, ...]
    test_status: str | None
    api_key: str
    base_url: str | None
    connection_params: Mapping[str, Any]


async def load_active_binding_candidate(
    db: AsyncSession, binding_id: str,
) -> BindingCandidate | None:
    row = await db.get(ModelBinding, binding_id)
    if row is None or not row.is_active:
        return None
    return BindingCandidate(
        id=row.id, user_id=row.user_id, scope_type=row.scope_type,
        scope_id=row.scope_id, task=row.task, capability=row.capability,
        profile_version_id=row.profile_version_id, connection_id=row.connection_id,
        priority=row.priority, route_policy=row.route_policy,
        fallback_profile_version_ids=tuple(row.fallback_profile_version_ids or []),
        version=row.version,
    )


async def _legacy_connection(
    db: AsyncSession, connection_id: str,
) -> RuntimeConnectionRecord | None:
    config = await db.get(LLMConfig, connection_id)
    if config is None:
        return None
    model = await db.get(LLMModel, config.model_id)
    provider = await db.get(LLMProvider, model.provider_id) if model else None
    if model is None or provider is None:
        return None
    params = dict(config.extra_params or {})
    return RuntimeConnectionRecord(
        provider_name=provider.name or provider.id,
        api_key=config.get_api_key_decrypted(),
        api_secret=config.get_api_secret_decrypted(),
        base_url=params.get("base_url") or model.base_url or provider.base_url,
        connection_params=params,
    )


async def load_legacy_runtime_model(
    db: AsyncSession, *, user_id: str, config_id: str,
) -> LegacyRuntimeModelRecord | None:
    config = await db.get(LLMConfig, config_id)
    if config is None or config.user_id != user_id or not config.is_active:
        return None
    model = await db.get(LLMModel, config.model_id)
    provider = await db.get(LLMProvider, model.provider_id) if model else None
    if model is None or provider is None or not model.is_active or not provider.is_active:
        return None
    params = dict(config.extra_params or {})
    return LegacyRuntimeModelRecord(
        config_id=config.id, provider_name=provider.name or provider.id,
        model_id=model.model_id, model_name=model.model_name_cn or model.model_name,
        model_type=str(model.model_type or ""),
        capabilities=tuple(str(item) for item in (model.capabilities or [])),
        test_status=config.test_status, api_key=config.get_api_key_decrypted(),
        base_url=params.get("base_url") or model.base_url or provider.base_url,
        connection_params=params,
    )


async def _canonical_provider_name(db: AsyncSession, provider_id: str) -> str:
    provider = await db.get(ModelProvider, provider_id)
    if provider is not None:
        return provider.code
    legacy = await db.get(LLMProvider, provider_id)
    return legacy.name if legacy is not None else provider_id


async def load_runtime_connection(
    db: AsyncSession,
    *,
    connection_id: str,
    provider_id: str,
    legacy: bool,
) -> RuntimeConnectionRecord | None:
    if legacy:
        return await _legacy_connection(db, connection_id)
    connection = await db.get(ModelConnection, connection_id)
    if connection is None:
        return None
    endpoints = dict(connection.endpoint_overrides or {})
    return RuntimeConnectionRecord(
        provider_name=await _canonical_provider_name(db, provider_id),
        api_key=connection.get_api_key_decrypted(),
        api_secret=connection.get_api_secret_decrypted(),
        base_url=endpoints.get("base_url") or endpoints.get("api_base_url"),
        connection_params=dict(connection.connection_params or {}),
    )


__all__ = [
    "LegacyRuntimeModelRecord", "RuntimeConnectionRecord", "load_active_binding_candidate",
    "load_legacy_runtime_model", "load_runtime_connection",
]
