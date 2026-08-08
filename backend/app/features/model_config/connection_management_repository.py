"""Safe persistence operations for user-owned Model Center connections."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_encryption import encrypt_key
from app.core.time_utils import utc_now
from app.models.model_center import ModelBinding, ModelConfigAuditEvent, ModelConnection, ModelProvider


@dataclass(frozen=True)
class ConnectionRow:
    id: str
    user_id: str
    provider_id: str
    name: str
    status: str
    endpoint_overrides: dict
    has_secret: bool
    secret_updated_at: object | None
    revision: int


@dataclass(frozen=True)
class ConnectionRemovalResult:
    state: str
    revision: int | None = None
    active_bindings: int = 0


def as_connection_row(row: ModelConnection) -> ConnectionRow:
    return ConnectionRow(
        id=row.id, user_id=row.user_id, provider_id=row.provider_id, name=row.name,
        status=row.status, endpoint_overrides=dict(row.endpoint_overrides or {}),
        has_secret=bool(row.api_key or row.api_secret),
        secret_updated_at=row.updated_at, revision=row.revision,
    )


async def create_connection(
    db: AsyncSession, *, user_id: str, provider_id: str, name: str,
    api_key: str | None, api_secret: str | None, base_url: str | None, reason: str,
) -> ConnectionRow | None:
    provider = await db.get(ModelProvider, provider_id)
    if provider is None:
        provider = await db.scalar(select(ModelProvider).where(ModelProvider.code == provider_id))
    if provider is None:
        return None
    row = ModelConnection(
        id=str(uuid4()), user_id=user_id, provider_id=provider.id, name=name,
        endpoint_overrides={"base_url": base_url} if base_url else {}, status="draft",
    )
    row.set_api_key_encrypted(api_key or "")
    row.set_api_secret_encrypted(api_secret)
    db.add(row)
    db.add(_audit(row, action="create", reason=reason, summary={
        "has_secret": bool(api_key or api_secret), "has_custom_base_url": bool(base_url),
    }))
    await db.flush()
    return as_connection_row(row)


async def update_connection_if_revision(
    db: AsyncSession, *, connection_id: str, user_id: str, expected_revision: int,
    metadata: dict | None = None, api_key: str | None = None, api_secret: str | None = None,
    reason: str | None = None,
) -> ConnectionRow | None:
    values = {"revision": ModelConnection.revision + 1, "updated_at": utc_now()}
    if metadata:
        values.update(deepcopy(metadata))
    if api_key is not None:
        values["api_key"] = encrypt_key(api_key) if api_key else ""
    if api_secret is not None:
        values["api_secret"] = encrypt_key(api_secret) if api_secret else None
    result = await db.execute(update(ModelConnection).where(
        ModelConnection.id == connection_id, ModelConnection.user_id == user_id,
        ModelConnection.revision == expected_revision,
    ).values(**values).returning(ModelConnection.id))
    if result.scalar_one_or_none() is None:
        return None
    row = await db.get(ModelConnection, connection_id)
    action = "replace_secret" if api_key is not None or api_secret is not None else "update_metadata"
    summary = {"secret_replaced": action == "replace_secret", "fields": sorted((metadata or {}).keys())}
    db.add(_audit(row, action=action, reason=reason or "metadata update", summary=summary))
    await db.flush()
    return as_connection_row(row)


async def queue_connection_test_intent(
    db: AsyncSession, *, connection_id: str, user_id: str,
) -> tuple[ConnectionRow, str] | None:
    row = await db.scalar(select(ModelConnection).where(
        ModelConnection.id == connection_id, ModelConnection.user_id == user_id,
    ))
    if row is None:
        return None
    if not (row.api_key or row.api_secret):
        raise ValueError("connection_secret_required")
    result = await db.execute(update(ModelConnection).where(
        ModelConnection.id == connection_id, ModelConnection.user_id == user_id,
        ModelConnection.revision == row.revision,
    ).values(
        status="connection_verification_queued", revision=ModelConnection.revision + 1,
        updated_at=utc_now(),
    ).returning(ModelConnection.id))
    if result.scalar_one_or_none() is None:
        return None
    queued = await db.get(ModelConnection, connection_id)
    audit = _audit(
        queued, action="connection_test_intent", reason="queue safe connection verification",
        summary={"execution_mode": "safe_intent_only"},
    )
    db.add(audit)
    await db.flush()
    return as_connection_row(queued), audit.id


async def remove_connection_if_unused(
    db: AsyncSession, *, connection_id: str, user_id: str,
    expected_revision: int, reason: str,
) -> ConnectionRemovalResult:
    row = await db.scalar(select(ModelConnection).where(
        ModelConnection.id == connection_id,
        ModelConnection.user_id == user_id,
        ModelConnection.status != "disabled",
    ))
    if row is None:
        return ConnectionRemovalResult(state="not_found")
    if row.revision != expected_revision:
        return ConnectionRemovalResult(state="revision_conflict", revision=row.revision)

    active_bindings = int(await db.scalar(select(func.count()).select_from(ModelBinding).where(
        ModelBinding.user_id == user_id,
        ModelBinding.connection_id == connection_id,
        ModelBinding.is_active.is_(True),
    )) or 0)
    if active_bindings:
        return ConnectionRemovalResult(state="in_use", active_bindings=active_bindings)

    result = await db.execute(update(ModelConnection).where(
        ModelConnection.id == connection_id,
        ModelConnection.user_id == user_id,
        ModelConnection.revision == expected_revision,
        ModelConnection.status != "disabled",
    ).values(
        status="disabled", api_key="", api_secret=None,
        revision=ModelConnection.revision + 1, updated_at=utc_now(),
    ).returning(ModelConnection.id))
    if result.scalar_one_or_none() is None:
        return ConnectionRemovalResult(state="revision_conflict")

    removed = await db.get(ModelConnection, connection_id)
    db.add(_audit(
        removed, action="remove", reason=reason,
        summary={"credentials_removed": True, "history_preserved": True},
    ))
    await db.flush()
    return ConnectionRemovalResult(state="removed", revision=removed.revision)


def _audit(row: ModelConnection, *, action: str, reason: str, summary: dict) -> ModelConfigAuditEvent:
    return ModelConfigAuditEvent(
        id=str(uuid4()), user_id=row.user_id, resource_type="model_connection", resource_id=row.id,
        action=action, from_version_id=None, to_version_id=None, reason=reason,
        sanitized_change_summary=summary,
    )
