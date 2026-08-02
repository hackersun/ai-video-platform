"""Versioned provider and model-profile management use cases."""

from __future__ import annotations

from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.management import ManagementOperationError
from app.features.model_config.video_contract import validate_video_capability_contract
from app.features.model_drivers.public import DriverUnavailableError, build_builtin_driver_registry
from app.models.model_center import (
    ModelConfigAuditEvent,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
)


def _checksum(values: dict) -> str:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()


def _audit(
    *, user_id: str, resource_type: str, resource_id: str, action: str,
    reason: str, from_version_id: str | None = None, to_version_id: str | None = None,
    summary: dict | None = None,
) -> ModelConfigAuditEvent:
    return ModelConfigAuditEvent(
        id=str(uuid4()), user_id=user_id, resource_type=resource_type,
        resource_id=resource_id, action=action, from_version_id=from_version_id,
        to_version_id=to_version_id, reason=reason,
        sanitized_change_summary=summary or {},
    )


def provider_item(row: ModelProvider) -> dict:
    return {
        "id": row.id, "code": row.code, "display_name": row.display_name,
        "provider_family": row.provider_family, "is_builtin": bool(row.is_builtin),
        "enabled": bool(row.enabled), "revision": row.revision,
    }


def profile_item(row: ModelProfile) -> dict:
    return {
        "id": row.id, "provider_id": row.provider_id, "profile_key": row.profile_key,
        "display_name": row.display_name, "enabled": bool(row.enabled), "revision": row.revision,
    }


def profile_version_item(row: ModelProfileVersion) -> dict:
    return {
        "id": row.id, "model_id": row.model_id, "version": row.version,
        "api_model_id": row.api_model_id, "driver_key": row.driver_key,
        "capabilities": list(row.capabilities or []), "contract_version": row.contract_version,
        "input_contract": dict(row.input_contract or {}),
        "output_contract": dict(row.output_contract or {}),
        "parameter_schema": dict(row.parameter_schema or {}),
        "default_params": dict(row.default_params or {}),
        "limits": dict(row.limits or {}),
        "status": row.status, "revision": row.version,
    }


def _require_driver(driver_key: str, capabilities: list[str]):
    try:
        driver = build_builtin_driver_registry().require(driver_key)
    except DriverUnavailableError as error:
        raise ManagementOperationError(
            "driver_not_installed", f"驱动 {driver_key} 尚未安装。",
            "install_or_select_driver", 422,
        ) from error
    unsupported = set(capabilities) - set(driver.capabilities)
    if unsupported:
        raise ManagementOperationError(
            "driver_capability_mismatch",
            f"驱动不支持能力：{', '.join(sorted(unsupported))}",
            "select_compatible_driver", 422,
        )
    return driver


async def create_provider(db: AsyncSession, *, user_id: str, request) -> dict:
    duplicate = await db.scalar(select(ModelProvider.id).where(ModelProvider.code == request.code))
    if duplicate:
        raise ManagementOperationError("resource_conflict", "提供方代码已存在。", "select_existing_provider", 409)
    row = ModelProvider(
        id=str(uuid4()), code=request.code, display_name=request.display_name,
        provider_family=request.provider_family, enabled=True, revision=1,
    )
    db.add(row)
    db.add(_audit(
        user_id=user_id, resource_type="model_provider", resource_id=row.id,
        action="create", reason="create provider", summary={"code": row.code},
    ))
    await db.flush()
    return provider_item(row)


async def create_profile(db: AsyncSession, *, user_id: str, request) -> dict:
    provider = await db.get(ModelProvider, request.provider_id)
    if provider is None or not provider.enabled:
        raise ManagementOperationError("resource_not_found", "提供方不存在或已停用。", "select_enabled_provider", 404)
    duplicate = await db.scalar(select(ModelProfile.id).where(
        ModelProfile.provider_id == provider.id, ModelProfile.profile_key == request.profile_key,
    ))
    if duplicate:
        raise ManagementOperationError("resource_conflict", "模型档案键已存在。", "select_existing_profile", 409)
    row = ModelProfile(
        id=str(uuid4()), provider_id=provider.id, profile_key=request.profile_key,
        display_name=request.display_name, enabled=request.enabled, revision=1,
    )
    db.add(row)
    db.add(_audit(
        user_id=user_id, resource_type="model_profile", resource_id=row.id,
        action="create", reason="create model profile", summary={"profile_key": row.profile_key},
    ))
    await db.flush()
    return profile_item(row)


