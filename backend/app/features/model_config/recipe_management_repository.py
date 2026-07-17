"""Repository operations for Model Center recipe mutations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.model_center import ModelConfigAuditEvent, ProductionRecipeVersion


@dataclass(frozen=True)
class RecipeRow:
    id: str
    user_id: str
    recipe_key: str
    name: str
    version: int
    status: str
    spec: dict
    revision: int


def as_recipe_row(row: ProductionRecipeVersion) -> RecipeRow:
    return RecipeRow(
        id=row.id, user_id=row.user_id, recipe_key=row.recipe_key, name=row.name,
        version=row.version, status=row.status, spec=deepcopy(dict(row.spec or {})),
        revision=row.revision,
    )


async def create_recipe_draft(
    db: AsyncSession, *, user_id: str, recipe_key: str, name: str, spec: dict, checksum: str,
) -> RecipeRow:
    latest = await db.scalar(select(ProductionRecipeVersion).where(
        ProductionRecipeVersion.user_id == user_id,
        ProductionRecipeVersion.recipe_key == recipe_key,
    ).order_by(desc(ProductionRecipeVersion.version), desc(ProductionRecipeVersion.id)).limit(1))
    row = ProductionRecipeVersion(
        id=str(uuid4()), user_id=user_id, recipe_key=recipe_key, name=name,
        version=(latest.version + 1) if latest else 1, status="draft",
        spec=deepcopy(spec), checksum=checksum,
    )
    db.add(row)
    await db.flush()
    return as_recipe_row(row)


async def record_recipe_create_audit(
    db: AsyncSession, *, row: RecipeRow, reason: str = "create recipe draft",
) -> str:
    audit = ModelConfigAuditEvent(
        id=str(uuid4()), user_id=row.user_id, resource_type="production_recipe",
        resource_id=row.id, action="create", from_version_id=None, to_version_id=row.id,
        reason=reason, sanitized_change_summary={"version": row.version, "recipe_key": row.recipe_key},
    )
    db.add(audit)
    await db.flush()
    return audit.id


async def load_recipe_for_user(db: AsyncSession, recipe_id: str, user_id: str) -> RecipeRow | None:
    row = await db.scalar(select(ProductionRecipeVersion).where(
        ProductionRecipeVersion.id == recipe_id,
        ProductionRecipeVersion.user_id == user_id,
    ))
    return as_recipe_row(row) if row else None


async def load_recipe_rollback_rows(
    db: AsyncSession, *, user_id: str, recipe_key: str, target_id: str,
) -> tuple[RecipeRow | None, RecipeRow | None, RecipeRow | None]:
    rows = list((await db.scalars(select(ProductionRecipeVersion).where(
        ProductionRecipeVersion.user_id == user_id,
        ProductionRecipeVersion.recipe_key == recipe_key,
    ).order_by(desc(ProductionRecipeVersion.version), desc(ProductionRecipeVersion.id)))).all())
    target = next((as_recipe_row(row) for row in rows if row.id == target_id), None)
    head = as_recipe_row(rows[0]) if rows else None
    published = next((as_recipe_row(row) for row in rows if row.status == "published"), None)
    return target, head, published


async def publish_recipe_draft(
    db: AsyncSession, *, row: RecipeRow, expected_revision: int, checksum: str, reason: str,
    action: str = "publish", previous_version_id: str | None = None,
) -> tuple[RecipeRow, str] | None:
    persisted = await db.get(ProductionRecipeVersion, row.id)
    if persisted is None or persisted.status != "draft" or persisted.revision != expected_revision:
        return None
    persisted.status = "published"
    persisted.published_at = utc_now()
    persisted.checksum = checksum
    persisted.revision += 1
    audit = ModelConfigAuditEvent(
        id=str(uuid4()), user_id=row.user_id, resource_type="production_recipe",
        resource_id=row.id, action=action, from_version_id=previous_version_id,
        to_version_id=row.id, reason=reason,
        sanitized_change_summary={"revision": persisted.revision, "recipe_key": row.recipe_key},
    )
    db.add(audit)
    await db.flush()
    return as_recipe_row(persisted), audit.id


async def create_rollback_recipe_draft(
    db: AsyncSession, *, source: RecipeRow, head: RecipeRow, checksum: str,
) -> RecipeRow:
    row = ProductionRecipeVersion(
        id=str(uuid4()), user_id=source.user_id, recipe_key=source.recipe_key, name=source.name,
        version=head.version + 1, status="draft", spec=deepcopy(source.spec), checksum=checksum,
    )
    db.add(row)
    await db.flush()
    return as_recipe_row(row)
