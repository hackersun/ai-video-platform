"""Prompt Profile management routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import raise_http, unsupported
from app.features.model_config.api.schemas import (
    PromptProfileCreateRequest,
    PromptProfileVersionRequest,
    PublishRequest,
    RollbackRequest,
)


router = APIRouter()


@router.get("/prompt-profiles")
async def list_prompt_profiles(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.prompt_profiles_page(db, user_id, page, page_size)


@router.post("/prompt-profiles")
async def create_prompt_profile(
    request: PromptProfileCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.create_prompt_profile_versioned(db, user_id=user_id, request=request)
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/prompt-profiles/{profile_id}/versions")
async def create_prompt_profile_version(
    profile_id: str, request: PromptProfileVersionRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.create_prompt_profile_draft(
            db, user_id=user_id, profile_id=profile_id,
            expected_revision=request.expected_revision, changes=request.changes(),
        )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/prompt-profile-versions/{version_id}/publish")
async def publish_prompt_profile_version(
    version_id: str, request: PublishRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.publish_prompt_profile_version(
            db, user_id=user_id, version_id=version_id,
            expected_revision=request.expected_revision, reason=request.reason,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/prompt-profile-versions/{version_id}/disable")
async def disable_prompt_profile_version(version_id: str, request: PublishRequest):
    del version_id, request
    return unsupported("prompt_profile_version.disable")


@router.post("/prompt-profiles/{profile_id}/rollback")
async def rollback_prompt_profile(
    profile_id: str, request: RollbackRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.rollback_prompt_profile(
            db, user_id=user_id, profile_id=profile_id, target_version_id=request.target_version_id,
            expected_revision=request.expected_revision, reason=request.reason,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)
