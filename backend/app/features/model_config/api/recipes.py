"""Versioned production recipe management routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.api import service
from app.features.model_config.api.errors import raise_http, unsupported
from app.features.model_config.api.schemas import (
    PublishRequest,
    RecipeBindingResolutionResponse,
    PublishResponse,
    RecipeCreateRequest,
    RollbackRequest,
)


router = APIRouter()


@router.get("/recipes")
async def list_recipes(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await service.recipes_page(db, user_id, page, page_size)


@router.post("/recipes")
async def create_recipe(
    request: RecipeCreateRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.create_recipe(
            db, user_id=user_id, recipe_key=request.recipe_key, name=request.name, spec=request.spec,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/recipe-versions/{recipe_version_id}/validate")
async def validate_recipe(
    recipe_version_id: str,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.validate_recipe_version(db, user_id=user_id, recipe_version_id=recipe_version_id)
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.get("/recipes/{recipe_version_id}/binding-resolution", response_model=RecipeBindingResolutionResponse)
async def recipe_binding_resolution(
    recipe_version_id: str,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.recipe_bindings_display(
            db, user_id=user_id, recipe_version_id=recipe_version_id,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/recipe-versions/{recipe_version_id}/publish", response_model=PublishResponse)
async def publish_recipe(
    recipe_version_id: str, request: PublishRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.publish_recipe(
            db, user_id=user_id, recipe_version_id=recipe_version_id,
            expected_revision=request.expected_revision, reason=request.reason,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)


@router.post("/recipe-versions/{recipe_version_id}/disable")
async def disable_recipe(recipe_version_id: str, request: PublishRequest):
    del recipe_version_id, request
    return unsupported("recipe_version.disable")


@router.post("/recipes/{recipe_key}/rollback")
async def rollback_recipe(
    recipe_key: str, request: RollbackRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await service.rollback_recipe(
            db, user_id=user_id, recipe_key=recipe_key, target_version_id=request.target_version_id,
            expected_revision=request.expected_revision, reason=request.reason,
        )
    except service.ManagementOperationError as error:
        return raise_http(error)
