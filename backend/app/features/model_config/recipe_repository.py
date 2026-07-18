"""Repository-owned persistence for versioned production recipes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.model_config.domain import RecipeBindingContract
from app.models.model_center import (
    ModelBinding,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)


@dataclass(frozen=True)
class RecipeVersionRecord:
    id: str
    user_id: str
    recipe_key: str
    name: str
    version: int
    status: str
    spec: Mapping[str, Any]
    checksum: str
    revision: int


def _recipe_record(row: ProductionRecipeVersion) -> RecipeVersionRecord:
    return RecipeVersionRecord(
        id=row.id,
        user_id=row.user_id,
        recipe_key=row.recipe_key,
        name=row.name,
        version=row.version,
        status=row.status,
        spec=deepcopy(row.spec),
        checksum=row.checksum,
        revision=row.revision,
    )


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


async def load_recipe_binding_contracts(
    db: AsyncSession, binding_ids: set[str]
) -> dict[str, RecipeBindingContract]:
    if not binding_ids:
        return {}
    rows = await db.execute(
        select(ModelBinding, ModelProfileVersion, ModelConnection, ModelProfile, ModelProvider)
        .outerjoin(ModelProfileVersion, ModelProfileVersion.id == ModelBinding.profile_version_id)
        .outerjoin(ModelConnection, ModelConnection.id == ModelBinding.connection_id)
        .outerjoin(ModelProfile, ModelProfile.id == ModelProfileVersion.model_id)
        .outerjoin(ModelProvider, ModelProvider.id == ModelProfile.provider_id)
        .where(ModelBinding.id.in_(binding_ids))
    )
    return {row[0].id: _binding_contract(row) for row in rows.all()}


async def load_recipe_version(
    db: AsyncSession, recipe_version_id: str
) -> RecipeVersionRecord | None:
    row = await db.get(ProductionRecipeVersion, recipe_version_id)
    return _recipe_record(row) if row is not None else None


async def create_recipe_version(
    db: AsyncSession,
    *,
    user_id: str,
    recipe_key: str,
    name: str,
    spec: Mapping[str, Any],
    checksum: str,
) -> RecipeVersionRecord:
    latest = await db.scalar(
        select(ProductionRecipeVersion)
        .where(
            ProductionRecipeVersion.user_id == user_id,
            ProductionRecipeVersion.recipe_key == recipe_key,
        )
        .order_by(desc(ProductionRecipeVersion.version), desc(ProductionRecipeVersion.id))
        .limit(1)
    )
    row = ProductionRecipeVersion(
        id=str(uuid4()),
        user_id=user_id,
        recipe_key=recipe_key,
        name=name,
        version=(latest.version + 1) if latest else 1,
        status="draft",
        spec=deepcopy(dict(spec)),
        checksum=checksum,
    )
    db.add(row)
    await db.flush()
    return _recipe_record(row)


async def create_next_recipe_version(
    db: AsyncSession,
    *,
    recipe_version_id: str,
    name: str,
    spec: Mapping[str, Any],
    checksum: str,
) -> RecipeVersionRecord | None:
    row = await db.get(ProductionRecipeVersion, recipe_version_id)
    if row is None:
        return None
    next_row = row.create_next_version(
        checksum=checksum, name=name, spec=deepcopy(dict(spec)),
    )
    db.add(next_row)
    await db.flush()
    return _recipe_record(next_row)


async def update_draft_recipe_version(
    db: AsyncSession,
    *,
    recipe_version_id: str,
    name: str,
    spec: Mapping[str, Any],
    checksum: str,
) -> RecipeVersionRecord | None:
    row = await db.get(ProductionRecipeVersion, recipe_version_id)
    if row is None:
        return None
    row.name = name
    row.spec = deepcopy(dict(spec))
    row.checksum = checksum
    row.revision += 1
    await db.flush()
    return _recipe_record(row)


async def publish_draft_recipe_version(
    db: AsyncSession, *, recipe_version_id: str, checksum: str
) -> RecipeVersionRecord | None:
    row = await db.get(ProductionRecipeVersion, recipe_version_id)
    if row is None:
        return None
    row.checksum = checksum
    row.status = "published"
    row.published_at = utc_now()
    row.revision += 1
    await db.flush()
    return _recipe_record(row)


__all__ = [
    "RecipeVersionRecord",
    "create_next_recipe_version",
    "create_recipe_version",
    "load_recipe_binding_contracts",
    "load_recipe_version",
    "publish_draft_recipe_version",
    "update_draft_recipe_version",
]
