from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.entity_review.repository import list_review_entities
from app.features.entity_review.schemas import PagedReviewEntities, ReviewSort, ReviewStatus


router = APIRouter(prefix="/entity-review")


@router.get("/novels/{novel_id}/entities", response_model=PagedReviewEntities)
async def get_novel_review_entities(
    novel_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    entity_type: str | None = Query(None, pattern="^(character|scene|prop|event)$"),
    review_status: ReviewStatus | None = None,
    query: str | None = Query(None, max_length=200),
    sort: ReviewSort = "updated_desc",
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> PagedReviewEntities:
    return await list_review_entities(
        db,
        user_id=user_id,
        novel_id=novel_id,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        review_status=review_status,
        query=query,
        sort=sort,
    )
