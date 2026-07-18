"""Scoped model binding management routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import unsupported
from app.features.model_config.api.schemas import CreateResourceRequest, RevisionedUpdateRequest


router = APIRouter()


@router.get("/bindings")
async def list_bindings(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.bindings_page(db, user_id, page, page_size)


@router.post("/bindings")
async def create_binding(request: CreateResourceRequest):
    del request
    return unsupported("binding.create")


@router.put("/bindings/{binding_id}")
async def update_binding(binding_id: str, request: RevisionedUpdateRequest):
    del binding_id, request
    return unsupported("binding.update")
