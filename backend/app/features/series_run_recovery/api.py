"""Series-run recovery HTTP routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.series_anchor_generation.schemas import RecoveryActionRequest

from .application import (
    RecoveryConflict,
    RecoveryNotFound,
    acknowledge_recovery_action,
    get_run_recovery,
)

router = APIRouter()


def _http_error(error: Exception) -> HTTPException:
    status_code = status.HTTP_404_NOT_FOUND if isinstance(error, RecoveryNotFound) else status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail={"code": "series_run_recovery_blocked", "message": str(error)})


@router.get("/series-runs/{run_id}/recovery")
async def get_recovery(
    run_id: str, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await get_run_recovery(db, user_id, run_id)
    except (RecoveryNotFound, RecoveryConflict) as error:
        raise _http_error(error) from error


@router.post("/series-runs/{run_id}/recovery/actions/{action_code}")
async def post_recovery_action(
    run_id: str, action_code: str, request: RecoveryActionRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await acknowledge_recovery_action(
            db, user_id, run_id, action_code=action_code,
            operation_id=request.operation_id, expected_run_version=request.expected_run_version,
        )
    except (RecoveryNotFound, RecoveryConflict) as error:
        raise _http_error(error) from error