async def create_profile_version(db: AsyncSession, *, user_id: str, profile_id: str, request) -> dict:
    profile = await db.get(ModelProfile, profile_id)
    if profile is None or not profile.enabled:
        raise ManagementOperationError("resource_not_found", "模型档案不存在或已停用。", "refresh", 404)
    if profile.revision != request.expected_revision:
        raise ManagementOperationError("revision_conflict", "模型档案已更新。", "refresh_and_retry", 409)
    _require_driver(request.driver_key, request.capabilities)
    latest = await db.scalar(select(ModelProfileVersion).where(
        ModelProfileVersion.model_id == profile.id,
    ).order_by(desc(ModelProfileVersion.version)).limit(1))
    version = (latest.version if latest else 0) + 1
    values = request.model_dump(exclude={"expected_revision"})
    row = ModelProfileVersion(
        id=str(uuid4()), model_id=profile.id, version=version, status="draft",
        checksum=_checksum(values), **values,
    )
    profile.revision += 1
    db.add(row)
    db.add(_audit(
        user_id=user_id, resource_type="model_profile_version", resource_id=row.id,
        action="create_draft", reason="create model profile version", to_version_id=row.id,
        summary={"version": version, "driver_key": row.driver_key, "capabilities": row.capabilities},
    ))
    await db.flush()
    return profile_version_item(row)


async def validate_profile_contract(db: AsyncSession, *, user_id: str, version_id: str) -> dict:
    version = await db.get(ModelProfileVersion, version_id)
    if version is None:
        raise ManagementOperationError("resource_not_found", "模型版本不存在。", "refresh", 404)
    _require_driver(version.driver_key, list(version.capabilities or []))
    errors = validate_video_capability_contract(
        list(version.capabilities or []),
        dict(version.input_contract or {}),
        dict(version.limits or {}),
    )
    audit = _audit(
        user_id=user_id, resource_type="model_profile_version", resource_id=version.id,
        action="validate_contract" if not errors else "validate_contract_failed",
        reason="local driver contract validation",
        to_version_id=version.id,
        summary={
            "driver_key": version.driver_key,
            "contract_version": version.contract_version,
            "error_codes": [item["code"] for item in errors],
        },
    )
    db.add(audit)
    await db.flush()
    return {"valid": not errors, "errors": errors, "audit_event_id": audit.id}


async def publish_profile_version(db: AsyncSession, *, user_id: str, version_id: str, request) -> dict:
    version = await db.get(ModelProfileVersion, version_id)
    if version is None:
        raise ManagementOperationError("resource_not_found", "模型版本不存在。", "refresh", 404)
    if version.version != request.expected_revision or version.status != "draft":
        raise ManagementOperationError("resource_state_conflict", "请选择最新草稿版本。", "refresh_and_retry", 409)
    validation = await db.scalar(select(ModelConfigAuditEvent.id).where(
        ModelConfigAuditEvent.user_id == user_id,
        ModelConfigAuditEvent.resource_id == version.id,
        ModelConfigAuditEvent.action == "validate_contract",
    ).limit(1))
    if validation is None:
        raise ManagementOperationError("contract_validation_required", "发布前请先运行契约校验。", "run_contract_validation", 422)
    previous = await db.scalar(select(ModelProfileVersion).where(
        ModelProfileVersion.model_id == version.model_id,
        ModelProfileVersion.status == "published",
    ).order_by(desc(ModelProfileVersion.version)).limit(1))
    version.status = "published"
    audit = _audit(
        user_id=user_id, resource_type="model_profile_version", resource_id=version.id,
        action="publish", reason=request.reason,
        from_version_id=previous.id if previous else None, to_version_id=version.id,
        summary={"version": version.version},
    )
    db.add(audit)
    await db.flush()
    return {
        "published_version_id": version.id,
        "previous_version_id": previous.id if previous else None,
        "impact": {"affected_bindings": 0, "affected_profiles": 1, "affected_recipes": 0, "affected_prompts": 0},
        "audit_event_id": audit.id,
    }
