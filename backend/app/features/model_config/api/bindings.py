"""Scoped model binding management routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import raise_http
from app.features.model_config.api.schemas import (
    BindingCreateRequest,
    BindingItem,
    BindingUpdateRequest,
    PageResponse,
)


router = APIRouter()


@router.get("/bindings", response_model=PageResponse[BindingItem])
async def list_bindings(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.bindings_page(db, user_id, page, page_size)


@router.post("/bindings", response_model=BindingItem)
async def create_binding(
    request: BindingCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        async with db.begin():
            return await service.create_model_binding(db, user_id=user_id, request=request)
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.put("/bindings/{binding_id}", response_model=BindingItem)
async def update_binding(
    binding_id: str, request: BindingUpdateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        async with db.begin():
            return await service.update_model_binding(
                db, user_id=user_id, binding_id=binding_id, request=request,
            )
    except service.ManagementOperationError as error:
        return raise_http(error)
