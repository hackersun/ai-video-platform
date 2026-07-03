"""Production card endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.production_card_service import (
    batch_finalize_supporting_characters,
    build_production_card_for_entity,
    build_production_cards_for_novel,
)

router = APIRouter(tags=["定稿卡"])


class BatchFinalizeSupportingRequest(BaseModel):
    min_occurrences: int = Field(2, ge=1, description="出场次数达到该阈值的配角才批量定稿")
    image_model_config_id: str | None = Field(None, description="可选图像模型配置")
    voice_pool: list[str] | None = Field(None, description="可选配角声线池")


@router.get("/novel/{novel_id}")
async def get_novel_production_cards(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await build_production_cards_for_novel(db, user_id, novel_id)


@router.post("/novel/{novel_id}/batch-finalize-supporting")
async def batch_finalize_supporting_cards(
    novel_id: str,
    request: BatchFinalizeSupportingRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await batch_finalize_supporting_characters(
        db,
        user_id,
        novel_id,
        min_occurrences=request.min_occurrences,
        image_model_config_id=request.image_model_config_id,
        voice_pool=request.voice_pool,
    )


@router.get("/entity/{entity_id}")
async def get_entity_production_card(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await build_production_card_for_entity(db, user_id, entity_id)
