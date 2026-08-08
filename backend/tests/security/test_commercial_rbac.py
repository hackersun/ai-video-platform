from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.core.permissions as permissions
from app.core.database import Base
from app.models.project import Project, ProjectMember
from app.models.tenant import Organization, OrganizationMember, Workspace, WorkspaceMember
from app.models.tenant import AuditEvent


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_reviewer_is_a_supported_project_role() -> None:
    assert permissions.normalize_project_role(" reviewer ") == "reviewer"


@pytest.mark.parametrize("role", ["billing", "platform_admin", "unknown"])
def test_non_project_roles_are_rejected(role: str) -> None:
    with pytest.raises(Exception, match="角色必须是"):
        permissions.normalize_project_role(role)


def test_project_roles_have_explicit_non_linear_capabilities() -> None:
    assert permissions.project_role_allows("reviewer", "view") is True
    assert permissions.project_role_allows("reviewer", "review") is True
    assert permissions.project_role_allows("reviewer", "edit") is False
    assert permissions.project_role_allows("editor", "review") is False
    assert permissions.project_role_allows("owner", "manage_members") is True
    assert permissions.project_role_allows("viewer", "review") is False


async def _seed_tenant_project(db: AsyncSession, *, workspace_member_active: bool) -> None:
    db.add_all(
        [
            Organization(id="org-1", name="测试组织", slug="test-org", is_active=True),
            OrganizationMember(
                id="org-member-1", organization_id="org-1", user_id="member-1",
                role="owner", is_active=True,
            ),
            OrganizationMember(
                id="org-owner-1", organization_id="org-1", user_id="owner-1",
                role="owner", is_active=True,
            ),
            Workspace(
                id="workspace-1", organization_id="org-1", name="测试工作区",
                slug="test", is_active=True,
            ),
            WorkspaceMember(
                id="workspace-member-1", workspace_id="workspace-1", user_id="member-1",
                role="member", is_active=workspace_member_active,
            ),
            WorkspaceMember(
                id="workspace-owner-1", workspace_id="workspace-1", user_id="owner-1",
                role="admin", is_active=True,
            ),
            Project(
                id="project-1", user_id="owner-1", workspace_id="workspace-1",
                name="商业项目", status="active",
            ),
            ProjectMember(
                id="project-member-1", project_id="project-1", user_id="member-1",
                role="reviewer", is_active=True,
            ),
        ]
    )
    await db.commit()


@pytest.mark.asyncio
async def test_inactive_workspace_member_cannot_use_active_project_membership(
    db_session: AsyncSession,
) -> None:
    await _seed_tenant_project(db_session, workspace_member_active=False)

    with pytest.raises(HTTPException) as error:
        await permissions.get_project_access(db_session, "project-1", "member-1", "viewer")

    assert error.value.status_code == 404
    assert error.value.detail == "项目不存在"


@pytest.mark.asyncio
async def test_active_reviewer_can_view_but_cannot_edit(db_session: AsyncSession) -> None:
    await _seed_tenant_project(db_session, workspace_member_active=True)

    project, role = await permissions.get_project_access(
        db_session, "project-1", "member-1", "viewer"
    )
    assert project.id == "project-1"
    assert role == "reviewer"
    with pytest.raises(HTTPException) as error:
        await permissions.get_project_access(db_session, "project-1", "member-1", "editor")
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_personal_workspace_creation_is_idempotent(db_session: AsyncSession) -> None:
    from app.features.access_control.tenancy import ensure_personal_workspace

    first = await ensure_personal_workspace(db_session, "new-user", "新用户")
    second = await ensure_personal_workspace(db_session, "new-user", "新用户")
    await db_session.commit()

    assert first.id == second.id
    assert len((await db_session.scalars(select(Organization))).all()) == 1
    assert len((await db_session.scalars(select(Workspace))).all()) == 1


