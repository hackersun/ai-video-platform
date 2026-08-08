"""Commercial tenant hierarchy and append-only audit records."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, event

from app.core.database import Base
from app.core.time_utils import utc_now


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),
    )

    id = Column(String(36), primary_key=True)
    organization_id = Column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="member")  # owner, billing, member
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_workspace_organization_slug"),
    )

    id = Column(String(36), primary_key=True)
    organization_id = Column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    id = Column(String(36), primary_key=True)
    workspace_id = Column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="member")  # admin, member
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class AuditEvent(Base):
    """Append-only security event; no update/delete API is exposed."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_scope_time", "organization_id", "project_id", "created_at"),
    )

    id = Column(String(36), primary_key=True)
    actor_user_id = Column(String(36), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    object_type = Column(String(80), nullable=False)
    object_id = Column(String(100), nullable=False)
    request_id = Column(String(100), nullable=True)
    before_summary = Column(JSON, nullable=True)
    after_summary = Column(JSON, nullable=True)
    result = Column(String(20), nullable=False, default="success")
    created_at = Column(DateTime, nullable=False, default=utc_now)


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def _reject_audit_mutation(_mapper, _connection, _target) -> None:
    raise RuntimeError("审计记录不可修改或删除")
