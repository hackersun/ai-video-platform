"""Deterministic scoped model binding resolution and retry safety policy."""

from __future__ import annotations

from typing import Literal, Mapping, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import (
    ModelCapability,
    ModelProfileContract,
    ResolvedModelBinding,
    normalize_capabilities,
)
from app.features.model_config.repository import (
    ModelConfigurationError,
    VERIFIED_CONNECTION_STATUSES,
    load_binding_candidates,
    load_legacy_config_rows,
    load_verified_connections,
    resolve_profile_version,
)
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.model_center import (
    ModelBinding, ModelConnection, ModelProfile, ModelProfileVersion, ModelProvider,
)


SCOPE_PRECEDENCE = ("request", "series", "project", "user", "system")

class ModelBindingError(ModelConfigurationError):
    """Raised when a binding cannot be resolved without weakening safety."""


class RoutePolicy(TypedDict):
    allow_pre_submit_fallback: bool
    allow_post_acceptance_fallback: Literal[False]
    retry_policy: Literal["never", "confirmed_pre_acceptance_only", "status_poll_only"]

def route_policy_for(policy: str) -> RoutePolicy:
    if policy == "pre_submit_fallback":
        return {
            "allow_pre_submit_fallback": True,
            "allow_post_acceptance_fallback": False,
            "retry_policy": "confirmed_pre_acceptance_only",
        }
    retry = "status_poll_only" if policy == "status_poll_only" else "never"
    return {
        "allow_pre_submit_fallback": False,
        "allow_post_acceptance_fallback": False,
        "retry_policy": retry,
    }

def _scope_matches(
    binding: ModelBinding,
    scope: str,
    *,
    user_id: str,
    project_id: str | None,
    series_id: str | None,
) -> bool:
    if binding.scope_type != scope:
        return False
    expected = {"series": series_id, "project": project_id}.get(scope)
    if scope in {"series", "project"}:
        return bool(expected) and binding.scope_id == expected
    if scope == "user":
        return binding.scope_id in {"", user_id}
    return scope == "system" and binding.scope_id == ""

def select_binding_candidate(
    candidates: tuple[ModelBinding, ...],
    *,
    user_id: str,
    project_id: str | None,
    series_id: str | None,
) -> ModelBinding | None:
    for scope in SCOPE_PRECEDENCE[1:]:
        matches = [
            item for item in candidates
            if _scope_matches(
                item, scope, user_id=user_id, project_id=project_id, series_id=series_id
            )
        ]
        if matches:
            return min(matches, key=lambda item: (item.priority, -item.version, item.id))
    return None

async def _ensure_profile_owners(
    db: AsyncSession,
    version: ModelProfileVersion,
    provider_id: str,
) -> None:
    model = await db.get(ModelProfile, version.model_id)
    if model is not None:
        provider = await db.get(ModelProvider, provider_id)
        if not model.enabled:
            raise ModelBindingError("model_profile_disabled")
        if provider is None or not provider.enabled:
            raise ModelBindingError("model_provider_disabled")
        return
    legacy_model = await db.get(LLMModel, version.model_id)
    legacy_provider = await db.get(LLMProvider, provider_id)
    if legacy_model is None or not legacy_model.is_active:
        raise ModelBindingError("model_profile_disabled")
    if legacy_provider is None or not legacy_provider.is_active:
        raise ModelBindingError("model_provider_disabled")

async def _ensure_profile_available(
    db: AsyncSession,
    profile_version_id: str,
    capability: ModelCapability,
) -> ModelProfileContract:
    try:
        profile = await resolve_profile_version(db, profile_version_id=profile_version_id)
    except ModelConfigurationError as error:
        raise ModelBindingError(str(error)) from error
    if capability not in profile.capabilities:
        raise ModelBindingError("capability_mismatch")
    version = await db.get(ModelProfileVersion, profile_version_id)
    if version is None:
        raise ModelBindingError("model_profile_not_published")
    await _ensure_profile_owners(db, version, profile.provider_id)
    return profile

def _validate_connection(
    connection: ModelConnection | None,
    *,
    user_id: str,
    provider_id: str,
) -> ModelConnection:
    if connection is None:
        raise ModelBindingError("connection_missing")
    if connection.user_id != user_id or connection.provider_id != provider_id:
        raise ModelBindingError("connection_scope_mismatch")
    if connection.status not in VERIFIED_CONNECTION_STATUSES:
        raise ModelBindingError("connection_not_verified")
    return connection

async def _connection_for_profile(
    db: AsyncSession,
    *,
    user_id: str,
    profile: ModelProfileContract,
) -> ModelConnection:
    connections = await load_verified_connections(
        db, user_id=user_id, provider_id=profile.provider_id
    )
    if not connections:
        raise ModelBindingError("connection_not_verified")
    return connections[0]

