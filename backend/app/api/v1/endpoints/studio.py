"""统一创作工作台 API。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Workflow
from app.services.studio_actions import create_studio_review_run, list_studio_actions, list_studio_review_runs, run_studio_action
from app.services.studio_mode import policy_from_request
from app.services.studio_snapshot import build_studio_snapshot
from app.services.continuity_review_tasks import list_continuity_review_tasks

router = APIRouter(tags=["创作工作台"])


class StudioActionRequest(BaseModel):
    code: str = Field(..., min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)
    mode: str = Field("production", pattern="^(test|production)$")
    allow_test_bypass: bool = False
    bypass_reason: Optional[str] = None
    source_issue_code: Optional[str] = None


class StudioActionExecuteRequest(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)
    mode: str = Field("production", pattern="^(test|production)$")
    allow_test_bypass: bool = False
    bypass_reason: Optional[str] = None
    source_issue_code: Optional[str] = None


class StudioReviewRequest(BaseModel):
    mode: str = Field("production", pattern="^(test|production)$")
    allow_test_bypass: bool = False
    bypass_reason: Optional[str] = None


@router.get("/workflows/{workflow_id}/continuity-review-tasks", response_model=Dict[str, Any])
async def get_workflow_continuity_review_tasks(
    workflow_id: str,
    status_filter: str = Query("open", alias="status", pattern="^(open|resolved|all)$"),
    sort: str = Query("updated_desc", pattern="^(updated_desc|updated_asc|episode_desc|episode_asc|entity_desc|entity_asc)$"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """读取单个工作流下的连续性复审任务。"""

    workflow_result = await db.execute(select(Workflow.id).where(Workflow.id == workflow_id, Workflow.user_id == user_id))
    if workflow_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    return await list_continuity_review_tasks(
        db,
        user_id,
        workflow_id=workflow_id,
        task_status=status_filter,
        sort=sort,
        limit=limit,
    )


@router.get("/workflows/{workflow_id}/snapshot", response_model=Dict[str, Any])
async def get_workflow_studio_snapshot(
    workflow_id: str,
    mode: str = Query("production", pattern="^(test|production)$"),
    allow_test_bypass: bool = Query(False),
    bypass_reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """读取工作流创作工作台快照。该接口只读，不触发外部模型调用。"""

    return await build_studio_snapshot(
        db,
        user_id,
        workflow_id,
        mode_policy=policy_from_request(
            mode=mode,
            allow_test_bypass=allow_test_bypass,
            bypass_reason=bypass_reason,
        ),
    )


@router.post("/workflows/{workflow_id}/review", response_model=Dict[str, Any])
async def create_workflow_studio_review(
    workflow_id: str,
    request: StudioReviewRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """运行一次规则检查并保存审计记录；不调用外部模型。"""

    return await create_studio_review_run(
        db,
        user_id,
        workflow_id,
        mode=request.mode,
        allow_test_bypass=request.allow_test_bypass,
        bypass_reason=request.bypass_reason,
    )


@router.get("/workflows/{workflow_id}/review-runs", response_model=Dict[str, Any])
async def get_workflow_studio_review_runs(
    workflow_id: str,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """读取工作台检查运行历史。"""

    return await list_studio_review_runs(db, user_id, workflow_id, limit=limit)


@router.get("/workflows/{workflow_id}/actions", response_model=Dict[str, Any])
async def get_workflow_studio_actions(
    workflow_id: str,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """读取工作台最近返修动作和跳过审计。"""

    return await list_studio_actions(db, user_id, workflow_id, limit=limit)


@router.post("/workflows/{workflow_id}/actions/{action_code}/execute", response_model=Dict[str, Any])
async def execute_workflow_studio_action_by_code(
    workflow_id: str,
    action_code: str,
    request: StudioActionExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """兼容计划中的动作执行路径，路径参数优先。"""

    return await run_studio_action(
        db,
        user_id,
        workflow_id,
        code=action_code,
        params=request.params,
        mode=request.mode,
        allow_test_bypass=request.allow_test_bypass,
        bypass_reason=request.bypass_reason,
        source_issue_code=request.source_issue_code,
    )


@router.post("/workflows/{workflow_id}/actions", response_model=Dict[str, Any])
async def execute_workflow_studio_action(
    workflow_id: str,
    request: StudioActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """执行受控返修动作；生产模式下不允许跳过阻断项。"""

    return await run_studio_action(
        db,
        user_id,
        workflow_id,
        code=request.code,
        params=request.params,
        mode=request.mode,
        allow_test_bypass=request.allow_test_bypass,
        bypass_reason=request.bypass_reason,
        source_issue_code=request.source_issue_code,
    )
