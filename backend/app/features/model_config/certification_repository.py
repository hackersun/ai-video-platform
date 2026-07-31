"""Safe intent persistence for Model Center certification runs.

This module deliberately does not import provider drivers or submit network jobs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.llm_config import LLMConfig, LLMModel
from app.models.model_center import (
    ModelCertificationRun,
    ModelConfigAuditEvent,
    ModelConnection,
    ModelProfile,
    ModelProfileVersion,
    ModelProvider,
)
from app.features.model_config.domain import VERIFIED_CONNECTION_STATUSES


_SENSITIVE_EVIDENCE_MARKERS = (
    "apikey", "apisecret", "authorization", "token", "password", "secret",
    "credential", "header", "prompt", "rawrequest", "rawresponse",
)
_TRANSIENT_PROVIDER_ERRORS = frozenset({
    "ConnectTimeout", "ReadTimeout", "TimeoutError", "TimeoutException",
})


def _safe_evidence(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, nested in value.items():
            normalized = "".join(character for character in str(key).lower() if character.isalnum())
            if any(marker in normalized for marker in _SENSITIVE_EVIDENCE_MARKERS):
                continue
            sanitized[str(key)] = _safe_evidence(nested)
        return sanitized
    if isinstance(value, list):
        return [_safe_evidence(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return f"<{type(value).__name__}>"


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
        level=row.level, status=row.status,
        sanitized_evidence=_safe_evidence(dict(row.sanitized_evidence or {})),
        estimated_cost_rmb=Decimal(row.estimated_cost_rmb), actual_cost_rmb=Decimal(row.actual_cost_rmb),
        created_at=row.created_at, completed_at=row.completed_at,
    )


def _is_transient_provider_failure(run: ModelCertificationRun) -> bool:
    evidence = run.sanitized_evidence or {}
    response = evidence.get("response_evidence") or {}
    error_type = response.get("provider_error_type") or evidence.get("error_code")
    return str(error_type or "") in _TRANSIENT_PROVIDER_ERRORS


async def _sync_legacy_config_test(
    db: AsyncSession, *, run: ModelCertificationRun,
    connection: ModelConnection, connection_status: str,
) -> None:
    legacy_config_id = (connection.connection_params or {}).get("legacy_config_id")
    if not legacy_config_id:
        return
    config = await db.scalar(
        select(LLMConfig).join(LLMModel, LLMModel.id == LLMConfig.model_id).join(
            ModelProfileVersion,
            ModelProfileVersion.api_model_id == LLMModel.model_id,
        ).where(
            LLMConfig.id == legacy_config_id,
            LLMConfig.user_id == run.user_id,
            ModelProfileVersion.id == run.profile_version_id,
        )
    )
    if config is None:
        return
    passed = connection_status == "connection_verified"
    if not passed and config.test_status == "success" and _is_transient_provider_failure(run):
        return
    config.test_status = "success" if passed else "failed"
    config.test_message = (
        "模型中心连接认证通过" if passed else "模型中心连接认证失败"
    )
    config.tested_at = run.completed_at


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


async def certification_candidates_page(
    db: AsyncSession, *, user_id: str, page: int, page_size: int,
    capability: str | None = None, query: str | None = None,
    level: str | None = None, profile_version_id: str | None = None,
    connection_id: str | None = None,
) -> dict:
    rows = (await db.execute(select(
        ModelProfileVersion, ModelProfile, ModelProvider, ModelConnection,
    ).join(ModelProfile, ModelProfile.id == ModelProfileVersion.model_id).join(
        ModelProvider, ModelProvider.id == ModelProfile.provider_id,
    ).join(ModelConnection, ModelConnection.provider_id == ModelProvider.id).where(
        ModelProfileVersion.status == "published", ModelProfile.enabled == True,
        ModelProvider.enabled == True, ModelConnection.user_id == user_id,
    ).order_by(ModelProfile.display_name, ModelConnection.name))).all()
    keyword = (query or "").strip().casefold()
    candidates = []
    for version, profile, provider, connection in rows:
        if profile_version_id and version.id != profile_version_id:
            continue
        if connection_id and connection.id != connection_id:
            continue
        if level == "connection":
            if not (connection.api_key or connection.api_secret):
                continue
        elif connection.status not in VERIFIED_CONNECTION_STATUSES:
            continue
        if capability and capability not in set(version.capabilities or []):
            continue
        searchable = " ".join((
            profile.display_name, version.api_model_id, provider.display_name,
            provider.code, connection.name,
        )).casefold()
        if keyword and keyword not in searchable:
            continue
        candidates.append({
            "id": f"{version.id}:{connection.id}",
            "profile": {
                "id": version.id, "name": profile.display_name,
                "api_model_id": version.api_model_id, "provider_id": provider.id,
                "provider_name": provider.display_name,
                "capabilities": list(version.capabilities or []),
            },
            "connection": {
                "id": connection.id, "name": connection.name,
                "provider_id": connection.provider_id, "status": connection.status,
            },
        })
    start = (page - 1) * page_size
    return {
        "items": candidates[start:start + page_size],
        "meta": {"page": page, "page_size": page_size, "total": len(candidates)},
    }


async def complete_certification_run(
    db: AsyncSession, *, user_id: str, run_id: str, status: str,
    evidence: dict, connection_status: str | None = None,
) -> CertificationRow | None:
    run = await db.scalar(select(ModelCertificationRun).where(
        ModelCertificationRun.id == run_id, ModelCertificationRun.user_id == user_id,
    ))
    if run is None:
        return None
    run.status = status
    run.sanitized_evidence = _safe_evidence(evidence)
    run.completed_at = utc_now()
    if connection_status is not None:
        connection = await db.scalar(select(ModelConnection).where(
            ModelConnection.id == run.connection_id, ModelConnection.user_id == user_id,
        ))
        if connection is not None:
            connection.status = connection_status
            connection.tested_at = run.completed_at
            connection.revision += 1
            await _sync_legacy_config_test(
                db, run=run, connection=connection,
                connection_status=connection_status,
            )
    await db.flush()
    return as_certification_row(run)


async def certification_history_page(
    db: AsyncSession, *, user_id: str, page: int, page_size: int,
    level: str | None = None, status: str | None = None,
) -> dict:
    statement = select(
        ModelCertificationRun, ModelProfileVersion, ModelProfile,
        ModelConnection, ModelProvider,
    ).join(
        ModelProfileVersion, ModelProfileVersion.id == ModelCertificationRun.profile_version_id,
    ).join(ModelProfile, ModelProfile.id == ModelProfileVersion.model_id).join(
        ModelConnection, ModelConnection.id == ModelCertificationRun.connection_id,
    ).join(ModelProvider, ModelProvider.id == ModelProfile.provider_id).where(
        ModelCertificationRun.user_id == user_id,
    )
    if level:
        statement = statement.where(ModelCertificationRun.level == level)
    if status:
        statement = statement.where(ModelCertificationRun.status == status)
    rows = (await db.execute(statement.order_by(
        desc(ModelCertificationRun.created_at), ModelCertificationRun.id,
    ))).all()
    start = (page - 1) * page_size
    items = []
    for run, version, profile, connection, provider in rows[start:start + page_size]:
        item = certification_item(run)
        item.update({
            "profile_name": profile.display_name, "api_model_id": version.api_model_id,
            "connection_name": connection.name, "provider_name": provider.display_name,
        })
        items.append(item)
    return {"items": items, "meta": {"page": page, "page_size": page_size, "total": len(rows)}}


def certification_item(row: ModelCertificationRun | CertificationRow) -> dict:
    values = as_certification_row(row) if isinstance(row, ModelCertificationRun) else row
    return {
        "id": values.id, "profile_version_id": values.profile_version_id,
        "connection_id": values.connection_id, "level": values.level, "status": values.status,
        "sanitized_evidence": values.sanitized_evidence,
        "estimated_cost_rmb": f"{values.estimated_cost_rmb:.4f}",
        "actual_cost_rmb": f"{values.actual_cost_rmb:.4f}",
        "created_at": values.created_at.isoformat(),
        "completed_at": values.completed_at.isoformat() if values.completed_at else None,
    }
