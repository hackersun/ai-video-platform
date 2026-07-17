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
from app.features.model_config.certification_repository import (
    create_certification_intent,
    load_certification_intent,
    validate_certification_target,
)
from app.features.model_config.public import list_product_catalog
from app.features.model_config.prompt_management_repository import (
    create_prompt_draft,
    create_prompt_profile,
    load_prompt_rollback_rows,
    load_prompt_version_for_user,
    prompt_impact,
    publish_prompt_draft,
)
from app.features.model_config.recipe_management_repository import (
    create_recipe_draft,
    create_rollback_recipe_draft,
    load_recipe_for_user,
    load_recipe_rollback_rows,
    publish_recipe_draft,
    record_recipe_create_audit,
)
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


def _recipe_item(row) -> dict:
    return {
        "id": row.id, "recipe_key": row.recipe_key, "name": row.name,
        "version": row.version, "status": row.status, "revision": row.revision,
        "spec": _safe_stage_metadata(row.spec),
    }


def _recipe_errors(errors) -> list[dict]:
    return [{
        "code": error.code, "message": error.message, "stage": error.stage,
        "binding_id": error.binding_id,
    } for error in errors]


async def create_recipe(
    db: AsyncSession, *, user_id: str, recipe_key: str, name: str, spec: dict,
) -> dict:
    async with db.begin():
        binding_ids = {binding_id for _, binding_id in recipe_binding_references(spec)}
        errors = validate_recipe(spec, await load_recipe_binding_contracts(db, binding_ids), user_id=user_id)
        if errors:
            raise ManagementOperationError("recipe_invalid", str(RecipeValidationError(errors)), "repair_recipe", 422)
        row = await create_recipe_draft(
            db, user_id=user_id, recipe_key=recipe_key, name=name, spec=spec,
            checksum=stable_recipe_checksum(spec),
        )
        await record_recipe_create_audit(db, row=row)
    return _recipe_item(row)


async def validate_recipe_version(db: AsyncSession, *, user_id: str, recipe_version_id: str) -> dict:
    row = await load_recipe_for_user(db, recipe_version_id, user_id)
    if row is None:
        raise ManagementOperationError("resource_not_found", "Recipe version was not found.", "refresh", 404)
    binding_ids = {binding_id for _, binding_id in recipe_binding_references(row.spec)}
    errors = validate_recipe(row.spec, await load_recipe_binding_contracts(db, binding_ids), user_id=user_id)
    return {"valid": not errors, "errors": _recipe_errors(errors)}


async def rollback_recipe(
    db: AsyncSession, *, user_id: str, recipe_key: str, target_version_id: str,
    expected_revision: int, reason: str,
) -> dict:
    async with db.begin():
        target, head, current = await load_recipe_rollback_rows(
            db, user_id=user_id, recipe_key=recipe_key, target_id=target_version_id,
        )
        if target is None or head is None:
            raise ManagementOperationError("resource_not_found", "Recipe version was not found.", "refresh", 404)
        if current is None or current.revision != expected_revision:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
        binding_ids = {binding_id for _, binding_id in recipe_binding_references(target.spec)}
        errors = validate_recipe(target.spec, await load_recipe_binding_contracts(db, binding_ids), user_id=user_id)
        if errors:
            raise ManagementOperationError("recipe_invalid", str(RecipeValidationError(errors)), "repair_recipe", 422)
        draft = await create_rollback_recipe_draft(
            db, source=target, head=head, checksum=stable_recipe_checksum(target.spec),
        )
        published = await publish_recipe_draft(
            db, row=draft, expected_revision=draft.revision,
            checksum=stable_recipe_checksum(draft.spec), reason=reason, action="rollback",
            previous_version_id=current.id,
        )
        if published is None:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
    row, audit_id = published
    return {
        "published_version_id": row.id, "previous_version_id": current.id,
        "impact": {"affected_bindings": len(binding_ids)}, "audit_event_id": audit_id,
    }


def _prompt_values_from_request(request) -> dict:
    return {
        "stage": request.stage, "system_contract": request.system_contract,
        "task_template": request.task_template, "input_mapping": request.input_mapping,
        "output_schema": request.output_schema, "negative_constraints": request.negative_constraints,
        "model_family_overrides": request.model_family_overrides,
        "validation_fixtures": request.validation_fixtures, "release_notes": request.release_notes,
    }


def _prompt_item(row) -> dict:
    return {
        "id": row.profile_id, "key": row.profile_key, "name": row.name, "task": row.task,
        "head_version_id": row.id, "head_version": row.version, "version": row.version,
        "status": row.status, "revision": row.version,
    }


async def create_prompt_profile_versioned(db: AsyncSession, *, user_id: str, request) -> dict:
    async with db.begin():
        row = await create_prompt_profile(
            db, user_id=user_id, key=request.key, name=request.name, task=request.task,
            values=_prompt_values_from_request(request),
        )
        if row is None:
            raise ManagementOperationError("resource_already_exists", "Prompt Profile key already exists.", "choose_another_key", 409)
    return _prompt_item(row)


