"""Thin HTTP adapter for selected-anchor media reconciliation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

from .errors import SeriesAnchorError
from .media_reconciliation import reconcile_selected_media


router = APIRouter()


@router.post("/series-runs/{run_id}/reconcile-selected")
async def reconcile_selected_series_run_media(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await reconcile_selected_media(db, run_id=run_id, user_id=user_id)
    except SeriesAnchorError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


__all__ = ["router"]
