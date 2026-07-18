"""Validated model-binding write use cases."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import VERIFIED_CONNECTION_STATUSES
from app.features.model_config.management import ManagementOperationError
from app.models.model_center import (
    ModelBinding,
    ModelConfigAuditEvent,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
)


async def _binding_target(db: AsyncSession, *, user_id: str, request):
    row = await db.execute(select(
        ModelProfileVersion, ModelProfile, ModelProvider, ModelConnection,
    ).join(
        ModelProfile, ModelProfile.id == ModelProfileVersion.model_id,
    ).join(ModelProvider, ModelProvider.id == ModelProfile.provider_id).join(
        ModelConnection, ModelConnection.id == request.connection_id,
    ).where(
        ModelProfileVersion.id == request.profile_version_id,
        ModelConnection.user_id == user_id,
    ))
    target = row.one_or_none()
    if target is None:
        raise ManagementOperationError("resource_not_found", "模型版本或连接不存在。", "refresh", 404)
    profile, model, provider, connection = target
    if profile.status != "published" or request.capability not in set(profile.capabilities or []):
        raise ManagementOperationError(
            "binding_capability_mismatch", "模型版本尚未发布或不支持所选能力。",
            "select_compatible_profile", 422,
        )
    if connection.provider_id != provider.id:
        raise ManagementOperationError(
            "binding_connection_mismatch", "模型版本和连接不属于同一提供方。",
            "select_matching_connection", 422,
        )
    if connection.status not in VERIFIED_CONNECTION_STATUSES:
        raise ManagementOperationError(
            "binding_connection_not_verified", "所选连接尚未完成认证。",
            "test_connection", 422,
        )
    await _validate_fallbacks(db, request)
    return profile, model, provider, connection


async def _validate_fallbacks(db: AsyncSession, request) -> None:
    fallback_ids = list(dict.fromkeys(request.fallback_profile_version_ids))
    if request.route_policy == "pre_submit_fallback" and not fallback_ids:
        raise ManagementOperationError(
            "binding_fallback_required", "提交前降级策略至少需要一个备用模型。",
            "select_fallback_profile", 422,
        )
    if request.route_policy != "pre_submit_fallback" and fallback_ids:
        raise ManagementOperationError(
            "binding_fallback_not_allowed", "当前路由策略不使用备用模型。",
            "clear_fallback_profiles", 422,
        )
    if not fallback_ids:
        return
    rows = list((await db.scalars(select(ModelProfileVersion).where(
        ModelProfileVersion.id.in_(fallback_ids),
    ))).all())
    valid = {
        row.id for row in rows
        if row.status == "published" and request.capability in set(row.capabilities or [])
    }
    if request.profile_version_id in fallback_ids or valid != set(fallback_ids):
        raise ManagementOperationError(
            "binding_fallback_mismatch", "备用模型必须是不同且已发布的同能力模型。",
            "select_compatible_fallback", 422,
        )


def _scope_id(request, user_id: str) -> str:
    scope_id = request.scope_id.strip()
    if request.scope_type == "user":
        return scope_id or user_id
    if not scope_id:
        raise ManagementOperationError(
            "binding_scope_required", "项目、系列或请求级绑定必须填写作用域标识。",
            "set_scope_id", 422,
        )
    return scope_id


def _binding_item(binding, profile, model, provider, connection) -> dict:
    return {
        "id": binding.id, "scope_type": binding.scope_type, "scope_id": binding.scope_id,
        "task": binding.task, "capability": binding.capability,
        "profile_version_id": profile.id, "profile_name": model.display_name,
        "api_model_id": profile.api_model_id, "connection_id": connection.id,
        "connection_name": connection.name, "provider_name": provider.display_name,
        "priority": binding.priority, "route_policy": binding.route_policy,
        "fallback_profile_version_ids": list(binding.fallback_profile_version_ids or []),
        "certification_status": "unverified", "affected_recipes": 0,
        "version": binding.version, "revision": binding.revision,
        "is_active": bool(binding.is_active),
    }


def _audit(binding, *, user_id: str, action: str, reason: str) -> ModelConfigAuditEvent:
    return ModelConfigAuditEvent(
        id=str(uuid4()), user_id=user_id, resource_type="model_binding",
        resource_id=binding.id, action=action, from_version_id=None,
        to_version_id=binding.profile_version_id, reason=reason,
        sanitized_change_summary={
            "task": binding.task, "capability": binding.capability,
            "route_policy": binding.route_policy, "priority": binding.priority,
        },
    )


async def create_binding(db: AsyncSession, *, user_id: str, request) -> dict:
    profile, model, provider, connection = await _binding_target(
        db, user_id=user_id, request=request,
    )
    scope_id = _scope_id(request, user_id)
    latest = await db.scalar(select(ModelBinding).where(
        ModelBinding.user_id == user_id, ModelBinding.scope_type == request.scope_type,
        ModelBinding.scope_id == scope_id, ModelBinding.task == request.task,
        ModelBinding.capability == request.capability,
    ).order_by(desc(ModelBinding.version)).limit(1))
    binding = ModelBinding(
        id=str(uuid4()), user_id=user_id, scope_type=request.scope_type,
        scope_id=scope_id, task=request.task, capability=request.capability,
        profile_version_id=profile.id, connection_id=connection.id,
        priority=request.priority, route_policy=request.route_policy,
        fallback_profile_version_ids=request.fallback_profile_version_ids,
        version=(latest.version if latest else 0) + 1,
        is_active=request.is_active, revision=1,
    )
    db.add(binding)
    db.add(_audit(binding, user_id=user_id, action="create", reason=request.reason))
    await db.flush()
    return _binding_item(binding, profile, model, provider, connection)


async def update_binding(db: AsyncSession, *, user_id: str, binding_id: str, request) -> dict:
    binding = await db.scalar(select(ModelBinding).where(
        ModelBinding.id == binding_id, ModelBinding.user_id == user_id,
    ))
    if binding is None:
        raise ManagementOperationError("resource_not_found", "能力绑定不存在。", "refresh", 404)
    if binding.revision != request.expected_revision:
        raise ManagementOperationError("revision_conflict", "能力绑定已更新。", "refresh_and_retry", 409)
    profile, model, provider, connection = await _binding_target(
        db, user_id=user_id, request=request,
    )
    for field in (
        "scope_type", "task", "capability", "profile_version_id", "connection_id",
        "priority", "route_policy", "fallback_profile_version_ids", "is_active",
    ):
        setattr(binding, field, getattr(request, field))
    binding.scope_id = _scope_id(request, user_id)
    binding.revision += 1
    binding.version += 1
    db.add(_audit(binding, user_id=user_id, action="update", reason=request.reason))
    await db.flush()
    return _binding_item(binding, profile, model, provider, connection)
