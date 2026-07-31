"""Resolve persisted model bindings into provider-neutral execution context."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.bindings import (
    ModelBindingError,
    RoutePolicy,
    hydrate_resolved_binding,
    resolve_model_binding,
    route_policy_for,
    select_binding_candidate,
)
from app.features.model_config.domain import ResolvedModelBinding, normalize_capabilities
from app.features.model_config.generation_context_repository import (
    RuntimeConnectionRecord,
    load_active_binding_candidate,
    load_legacy_runtime_model,
    load_runtime_connection,
)
from app.features.model_config.recipes import STAGE_REQUIREMENTS
from app.features.model_drivers.public import (
    DriverContext,
    normalize_provider_base_url,
    select_llm_connection_driver_key,
)


@dataclass(frozen=True)
class GenerationContext:
    binding: ResolvedModelBinding
    route_policy: RoutePolicy
    api_key: str = field(repr=False)
    api_secret: str = field(default="", repr=False)
    base_url: str | None = None
    connection_params: Mapping[str, Any] = field(default_factory=dict, repr=False)
    recipe_version_id: str | None = None
    prompt_profile_version_id: str | None = None

    @property
    def profile(self):
        return self.binding.profile

    @property
    def driver_context(self):
        return DriverContext(
            profile=self.profile,
            driver_key=self.profile.driver_key,
            connection_id=self.binding.connection_id,
            secrets={"api_key": self.api_key, "api_secret": self.api_secret},
            base_url=self.base_url,
            connection_params=self.connection_params,
        )


def _recipe_binding_id(recipe_spec: Mapping[str, Any] | None, stage: str) -> str | None:
    if recipe_spec is None:
        return None
    values = recipe_spec.get(stage, {})
    return str(values.get("binding_id") or "") if isinstance(values, Mapping) else ""


async def _resolve_recipe_binding(
    db: AsyncSession,
    *,
    user_id: str,
    stage: str,
    binding_id: str,
    project_id: str | None,
    series_id: str | None,
) -> ResolvedModelBinding:
    task, capability = STAGE_REQUIREMENTS[stage]
    candidate = await load_active_binding_candidate(db, binding_id)
    if candidate is None:
        raise ModelBindingError("binding_not_found")
    if candidate.task != task:
        raise ModelBindingError("binding_task_mismatch")
    if candidate.capability != capability:
        raise ModelBindingError("binding_capability_mismatch")
    selected = select_binding_candidate(
        (candidate,), user_id=user_id, project_id=project_id, series_id=series_id,
    )
    if selected is None:
        raise ModelBindingError("binding_scope_mismatch")
    return await hydrate_resolved_binding(
        db, selected, user_id=user_id, task=task, capability=capability,
    )


def _legacy_driver(binding: ResolvedModelBinding, connection: RuntimeConnectionRecord):
    if binding.binding_version != 0:
        return binding
    model_type = binding.capability.split("_", 1)[0]
    driver_key = select_llm_connection_driver_key(connection.provider_name, model_type)
    return replace(binding, profile=_legacy_execution_profile(binding.profile, driver_key))


def _runtime_execution_binding(binding: ResolvedModelBinding) -> ResolvedModelBinding:
    """Translate catalog-oriented limits into the strict driver command contract."""
    if binding.capability != "text_generation":
        return binding
    limits = dict(binding.profile.limits or {})
    if set(limits) == {"max_prompt_chars"}:
        return binding
    maximum = limits.get("context_window") or limits.get("max_tokens") or 12000
    try:
        maximum = max(1, int(maximum))
    except (TypeError, ValueError):
        maximum = 12000
    return replace(binding, profile=replace(
        binding.profile, limits={"max_prompt_chars": maximum},
    ))


def _legacy_execution_profile(profile, driver_key: str):
    capability = next(iter(profile.capabilities), "")
    contracts = {
        "video_generation": (
            {"max_prompt_chars": 12000, "max_reference_images": 8, "max_reference_videos": 2, "max_reference_audios": 2},
            {"duration": {"type": "integer"}, "resolution": {"type": "string"}, "camera_fixed": {"type": "boolean"}, "watermark": {"type": "boolean"}, "seed": {"type": "integer"}},
        ),
        "image_generation": (
            {"max_prompt_chars": 12000,
             "max_reference_images": 10 if driver_key == "volcano_ark_image_v3" else 0},
            {"size": {"type": "string"}, "num": {"type": "integer"}, "aspect_ratio": {"type": "string"}, "n": {"type": "integer"}, "response_format": {"type": "string"}},
        ),
        "speech_generation": (
            {"max_text_chars": 12000}, {"speed": {"type": "number"}},
        ),
        "text_generation": ({"max_prompt_chars": 12000}, {}),
    }
    limits, properties = contracts.get(capability, ({}, {}))
    return replace(
        profile, driver_key=driver_key, limits=limits,
        parameter_schema={
            "type": "object", "properties": properties, "required": [], "additionalProperties": False,
        },
    )


def _normalized_base_url(
    binding: ResolvedModelBinding, connection: RuntimeConnectionRecord,
) -> str | None:
    base_url = connection.base_url
    if binding.binding_version == 0 and connection.provider_name == "minimax" and not base_url:
        from app.core.minimax_config import get_minimax_base_url

        base_url = get_minimax_base_url(connection.api_key)
    return normalize_provider_base_url(connection.provider_name, base_url)


async def resolve_generation_context(
    db: AsyncSession,
    *,
    user_id: str,
    stage: str,
    explicit_config_id: str | None = None,
    project_id: str | None = None,
    series_id: str | None = None,
    recipe_spec: Mapping[str, Any] | None = None,
    recipe_version_id: str | None = None,
    prompt_profile_version_id: str | None = None,
    prefer_canonical_binding: bool = False,
) -> GenerationContext:
    if stage not in STAGE_REQUIREMENTS:
        raise ModelBindingError("recipe_stage_invalid")
    task, capability = STAGE_REQUIREMENTS[stage]
    recipe_binding_id = _recipe_binding_id(recipe_spec, stage)
    if recipe_spec is not None and not recipe_binding_id:
        raise ModelBindingError(f"{stage}_binding_required")
    if recipe_binding_id and explicit_config_id:
        raise ModelBindingError("conflicting_explicit_overrides")
    binding = (
        await _resolve_recipe_binding(
            db, user_id=user_id, stage=stage, binding_id=recipe_binding_id,
            project_id=project_id, series_id=series_id,
        )
        if recipe_binding_id else
        await resolve_model_binding(
            db, user_id=user_id, task=task, capability=capability,
            explicit_config_id=explicit_config_id, project_id=project_id, series_id=series_id,
            prefer_canonical_binding=prefer_canonical_binding,
        )
    )
    if not binding.connection_id:
        raise ModelBindingError("connection_missing")
    connection = await load_runtime_connection(
        db, connection_id=binding.connection_id, provider_id=binding.profile.provider_id,
        legacy=binding.binding_version == 0,
    )
    if connection is None:
        raise ModelBindingError("connection_missing")
    binding = _legacy_driver(binding, connection)
    binding = _runtime_execution_binding(binding)
    params = {**dict(connection.connection_params), "provider_name": connection.provider_name}
    return GenerationContext(
        binding=binding, route_policy=route_policy_for(binding.route_policy),
        api_key=connection.api_key, api_secret=connection.api_secret,
        base_url=_normalized_base_url(binding, connection), connection_params=params,
        recipe_version_id=recipe_version_id or _legacy_provenance(binding),
        prompt_profile_version_id=prompt_profile_version_id or _legacy_provenance(binding),
    )


def _legacy_provenance(binding: ResolvedModelBinding) -> str | None:
    return "legacy:unavailable" if binding.binding_version == 0 else None


async def resolve_legacy_model_projection(
    db: AsyncSession, *, user_id: str, stage: str, config_id: str,
) -> Mapping[str, Any]:
    if stage not in STAGE_REQUIREMENTS:
        raise ModelBindingError("recipe_stage_invalid")
    record = await load_legacy_runtime_model(db, user_id=user_id, config_id=config_id)
    if record is None:
        raise ModelBindingError("legacy_config_not_found")
    capability = STAGE_REQUIREMENTS[stage][1]
    if capability not in normalize_capabilities(record.model_type, record.capabilities):
        raise ModelBindingError("capability_mismatch")
    driver_key = select_llm_connection_driver_key(
        record.provider_name, capability.split("_", 1)[0],
    )
    return {
        "config_id": record.config_id, "provider_id": record.provider_name,
        "model_id": record.model_id, "model_name": record.model_name,
        "capabilities": list(record.capabilities), "test_status": record.test_status,
        "base_url": record.base_url, "api_key": record.api_key,
        "connection_params": dict(record.connection_params), "driver_key": driver_key,
    }


__all__ = [
    "GenerationContext", "resolve_generation_context", "resolve_legacy_model_projection",
]
