"""Connection management routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import raise_http
from app.features.model_config.api.schemas import (
    ConnectionCreateRequest,
    ConnectionItem,
    ConnectionMetadataUpdateRequest,
    ConnectionRemovalResponse,
    ConnectionSecretReplacementRequest,
    ConnectionTestIntentResponse,
    PageResponse,
    PublishRequest,
)


router = APIRouter()


@router.get("/connections", response_model=PageResponse[ConnectionItem])
async def list_connections(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.connections_page(db, user_id, page, page_size)


@router.post("/connections", response_model=ConnectionItem)
async def create_connection(
    request: ConnectionCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.create_connection(db, user_id=user_id, request=request)
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.put("/connections/{connection_id}", response_model=ConnectionItem)
async def update_connection(
    connection_id: str,
    request: ConnectionMetadataUpdateRequest | ConnectionSecretReplacementRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.update_connection(
            db, user_id=user_id, connection_id=connection_id, request=request,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.delete("/connections/{connection_id}", response_model=ConnectionRemovalResponse)
async def remove_connection(
    connection_id: str,
    request: PublishRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.remove_connection(
            db, user_id=user_id, connection_id=connection_id,
            expected_revision=request.expected_revision, reason=request.reason,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestIntentResponse)
async def test_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.test_connection(db, user_id=user_id, connection_id=connection_id)
    except service.ManagementOperationError as error:
        return raise_http(error)
