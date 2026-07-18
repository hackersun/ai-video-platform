"""Persistence ownership for Model Center management reads and recipe publication."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.model_center import (
    ModelBinding,
    ModelConfigAuditEvent,
    ModelConnection,
    ModelProfile,
    ModelProvider,
    ProductionRecipeVersion,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion


@dataclass(frozen=True)
class RecipePublishCandidate:
    id: str
    user_id: str
    recipe_key: str
    status: str
    revision: int
    spec: dict


@dataclass(frozen=True)
class RecipePublishOutcome:
    recipe_id: str
    previous_version_id: str | None
    revision: int
    audit_event_id: str


def _page(items: list[dict], page: int, page_size: int, total: int) -> dict:
    return {"items": items, "meta": {"page": page, "page_size": page_size, "total": total}}


async def _paged_rows(db: AsyncSession, model, filters: tuple, page: int, page_size: int):
    total = await db.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    rows = list((await db.scalars(
        select(model).where(*filters).order_by(model.id).offset((page - 1) * page_size).limit(page_size)
    )).all())
    return rows, int(total)


async def management_overview(db: AsyncSession, user_id: str) -> dict:
    resources = {
        "providers": (ModelProvider, ()),
        "connections": (ModelConnection, (ModelConnection.user_id == user_id,)),
        "profiles": (ModelProfile, ()),
        "bindings": (ModelBinding, (ModelBinding.user_id == user_id,)),
        "recipes": (ProductionRecipeVersion, (ProductionRecipeVersion.user_id == user_id,)),
        "prompt_profiles": (PromptProfile, (PromptProfile.user_id == user_id,)),
    }
    counts = {
        key: int(await db.scalar(select(func.count()).select_from(model).where(*filters)) or 0)
        for key, (model, filters) in resources.items()
    }
    return {"counts": counts}


async def connection_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    rows, total = await _paged_rows(
        db, ModelConnection, (ModelConnection.user_id == user_id,), page, page_size,
    )
    items = [{
        "id": row.id, "provider_id": row.provider_id, "name": row.name, "status": row.status,
        "base_url": (row.endpoint_overrides or {}).get("base_url"),
        "enabled": row.status in {"enabled", "verified"},
        "has_secret": bool(row.api_key or row.api_secret),
        "secret_hint": "****" if row.api_key or row.api_secret else None,
        "secret_updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "revision": row.revision,
    } for row in rows]
    return _page(items, page, page_size, total)


async def binding_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    rows, total = await _paged_rows(db, ModelBinding, (ModelBinding.user_id == user_id,), page, page_size)
    items = [{
        "id": row.id, "scope_type": row.scope_type, "scope_id": row.scope_id,
        "task": row.task, "capability": row.capability,
        "profile_version_id": row.profile_version_id, "connection_id": row.connection_id,
        "version": row.version, "revision": row.revision, "is_active": bool(row.is_active),
    } for row in rows]
    return _page(items, page, page_size, total)


async def recipe_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> tuple[list[dict], int]:
    rows, total = await _paged_rows(
        db, ProductionRecipeVersion, (ProductionRecipeVersion.user_id == user_id,), page, page_size,
    )
    return [{
        "id": row.id, "recipe_key": row.recipe_key, "name": row.name, "version": row.version,
        "status": row.status, "spec": dict(row.spec or {}), "revision": row.revision,
    } for row in rows], total


async def prompt_profile_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    profiles, total = await _paged_rows(
        db, PromptProfile, (PromptProfile.user_id == user_id,), page, page_size,
    )
    items = []
    for profile in profiles:
        head = await db.scalar(select(PromptProfileVersion).where(
            PromptProfileVersion.profile_id == profile.id,
        ).order_by(desc(PromptProfileVersion.version), PromptProfileVersion.id).limit(1))
        items.append({
            "id": profile.id, "key": profile.key, "name": profile.name, "task": profile.task,
            "head_version_id": head.id if head else None,
            "head_version": head.version if head else None,
            "status": head.status if head else None,
        })
    return _page(items, page, page_size, total)


async def load_recipe_publish_candidate(
    db: AsyncSession, recipe_version_id: str, user_id: str,
) -> RecipePublishCandidate | None:
    row = await db.scalar(select(ProductionRecipeVersion).where(
        ProductionRecipeVersion.id == recipe_version_id,
        ProductionRecipeVersion.user_id == user_id,
    ))
    if row is None:
        return None
    return RecipePublishCandidate(
        id=row.id, user_id=row.user_id, recipe_key=row.recipe_key,
        status=row.status, revision=row.revision, spec=dict(row.spec or {}),
    )


async def publish_recipe_if_revision(
    db: AsyncSession, *, candidate: RecipePublishCandidate, expected_revision: int,
    checksum: str, reason: str,
) -> RecipePublishOutcome | None:
    previous = await db.scalar(select(ProductionRecipeVersion.id).where(
        ProductionRecipeVersion.user_id == candidate.user_id,
        ProductionRecipeVersion.recipe_key == candidate.recipe_key,
        ProductionRecipeVersion.status == "published",
        ProductionRecipeVersion.id != candidate.id,
    ).order_by(desc(ProductionRecipeVersion.version), ProductionRecipeVersion.id).limit(1))
    result = await db.execute(update(ProductionRecipeVersion).where(
        ProductionRecipeVersion.id == candidate.id,
        ProductionRecipeVersion.user_id == candidate.user_id,
        ProductionRecipeVersion.status == "draft",
        ProductionRecipeVersion.revision == expected_revision,
    ).values(
        checksum=checksum,
        status="published",
        published_at=utc_now(),
        revision=ProductionRecipeVersion.revision + 1,
    ).returning(ProductionRecipeVersion.id, ProductionRecipeVersion.revision))
    published = result.one_or_none()
    if published is None:
        return None
    audit = ModelConfigAuditEvent(
        id=str(uuid4()), user_id=candidate.user_id, resource_type="production_recipe",
        resource_id=candidate.id, action="publish", from_version_id=previous,
        to_version_id=published.id, reason=reason,
        sanitized_change_summary={"revision": published.revision},
    )
    db.add(audit)
    await db.flush()
    return RecipePublishOutcome(
        recipe_id=published.id, previous_version_id=previous,
        revision=published.revision, audit_event_id=audit.id,
    )