async def hydrate_resolved_binding(
    db: AsyncSession,
    binding: ModelBinding,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
) -> ResolvedModelBinding:
    profile = await _ensure_profile_available(db, binding.profile_version_id, capability)
    connection_user_id = binding.user_id if binding.scope_type == "system" else user_id
    connection = _validate_connection(
        await db.get(ModelConnection, binding.connection_id),
        user_id=connection_user_id,
        provider_id=profile.provider_id,
    )
    return ResolvedModelBinding(
        task=task, capability=capability, profile=profile, connection_id=connection.id,
        binding_version=binding.version, source_scope=binding.scope_type,
    )

def legacy_config_sort_key(
    row: tuple[LLMConfig, LLMModel, LLMProvider],
) -> tuple[int, float, str]:
    config = row[0]
    updated = config.updated_at or config.created_at
    return (-int(bool(config.is_default)), -(updated.timestamp() if updated else 0), config.id)

def legacy_model_capabilities(model: LLMModel) -> set[ModelCapability]:
    return normalize_capabilities(model.model_type, model.capabilities or [])


def _select_legacy_row(
    rows: tuple[tuple[LLMConfig, LLMModel, LLMProvider], ...],
    capability: ModelCapability,
    explicit_config_id: str | None,
) -> tuple[LLMConfig, LLMModel, LLMProvider] | None:
    eligible = [row for row in rows if capability in legacy_model_capabilities(row[1])]
    if explicit_config_id:
        return next((row for row in eligible if row[0].id == explicit_config_id), None)
    return min(eligible, key=legacy_config_sort_key) if eligible else None


async def resolve_legacy_binding(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
    explicit_config_id: str | None = None,
) -> ResolvedModelBinding:
    selected = _select_legacy_row(
        await load_legacy_config_rows(db, user_id=user_id), capability, explicit_config_id
    )
    if selected is None:
        code = "legacy_config_not_verified" if explicit_config_id else "model_binding_not_found"
        raise ModelBindingError(code)
    config, model, _provider = selected
    profile = await resolve_profile_version(db, legacy_model_id=model.id)
    return ResolvedModelBinding(
        task=task, capability=capability, profile=profile, connection_id=config.id,
        binding_version=0, source_scope="request" if explicit_config_id else "legacy",
    )


async def _resolve_explicit_profile(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
    profile_version_id: str,
) -> ResolvedModelBinding:
    profile = await _ensure_profile_available(db, profile_version_id, capability)
    connection = await _connection_for_profile(db, user_id=user_id, profile=profile)
    return ResolvedModelBinding(
        task=task, capability=capability, profile=profile, connection_id=connection.id,
        binding_version=0, source_scope="request",
    )


async def resolve_model_binding(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
    explicit_profile_version_id: str | None = None,
    explicit_config_id: str | None = None,
    project_id: str | None = None,
    series_id: str | None = None,
) -> ResolvedModelBinding:
    if explicit_profile_version_id and explicit_config_id:
        raise ModelBindingError("conflicting_explicit_overrides")
    if explicit_config_id:
        return await resolve_legacy_binding(
            db, user_id=user_id, task=task, capability=capability,
            explicit_config_id=explicit_config_id,
        )
    if explicit_profile_version_id:
        return await _resolve_explicit_profile(
            db, user_id=user_id, task=task, capability=capability,
            profile_version_id=explicit_profile_version_id,
        )
    candidates = await load_binding_candidates(
        db, user_id=user_id, task=task, capability=capability
    )
    selected = select_binding_candidate(
        candidates, user_id=user_id, project_id=project_id, series_id=series_id
    )
    if selected is not None:
        return await hydrate_resolved_binding(
            db, selected, user_id=user_id, task=task, capability=capability
        )
    return await resolve_legacy_binding(db, user_id=user_id, task=task, capability=capability)


async def resolve_retry_binding(
    db: AsyncSession,
    binding: ModelBinding,
    operation: Any,
) -> ModelProfileContract:
    value = (
        operation.get
        if isinstance(operation, Mapping)
        else lambda key, default=None: getattr(operation, key, default)
    )
    status = str(value("status", "") or "")
    accepted = {"accepted", "submitted", "queued", "pending", "running", "succeeded", "completed", "failed", "unknown"}
    if value("provider_accepted") or value("accepted_at") or value("provider_task_id") or status in accepted:
        raise ModelBindingError("status_only")
    policy = route_policy_for(binding.route_policy)
    if status != "pre_submit_failed" or not policy["allow_pre_submit_fallback"]:
        raise ModelBindingError("fallback_not_allowed")
    if not binding.fallback_profile_version_ids:
        raise ModelBindingError("fallback_not_configured")
    profile = await _ensure_profile_available(
        db, binding.fallback_profile_version_ids[0], binding.capability
    )
    await _connection_for_profile(db, user_id=binding.user_id, profile=profile)
    return profile


__all__ = [
    "ModelBindingError", "RoutePolicy", "SCOPE_PRECEDENCE", "hydrate_resolved_binding",
    "legacy_config_sort_key", "legacy_model_capabilities", "resolve_legacy_binding",
    "resolve_model_binding", "resolve_retry_binding", "route_policy_for", "select_binding_candidate",
]
