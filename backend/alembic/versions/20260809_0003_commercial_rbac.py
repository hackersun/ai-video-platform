"""Add organizations, workspaces, project tenancy, and audit events.

Revision ID: 20260809_0003
Revises: 20260808_0002
Create Date: 2026-08-09
"""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from alembic import op
import sqlalchemy as sa


revision = "20260809_0003"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None


def _id(kind: str, value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ai-video-platform:{kind}:{value}"))


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_organizations() -> None:
    if "organizations" in _table_names():
        return
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)


def _create_members_and_workspaces() -> None:
    tables = _table_names()
    if "organization_members" not in tables:
        op.create_table(
            "organization_members",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),
        )
    if "workspaces" not in tables:
        op.create_table(
            "workspaces",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("organization_id", "slug", name="uq_workspace_organization_slug"),
        )
    tables = _table_names()
    if "workspace_members" not in tables:
        op.create_table(
            "workspace_members",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
        )


def _create_audit_events() -> None:
    if "audit_events" in _table_names():
        return
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("object_type", sa.String(80), nullable=False),
        sa.Column("object_id", sa.String(100), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("before_summary", sa.JSON(), nullable=True),
        sa.Column("after_summary", sa.JSON(), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_events_scope_time", "audit_events", ["organization_id", "project_id", "created_at"])


def _ensure_indexes() -> None:
    specs = (
        ("organization_members", "ix_organization_members_organization_id", ["organization_id"]),
        ("organization_members", "ix_organization_members_user_id", ["user_id"]),
        ("workspaces", "ix_workspaces_organization_id", ["organization_id"]),
        ("workspace_members", "ix_workspace_members_workspace_id", ["workspace_id"]),
        ("workspace_members", "ix_workspace_members_user_id", ["user_id"]),
        ("audit_events", "ix_audit_events_actor_user_id", ["actor_user_id"]),
        ("audit_events", "ix_audit_events_action", ["action"]),
    )
    for table, name, columns in specs:
        if name not in _index_names(table):
            op.create_index(name, table, columns)


def _ensure_project_workspace() -> None:
    if "projects" not in _table_names():
        return
    if "workspace_id" not in _column_names("projects"):
        op.add_column("projects", sa.Column("workspace_id", sa.String(36), nullable=True))
    if "ix_projects_workspace_id" not in _index_names("projects"):
        op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        foreign_keys = {item.get("name") for item in sa.inspect(bind).get_foreign_keys("projects")}
        if "fk_projects_workspace_id" not in foreign_keys:
            op.create_foreign_key(
                "fk_projects_workspace_id", "projects", "workspaces", ["workspace_id"], ["id"], ondelete="SET NULL"
            )


def _insert_if_missing(table: sa.Table, key: str, values: dict) -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.select(table.c.id).where(table.c.id == key)).first()
    if not exists:
        bind.execute(table.insert().values(**values))


def _backfill_personal_spaces() -> None:
    tables = _table_names()
    if not {"users", "projects", "project_members"} <= tables:
        return
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, autoload_with=op.get_bind())
    projects = sa.Table("projects", metadata, autoload_with=op.get_bind())
    project_members = sa.Table("project_members", metadata, autoload_with=op.get_bind())
    organizations = sa.Table("organizations", metadata, autoload_with=op.get_bind())
    organization_members = sa.Table("organization_members", metadata, autoload_with=op.get_bind())
    workspaces = sa.Table("workspaces", metadata, autoload_with=op.get_bind())
    workspace_members = sa.Table("workspace_members", metadata, autoload_with=op.get_bind())
    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for user in bind.execute(sa.select(users.c.id, users.c.username)):
        user_id = str(user.id)
        organization_id = _id("personal-organization", user_id)
        workspace_id = _id("personal-workspace", user_id)
        _insert_if_missing(organizations, organization_id, {
            "id": organization_id, "name": f"{user.username}的个人组织",
            "slug": f"personal-{_id('slug', user_id)}", "is_active": True,
            "created_at": now, "updated_at": now,
        })
        _insert_if_missing(organization_members, _id("organization-member", user_id), {
            "id": _id("organization-member", user_id), "organization_id": organization_id,
            "user_id": user_id, "role": "owner", "is_active": True,
            "created_at": now, "updated_at": now,
        })
        _insert_if_missing(workspaces, workspace_id, {
            "id": workspace_id, "organization_id": organization_id, "name": "个人工作区",
            "slug": "personal", "is_active": True, "created_at": now, "updated_at": now,
        })
        _insert_if_missing(workspace_members, _id("workspace-member", user_id), {
            "id": _id("workspace-member", user_id), "workspace_id": workspace_id,
            "user_id": user_id, "role": "admin", "is_active": True,
            "created_at": now, "updated_at": now,
        })
        bind.execute(
            projects.update().where(
                projects.c.user_id == user_id, projects.c.workspace_id.is_(None)
            ).values(workspace_id=workspace_id)
        )
    for project in bind.execute(sa.select(projects.c.id, projects.c.user_id)):
        exists = bind.execute(sa.select(project_members.c.id).where(
            project_members.c.project_id == project.id,
            project_members.c.user_id == project.user_id,
            project_members.c.is_active.is_(True),
        )).first()
        if not exists:
            bind.execute(project_members.insert().values(
                id=str(uuid4()), project_id=project.id, user_id=project.user_id,
                role="owner", is_active=True, invited_at=now, joined_at=now, created_at=now,
            ))


