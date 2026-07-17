"""Application facade for thin Model Center management APIs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.management_repository import (
    binding_page,
    connection_page,
    load_recipe_publish_candidate,
    management_overview,
    prompt_profile_page,
    publish_recipe_if_revision,
    recipe_page,
)
from app.features.model_config.public import list_product_catalog
from app.features.model_config.recipes import RecipeValidationError, recipe_binding_references, stable_recipe_checksum, validate_recipe
from app.features.model_config.recipe_repository import load_recipe_binding_contracts
from app.features.model_drivers.public import describe_installed_drivers


class ManagementOperationError(ValueError):
    def __init__(self, code: str, message: str, action_code: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.action_code = action_code
        self.status_code = status_code


def unavailable(operation: str) -> None:
    raise ManagementOperationError(
        "operation_not_implemented",
        f"{operation} is registered but its persistence service is not implemented.",
        "contact_operator_or_use_legacy_api",
        501,
    )


def _page(items: list[dict], page: int, page_size: int, total: int) -> dict:
    return {"items": items, "meta": {"page": page, "page_size": page_size, "total": total}}


def _safe_stage_metadata(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    safe = {}
    for stage in ("text", "vision", "image", "video", "audio", "subtitle", "render", "storage"):
        values = spec.get(stage)
        if not isinstance(values, dict):
            continue
        allowed = {
            key: values[key]
            for key in ("binding_id", "required", "mode", "source", "capabilities")
            if key in values
        }
        safe[stage] = allowed
    return safe


async def overview(db: AsyncSession, user_id: str) -> dict:
    return await management_overview(db, user_id)


async def drivers_page(page: int, page_size: int) -> dict:
    drivers = describe_installed_drivers()
    start = (page - 1) * page_size
    return _page([dict(item) for item in drivers[start:start + page_size]], page, page_size, len(drivers))


async def connections_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    return await connection_page(db, user_id, page, page_size)


async def catalog_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    catalog = await list_product_catalog(db, user_id)
    start = (page - 1) * page_size
    items = []
    for item in catalog.models[start:start + page_size]:
        values = asdict(item)
        values["capabilities"] = sorted(item.capabilities)
        items.append(values)
    return _page(items, page, page_size, len(catalog.models))


async def bindings_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    return await binding_page(db, user_id, page, page_size)


async def recipes_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    items, total = await recipe_page(db, user_id, page, page_size)
    for item in items:
        item["spec"] = _safe_stage_metadata(item["spec"])
    return _page(items, page, page_size, total)


async def prompt_profiles_page(db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
    return await prompt_profile_page(db, user_id, page, page_size)


async def publish_recipe(
    db: AsyncSession, *, user_id: str, recipe_version_id: str, expected_revision: int, reason: str,
) -> dict:
    async with db.begin():
        candidate = await load_recipe_publish_candidate(db, recipe_version_id, user_id)
        if candidate is None:
            raise ManagementOperationError("resource_not_found", "Recipe version was not found.", "refresh", 404)
        if candidate.revision != expected_revision:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
        if candidate.status != "draft":
            raise ManagementOperationError(
                "resource_state_conflict", "Only a draft recipe version can be published.",
                "create_or_select_draft", 409,
            )
        binding_ids = {binding_id for _, binding_id in recipe_binding_references(candidate.spec)}
        bindings = await load_recipe_binding_contracts(db, binding_ids)
        errors = validate_recipe(candidate.spec, bindings, user_id=user_id)
        if errors:
            raise ManagementOperationError(
                "recipe_invalid", str(RecipeValidationError(errors)), "repair_recipe_and_retry", 422,
            )
        outcome = await publish_recipe_if_revision(
            db, candidate=candidate, expected_revision=expected_revision,
            checksum=stable_recipe_checksum(candidate.spec), reason=reason,
        )
        if outcome is None:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
    affected = len({binding_id for _, binding_id in recipe_binding_references(candidate.spec)})
    return {
        "published_version_id": outcome.recipe_id,
        "previous_version_id": outcome.previous_version_id,
        "impact": {"affected_bindings": affected},
        "audit_event_id": outcome.audit_event_id,
    }
