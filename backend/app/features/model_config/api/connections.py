"""Connection management routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import unsupported
from app.features.model_config.api.schemas import (
    ConnectionCreateRequest,
    ConnectionItem,
    ConnectionMetadataUpdateRequest,
    ConnectionSecretReplacementRequest,
    PageResponse,
)


router = APIRouter()


@router.get("/connections", response_model=PageResponse[ConnectionItem])
async def list_connections(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.connections_page(db, user_id, page, page_size)


@router.post("/connections")
async def create_connection(
    request: ConnectionCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    del request, db, user_id
    return unsupported("connection.create")


@router.put("/connections/{connection_id}")
async def update_connection(
    connection_id: str,
    request: ConnectionMetadataUpdateRequest | ConnectionSecretReplacementRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    del connection_id, request, db, user_id
    return unsupported("connection.update")


@router.post("/connections/{connection_id}/test")
async def test_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    del connection_id, db, user_id
    return unsupported("connection.test")