@pytest.mark.asyncio
async def test_project_member_change_is_audited_and_grants_tenant_membership(
    db_session: AsyncSession,
) -> None:
    from app.features.access_control.membership import add_or_restore_project_member

    await _seed_tenant_project(db_session, workspace_member_active=True)
    member = await add_or_restore_project_member(
        db_session,
        project_id="project-1",
        actor_user_id="owner-1",
        member_user_id="reviewer-2",
        role="reviewer",
    )
    await db_session.commit()

    assert member.role == "reviewer"
    workspace_member = await db_session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == "workspace-1",
            WorkspaceMember.user_id == "reviewer-2",
        )
    )
    organization_member = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == "org-1",
            OrganizationMember.user_id == "reviewer-2",
        )
    )
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.object_id == "reviewer-2")
    )
    assert workspace_member and workspace_member.role == "member"
    assert organization_member and organization_member.role == "member"
    assert audit and audit.action == "project.member.upsert"
    assert audit.actor_user_id == "owner-1"


@pytest.mark.asyncio
async def test_project_member_removal_is_soft_and_audited(db_session: AsyncSession) -> None:
    from app.features.access_control.membership import deactivate_project_member

    await _seed_tenant_project(db_session, workspace_member_active=True)
    member = await deactivate_project_member(
        db_session,
        project_id="project-1",
        actor_user_id="owner-1",
        member_user_id="member-1",
    )
    await db_session.commit()

    assert member.is_active is False
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "project.member.deactivate")
    )
    assert audit and audit.before_summary == {"role": "reviewer", "is_active": True}
    assert audit.after_summary == {"role": "reviewer", "is_active": False}


@pytest.mark.asyncio
async def test_role_update_does_not_create_a_missing_member(db_session: AsyncSession) -> None:
    from app.features.access_control.membership import change_project_member_role

    await _seed_tenant_project(db_session, workspace_member_active=True)
    with pytest.raises(HTTPException) as error:
        await change_project_member_role(
            db_session,
            project_id="project-1",
            actor_user_id="owner-1",
            member_user_id="missing-member",
            role="viewer",
        )
    assert error.value.status_code == 404
    assert error.value.detail == "成员不存在"


@pytest.mark.asyncio
async def test_audit_events_cannot_be_updated(db_session: AsyncSession) -> None:
    audit = AuditEvent(
        id="audit-immutable",
        actor_user_id="owner-1",
        action="project.member.upsert",
        object_type="project_member",
        object_id="member-1",
        result="success",
    )
    db_session.add(audit)
    await db_session.commit()

    audit.action = "tampered"
    with pytest.raises(RuntimeError, match="审计记录不可修改"):
        await db_session.flush()


def test_access_control_http_flow_uses_server_side_permissions(registration_client) -> None:
    owner_headers = {"Authorization": "Bearer rbac-http-owner"}
    reviewer_headers = {"Authorization": "Bearer rbac-http-reviewer"}
    created = registration_client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "商用权限验收项目"},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    added = registration_client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=owner_headers,
        json={"user_id": "rbac-http-reviewer", "role": "reviewer"},
    )
    assert added.status_code == 201
    assert added.json()["role"] == "reviewer"
    assert registration_client.get(
        f"/api/v1/projects/{project_id}", headers=reviewer_headers
    ).status_code == 200
    assert registration_client.put(
        f"/api/v1/projects/{project_id}",
        headers=reviewer_headers,
        json={"description": "审核角色不得编辑"},
    ).status_code == 404

    organizations = registration_client.get(
        "/api/v1/access-control/organizations", headers=owner_headers
    )
    workspaces = registration_client.get(
        "/api/v1/access-control/workspaces", headers=owner_headers
    )
    audits = registration_client.get(
        "/api/v1/access-control/audit-events",
        headers=owner_headers,
        params={"project_id": project_id},
    )
    assert organizations.status_code == 200 and len(organizations.json()) == 1
    assert workspaces.status_code == 200 and len(workspaces.json()) == 1
    assert audits.status_code == 200
    assert audits.json()[0]["action"] == "project.member.upsert"
