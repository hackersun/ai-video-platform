"""Database-backed project authorization with tenant-state enforcement."""

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.access_control.roles import has_role_at_least, normalize_project_role
from app.models.project import Project, ProjectMember
from app.models.tenant import Organization, OrganizationMember, Workspace, WorkspaceMember


def _hidden_project_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")


async def _effective_project_role(
    db: AsyncSession, project: Project, user_id: str
) -> str | None:
    if project.user_id == user_id:
        return "owner"
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user_id,
            ProjectMember.is_active.is_(True),
        )
    )
    return member.role if member else None


async def _tenant_membership_is_active(
    db: AsyncSession, workspace_id: str, user_id: str
) -> bool:
    workspace = await db.scalar(
        select(Workspace.id)
        .join(Organization, Organization.id == Workspace.organization_id)
        .join(
            WorkspaceMember,
            and_(
                WorkspaceMember.workspace_id == Workspace.id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_active.is_(True),
            ),
        )
        .join(
            OrganizationMember,
            and_(
                OrganizationMember.organization_id == Organization.id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active.is_(True),
            ),
        )
        .where(
            Workspace.id == workspace_id,
            Workspace.is_active.is_(True),
            Organization.is_active.is_(True),
        )
    )
    return workspace is not None


async def get_project_access(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    required_role: str = "viewer",
) -> tuple[Project, str]:
    required = normalize_project_role(required_role)
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise _hidden_project_error()

    role = await _effective_project_role(db, project, user_id)
    if not role or not has_role_at_least(role, required):
        raise _hidden_project_error()
    if project.workspace_id and not await _tenant_membership_is_active(
        db, project.workspace_id, user_id
    ):
        raise _hidden_project_error()
    return project, role


async def require_project_role(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    required_role: str,
) -> Project:
    project, _role = await get_project_access(db, project_id, user_id, required_role)
    return project
