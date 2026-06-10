"""Prompt 技能配置 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.prompt_skill_service import (
    activate_prompt_skill,
    clone_prompt_skill,
    create_prompt_skill,
    delete_prompt_skill as delete_prompt_skill_record,
    list_prompt_skills,
    optimize_prompt_skill_content,
    preview_prompt_skills,
    update_prompt_skill,
)

router = APIRouter(tags=["Prompt 技能"])


class PromptSkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    task: str = Field(..., min_length=1, max_length=80)
    stage: Optional[str] = Field(None, max_length=80)
    content: str = Field(..., min_length=1)
    variables: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(100, ge=0, le=10000)
    inject_position: str = Field("before_constraints", max_length=40)
    is_active: bool = True
    tags: List[str] = Field(default_factory=list)


class PromptSkillUpdateRequest(PromptSkillCreateRequest):
    pass


class PromptSkillPreviewRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=80)
    skill_ids: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    draft_name: Optional[str] = Field(None, max_length=120)
    draft_content: Optional[str] = None
    draft_stage: Optional[str] = Field(None, max_length=80)


class PromptSkillOptimizeRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=80)
    name: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    mode: str = Field("polish", pattern="^(polish|tighten|productionize)$")
    model_config_id: Optional[str] = None


@router.get("", response_model=Dict[str, Any])
async def get_prompt_skills(
    task: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await list_prompt_skills(db, user_id, task=task, stage=stage, active=active)


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def post_prompt_skill(
    request: PromptSkillCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await create_prompt_skill(db, user_id, request.model_dump())


@router.post("/optimize", response_model=Dict[str, Any])
async def optimize_prompt_skill_endpoint(
    request: PromptSkillOptimizeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await optimize_prompt_skill_content(db, user_id, request.model_dump())


@router.put("/{skill_id}", response_model=Dict[str, Any])
async def put_prompt_skill(
    skill_id: str,
    request: PromptSkillUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await update_prompt_skill(db, user_id, skill_id, request.model_dump())


@router.delete("/{skill_id}", response_model=Dict[str, Any])
async def delete_prompt_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await delete_prompt_skill_record(db, user_id, skill_id)


@router.post("/{skill_id}/clone", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def clone_prompt_skill_endpoint(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await clone_prompt_skill(db, user_id, skill_id)


@router.post("/{skill_id}/activate", response_model=Dict[str, Any])
async def activate_prompt_skill_endpoint(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await activate_prompt_skill(db, user_id, skill_id)


@router.post("/preview", response_model=Dict[str, Any])
async def preview_prompt_skill_endpoint(
    request: PromptSkillPreviewRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await preview_prompt_skills(
        db,
        user_id,
        task=request.task,
        skill_ids=request.skill_ids,
        context=request.context,
        draft_name=request.draft_name,
        draft_content=request.draft_content,
        draft_stage=request.draft_stage,
    )
