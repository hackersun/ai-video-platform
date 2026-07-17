"""Read-only, secret-free effective binding views for recipe editors."""

from __future__ import annotations

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.recipes import recipe_binding_references
from app.models.model_center import (
    ModelBinding,
    ModelCertificationRun,
    ModelProfileVersion,
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
        item = await _stage_resolution(db, user_id=user_id, stage=stage, binding_id=binding_id)
        if item is not None:
            stages.append(item)
    return {"recipe_version_id": recipe.id, "stages": stages}


async def _stage_resolution(
    db: AsyncSession, *, user_id: str, stage: str, binding_id: str,
) -> dict | None:
    row = await db.execute(select(ModelBinding, ModelProfileVersion).join(
        ModelProfileVersion, ModelProfileVersion.id == ModelBinding.profile_version_id,
    ).where(ModelBinding.id == binding_id, or_(
        ModelBinding.user_id == user_id,
        ModelBinding.scope_type == "system",
    )))
    pair = row.one_or_none()
    if pair is None:
        return None
    binding, profile = pair
    prompt = await _selected_prompt_profile(db, user_id=user_id, key=profile.prompt_profile_key)
    certification = await _latest_certification(
        db, user_id=user_id, profile_version_id=profile.id, connection_id=binding.connection_id,
    )
    return {
        "stage": stage, "binding_id": binding.id,
        "profile": {
            "id": profile.id, "api_model_id": profile.api_model_id, "version": profile.version,
            "driver_key": profile.driver_key, "contract_version": profile.contract_version,
        },
        "prompt_profile": prompt,
        "latest_certification": certification,
    }


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
