"""统一创作工作台返修动作执行和审计。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models import StudioRepairAction, StudioReviewRun, Workflow
from app.services.production_control import (
    apply_asset_locks_to_workflow,
    audit_and_persist_workflow_media,
    build_workflow_quality_report,
    refresh_workflow_production_contracts,
)
from app.services.studio_mode import StudioModePolicy, apply_mode_policy
from app.services.studio_snapshot import build_studio_snapshot


ACTION_REGISTRY: Dict[str, Dict[str, str]] = {
    "apply_asset_locks": {"label": "应用资产锁", "risk": "safe"},
    "refresh_contracts": {"label": "刷新生产合约", "risk": "safe"},
    "quality_check": {"label": "运行质量检查", "risk": "safe"},
    "media_audit": {"label": "审计媒体文件", "risk": "safe"},
    "skip_issue": {"label": "测试模式跳过", "risk": "confirm"},
}

RESUME_ACTION_BY_STAGE = {
    "assets": "apply_asset_locks",
    "review": "quality_check",
    "final": "quality_check",
}


async def resume_studio_orchestration(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    task_id: str,
) -> Dict[str, Any]:
    workflow = await _load_workflow(db, user_id, workflow_id)
    metadata = dict(workflow.metadata_ or {})
    key = "studio_orchestration" if isinstance(metadata.get("studio_orchestration"), dict) else "episode_preview_orchestration"
    orchestration = dict(metadata.get(key) or {})
    if not orchestration or str(orchestration.get("task_id")) != task_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="持久化编排任务不存在")
    if orchestration.get("status") != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该编排任务当前不需要恢复")

    failed_stage = str(orchestration.get("failed_stage") or "draft")
    action_code = RESUME_ACTION_BY_STAGE.get(failed_stage)
    action_result = None
    if action_code:
        action_result = await run_studio_action(
            db,
            user_id,
            workflow_id,
            code=action_code,
            params={"resumed_from_task_id": task_id},
        )
        orchestration["status"] = "resumed"
    else:
        orchestration["status"] = "handoff_ready"

    handoff_href = None
    if failed_stage == "draft" and not action_code:
        handoff_href = "/producer?" + urlencode({
            "workflow_id": workflow.id,
            "novel_id": workflow.novel_id or "",
            "chapter_id": workflow.chapter_id or "",
            "resume_task_id": task_id,
        })

    safe_next = {
        "code": action_code or ("open_producer" if failed_stage == "draft" else f"resume_{failed_stage}"),
        "label": "继续失败阶段" if action_code else "打开安全恢复入口",
        "stage": failed_stage,
        "safe": True,
        "href": handoff_href,
    }
    orchestration["safe_next_action"] = safe_next
    orchestration["last_resume_at"] = utc_now().isoformat()
    metadata[key] = orchestration
    workflow.metadata_ = metadata
    flag_modified(workflow, "metadata_")
    await db.commit()
    return {
        "workflow_id": workflow_id,
        "task_id": task_id,
        "status": orchestration["status"],
        "resumed_stage": failed_stage,
        "completed_stages": orchestration.get("completed_stages") or [],
        "safe_next_action": safe_next,
        "action_result": action_result,
    }


async def _load_workflow(db: AsyncSession, user_id: str, workflow_id: str) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return workflow


def _action_payload(action: StudioRepairAction) -> Dict[str, Any]:
    return {
        "id": action.id,
        "workflow_id": action.workflow_id,
        "code": action.code,
        "label": action.label,
        "status": action.status,
        "risk": action.risk,
        "source_issue_code": action.source_issue_code,
        "target_type": action.target_type,
        "target_id": action.target_id,
        "params": action.params or {},
        "result": action.result or {},
        "error_message": action.error_message,
        "mode": action.mode,
        "allow_test_bypass": bool(action.allow_test_bypass),
        "bypass_reason": action.bypass_reason,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
    }


def _review_payload(run: StudioReviewRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "mode": run.mode,
        "status": run.status,
        "summary": run.summary or {},
        "issues": run.issues or [],
        "actions": run.actions or [],
        "bypass_audit": run.bypass_audit,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


async def list_studio_actions(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    limit: int = 30,
) -> Dict[str, Any]:
    await _load_workflow(db, user_id, workflow_id)
    result = await db.execute(
        select(StudioRepairAction)
        .where(StudioRepairAction.user_id == user_id, StudioRepairAction.workflow_id == workflow_id)
        .order_by(desc(StudioRepairAction.created_at))
        .limit(limit)
    )
    items = [_action_payload(action) for action in result.scalars().all()]
    return {"workflow_id": workflow_id, "items": items, "count": len(items)}


async def list_studio_review_runs(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    limit: int = 30,
) -> Dict[str, Any]:
    await _load_workflow(db, user_id, workflow_id)
    result = await db.execute(
        select(StudioReviewRun)
        .where(StudioReviewRun.user_id == user_id, StudioReviewRun.workflow_id == workflow_id)
        .order_by(desc(StudioReviewRun.created_at))
        .limit(limit)
    )
    items = [_review_payload(run) for run in result.scalars().all()]
    return {"workflow_id": workflow_id, "items": items, "count": len(items)}


def _unsupported_action(code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"不支持的工作台修复动作：{code}",
    )


async def _record_action(
    db: AsyncSession,
    *,
    user_id: str,
    workflow_id: str,
    code: str,
    status_value: str,
    result: Dict[str, Any],
    mode: str = "production",
    allow_test_bypass: bool = False,
    bypass_reason: Optional[str] = None,
    source_issue_code: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> StudioRepairAction:
    config = ACTION_REGISTRY[code]
    action = StudioRepairAction(
        id=str(uuid4()),
        user_id=user_id,
        workflow_id=workflow_id,
        code=code,
        label=config["label"],
        status=status_value,
        risk=config["risk"],
        source_issue_code=source_issue_code,
        params=params or {},
        result=result,
        error_message=error_message,
        mode=mode,
        allow_test_bypass=allow_test_bypass,
        bypass_reason=bypass_reason,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


async def run_studio_action(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    code: str,
    params: Optional[Dict[str, Any]] = None,
    mode: str = "production",
    allow_test_bypass: bool = False,
    bypass_reason: Optional[str] = None,
    source_issue_code: Optional[str] = None,
) -> Dict[str, Any]:
    if code not in ACTION_REGISTRY:
        raise _unsupported_action(code)

    await _load_workflow(db, user_id, workflow_id)
    normalized_mode = "test" if mode == "test" else "production"

    if code == "apply_asset_locks":
        result = await apply_asset_locks_to_workflow(
            db,
            user_id,
            workflow_id,
            persist=True,
            create_missing_assets=True,
        )
        audit = await _record_action(
            db,
            user_id=user_id,
            workflow_id=workflow_id,
            code=code,
            status_value="succeeded",
            result={
                "applied_shot_count": len(result.get("applied_shots") or []),
                "production_pack_summary": (result.get("production_pack") or {}).get("summary") or {},
            },
            mode=normalized_mode,
            params=params,
        )
        return _action_payload(audit)

    if code == "skip_issue":
        if normalized_mode != "test":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="生产出片模式不能跳过阻断项，请按修复入口补齐后再继续。",
            )
        issue_code = source_issue_code or str((params or {}).get("source_issue_code") or "")
        policy_result = apply_mode_policy(
            [{"code": issue_code or "manual_bypass", "severity": "blocking", "message": "测试模式临时跳过"}],
            StudioModePolicy(
                mode=normalized_mode,
                allow_test_bypass=allow_test_bypass,
                bypass_reason=bypass_reason,
            ),
        )
        if policy_result["blocking_issue_count"]:
            first_issue = policy_result["issues"][0]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=first_issue.get("bypass_error") or "测试模式跳过需要填写至少 8 个字符的原因",
            )
        audit = await _record_action(
            db,
            user_id=user_id,
            workflow_id=workflow_id,
            code=code,
            status_value="skipped",
            source_issue_code=issue_code,
            result={"bypass_audit": policy_result["bypass_audit"]},
            mode=normalized_mode,
            allow_test_bypass=allow_test_bypass,
            bypass_reason=bypass_reason,
            params=params,
        )
        return _action_payload(audit)

    if code == "quality_check":
        action_params = params or {}
        result = await build_workflow_quality_report(
            db,
            user_id,
            workflow_id,
            persist=bool(action_params.get("persist", True)),
        )
        audit = await _record_action(
            db,
            user_id=user_id,
            workflow_id=workflow_id,
            code=code,
            status_value="succeeded",
            result={
                "summary": result.get("summary") or {},
                "item_count": len(result.get("items") or []),
                "blocking_issue_count": len(result.get("blocking_issues") or []),
                "warning_count": len(result.get("warnings") or []),
                "recommendations": result.get("recommendations") or [],
            },
            mode=normalized_mode,
            params=params,
        )
        return _action_payload(audit)

    if code == "media_audit":
        action_params = params or {}
        result = await audit_and_persist_workflow_media(
            db,
            user_id,
            workflow_id,
            persist_remote=bool(action_params.get("persist_remote", True)),
            dry_run=bool(action_params.get("dry_run", False)),
        )
        audit = await _record_action(
            db,
            user_id=user_id,
            workflow_id=workflow_id,
            code=code,
            status_value="succeeded" if not result.get("blocking_issues") else "failed",
            result={
                "summary": result.get("summary") or {},
                "item_count": len(result.get("items") or []),
                "blocking_issues": result.get("blocking_issues") or [],
                "recommendations": result.get("recommendations") or [],
            },
            mode=normalized_mode,
            params=params,
            error_message="媒体巡检发现缺失文件" if result.get("blocking_issues") else None,
        )
        return _action_payload(audit)

    if code == "refresh_contracts":
        action_params = params or {}
        result = await refresh_workflow_production_contracts(
            db,
            user_id,
            workflow_id,
            shot_ids=action_params.get("shot_ids"),
            force=bool(action_params.get("force", False)),
            persist=bool(action_params.get("persist", True)),
        )
        audit = await _record_action(
            db,
            user_id=user_id,
            workflow_id=workflow_id,
            code=code,
            status_value="succeeded",
            result={
                "refreshed_count": result.get("refreshed_count") or 0,
                "skipped_count": result.get("skipped_count") or 0,
                "refreshed_shot_ids": [
                    item.get("shot_id")
                    for item in (result.get("refreshed_shots") or [])
                    if item.get("shot_id")
                ],
            },
            mode=normalized_mode,
            params=params,
        )
        return _action_payload(audit)

    raise _unsupported_action(code)


async def create_studio_review_run(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    mode: str = "production",
    allow_test_bypass: bool = False,
    bypass_reason: Optional[str] = None,
) -> Dict[str, Any]:
    snapshot = await build_studio_snapshot(
        db,
        user_id,
        workflow_id,
        mode_policy=StudioModePolicy(
            mode=mode,
            allow_test_bypass=allow_test_bypass,
            bypass_reason=bypass_reason,
        ),
    )
    mode_policy = snapshot.get("mode_policy") or {}
    blocking_count = int(mode_policy.get("blocking_issue_count") or 0)
    confirmable_count = int(mode_policy.get("confirmable_issue_count") or 0)
    bypassed_count = int(mode_policy.get("bypassed_issue_count") or 0)
    if blocking_count:
        status_value = "blocked"
    elif confirmable_count or bypassed_count:
        status_value = "confirmable"
    else:
        status_value = "ready"

    summary = {
        "ready": bool(mode_policy.get("ready")),
        "issue_count": len(snapshot.get("issues") or []),
        "action_count": len(snapshot.get("actions") or []),
        "blocking_issue_count": blocking_count,
        "warning_issue_count": int(mode_policy.get("warning_issue_count") or 0),
        "confirmable_issue_count": confirmable_count,
        "bypassed_issue_count": bypassed_count,
    }
    run = StudioReviewRun(
        id=str(uuid4()),
        user_id=user_id,
        workflow_id=workflow_id,
        mode=str(mode_policy.get("mode") or "production"),
        status=status_value,
        summary=summary,
        issues=snapshot.get("issues") or [],
        actions=snapshot.get("actions") or [],
        bypass_audit=mode_policy.get("bypass_audit"),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return _review_payload(run)
