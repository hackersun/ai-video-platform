"""Safe certification intent and impact-preview routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import raise_http
from app.features.model_config.api.schemas import (
    CertificationCandidateItem,
    CertificationHistoryItem,
    CertificationRequest,
    PageResponse,
)


router = APIRouter()


@router.get("/certification-candidates", response_model=PageResponse[CertificationCandidateItem])
async def list_certification_candidates(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    capability: str | None = Query(default=None), q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.certification_candidates(
        db, user_id=user_id, page=page, page_size=page_size,
        capability=capability, query=q,
    )


@router.get("/certifications", response_model=PageResponse[CertificationHistoryItem])
async def list_certifications(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    level: str | None = Query(default=None), status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.certifications_history(
        db, user_id=user_id, page=page, page_size=page_size,
        level=level, status=status,
    )


@router.post("/certifications")
async def create_certification(
    request: CertificationRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.create_certification(db, user_id=user_id, request=request)
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.get("/certifications/{run_id}")
async def get_certification(
    run_id: str,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.get_certification(db, user_id=user_id, run_id=run_id)
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.get("/impact")
async def get_impact(
    resource_type: str | None = Query(default=None), resource_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.impact_preview(
            db, user_id=user_id, resource_type=resource_type, resource_id=resource_id,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)
