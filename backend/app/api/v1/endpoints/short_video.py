"""Short-video production APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Shot
from app.services.short_video_production import (
    build_short_episode_plan,
    build_shot_production_contract,
    build_workflow_short_video_readiness,
    persist_contract_to_shot,
    refresh_workflow_shot_contracts,
)

router = APIRouter(tags=["短视频生产"])


class ShortEpisodePlanRequest(BaseModel):
    novel_id: str = Field(..., min_length=1, description="小说ID")
    chapter_id: Optional[str] = Field(None, description="章节ID")
    target_duration_seconds: int = Field(60, ge=30, le=90, description="目标短视频时长")
    aspect_ratio: str = Field("9:16", description="画幅比例")
    style: Optional[str] = Field(None, description="出片风格")


class ShotContractResponse(BaseModel):
    shot_id: str
    persisted: bool
    contract: Dict[str, Any]


class WorkflowRefreshContractsRequest(BaseModel):
    shot_ids: Optional[List[str]] = Field(None, description="指定刷新镜头ID；不传则刷新工作流分镜下全部镜头")


@router.post("/episode-plan", response_model=Dict[str, Any])
async def create_short_episode_plan(
    request: ShortEpisodePlanRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成短剧式单集叙事规划。"""
    return await build_short_episode_plan(
        db,
        user_id,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        target_duration_seconds=request.target_duration_seconds,
        aspect_ratio=request.aspect_ratio,
        style=request.style,
    )


@router.post("/shots/{shot_id}/production-contract", response_model=ShotContractResponse)
async def create_shot_production_contract(
    shot_id: str,
    persist: bool = Query(True, description="是否写入 Shot.extra_data.production_context.production_contract"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成并可选锁定单个镜头的 Production Contract。"""
    contract = await build_shot_production_contract(db, user_id, shot_id)
    if persist:
        result = await db.execute(select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id)))
        shot = result.scalar_one_or_none()
        if shot:
            persist_contract_to_shot(shot, contract)
            await db.commit()
    return ShotContractResponse(shot_id=shot_id, persisted=persist, contract=contract)


@router.get("/workflow/{workflow_id}/readiness", response_model=Dict[str, Any])
async def get_workflow_short_video_readiness(
    workflow_id: str,
    target_duration_seconds: int = Query(60, ge=30, le=90),
    aspect_ratio: str = Query("9:16"),
    style_asset_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取工作流短视频出片模式就绪度。"""
    return await build_workflow_short_video_readiness(
        db,
        user_id,
        workflow_id,
        target_duration_seconds=target_duration_seconds,
        aspect_ratio=aspect_ratio,
        style_asset_id=style_asset_id,
    )


@router.post("/workflow/{workflow_id}/refresh-contracts", response_model=Dict[str, Any])
async def refresh_workflow_short_video_contracts(
    workflow_id: str,
    request: WorkflowRefreshContractsRequest = WorkflowRefreshContractsRequest(),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """刷新工作流下镜头的短视频生产合约。"""
    result = await refresh_workflow_shot_contracts(
        db,
        user_id,
        workflow_id,
        shot_ids=request.shot_ids,
    )
    await db.commit()
    return result
