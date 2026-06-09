"""统一创作工作台返修动作执行和审计。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StudioRepairAction, Workflow
from app.services.production_control import apply_asset_locks_to_workflow
from app.services.studio_mode import StudioModePolicy, apply_mode_policy


ACTION_REGISTRY: Dict[str, Dict[str, str]] = {
    "apply_asset_locks": {"label": "应用资产锁", "risk": "safe"},
    "skip_issue": {"label": "测试模式跳过", "risk": "confirm"},
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

    raise _unsupported_action(code)
