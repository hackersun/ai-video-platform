"""Project membership mutations with tenant propagation and audit."""

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.access_control.audit import record_audit_event
from app.features.access_control.roles import normalize_project_role
from app.features.access_control.service import require_project_role
from app.features.access_control.tenancy import ensure_project_tenant_membership
from app.models.project import ProjectMember
from app.models.tenant import Workspace


async def add_or_restore_project_member(
    db: AsyncSession,
    *,
    project_id: str,
    actor_user_id: str,
    member_user_id: str,
    role: str,
) -> ProjectMember:
    project = await require_project_role(db, project_id, actor_user_id, "owner")
    normalized_role = normalize_project_role(role)
    if member_user_id == project.user_id and normalized_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目所有者必须保持 owner 角色",
        )
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == member_user_id,
        )
    )
    before = {"role": member.role, "is_active": member.is_active} if member else None
    if not member:
        member = ProjectMember(
            id=str(uuid4()),
            project_id=project_id,
            user_id=member_user_id,
            invited_at=utc_now(),
            joined_at=utc_now(),
        )
        db.add(member)
    member.role = "owner" if member_user_id == project.user_id else normalized_role
    member.is_active = True
    member.joined_at = member.joined_at or utc_now()
    await ensure_project_tenant_membership(db, project, member_user_id)
    workspace = await db.get(Workspace, project.workspace_id) if project.workspace_id else None
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="project.member.upsert",
        object_type="project_member",
        object_id=member_user_id,
        organization_id=workspace.organization_id if workspace else None,
        workspace_id=project.workspace_id,
        project_id=project_id,
        before_summary=before,
        after_summary={"role": member.role, "is_active": True},
    )
    return member


async def change_project_member_role(
    db: AsyncSession,
    *,
    project_id: str,
    actor_user_id: str,
    member_user_id: str,
    role: str,
) -> ProjectMember:
    project = await require_project_role(db, project_id, actor_user_id, "owner")
    normalized_role = normalize_project_role(role)
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == member_user_id,
            ProjectMember.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成员不存在",
        )
    if member_user_id == project.user_id and normalized_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目所有者必须保持 owner 角色",
        )
    before = {"role": member.role, "is_active": True}
    member.role = "owner" if member_user_id == project.user_id else normalized_role
    await ensure_project_tenant_membership(db, project, member_user_id)
    workspace = await db.get(Workspace, project.workspace_id) if project.workspace_id else None
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="project.member.role_changed",
        object_type="project_member",
        object_id=member_user_id,
        organization_id=workspace.organization_id if workspace else None,
        workspace_id=project.workspace_id,
        project_id=project_id,
        before_summary=before,
        after_summary={"role": member.role, "is_active": True},
    )
    return member


async def deactivate_project_member(
    db: AsyncSession,
    *,
    project_id: str,
    actor_user_id: str,
    member_user_id: str,
) -> ProjectMember:
    project = await require_project_role(db, project_id, actor_user_id, "owner")
    if member_user_id == project.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除项目所有者",
        )
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == member_user_id,
            ProjectMember.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成员不存在",
        )
    if member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除 owner 成员",
        )
    before = {"role": member.role, "is_active": True}
    member.is_active = False
    workspace = await db.get(Workspace, project.workspace_id) if project.workspace_id else None
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="project.member.deactivate",
        object_type="project_member",
        object_id=member_user_id,
        organization_id=workspace.organization_id if workspace else None,
        workspace_id=project.workspace_id,
        project_id=project_id,
        before_summary=before,
        after_summary={"role": member.role, "is_active": False},
    )
    return member
