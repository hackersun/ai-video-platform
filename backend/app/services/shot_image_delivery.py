"""Persist generated shot images and expose them through configured public storage."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.media_persistence import persist_remote_media_url
from app.features.private_media.integration import resolve_process_image


@dataclass(frozen=True)
class ShotImageDelivery:
    local_url: str
    public_url: str
    delivery: dict[str, Any]

    @property
    def storage_url(self) -> str:
        """Stable URL persisted on the shot; provider URLs may expire."""
        return self.local_url


def is_live_ready_shot_image(url: str | None) -> bool:
    """Only provider-backed artifacts can satisfy a live-run first-frame gate."""
    value = str(url or "").strip()
    return bool(value) and "/static/dev/" not in value


def should_use_dev_shot_image_fallback(*, live_run: object | None, model_config_id: str | None) -> bool:
    """Explicit/live provider requests must expose their real error instead of faking success."""
    return live_run is None and not str(model_config_id or "").strip()


def should_refresh_shot_entity_refs(*, live_run: object | None) -> bool:
    """A locked live-run shot must retain the exact references covered by its story lock."""
    return live_run is None


async def persist_shot_image_publicly(
    db: AsyncSession, *, user_id: str, source_url: str, shot_id: str,
) -> ShotImageDelivery:
    local_url = await persist_remote_media_url(
        source_url, media_type="image", subdir="images",
        prefix=f"shot-{shot_id[:8]}", max_bytes=20 * 1024 * 1024,
        optimize_image=True, image_max_dimension=1024, image_quality=76,
    ) or source_url
    delivery = await resolve_process_image(db, user_id, local_url)
    public_url = str(delivery.get("provider_url") or "")
    return ShotImageDelivery(
        local_url=local_url,
        public_url=public_url if delivery.get("image_url_sent") else local_url,
        delivery=delivery,
    )
