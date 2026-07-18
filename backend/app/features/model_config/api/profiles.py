"""Versioned model profile management routes."""

from fastapi import APIRouter

from app.features.model_config.api.errors import unsupported
from app.features.model_config.api.schemas import (
    CreateResourceRequest,
    CreateVersionRequest,
    PublishRequest,
    RevisionedUpdateRequest,
    RollbackRequest,
)


router = APIRouter()


@router.post("/profiles")
async def create_profile(request: CreateResourceRequest):
    del request
    return unsupported("profile.create")


@router.post("/profiles/{profile_id}/versions")
async def create_profile_version(profile_id: str, request: CreateVersionRequest):
    del profile_id, request
    return unsupported("profile_version.create")


@router.put("/profile-versions/{profile_version_id}")
async def update_profile_version(profile_version_id: str, request: RevisionedUpdateRequest):
    del profile_version_id, request
    return unsupported("profile_version.update")


@router.post("/profile-versions/{profile_version_id}/publish")
async def publish_profile_version(profile_version_id: str, request: PublishRequest):
    del profile_version_id, request
    return unsupported("profile_version.publish")


@router.post("/profile-versions/{profile_version_id}/disable")
async def disable_profile_version(profile_version_id: str, request: PublishRequest):
    del profile_version_id, request
    return unsupported("profile_version.disable")


@router.post("/profiles/{profile_id}/rollback")
async def rollback_profile(profile_id: str, request: RollbackRequest):
    del profile_id, request
    return unsupported("profile.rollback")
