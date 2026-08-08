"""Prompt Usage Map HTTP routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.model_config.prompt_usage import (
    PromptUsageError,
    create_prompt_usage_assignment_draft,
    get_prompt_usage_map,
    list_prompt_usage_candidates,
    resolve_prompt_usage_stage,
)


router = APIRouter()


class PromptUsageAssignmentRequest(BaseModel):
    prompt_version_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=2, max_length=200)


def _raise_prompt_usage_error(error: PromptUsageError) -> None:
    status_code = 404 if error.code in {"stage_not_found", "template_not_found"} else 422
    raise HTTPException(status_code=status_code, detail=error.message) from error


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
        _raise_prompt_usage_error(error)


@router.get("/prompt-usage-map/stages/{stage_id}/candidates")
async def prompt_usage_candidates(
    stage_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await list_prompt_usage_candidates(
            db, user_id=user_id, stage_id=stage_id,
        )
    except PromptUsageError as error:
        _raise_prompt_usage_error(error)


@router.post("/prompt-usage-map/stages/{stage_id}/assignment-drafts")
async def create_prompt_usage_assignment(
    stage_id: str,
    request: PromptUsageAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await create_prompt_usage_assignment_draft(
            db, user_id=user_id, stage_id=stage_id,
            prompt_version_id=request.prompt_version_id, reason=request.reason,
        )
    except PromptUsageError as error:
        _raise_prompt_usage_error(error)


__all__ = ["router"]
