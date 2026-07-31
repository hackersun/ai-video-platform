"""Recover a generated reference image without another model submission."""

from __future__ import annotations

from typing import Any

from app.services.media_delivery import resolve_provider_media_url
from app.services.media_persistence import STATIC_ROOT
from app.services.series_reference_provider import _signed_url_expiry


class PersistedReferenceArtifactAdapter:
    """Republish the exact local artifact associated with a held operation."""

    async def generate(self, *, db, run, prompt, image_config_id, operation) -> dict[str, Any]:
        folder = STATIC_ROOT / "generated" / "series-references"
        candidates = sorted(folder.glob(f"reference-{operation.id}-*"))
        if len(candidates) != 1 or not candidates[0].is_file():
            raise RuntimeError("exact persisted reference artifact was not found")
        local_url = f"/static/generated/series-references/{candidates[0].name}"
        delivery = await resolve_provider_media_url(
            db, run.user_id, local_url, media_type="图",
        )
        public_url = str(delivery.get("provider_url") or "")
        if delivery.get("delivery_method") != "qiniu_object_upload" or not public_url:
            raise RuntimeError("persisted reference artifact could not be republished")
        return {
            "status": "completed",
            "public_url": public_url,
            "public_url_expires_at": _signed_url_expiry(public_url),
            "provider_task_id": f"sync-recovered:{operation.id}",
            "actual_cost_rmb": None,
            "storage_delivery": {
                "delivery_method": delivery["delivery_method"],
                "storage_config_id": delivery.get("storage_config_id"),
                "object_key": delivery.get("object_key"),
                "canonical_local_url": local_url,
            },
        }


__all__ = ["PersistedReferenceArtifactAdapter"]
