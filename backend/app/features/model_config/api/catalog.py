"""Overview, driver, provider, and model catalog routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import raise_http, unsupported
from app.features.model_config.api.schemas import (
    CatalogItem,
    DriverItem,
    PageResponse,
    ProviderItem,
    ProviderCreateRequest,
    RevisionedUpdateRequest,
)
from app.features.model_config.catalog_permissions import CatalogPermissionError, require_catalog_admin


router = APIRouter()


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.overview(db, user_id)


@router.get("/drivers", response_model=PageResponse[DriverItem])
async def list_drivers(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return await service.drivers_page(page, page_size)


@router.post("/providers", response_model=ProviderItem)
async def create_provider(
    request: ProviderCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        require_catalog_admin(user_id)
        async with db.begin():
            return await service.create_model_provider(db, user_id=user_id, request=request)
    except CatalogPermissionError as error:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={
            "code": "catalog_admin_required", "message": str(error),
            "action_code": "contact_catalog_admin",
        }) from error
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.get("/providers", response_model=PageResponse[ProviderItem])
async def list_providers(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    del user_id
    return await service.providers_page(db, page, page_size)


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, request: RevisionedUpdateRequest):
    del provider_id, request
    return unsupported("provider.update")


@router.get("/catalog", response_model=PageResponse[CatalogItem])
async def list_catalog(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    capability: str | None = Query(None), provider_id: str | None = Query(None),
    status: str | None = Query(None), q: str | None = Query(None, max_length=160),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.catalog_page(
        db, user_id, page, page_size,
        capability=capability, provider_id=provider_id, status=status, query=q,
    )
