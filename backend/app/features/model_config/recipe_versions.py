"""Application services for append-only production recipe versions."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import require_recipe_user_id
from app.features.model_config.recipes import (
    RecipeValidationError,
    recipe_binding_references,
    stable_recipe_checksum,
    validate_recipe,
)
from app.features.model_config.recipe_repository import (
    RecipeVersionRecord,
    create_next_recipe_version,
    create_recipe_version as create_recipe_record,
    load_recipe_binding_contracts,
    load_recipe_version,
    publish_draft_recipe_version,
    update_draft_recipe_version,
)


async def _validate_persisted_spec(
    db: AsyncSession, *, user_id: str, spec: Mapping[str, Any]
) -> None:
    ids = {binding_id for _, binding_id in recipe_binding_references(spec)}
    bindings = await load_recipe_binding_contracts(db, ids)
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
) -> RecipeVersionRecord:
    user_id = require_recipe_user_id(user_id)
    await _validate_persisted_spec(db, user_id=user_id, spec=spec)
    return await create_recipe_record(
        db,
        user_id=user_id,
        recipe_key=recipe_key,
        name=name,
        spec=spec,
        checksum=stable_recipe_checksum(spec),
    )


async def update_recipe_version(
    db: AsyncSession,
    *,
    recipe_version_id: str,
    user_id: str,
    name: str | None = None,
    spec: Mapping[str, Any] | None = None,
) -> RecipeVersionRecord:
    user_id = require_recipe_user_id(user_id)
    recipe = await load_recipe_version(db, recipe_version_id)
    if recipe is None or recipe.user_id != user_id:
        raise ValueError("recipe_version_not_found")
    next_spec = dict(spec) if spec is not None else dict(recipe.spec)
    await _validate_persisted_spec(db, user_id=user_id, spec=next_spec)
    checksum = stable_recipe_checksum(next_spec)
    if recipe.status == "published":
        next_recipe = await create_next_recipe_version(
            db,
            recipe_version_id=recipe.id,
            checksum=checksum,
            name=name or recipe.name,
            spec=next_spec,
        )
        if next_recipe is None:
            raise ValueError("recipe_version_not_found")
        return next_recipe
    if recipe.status != "draft":
        raise ValueError("recipe_version_not_editable")
    updated = await update_draft_recipe_version(
        db,
        recipe_version_id=recipe.id,
        name=name or recipe.name,
        spec=next_spec,
        checksum=checksum,
    )
    if updated is None:
        raise ValueError("recipe_version_not_found")
    return updated


async def publish_recipe_version(
    db: AsyncSession, *, recipe_version_id: str, user_id: str
) -> RecipeVersionRecord:
    user_id = require_recipe_user_id(user_id)
    recipe = await load_recipe_version(db, recipe_version_id)
    if recipe is None or recipe.user_id != user_id:
        raise ValueError("recipe_version_not_found")
    if recipe.status != "draft":
        raise ValueError("recipe_version_not_draft")
    await _validate_persisted_spec(db, user_id=user_id, spec=recipe.spec)
    published = await publish_draft_recipe_version(
        db,
        recipe_version_id=recipe.id,
        checksum=stable_recipe_checksum(recipe.spec),
    )
    if published is None:
        raise ValueError("recipe_version_not_found")
    return published


__all__ = [
    "create_recipe_version",
    "publish_recipe_version",
    "update_recipe_version",
]
