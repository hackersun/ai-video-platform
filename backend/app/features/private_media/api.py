"""Customer-scoped private media endpoints."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.features.private_media.service import create_deletion_request, get_playback_delivery


router = APIRouter(prefix="/media-objects", tags=["私有媒体"])


class DeletionRequestBody(BaseModel):
    idempotency_key: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=2, max_length=300)


@router.get("/{media_object_id}/playback-url")
async def playback_url(
    media_object_id: str, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    delivery = await get_playback_delivery(
        db, user_id=user_id, media_object_id=media_object_id,
    )
    return {
        "media_object_id": media_object_id,
        "url": delivery.url,
        "expires_at": delivery.expires_at,
    }


@router.post("/{media_object_id}/deletion-requests", status_code=status.HTTP_202_ACCEPTED)
async def request_deletion(
    media_object_id: str, body: DeletionRequestBody,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    request = await create_deletion_request(
        db, user_id=user_id, media_object_id=media_object_id,
        idempotency_key=body.idempotency_key, reason=body.reason,
    )
    return {"id": request.id, "media_object_id": request.media_object_id, "status": request.status}
