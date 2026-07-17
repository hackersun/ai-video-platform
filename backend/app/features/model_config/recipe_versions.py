"""Application services for append-only production recipe versions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.model_config.recipes import (
    RecipeBindingContract,
    RecipeValidationError,
    recipe_binding_references,
    stable_recipe_checksum,
    validate_recipe,
)
from app.features.model_config.repository import (
    load_latest_recipe_version,
    load_recipe_binding_rows,
    load_recipe_version,
    persist_recipe_version,
)
from app.models.model_center import ProductionRecipeVersion


def _binding_contract(row: tuple[Any, ...]) -> RecipeBindingContract:
    binding, profile, connection, model, provider = row
    return RecipeBindingContract(
        binding_id=binding.id,
        owner_id=binding.user_id,
        scope_type=binding.scope_type,
        scope_id=binding.scope_id,
        task=binding.task,
        capability=binding.capability,
        is_active=bool(binding.is_active),
        profile_status=profile.status if profile else "",
        profile_capabilities=frozenset(
            str(item) for item in (profile.capabilities if profile else [])
        ),
        model_enabled=bool(model and model.enabled),
        provider_enabled=bool(provider and provider.enabled),
        connection_status=connection.status if connection else "",
        connection_owner_id=connection.user_id if connection else "",
        connection_matches_profile=bool(
            connection and provider and connection.provider_id == provider.id
        ),
    )


async def _validate_persisted_spec(
    db: AsyncSession, *, user_id: str, spec: Mapping[str, Any]
) -> None:
    ids = {binding_id for _, binding_id in recipe_binding_references(spec)}
    rows = await load_recipe_binding_rows(db, ids)
    bindings = {row[0].id: _binding_contract(row) for row in rows}
    errors = validate_recipe(spec, bindings, user_id=user_id)
    if errors:
        raise RecipeValidationError(errors)


async def create_recipe_version(
    db: AsyncSession,
    *,
    user_id: str,
    recipe_key: str,
    name: str,
    spec: Mapping[str, Any],
) -> ProductionRecipeVersion:
    await _validate_persisted_spec(db, user_id=user_id, spec=spec)
    latest = await load_latest_recipe_version(db, user_id=user_id, recipe_key=recipe_key)
    recipe = ProductionRecipeVersion(
        id=str(uuid4()),
        user_id=user_id,
        recipe_key=recipe_key,
        name=name,
        version=(latest.version + 1) if latest else 1,
        status="draft",
        spec=deepcopy(dict(spec)),
        checksum=stable_recipe_checksum(spec),
    )
    return await persist_recipe_version(db, recipe)


async def update_recipe_version(
    db: AsyncSession,
    *,
    recipe_version_id: str,
    user_id: str,
    name: str | None = None,
    spec: Mapping[str, Any] | None = None,
) -> ProductionRecipeVersion:
    recipe = await load_recipe_version(db, recipe_version_id)
    if recipe is None or recipe.user_id != user_id:
        raise ValueError("recipe_version_not_found")
    next_spec = deepcopy(dict(spec)) if spec is not None else deepcopy(recipe.spec)
    await _validate_persisted_spec(db, user_id=user_id, spec=next_spec)
    checksum = stable_recipe_checksum(next_spec)
    if recipe.status == "published":
        next_recipe = recipe.create_next_version(
            checksum=checksum, name=name or recipe.name, spec=next_spec,
        )
        return await persist_recipe_version(db, next_recipe)
    if recipe.status != "draft":
        raise ValueError("recipe_version_not_editable")
    recipe.name = name or recipe.name
    recipe.spec = next_spec
    recipe.checksum = checksum
    recipe.revision += 1
    return await persist_recipe_version(db, recipe)


async def publish_recipe_version(
    db: AsyncSession, *, recipe_version_id: str, user_id: str
) -> ProductionRecipeVersion:
    recipe = await load_recipe_version(db, recipe_version_id)
    if recipe is None or recipe.user_id != user_id:
        raise ValueError("recipe_version_not_found")
    if recipe.status != "draft":
        raise ValueError("recipe_version_not_draft")
    await _validate_persisted_spec(db, user_id=user_id, spec=recipe.spec)
    recipe.checksum = stable_recipe_checksum(recipe.spec)
    recipe.status = "published"
    recipe.published_at = utc_now()
    recipe.revision += 1
    return await persist_recipe_version(db, recipe)


__all__ = [
    "create_recipe_version",
    "publish_recipe_version",
    "update_recipe_version",
]
