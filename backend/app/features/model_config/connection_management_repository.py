"""Safe persistence operations for user-owned Model Center connections."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_encryption import encrypt_key
from app.core.time_utils import utc_now
from app.models.model_center import ModelConfigAuditEvent, ModelConnection, ModelProvider


@dataclass(frozen=True)
class ConnectionRow:
    id: str
    user_id: str
    provider_id: str
    name: str
    status: str
    has_secret: bool
    secret_updated_at: object | None
    revision: int


def as_connection_row(row: ModelConnection) -> ConnectionRow:
    return ConnectionRow(
        id=row.id, user_id=row.user_id, provider_id=row.provider_id, name=row.name,
        status=row.status, has_secret=bool(row.api_key or row.api_secret),
        secret_updated_at=row.updated_at, revision=row.revision,
    )


async def create_connection(
    db: AsyncSession, *, user_id: str, provider_id: str, name: str,
    api_key: str | None, api_secret: str | None, reason: str,
) -> ConnectionRow | None:
    provider = await db.get(ModelProvider, provider_id)
    if provider is None:
        provider = await db.scalar(select(ModelProvider).where(ModelProvider.code == provider_id))
    if provider is None:
        return None
    row = ModelConnection(
        id=str(uuid4()), user_id=user_id, provider_id=provider.id, name=name, status="draft",
    )
    row.set_api_key_encrypted(api_key or "")
    row.set_api_secret_encrypted(api_secret)
    db.add(row)
    db.add(_audit(row, action="create", reason=reason, summary={"has_secret": bool(api_key or api_secret)}))
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


def _audit(row: ModelConnection, *, action: str, reason: str, summary: dict) -> ModelConfigAuditEvent:
    return ModelConfigAuditEvent(
        id=str(uuid4()), user_id=row.user_id, resource_type="model_connection", resource_id=row.id,
        action=action, from_version_id=None, to_version_id=None, reason=reason,
        sanitized_change_summary=summary,
    )
