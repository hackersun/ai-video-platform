from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.entity_review.repository import list_review_entities
from app.features.entity_review.schemas import (
    BulkReviewRequest,
    BulkReviewResponse,
    PagedReviewEntities,
    ReviewSort,
    ReviewStatus,
    ReanalysisRequest,
    ReanalysisResponse,
    RebuildCandidatesRequest,
    RebuildCandidatesResponse,
)
from app.features.entity_review.service import (
    ProviderModelRequiredError,
    bulk_review_entities,
    reanalyze_entity,
    rebuild_candidates,
)


router = APIRouter(prefix="/entity-review")


async def _run_ai_action(action):
    try:
        return await action
    except ProviderModelRequiredError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/entities/{entity_id}/reanalyze", response_model=ReanalysisResponse)
async def reanalyze(
    entity_id: str, payload: ReanalysisRequest, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ReanalysisResponse:
    return await _run_ai_action(reanalyze_entity(db, user_id=user_id, entity_id=entity_id, payload=payload))


@router.post("/novels/{novel_id}/rebuild-candidates", response_model=RebuildCandidatesResponse)
async def rebuild(
    novel_id: str, payload: RebuildCandidatesRequest, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> RebuildCandidatesResponse:
    return await _run_ai_action(rebuild_candidates(db, user_id=user_id, novel_id=novel_id, payload=payload))


@router.post("/bulk-review", response_model=BulkReviewResponse)
async def bulk_review(
    payload: BulkReviewRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> BulkReviewResponse:
    return await bulk_review_entities(db, user_id=user_id, payload=payload)


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
