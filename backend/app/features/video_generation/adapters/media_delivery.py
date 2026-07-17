"""Resolve stored media into a provider-consumable URL."""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.media_delivery import resolve_provider_media_url


async def resolve_provider_image_delivery(
    db: AsyncSession, user_id: str, image_url: Optional[str],
) -> dict[str, Any]:
    delivery = await resolve_provider_media_url(db, user_id, image_url, media_type="图")
    return {
        "provider_image_url": delivery.get("provider_url"),
        "image_url_omitted_reason": delivery.get("omitted_reason"),
        "image_delivery": delivery,
    }
