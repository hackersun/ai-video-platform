"""Production control APIs for final packs, media audit and AI producer."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.production_control import (
    apply_asset_locks_to_workflow,
    audit_and_persist_workflow_media,
    build_ai_producer_assistant,
    build_novel_production_pack,
    build_workflow_quality_report,
)

router = APIRouter(tags=["生产控制"])


class ProductionPackRequest(BaseModel):
    create_missing_assets: bool = Field(True, description="缺少定稿资产时自动创建占位资产")
    persist: bool = Field(True, description="是否保存到小说 extra_data.production_pack")


class WorkflowAssetLocksRequest(BaseModel):
    create_missing_assets: bool = Field(True, description="缺少定稿资产时自动创建占位资产")
    persist: bool = Field(True, description="是否写入 Shot.production_context")


class MediaAuditRequest(BaseModel):
    persist_remote: bool = Field(True, description="是否尝试把远端临时 URL 转存到本地 static")
    dry_run: bool = Field(False, description="只检查不写入")


class QualityCheckRequest(BaseModel):
    persist: bool = Field(True, description="是否把质量报告写回 Shot 和 Workflow")


class ProducerAssistantRequest(BaseModel):
    auto_fix: bool = Field(False, description="是否自动执行安全的补齐动作")
    action_code: Optional[str] = Field(None, description="只执行指定安全动作；不传时按原逻辑执行全部安全补齐")


@router.get("/novels/{novel_id}/production-pack", response_model=Dict[str, Any])
async def get_novel_production_pack(
    novel_id: str,
    create_missing_assets: bool = Query(False, description="GET 默认不创建资产，设为 true 可补占位"),
    persist: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成或读取小说级资产定稿包。"""
    return await build_novel_production_pack(
        db,
        user_id,
        novel_id,
        create_missing_assets=create_missing_assets,
        persist=persist,
    )


@router.post("/novels/{novel_id}/production-pack", response_model=Dict[str, Any])
async def create_novel_production_pack(
    novel_id: str,
    request: ProductionPackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建并保存小说级资产定稿包。"""
    return await build_novel_production_pack(
        db,
        user_id,
        novel_id,
        create_missing_assets=request.create_missing_assets,
        persist=request.persist,
    )


@router.post("/workflow/{workflow_id}/asset-locks", response_model=Dict[str, Any])
async def create_workflow_asset_locks(
    workflow_id: str,
    request: WorkflowAssetLocksRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """把小说定稿包中的资产锁应用到工作流镜头。"""
    return await apply_asset_locks_to_workflow(
        db,
        user_id,
        workflow_id,
        persist=request.persist,
        create_missing_assets=request.create_missing_assets,
    )


@router.post("/workflow/{workflow_id}/media-audit", response_model=Dict[str, Any])
async def create_workflow_media_audit(
    workflow_id: str,
    request: MediaAuditRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """巡检并可选转存工作流媒体历史。"""
    return await audit_and_persist_workflow_media(
        db,
        user_id,
        workflow_id,
        persist_remote=request.persist_remote,
        dry_run=request.dry_run,
    )


@router.post("/workflow/{workflow_id}/quality-check", response_model=Dict[str, Any])
async def create_workflow_quality_check(
    workflow_id: str,
    request: QualityCheckRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """执行工作流生产质量检查。"""
    return await build_workflow_quality_report(
        db,
        user_id,
        workflow_id,
        persist=request.persist,
    )


@router.post("/workflow/{workflow_id}/producer-assistant", response_model=Dict[str, Any])
async def create_producer_assistant(
    workflow_id: str,
    request: ProducerAssistantRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """AI 制片助手：判断缺失项、推荐下一步，并可自动补齐安全项。"""
    return await build_ai_producer_assistant(
        db,
        user_id,
        workflow_id,
        auto_fix=request.auto_fix,
        action_code=request.action_code,
    )
