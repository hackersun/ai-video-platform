"""Focused HTTP transport for Story Lock asset repair."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.series_production_run import SeriesProductionRun

from .application.asset_repair import StoryAssetRepairBlocked, repair_story_assets


router = APIRouter()


@router.post("/series-runs/{run_id}/story-assets/repair")
async def post_story_asset_repair(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run = await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.id == run_id,
        SeriesProductionRun.user_id == user_id,
    ))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="整书生产运行不存在")
    try:
        return await repair_story_assets(db, run)
    except StoryAssetRepairBlocked as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "story_asset_repair_blocked", "message": str(error),
        }) from error


__all__ = ["router"]
