"""Read-only, secret-free effective binding views for recipe editors."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.recipes import STAGE_REQUIREMENTS, recipe_binding_references
from app.features.model_config.domain import (
    VERIFIED_CONNECTION_STATUSES,
    is_safe_model_binding_scope,
    is_trusted_system_binding,
)
from app.models.model_center import (
    ModelBinding,
    ModelCertificationRun,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion


async def recipe_binding_resolution(
    db: AsyncSession, *, user_id: str, recipe_version_id: str,
) -> dict | None:
    recipe = await db.scalar(select(ProductionRecipeVersion).where(
        ProductionRecipeVersion.id == recipe_version_id,
        ProductionRecipeVersion.user_id == user_id,
    ))
    if recipe is None:
        return None
    stages = []
    for stage, binding_id in recipe_binding_references(recipe.spec or {}):
        stages.append(await _stage_resolution(db, user_id=user_id, stage=stage, binding_id=binding_id))
    return {"recipe_version_id": recipe.id, "stages": stages}


async def _stage_resolution(
    db: AsyncSession, *, user_id: str, stage: str, binding_id: str,
) -> dict:
    row = await db.execute(select(
        ModelBinding, ModelProfileVersion, ModelConnection, ModelProfile, ModelProvider,
    ).outerjoin(
        ModelProfileVersion, ModelProfileVersion.id == ModelBinding.profile_version_id,
    ).outerjoin(ModelConnection, ModelConnection.id == ModelBinding.connection_id).outerjoin(
        ModelProfile, ModelProfile.id == ModelProfileVersion.model_id,
    ).outerjoin(ModelProvider, ModelProvider.id == ModelProfile.provider_id).where(
        ModelBinding.id == binding_id,
    ))
    pair = row.one_or_none()
    if pair is None:
        return _unavailable(stage, binding_id, "binding_not_found")
    binding, profile, connection, model, provider = pair
    error = _binding_safety_error(
        binding=binding, profile=profile, connection=connection, model=model,
        provider=provider, user_id=user_id, stage=stage,
    )
    if error:
        return _unavailable(stage, binding_id, error)
    prompt = await _selected_prompt_profile(db, user_id=user_id, key=profile.prompt_profile_key)
    certification = await _latest_certification(
        db, user_id=user_id, profile_version_id=profile.id, connection_id=binding.connection_id,
    )
    return {
        "stage": stage, "binding_id": binding.id, "resolution_status": "resolved", "error_code": None,
        "profile": {
            "id": profile.id, "api_model_id": profile.api_model_id, "version": profile.version,
            "driver_key": profile.driver_key, "contract_version": profile.contract_version,
        },
        "prompt_profile": prompt,
        "latest_certification": certification,
    }


def _unavailable(stage: str, binding_id: str, error_code: str) -> dict:
    return {
        "stage": stage, "binding_id": binding_id, "resolution_status": "unavailable",
        "error_code": error_code, "profile": None, "prompt_profile": None,
        "latest_certification": {"level": "none", "status": "none"},
    }


def _binding_safety_error(*, binding, profile, connection, model, provider, user_id: str, stage: str) -> str | None:
    expected_task, expected_capability = STAGE_REQUIREMENTS[stage]
    if binding.task != expected_task:
        return "binding_task_mismatch"
    if binding.capability != expected_capability:
        return "binding_capability_mismatch"
    trusted_system = is_trusted_system_binding(
        scope_type=binding.scope_type, owner_id=binding.user_id, scope_id=binding.scope_id,
    )
    if binding.user_id != user_id and not trusted_system:
        return "binding_scope_invalid"
    if not is_safe_model_binding_scope(
        scope_type=binding.scope_type, owner_id=binding.user_id, scope_id=binding.scope_id,
        allow_unscoped_user=True,
    ):
        return "binding_scope_invalid"
    if not binding.is_active:
        return "binding_inactive"
    if profile is None or profile.status != "published":
        return "binding_profile_not_published"
    if expected_capability not in set(profile.capabilities or []):
        return "binding_capability_mismatch"
    if model is None or not model.enabled or provider is None or not provider.enabled:
        return "binding_owner_disabled"
    if connection is None or connection.status not in VERIFIED_CONNECTION_STATUSES:
        return "binding_connection_not_verified"
    if connection.user_id != binding.user_id:
        return "binding_owner_mismatch"
    if connection.provider_id != provider.id:
        return "binding_connection_mismatch"
    return None


async def _selected_prompt_profile(db: AsyncSession, *, user_id: str, key: str | None) -> dict | None:
    if not key:
        return None
    row = await db.execute(select(PromptProfile, PromptProfileVersion).join(
        PromptProfileVersion, PromptProfileVersion.profile_id == PromptProfile.id,
    ).where(
        PromptProfile.key == key,
        PromptProfile.user_id.in_((user_id, "system")),
        PromptProfileVersion.status == "published",
    ).order_by(desc(PromptProfileVersion.version), PromptProfileVersion.id).limit(1))
    pair = row.one_or_none()
    if pair is None:
        return None
    profile, version = pair
    return {"id": version.id, "key": profile.key, "version": version.version}


async def _latest_certification(
    db: AsyncSession, *, user_id: str, profile_version_id: str, connection_id: str,
) -> dict:
    row = await db.scalar(select(ModelCertificationRun).where(
        ModelCertificationRun.user_id == user_id,
        ModelCertificationRun.profile_version_id == profile_version_id,
        ModelCertificationRun.connection_id == connection_id,
    ).order_by(desc(ModelCertificationRun.created_at), desc(ModelCertificationRun.id)).limit(1))
    if row is None:
        return {"level": "none", "status": "none"}
    return {"level": row.level, "status": row.status}