async def create_prompt_profile_draft(
    db: AsyncSession, *, user_id: str, profile_id: str, expected_revision: int, changes: dict,
) -> dict:
    async with db.begin():
        try:
            row = await create_prompt_draft(
                db, profile_id=profile_id, user_id=user_id, expected_version=expected_revision, changes=changes,
            )
        except ValueError as error:
            raise ManagementOperationError("prompt_profile_invalid", str(error), "repair_prompt_profile", 422) from error
        if row is None:
            raise ManagementOperationError("revision_conflict", "Configuration has changed or was not found.", "refresh_and_retry", 409)
    return _prompt_item(row)


async def publish_prompt_profile_version(
    db: AsyncSession, *, user_id: str, version_id: str, expected_revision: int, reason: str,
) -> dict:
    async with db.begin():
        candidate = await load_prompt_version_for_user(db, version_id=version_id, user_id=user_id)
        if candidate is None:
            raise ManagementOperationError("resource_not_found", "Prompt Profile version was not found.", "refresh", 404)
        if candidate.status != "draft" or candidate.version != expected_revision:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
        impact = await prompt_impact(db, user_id=user_id, profile_id=candidate.profile_id)
        published = await publish_prompt_draft(
            db, candidate=candidate, expected_version=expected_revision, reason=reason,
        )
        if published is None:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
    row, audit_id = published
    return {
        "published_version_id": row.id, "previous_version_id": None,
        "impact": impact, "audit_event_id": audit_id,
    }


async def rollback_prompt_profile(
    db: AsyncSession, *, user_id: str, profile_id: str, target_version_id: str,
    expected_revision: int, reason: str,
) -> dict:
    async with db.begin():
        target, head = await load_prompt_rollback_rows(
            db, profile_id=profile_id, user_id=user_id, target_id=target_version_id,
        )
        if target is None or head is None:
            raise ManagementOperationError("resource_not_found", "Prompt Profile version was not found.", "refresh", 404)
        if head.version != expected_revision:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
        draft = await create_prompt_draft(
            db, profile_id=profile_id, user_id=user_id, expected_version=head.version, changes=target.values,
        )
        if draft is None:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
        impact = await prompt_impact(db, user_id=user_id, profile_id=profile_id)
        published = await publish_prompt_draft(
            db, candidate=draft, expected_version=draft.version, reason=reason,
            action="rollback", previous_version_id=head.id,
        )
        if published is None:
            raise ManagementOperationError("revision_conflict", "Configuration has changed.", "refresh_and_retry", 409)
    row, audit_id = published
    return {
        "published_version_id": row.id, "previous_version_id": head.id,
        "impact": impact, "audit_event_id": audit_id,
    }


def _certification_item(row) -> dict:
    return {
        "id": row.id, "profile_version_id": row.profile_version_id, "connection_id": row.connection_id,
        "level": row.level, "status": row.status, "sanitized_evidence": row.sanitized_evidence,
        "estimated_cost_rmb": f"{row.estimated_cost_rmb:.4f}",
        "actual_cost_rmb": f"{row.actual_cost_rmb:.4f}",
        "created_at": row.created_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


async def create_certification(db: AsyncSession, *, user_id: str, request) -> dict:
    async with db.begin():
        if not await validate_certification_target(
            db, user_id=user_id, profile_version_id=request.profile_version_id, connection_id=request.connection_id,
        ):
            raise ManagementOperationError("resource_not_found", "Profile version or connection was not found.", "refresh", 404)
        if request.recipe_version_id and await load_recipe_for_user(db, request.recipe_version_id, user_id) is None:
            raise ManagementOperationError("resource_not_found", "Recipe version was not found.", "refresh", 404)
        evidence = {
            "execution_mode": "safe_intent_only", "user_scope": request.user_scope,
            "recipe_version_id": request.recipe_version_id, "chapter_id": request.chapter_id,
            "run_id": request.run_id, "selected_shot_ids": request.selected_shot_ids,
            "budget_ceiling_rmb": str(request.budget_ceiling_rmb) if request.budget_ceiling_rmb is not None else None,
            "retry_policy": request.retry_policy, "storage_policy": request.storage_policy,
            "real_cost_acknowledged": request.real_cost_acknowledged,
        }
        row = await create_certification_intent(
            db, user_id=user_id, profile_version_id=request.profile_version_id,
            connection_id=request.connection_id, level=request.level, reason=request.reason,
            evidence=evidence, estimated_cost_rmb=request.budget_ceiling_rmb or 0,
        )
    return _certification_item(row)


async def get_certification(db: AsyncSession, *, user_id: str, run_id: str) -> dict:
    row = await load_certification_intent(db, user_id=user_id, run_id=run_id)
    if row is None:
        raise ManagementOperationError("resource_not_found", "Certification run was not found.", "refresh", 404)
    return _certification_item(row)


async def impact_preview(
    db: AsyncSession, *, user_id: str, resource_type: str | None, resource_id: str | None,
) -> dict:
    if resource_type in (None, "prompt_profile"):
        return await prompt_impact(db, user_id=user_id, profile_id=resource_id)
    if resource_type == "recipe":
        row = await load_recipe_for_user(db, resource_id or "", user_id)
        if row is None:
            raise ManagementOperationError("resource_not_found", "Recipe version was not found.", "refresh", 404)
        return {
            "affected_bindings": len({binding_id for _, binding_id in recipe_binding_references(row.spec)}),
            "affected_profiles": 0, "affected_recipes": 1, "affected_prompts": 0,
        }
    raise ManagementOperationError("invalid_resource_type", "Impact preview resource type is invalid.", "choose_supported_resource", 422)
