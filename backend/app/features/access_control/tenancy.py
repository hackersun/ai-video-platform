"""Idempotent personal tenancy and collaborator membership helpers."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.tenant import Organization, OrganizationMember, Workspace, WorkspaceMember


def _stable_id(kind: str, value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ai-video-platform:{kind}:{value}"))


async def _ensure_organization(
    db: AsyncSession, user_id: str, username: str
) -> Organization:
    organization_id = _stable_id("personal-organization", user_id)
    organization = await db.get(Organization, organization_id)
    if not organization:
        organization = Organization(
            id=organization_id,
            name=f"{username}的个人组织",
            slug=f"personal-{_stable_id('slug', user_id)}",
            is_active=True,
        )
        db.add(organization)
        await db.flush()
    member = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id == user_id,
        )
    )
    if not member:
        db.add(OrganizationMember(
            id=_stable_id("organization-member", user_id),
            organization_id=organization.id,
            user_id=user_id,
            role="owner",
            is_active=True,
        ))
        await db.flush()
    return organization


async def ensure_personal_workspace(
    db: AsyncSession, user_id: str, username: str
) -> Workspace:
    organization = await _ensure_organization(db, user_id, username)
    workspace_id = _stable_id("personal-workspace", user_id)
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        workspace = Workspace(
            id=workspace_id,
            organization_id=organization.id,
            name="个人工作区",
            slug="personal",
            is_active=True,
        )
        db.add(workspace)
        await db.flush()
    member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not member:
        db.add(WorkspaceMember(
            id=_stable_id("workspace-member", user_id),
            workspace_id=workspace.id,
            user_id=user_id,
            role="admin",
            is_active=True,
        ))
        await db.flush()
    return workspace


async def ensure_project_tenant_membership(
    db: AsyncSession, project: Project, user_id: str
) -> None:
    if not project.workspace_id:
        return
    workspace = await db.get(Workspace, project.workspace_id)
    if not workspace:
        return
    organization_member = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == workspace.organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if not organization_member:
        organization_member = OrganizationMember(
            id=_stable_id("organization-member", f"{workspace.organization_id}:{user_id}"),
            organization_id=workspace.organization_id,
            user_id=user_id,
            role="member",
        )
        db.add(organization_member)
    organization_member.is_active = True
    workspace_member = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not workspace_member:
        workspace_member = WorkspaceMember(
            id=_stable_id("workspace-member", f"{workspace.id}:{user_id}"),
            workspace_id=workspace.id,
            user_id=user_id,
            role="member",
        )
        db.add(workspace_member)
    workspace_member.is_active = True
    await db.flush()
