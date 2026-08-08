"""Read models for tenant and audit administration."""

from datetime import datetime

from pydantic import BaseModel


class OrganizationSummary(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class WorkspaceSummary(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    role: str


class AuditEventSummary(BaseModel):
    id: str
    actor_user_id: str
    action: str
    object_type: str
    object_id: str
    before_summary: dict | None
    after_summary: dict | None
    created_at: datetime
