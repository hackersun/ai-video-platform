"""Deterministic scoped model binding resolution and retry safety policy."""

from __future__ import annotations

from typing import Literal, Mapping, Protocol, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import (
    BindingScope,
    ModelCapability,
    ModelProfileContract,
    ResolvedModelBinding,
    SYSTEM_MODEL_BINDING_OWNER_ID,
    is_safe_model_binding_scope,
    is_trusted_system_binding,
)
from app.features.model_config.repository import (
    BindingCandidate,
    ConnectionRecord,
    LegacyConfigCandidate,
    ModelConfigurationError,
    ProfileOwnerState,
    VERIFIED_CONNECTION_STATUSES,
    load_binding_candidates,
    load_connection,
    load_legacy_config_rows,
    load_profile_owner_state,
    load_shadow_connection_identity,
    load_verified_connections,
    resolve_profile_version,
)
from app.features.model_config.settings import (
    ModelCenterReadMode,
    legacy_canonical_fallback_enabled,
    model_center_read_mode,
)
from app.features.model_config.shadow_compare import compare_resolutions, record_shadow_difference


SCOPE_PRECEDENCE = ("request", "series", "project", "user", "system")

class ModelBindingError(ModelConfigurationError):
    """Raised when a binding cannot be resolved without weakening safety."""


class RoutePolicy(TypedDict):
    allow_pre_submit_fallback: bool
    allow_post_acceptance_fallback: Literal[False]
    retry_policy: Literal["never", "confirmed_pre_acceptance_only", "status_poll_only"]


class RetryBinding(Protocol):
    user_id: str
    capability: ModelCapability
    route_policy: str
    fallback_profile_version_ids: list[str] | tuple[str, ...]

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
    binding: BindingCandidate,
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
        return binding.user_id == user_id and is_safe_model_binding_scope(
            scope_type=binding.scope_type,
            owner_id=binding.user_id,
            scope_id=binding.scope_id,
            allow_unscoped_user=True,
        )
    return scope == BindingScope.SYSTEM.value and is_safe_model_binding_scope(
        scope_type=binding.scope_type,
        owner_id=binding.user_id,
        scope_id=binding.scope_id,
    )

def select_binding_candidate(
    candidates: tuple[BindingCandidate, ...],
    *,
    user_id: str,
    project_id: str | None,
    series_id: str | None,
) -> BindingCandidate | None:
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

def _ensure_profile_owners(state: ProfileOwnerState) -> None:
    if not state.model_exists or not state.model_enabled:
        raise ModelBindingError("model_profile_disabled")
    if not state.provider_exists or not state.provider_enabled:
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
    state = await load_profile_owner_state(
        db, profile_version_id=profile_version_id, provider_id=profile.provider_id
    )
    _ensure_profile_owners(state)
    return profile

def _validate_connection(
    connection: ConnectionRecord | None,
    *,
    user_id: str,
    provider_id: str,
) -> ConnectionRecord:
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
) -> ConnectionRecord:
    connections = await load_verified_connections(
        db, user_id=user_id, provider_id=profile.provider_id
    )
    if not connections:
        raise ModelBindingError("connection_not_verified")
    return connections[0]

async def hydrate_resolved_binding(
    db: AsyncSession,
    binding: BindingCandidate,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
) -> ResolvedModelBinding:
    profile = await _ensure_profile_available(db, binding.profile_version_id, capability)
    trusted_system = is_trusted_system_binding(
        scope_type=binding.scope_type,
        owner_id=binding.user_id,
        scope_id=binding.scope_id,
    )
    if binding.scope_type == BindingScope.SYSTEM.value and not trusted_system:
        raise ModelBindingError("untrusted_system_binding")
    connection_user_id = SYSTEM_MODEL_BINDING_OWNER_ID if trusted_system else user_id
    connection = _validate_connection(
        await load_connection(db, binding.connection_id),
        user_id=connection_user_id,
        provider_id=profile.provider_id,
    )
    return ResolvedModelBinding(
        task=task, capability=capability, profile=profile, connection_id=connection.id,
        binding_version=binding.version, source_scope=binding.scope_type,
        route_policy=binding.route_policy, binding_id=binding.id,
    )

