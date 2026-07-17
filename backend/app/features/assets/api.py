from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.assets.application import deactivate_asset_entity, list_asset_entity_options
from app.features.assets.schemas import (
    AssetEntityOption,
    DeactivateAssetEntityRequest,
    DeactivateAssetEntityResponse,
)

router = APIRouter(prefix="/asset-maintenance")


@router.get("/entity-options", response_model=list[AssetEntityOption])
async def get_asset_entity_options(
    novel_id: Optional[str] = Query(None),
    chapter_id: Optional[str] = Query(None),
    script_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await list_asset_entity_options(
        db,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        script_id=script_id,
        entity_type=entity_type,
        limit=limit,
    )


@router.post(
    "/entities/{entity_id}/deactivate",
    response_model=DeactivateAssetEntityResponse,
)
async def deactivate_production_entity(
    entity_id: str,
    request: DeactivateAssetEntityRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await deactivate_asset_entity(
            db,
            user_id=user_id,
            entity_id=entity_id,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
