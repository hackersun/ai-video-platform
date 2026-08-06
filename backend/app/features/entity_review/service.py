from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.entity_review.repository import to_review_item
from app.features.entity_review.schemas import (
    BulkReviewRequest,
    BulkReviewResponse,
    BulkSkippedItem,
    ReviewSummary,
)
from app.models import StoryEntity
from app.services.entity_review_service import (
    EntityApprovalEvidenceError,
    approve_review_entity,
    entity_has_duplicate_risk,
    get_entity_review_summary,
    reject_review_entity,
)


async def _review_one(
    db: AsyncSession,
    *,
    user_id: str,
    payload: BulkReviewRequest,
    entity_id: str,
) -> tuple[StoryEntity | None, BulkSkippedItem | None]:
    entity = await db.get(StoryEntity, entity_id)
    if entity is None or entity.user_id != user_id or entity.novel_id != payload.novel_id:
        return None, BulkSkippedItem(id=entity_id, reason="实体不存在或不属于当前小说")
    if payload.action == "approve" and await entity_has_duplicate_risk(db, user_id=user_id, entity=entity):
        return None, BulkSkippedItem(id=entity_id, reason="存在高重复风险，不能批量定稿", repair_action="先合并重复实体")
    try:
        updated = (
            await approve_review_entity(db, user_id=user_id, entity_id=entity_id, reason=payload.reason)
            if payload.action == "approve"
            else await reject_review_entity(db, user_id=user_id, entity_id=entity_id, reason=payload.reason)
        )
        return updated, None
    except EntityApprovalEvidenceError as error:
        return None, BulkSkippedItem(id=entity_id, reason=str(error), repair_action="补充原文证据后再定稿")


async def bulk_review_entities(
    db: AsyncSession,
    *,
    user_id: str,
    payload: BulkReviewRequest,
) -> BulkReviewResponse:
    updated = []
    skipped = []
    for entity_id in dict.fromkeys(payload.entity_ids):
        entity, skip = await _review_one(db, user_id=user_id, payload=payload, entity_id=entity_id)
        if entity is not None:
            updated.append(to_review_item(entity))
        if skip is not None:
            skipped.append(skip)
    raw_summary = await get_entity_review_summary(db, user_id=user_id, novel_id=payload.novel_id)
    summary = ReviewSummary(total=sum(raw_summary.get("counts", {}).values()), **raw_summary)
    return BulkReviewResponse(updated=updated, skipped=skipped, summary=summary)
