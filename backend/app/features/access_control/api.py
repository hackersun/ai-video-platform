"""Read-only tenant, permission-matrix, and audit endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.access_control.permission_matrix import PERMISSION_MATRIX
from app.features.access_control.schemas import AuditEventSummary, OrganizationSummary, WorkspaceSummary
from app.features.access_control.service import require_project_role
from app.features.access_control.tenancy import ensure_personal_workspace
from app.models.tenant import AuditEvent, Organization, OrganizationMember, Workspace, WorkspaceMember
from app.models.user import User


router = APIRouter(prefix="/access-control", tags=["权限与组织"])


async def _ensure_personal_space(db: AsyncSession, user_id: str) -> None:
    user = await db.get(User, user_id)
    await ensure_personal_workspace(db, user_id, user.username if user else user_id)
    await db.commit()


@router.get("/permission-matrix")
async def get_permission_matrix(
    _user_id: str = Depends(get_current_user_id),
) -> dict:
    return {"items": PERMISSION_MATRIX}


@router.get("/organizations", response_model=list[OrganizationSummary])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[OrganizationSummary]:
    await _ensure_personal_space(db, user_id)
    rows = (
        await db.execute(
            select(Organization, OrganizationMember.role)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active.is_(True),
                Organization.is_active.is_(True),
            )
            .order_by(Organization.name)
        )
    ).all()
    return [OrganizationSummary(id=item.id, name=item.name, slug=item.slug, role=role) for item, role in rows]


@router.get("/workspaces", response_model=list[WorkspaceSummary])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[WorkspaceSummary]:
    await _ensure_personal_space(db, user_id)
    rows = (
        await db.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_active.is_(True),
                Workspace.is_active.is_(True),
            )
            .order_by(Workspace.name)
        )
    ).all()
    return [
        WorkspaceSummary(
            id=item.id,
            organization_id=item.organization_id,
            name=item.name,
            slug=item.slug,
            role=role,
        )
        for item, role in rows
    ]


@router.get("/audit-events", response_model=list[AuditEventSummary])
async def list_project_audit_events(
    project_id: str = Query(...),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[AuditEvent]:
    await require_project_role(db, project_id, user_id, "owner")
    return list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(AuditEvent.project_id == project_id)
                .order_by(desc(AuditEvent.created_at))
                .limit(limit)
            )
        ).all()
    )