def _select_legacy_row(
    rows: tuple[LegacyConfigCandidate, ...],
    capability: ModelCapability,
    explicit_config_id: str | None,
) -> LegacyConfigCandidate | None:
    eligible = [row for row in rows if capability in row.capabilities]
    if explicit_config_id:
        return next((row for row in eligible if row.config_id == explicit_config_id), None)
    return eligible[0] if eligible else None


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
    profile = await resolve_profile_version(db, legacy_model_id=selected.model_id)
    return ResolvedModelBinding(
        task=task, capability=capability, profile=profile, connection_id=selected.config_id,
        binding_version=0, source_scope="request" if explicit_config_id else "legacy",
        binding_id=f"legacy:{selected.config_id}",
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
        binding_id=f"request:{profile.profile_version_id}:{connection.id}",
    )


async def _resolve_canonical_binding(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
    project_id: str | None,
    series_id: str | None,
) -> ResolvedModelBinding | None:
    candidates = await load_binding_candidates(
        db, user_id=user_id, task=task, capability=capability
    )
    selected = select_binding_candidate(
        candidates, user_id=user_id, project_id=project_id, series_id=series_id
    )
    if selected is None:
        return None
    return await hydrate_resolved_binding(
        db, selected, user_id=user_id, task=task, capability=capability
    )


async def _shadow_resolution(
    db: AsyncSession, binding: ResolvedModelBinding,
) -> dict[str, object]:
    identity = await load_shadow_connection_identity(db, binding.connection_id)
    return {
        "capability": binding.capability,
        "provider_id": identity.get("provider_id", binding.profile.provider_id),
        "api_model_id": binding.profile.api_model_id,
        "connection_id": identity.get("connection_id", binding.connection_id),
        "prompt_profile_key": binding.profile.prompt_profile_key,
        "prompt_profile_version_id": None,
        "native_audio": bool(binding.profile.default_params.get("native_audio")),
        "output_contract": dict(binding.profile.output_contract),
    }


async def _resolve_by_read_mode(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
    project_id: str | None,
    series_id: str | None,
    prefer_canonical_binding: bool,
) -> ResolvedModelBinding:
    if prefer_canonical_binding:
        preferred = await _resolve_canonical_binding(
            db, user_id=user_id, task=task, capability=capability,
            project_id=project_id, series_id=series_id,
        )
        if preferred is not None:
            return preferred
    mode = model_center_read_mode()
    if mode is ModelCenterReadMode.CANONICAL:
        canonical = await _resolve_canonical_binding(
            db, user_id=user_id, task=task, capability=capability,
            project_id=project_id, series_id=series_id,
        )
        if canonical is None:
            raise ModelBindingError("model_binding_not_found")
        return canonical
    try:
        legacy = await resolve_legacy_binding(
            db, user_id=user_id, task=task, capability=capability,
        )
    except ModelBindingError:
        if mode is ModelCenterReadMode.LEGACY and legacy_canonical_fallback_enabled():
            canonical = await _resolve_canonical_binding(
                db, user_id=user_id, task=task, capability=capability,
                project_id=project_id, series_id=series_id,
            )
            if canonical is not None:
                return canonical
        raise
    if mode is not ModelCenterReadMode.SHADOW:
        return legacy
    try:
        canonical = await _resolve_canonical_binding(
            db, user_id=user_id, task=task, capability=capability,
            project_id=project_id, series_id=series_id,
        )
    except ModelBindingError:
        canonical = None
    if canonical is not None:
        comparison = compare_resolutions(
            legacy=await _shadow_resolution(db, legacy),
            canonical=await _shadow_resolution(db, canonical),
        )
        try:
            await record_shadow_difference(
                db, user_id=user_id, resource_id=canonical.binding_id, comparison=comparison,
            )
        except Exception:
            pass
    return legacy


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
    prefer_canonical_binding: bool = False,
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
    return await _resolve_by_read_mode(
        db, user_id=user_id, task=task, capability=capability,
        project_id=project_id, series_id=series_id,
        prefer_canonical_binding=prefer_canonical_binding,
    )


async def resolve_retry_binding(
    db: AsyncSession,
    binding: RetryBinding,
    operation: object,
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
    "resolve_legacy_binding", "resolve_model_binding", "resolve_retry_binding",
    "route_policy_for", "select_binding_candidate",
]
