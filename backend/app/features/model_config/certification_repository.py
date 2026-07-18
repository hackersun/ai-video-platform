"""Safe intent persistence for Model Center certification runs.

This module deliberately does not import provider drivers or submit network jobs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_center import (
    ModelCertificationRun,
    ModelConfigAuditEvent,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
)


@dataclass(frozen=True)
class CertificationRow:
    id: str
    profile_version_id: str
    connection_id: str
    level: str
    status: str
    sanitized_evidence: dict
    estimated_cost_rmb: Decimal
    actual_cost_rmb: Decimal
    created_at: object
    completed_at: object | None


def as_certification_row(row: ModelCertificationRun) -> CertificationRow:
    return CertificationRow(
        id=row.id, profile_version_id=row.profile_version_id, connection_id=row.connection_id,
        level=row.level, status=row.status, sanitized_evidence=dict(row.sanitized_evidence or {}),
        estimated_cost_rmb=Decimal(row.estimated_cost_rmb), actual_cost_rmb=Decimal(row.actual_cost_rmb),
        created_at=row.created_at, completed_at=row.completed_at,
    )


async def validate_certification_target(
    db: AsyncSession, *, user_id: str, profile_version_id: str, connection_id: str,
) -> bool:
    row = await db.execute(select(ModelProfileVersion, ModelProfile, ModelConnection).join(
        ModelProfile, ModelProfile.id == ModelProfileVersion.model_id,
    ).join(
        ModelConnection, ModelConnection.id == connection_id,
    ).where(
        ModelProfileVersion.id == profile_version_id,
        ModelConnection.user_id == user_id,
        ModelConnection.provider_id == ModelProfile.provider_id,
    ))
    return row.one_or_none() is not None


def _fingerprint(values: dict) -> str:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


async def create_certification_intent(
    db: AsyncSession, *, user_id: str, profile_version_id: str, connection_id: str,
    level: str, reason: str, evidence: dict, estimated_cost_rmb: Decimal,
) -> CertificationRow:
    row = ModelCertificationRun(
        id=str(uuid4()), user_id=user_id, profile_version_id=profile_version_id,
        connection_id=connection_id, level=level, status="queued",
        request_fingerprint=_fingerprint(evidence), sanitized_evidence=evidence,
        estimated_cost_rmb=estimated_cost_rmb, actual_cost_rmb=Decimal("0"),
    )
    db.add(row)
    audit = ModelConfigAuditEvent(
        id=str(uuid4()), user_id=user_id, resource_type="model_certification_run",
        resource_id=row.id, action="create", from_version_id=None, to_version_id=profile_version_id,
        reason=reason, sanitized_change_summary={"level": level, "execution_mode": "safe_intent_only"},
    )
    db.add(audit)
    await db.flush()
    return as_certification_row(row)


async def load_certification_intent(
    db: AsyncSession, *, user_id: str, run_id: str,
) -> CertificationRow | None:
    row = await db.scalar(select(ModelCertificationRun).where(
        ModelCertificationRun.id == run_id, ModelCertificationRun.user_id == user_id,
    ))
    return as_certification_row(row) if row else None

