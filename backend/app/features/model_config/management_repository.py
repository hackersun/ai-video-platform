"""Persistence ownership for Model Center management reads and recipe publication."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.model_config.catalog import is_product_visible_provider
from app.features.model_config.domain import VERIFIED_CONNECTION_STATUSES
from app.features.model_config.readiness import production_readiness
from app.models.model_center import (
    ModelBinding,
    ModelCertificationRun,
    ModelConfigAuditEvent,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
    ProductionRecipeVersion,
)
from app.models.llm_config import LLMProvider
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


async def _provider_labels(db: AsyncSession, provider_ids: set[str]) -> dict[str, tuple[str, str]]:
    if not provider_ids:
        return {}
    legacy_rows = list((await db.scalars(select(LLMProvider).where(LLMProvider.id.in_(provider_ids)))).all())
    canonical_rows = list((await db.scalars(select(ModelProvider).where(ModelProvider.id.in_(provider_ids)))).all())
    labels = {
        row.id: (row.name_cn or row.name_en or row.name, row.name)
        for row in legacy_rows
    }
    labels.update({row.id: (row.display_name, row.code) for row in canonical_rows})
    return labels


def _connection_view(
    row,
    provider_labels: dict[str, tuple[str, str]] | None = None,
) -> dict:
    provider_name, provider_code = (provider_labels or {}).get(
        row.provider_id, (row.provider_id, row.provider_id),
    )
    overrides = getattr(row, "endpoint_overrides", {}) or {}
    has_secret = getattr(row, "has_secret", None)
    if has_secret is None:
        has_secret = bool(getattr(row, "api_key", None) or getattr(row, "api_secret", None))
    secret_updated_at = getattr(row, "secret_updated_at", None) or getattr(row, "updated_at", None)
    return {
        "id": row.id, "provider_id": row.provider_id,
        "provider_name": provider_name, "provider_code": provider_code,
        "name": row.name, "status": row.status,
        "base_url": overrides.get("base_url"),
        "enabled": row.status in VERIFIED_CONNECTION_STATUSES,
        "has_secret": bool(has_secret),
        "secret_hint": "****" if has_secret else None,
        "secret_updated_at": secret_updated_at.isoformat() if secret_updated_at else None,
        "revision": row.revision,
    }


def _recipe_view(row: ProductionRecipeVersion) -> dict:
    return {
        "id": row.id, "recipe_key": row.recipe_key, "name": row.name, "version": row.version,
        "status": row.status, "spec": dict(row.spec or {}), "revision": row.revision,
    }


async def management_overview(db: AsyncSession, user_id: str) -> dict:
    connection_rows = list((await db.scalars(select(ModelConnection).where(
        ModelConnection.user_id == user_id,
        ModelConnection.status != "disabled",
    ).order_by(ModelConnection.id))).all())
    recipe_rows = list((await db.scalars(select(ProductionRecipeVersion).where(
        ProductionRecipeVersion.user_id == user_id,
    ).order_by(ProductionRecipeVersion.id))).all())
    blocking_issues = await production_readiness(db, user_id=user_id)
    provider_labels = await _provider_labels(db, {row.provider_id for row in connection_rows})
    return {
        "blocking_issues": blocking_issues,
        "connections": [_connection_view(row, provider_labels) for row in connection_rows],
        "recipes": [_recipe_view(row) for row in recipe_rows],
    }


async def connection_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    rows, total = await _paged_rows(
        db, ModelConnection, (
            ModelConnection.user_id == user_id,
            ModelConnection.status != "disabled",
        ), page, page_size,
    )
    provider_labels = await _provider_labels(db, {row.provider_id for row in rows})
    items = [_connection_view(row, provider_labels) for row in rows]
    return _page(items, page, page_size, total)


async def provider_page(db: AsyncSession, page: int, page_size: int) -> dict:
    visible_rows = [
        row for row in (await db.scalars(
            select(ModelProvider).where(ModelProvider.enabled == True).order_by(ModelProvider.id)
        )).all()
        if is_product_visible_provider(row)
    ]
    total = len(visible_rows)
    start = (page - 1) * page_size
    rows = visible_rows[start:start + page_size]
    items = [{
        "id": row.id, "code": row.code, "display_name": row.display_name,
        "provider_family": row.provider_family, "is_builtin": bool(row.is_builtin),
        "enabled": bool(row.enabled), "revision": row.revision,
    } for row in rows]
    return _page(items, page, page_size, total)


async def connection_view(db: AsyncSession, row: ModelConnection) -> dict:
    labels = await _provider_labels(db, {row.provider_id})
    return _connection_view(row, labels)


def _contains_binding_id(value, binding_id: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_binding_id(item, binding_id) for item in value.values())
    if isinstance(value, list):
        return any(_contains_binding_id(item, binding_id) for item in value)
    return value == binding_id


async def binding_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    total = await db.scalar(select(func.count()).select_from(ModelBinding).where(
        ModelBinding.user_id == user_id,
    )) or 0
    rows = (await db.execute(select(
        ModelBinding, ModelProfileVersion, ModelProfile, ModelConnection, ModelProvider,
    ).join(
        ModelProfileVersion, ModelProfileVersion.id == ModelBinding.profile_version_id,
    ).join(ModelProfile, ModelProfile.id == ModelProfileVersion.model_id).join(
        ModelConnection, ModelConnection.id == ModelBinding.connection_id,
    ).join(ModelProvider, ModelProvider.id == ModelProfile.provider_id).where(
        ModelBinding.user_id == user_id,
    ).order_by(ModelBinding.id).offset((page - 1) * page_size).limit(page_size))).all()
    recipes = list((await db.scalars(select(ProductionRecipeVersion).where(
        ProductionRecipeVersion.user_id == user_id,
    ))).all())
    items = []
    for binding, profile, model, connection, provider in rows:
        certification = await db.scalar(select(ModelCertificationRun.status).where(
            ModelCertificationRun.user_id == user_id,
            ModelCertificationRun.profile_version_id == profile.id,
            ModelCertificationRun.connection_id == connection.id,
        ).order_by(desc(ModelCertificationRun.created_at)).limit(1))
        items.append({
            "id": binding.id, "scope_type": binding.scope_type, "scope_id": binding.scope_id,
            "task": binding.task, "capability": binding.capability,
            "profile_version_id": profile.id, "profile_name": model.display_name,
            "api_model_id": profile.api_model_id, "connection_id": connection.id,
            "connection_name": connection.name, "provider_name": provider.display_name,
            "priority": binding.priority, "route_policy": binding.route_policy,
            "fallback_profile_version_ids": list(binding.fallback_profile_version_ids or []),
            "certification_status": certification or "unverified",
            "affected_recipes": sum(_contains_binding_id(recipe.spec, binding.id) for recipe in recipes),
            "version": binding.version, "revision": binding.revision,
            "is_active": bool(binding.is_active),
        })
    return _page(items, page, page_size, int(total))


async def recipe_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> tuple[list[dict], int]:
    rows, total = await _paged_rows(
        db, ProductionRecipeVersion, (ProductionRecipeVersion.user_id == user_id,), page, page_size,
    )
    return [_recipe_view(row) for row in rows], total


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
