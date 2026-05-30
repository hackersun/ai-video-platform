"""
Shared project permission helpers.
"""
from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectMember


PROJECT_ROLES = {"owner", "editor", "viewer"}
ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def normalize_project_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in PROJECT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="角色必须是 owner、editor 或 viewer",
        )
    return normalized


def has_role_at_least(actual_role: str, required_role: str) -> bool:
    return ROLE_RANK[actual_role] >= ROLE_RANK[required_role]


async def get_project_access(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    required_role: str = "viewer",
) -> tuple[Project, str]:
    """Return the project and effective role, honoring owner fallback."""
    required_role = normalize_project_role(required_role)
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if project.user_id == user_id:
        effective_role = "owner"
    else:
        member_result = await db.execute(
            select(ProjectMember).where(
                and_(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user_id,
                    ProjectMember.is_active == True,
                )
            )
        )
        member = member_result.scalar_one_or_none()
        effective_role = member.role if member else None

    if not effective_role or not has_role_at_least(effective_role, required_role):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    return project, effective_role


async def require_project_role(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    required_role: str,
) -> Project:
    project, _role = await get_project_access(db, project_id, user_id, required_role)
    return project


def allowed_roles_for_query(required_role: str = "viewer") -> Iterable[str]:
    required_role = normalize_project_role(required_role)
    return [role for role in PROJECT_ROLES if has_role_at_least(role, required_role)]