def _backfill_project_collaborators() -> None:
    metadata = sa.MetaData()
    bind = op.get_bind()
    projects = sa.Table("projects", metadata, autoload_with=bind)
    project_members = sa.Table("project_members", metadata, autoload_with=bind)
    workspaces = sa.Table("workspaces", metadata, autoload_with=bind)
    organization_members = sa.Table("organization_members", metadata, autoload_with=bind)
    workspace_members = sa.Table("workspace_members", metadata, autoload_with=bind)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    memberships = bind.execute(
        sa.select(
            project_members.c.user_id,
            projects.c.user_id.label("owner_id"),
            projects.c.workspace_id,
            workspaces.c.organization_id,
        )
        .join(projects, projects.c.id == project_members.c.project_id)
        .join(workspaces, workspaces.c.id == projects.c.workspace_id)
        .where(project_members.c.is_active.is_(True))
    )
    for membership in memberships:
        organization_member = bind.execute(
            sa.select(organization_members.c.id).where(
                organization_members.c.organization_id == membership.organization_id,
                organization_members.c.user_id == membership.user_id,
            )
        ).first()
        if not organization_member:
            bind.execute(organization_members.insert().values(
                id=_id("organization-member", f"{membership.organization_id}:{membership.user_id}"),
                organization_id=membership.organization_id,
                user_id=membership.user_id,
                role="owner" if membership.user_id == membership.owner_id else "member",
                is_active=True,
                created_at=now,
                updated_at=now,
            ))
        workspace_member = bind.execute(
            sa.select(workspace_members.c.id).where(
                workspace_members.c.workspace_id == membership.workspace_id,
                workspace_members.c.user_id == membership.user_id,
            )
        ).first()
        if not workspace_member:
            bind.execute(workspace_members.insert().values(
                id=_id("workspace-member", f"{membership.workspace_id}:{membership.user_id}"),
                workspace_id=membership.workspace_id,
                user_id=membership.user_id,
                role="admin" if membership.user_id == membership.owner_id else "member",
                is_active=True,
                created_at=now,
                updated_at=now,
            ))


def upgrade() -> None:
    _create_organizations()
    _create_members_and_workspaces()
    _create_audit_events()
    _ensure_indexes()
    _ensure_project_workspace()
    _backfill_personal_spaces()
    _backfill_project_collaborators()


def downgrade() -> None:
    raise RuntimeError("租户权限迁移不可安全降级；请恢复迁移前备份")
