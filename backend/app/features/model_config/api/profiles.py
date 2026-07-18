"""Versioned model profile management routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import raise_http, unsupported
from app.features.model_config.api.schemas import (
    ContractValidationResponse,
    ModelProfileCreateRequest,
    ModelProfileItem,
    ModelProfileVersionCreateRequest,
    ModelProfileVersionItem,
    PublishRequest,
    PublishResponse,
    RevisionedUpdateRequest,
    RollbackRequest,
)


router = APIRouter()


@router.post("/profiles", response_model=ModelProfileItem)
async def create_profile(
    request: ModelProfileCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        async with db.begin():
            return await service.create_model_profile(db, user_id=user_id, request=request)
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/profiles/{profile_id}/versions", response_model=ModelProfileVersionItem)
async def create_profile_version(
    profile_id: str, request: ModelProfileVersionCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        async with db.begin():
            return await service.create_model_profile_version(
                db, user_id=user_id, profile_id=profile_id, request=request,
            )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.put("/profile-versions/{profile_version_id}")
async def update_profile_version(profile_version_id: str, request: RevisionedUpdateRequest):
    del profile_version_id, request
    return unsupported("profile_version.update")


@router.post("/profile-versions/{profile_version_id}/validate", response_model=ContractValidationResponse)
async def validate_profile_version(
    profile_version_id: str,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        async with db.begin():
            return await service.validate_profile_contract(
                db, user_id=user_id, version_id=profile_version_id,
            )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/profile-versions/{profile_version_id}/publish", response_model=PublishResponse)
async def publish_profile_version(
    profile_version_id: str, request: PublishRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        async with db.begin():
            return await service.publish_model_profile_version(
                db, user_id=user_id, version_id=profile_version_id, request=request,
            )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/profile-versions/{profile_version_id}/disable")
async def disable_profile_version(profile_version_id: str, request: PublishRequest):
    del profile_version_id, request
    return unsupported("profile_version.disable")


@router.post("/profiles/{profile_id}/rollback")
async def rollback_profile(profile_id: str, request: RollbackRequest):
    del profile_id, request
    return unsupported("profile.rollback")
