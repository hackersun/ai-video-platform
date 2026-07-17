"""Configured image-provider delivery for a series reference board."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_budget import bind_provider_operation_task
from app.services.minimax_errors import MiniMaxProviderRejected


_REFERENCE_ADAPTER_STAGES = frozenset({
    "provider_call", "response_parse", "local_persistence", "qiniu_upload",
})


class ReferenceAdapterStageError(RuntimeError):
    """Secret-safe boundary for a reference provider or delivery failure."""

    def __init__(
        self, stage: str, *, provider_task_id: str | None = None,
        provider_completed: bool = False,
    ) -> None:
        if stage not in _REFERENCE_ADAPTER_STAGES:
            raise ValueError("unsupported reference adapter stage")
        super().__init__(f"reference adapter failed during {stage}")
        self.stage = stage
        self.provider_task_id = str(provider_task_id).strip() if provider_task_id else None
        self.provider_completed = bool(provider_completed)


class ReferencePreSubmitRejected(RuntimeError):
    """Provider explicitly rejected a request before returning a task or artifact."""

    def __init__(self, _message: str | None = None) -> None:
        super().__init__("reference provider rejected before submission")


def _signed_url_expiry(url: str) -> str | None:
    raw = (parse_qs(urlparse(url).query).get("e") or [None])[0]
    try:
        return datetime.fromtimestamp(int(raw), timezone.utc).isoformat() if raw else None
    except (TypeError, ValueError, OverflowError):
        return None


def parse_public_url_expiry(value: Any) -> datetime | None:
    """Convert persisted ISO evidence to the binding model's datetime boundary."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("public URL expiry must be a non-empty ISO datetime string")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("public URL expiry is not a valid ISO datetime") from error
    if parsed.tzinfo is None:
        raise ValueError("public URL expiry must include a timezone")
    return parsed


async def persist_qiniu_reference(
    db: AsyncSession,
    user_id: str,
    url: str,
    operation_id: str,
) -> dict[str, Any]:
    from app.services.media_delivery import resolve_provider_media_url
    from app.services.media_persistence import persist_remote_media_url

    try:
        local_url = await persist_remote_media_url(
            url, media_type="image", subdir="series-references", prefix=f"reference-{operation_id}",
        )
    except Exception as error:
        raise ReferenceAdapterStageError("local_persistence") from error
    try:
        delivery = await resolve_provider_media_url(db, user_id, local_url, media_type="图")
        public_url = str(delivery.get("provider_url") or "")
        if delivery.get("delivery_method") != "qiniu_object_upload" or not public_url:
            raise ReferenceAdapterStageError("qiniu_upload")
    except ReferenceAdapterStageError:
        raise
    except Exception as error:
        raise ReferenceAdapterStageError("qiniu_upload") from error
    return {
        "public_url": public_url,
        "public_url_expires_at": _signed_url_expiry(public_url),
        "storage_delivery": {
            "delivery_method": delivery["delivery_method"],
            "storage_config_id": delivery.get("storage_config_id"),
            "object_key": delivery.get("object_key"),
            "canonical_local_url": local_url,
        },
    }


class ConfiguredReferenceAdapter:
    """Production adapter; provider access occurs after the committed operation boundary."""

    async def generate(
        self,
        *,
        db: AsyncSession,
        run: SeriesProductionRun,
        prompt: str,
        image_config_id: str,
        operation: LiveCanaryProviderOperation,
    ) -> dict[str, Any]:
        from app.core.api_key_utils import create_image_generation_service, get_user_image_model_config
        from app.services.image_generation_pipeline import call_image_generation_provider
        from app.services.image_provider_response_contract import (
            classify_image_provider_response,
            persist_image_response_evidence,
        )

        try:
            api_key, provider_name, model_id, base_url = await get_user_image_model_config(
                db, run.user_id, config_id=image_config_id,
            )
            service = create_image_generation_service(api_key or "", provider_name or "", base_url)
            result = await call_image_generation_provider(
                service, provider_name=provider_name or "", model_id=model_id or "", prompt=prompt,
                num=1, size="2K", aspect_ratio="3:2", openai_size="1536x1024", minimax_response_format="url",
            )
        except MiniMaxProviderRejected as error:
            if error.provider_task_id or error.artifact_returned:
                raise ReferenceAdapterStageError(
                    "provider_call", provider_task_id=error.provider_task_id,
                    provider_completed=error.artifact_returned,
                ) from error
            raise ReferencePreSubmitRejected() from error
        except Exception as error:
            raise ReferenceAdapterStageError("provider_call") from error
        try:
            classified = classify_image_provider_response(result, provider_name or "")
            task_id = classified["provider_task_id"]
            provider_completed = bool(classified["image_urls"])
            if task_id:
                operation = await bind_provider_operation_task(
                    db, operation, provider_task_id=task_id,
                )
            await persist_image_response_evidence(
                db, run, operation_id=operation.id, evidence=classified["evidence"],
            )
        except Exception as error:
            if isinstance(error, ReferenceAdapterStageError):
                raise
            raise ReferenceAdapterStageError(
                "response_parse",
                provider_task_id=locals().get("task_id"),
                provider_completed=locals().get("provider_completed", False),
            ) from error
        urls = classified["image_urls"]
        try:
            delivery = await persist_qiniu_reference(
                db, run.user_id, urls[0], operation.id,
            ) if urls else {}
        except ReferenceAdapterStageError as error:
            raise ReferenceAdapterStageError(
                error.stage, provider_task_id=task_id,
                provider_completed=provider_completed,
            ) from error
        return {
            "status": classified["status"],
            "public_url": delivery.get("public_url"),
            "public_url_expires_at": delivery.get("public_url_expires_at"),
            "storage_delivery": delivery.get("storage_delivery"),
            "provider_task_id": task_id,
            "actual_cost_rmb": result.get("actual_cost_rmb", result.get("cost_rmb")) if isinstance(result, dict) else None,
            "width": result.get("width") if isinstance(result, dict) else None,
            "height": result.get("height") if isinstance(result, dict) else None,
        }


__all__ = [
    "ConfiguredReferenceAdapter", "ReferenceAdapterStageError", "ReferencePreSubmitRejected",
    "parse_public_url_expiry", "persist_qiniu_reference",
]
