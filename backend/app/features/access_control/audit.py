"""Append-only audit event writer."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import AuditEvent


def record_audit_event(
    db: AsyncSession,
    *,
    actor_user_id: str,
    action: str,
    object_type: str,
    object_id: str,
    organization_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    before_summary: dict | None = None,
    after_summary: dict | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        id=str(uuid4()),
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        project_id=project_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        request_id=request_id,
        before_summary=before_summary,
        after_summary=after_summary,
        result="success",
    )
    db.add(event)
    return event
