"""统一创作工作台 API。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.studio_mode import policy_from_request
from app.services.studio_snapshot import build_studio_snapshot

router = APIRouter(tags=["创作工作台"])


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
