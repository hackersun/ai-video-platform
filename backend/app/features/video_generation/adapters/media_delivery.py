"""Resolve stored media into a provider-consumable URL."""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.private_media.integration import resolve_original_image


async def resolve_provider_image_delivery(
    db: AsyncSession, user_id: str, image_url: Optional[str],
) -> dict[str, Any]:
    delivery = await resolve_original_image(db, user_id, image_url)
    return {
        "provider_image_url": delivery.get("provider_url"),
        "image_url_omitted_reason": delivery.get("omitted_reason"),
        "image_delivery": delivery,
    }
