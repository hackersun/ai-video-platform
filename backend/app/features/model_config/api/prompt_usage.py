"""Prompt Usage Map HTTP routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.prompt_usage import (
    PromptUsageError,
    get_prompt_usage_map,
    resolve_prompt_usage_stage,
)


router = APIRouter()


@router.get("/prompt-usage-map")
async def prompt_usage_map(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await get_prompt_usage_map(db, user_id=user_id)


@router.get("/prompt-usage-map/stages/{stage_id}/resolve")
async def resolve_prompt_usage(
    stage_id: str,
    profile_version_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await resolve_prompt_usage_stage(
            db, user_id=user_id, stage_id=stage_id,
            profile_version_id=profile_version_id,
        )
    except PromptUsageError as error:
        status_code = 404 if error.code == "stage_not_found" else 422
        raise HTTPException(status_code=status_code, detail=error.message) from error


__all__ = ["router"]
