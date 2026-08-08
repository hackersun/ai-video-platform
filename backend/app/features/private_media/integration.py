"""Narrow integration facade for legacy media generation callers."""

from __future__ import annotations

import hashlib
import os
from pathlib import PurePosixPath
from typing import Any

from fastapi import HTTPException

from app.features.private_media.domain import is_private_delivery_url, lifecycle_policy, sanitize_provider_url
from app.features.private_media.service import record_provider_inputs_for_urls, register_persisted_media
from app.services.media_delivery import resolve_provider_media_url
from app.services.media_persistence import local_static_path_for_url, persist_remote_media_url


async def resolve_and_register_media(
    db: Any, *, user_id: str, canonical_url: str | None,
    media_kind: str, lifecycle_class: str, media_type: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    local_media = str(canonical_url or "").startswith("/static/")
    object_key = None
    if local_media:
        filename = PurePosixPath(str(canonical_url)).name
        local_path = local_static_path_for_url(str(canonical_url))
        if local_path is not None and local_path.is_file():
            with local_path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()[:16]
        else:
            digest = hashlib.sha256(str(canonical_url).encode("utf-8")).hexdigest()[:16]
        object_key = lifecycle_policy(
            lifecycle_class, user_id=user_id, filename=f"{digest}-{filename}",
        ).object_key
    delivery = await resolve_provider_media_url(
        db, user_id, canonical_url, media_type=media_type, object_key_override=object_key,
    )
    if local_media and object_key and not delivery.get("object_key"):
        delivery = {**delivery, "object_key": object_key}
    if local_media and os.getenv("APP_ENV", "local").lower() in {"staging", "production"}:
        if not is_private_delivery_url(str(delivery.get("provider_url") or "")):
            return {
                **delivery, "provider_url": None, "image_url_sent": False,
                "omitted_reason": "对象存储未启用私有短时下载，正式环境拒绝发送媒体",
            }
    if local_media:
        media = await register_persisted_media(
            db, user_id=user_id, canonical_url=str(canonical_url), delivery=delivery,
            media_kind=media_kind, lifecycle_class=lifecycle_class, project_id=project_id,
        )
        if media is not None:
            delivery = {**delivery, "media_object_id": media.id}
    return delivery


async def resolve_original_image(
    db: Any, user_id: str, canonical_url: str | None, *, project_id: str | None = None,
) -> dict[str, Any]:
    return await resolve_and_register_media(
        db, user_id=user_id, canonical_url=canonical_url, media_kind="image",
        lifecycle_class="original", media_type="图", project_id=project_id,
    )


async def resolve_process_image(db: Any, user_id: str, canonical_url: str | None) -> dict[str, Any]:
    return await resolve_and_register_media(
        db, user_id=user_id, canonical_url=canonical_url, media_kind="image",
        lifecycle_class="process", media_type="image",
    )


async def record_image_reference_evidence(
    db: Any, user_id: str | None, job_id: str | None, output: dict,
    reference_images: list[str] | tuple[str, ...], *, provider_task_id: str | None,
) -> None:
    if db is None or not user_id or not reference_images:
        return
    submission_id = f"{job_id or 'image'}:{provider_task_id or output.get('execution_snapshot_id') or 'sync'}"
    await record_provider_inputs_for_urls(
        db, user_id=user_id, delivered_urls=list(reference_images),
        provider_task_id=provider_task_id, submission_id=submission_id,
        purpose="图像模型参考图",
    )


async def call_legacy_image_provider(
    service: Any, *, provider: str, model_id: str, prompt: str,
    num: int, size: str, aspect_ratio: str, openai_size: str,
    minimax_response_format: str, reference_images: list[str] | tuple[str, ...],
) -> dict:
    if provider in ("volcano", "volcano_agent_plan"):
        return await service.generate_image(
            prompt=prompt, model=model_id, size=size, num=num, watermark=False,
            **({"image": list(reference_images)} if reference_images else {}),
        )
    if provider == "minimax":
        return await service.generate_image(
            prompt=prompt, model=model_id, aspect_ratio=aspect_ratio,
            n=num, response_format=minimax_response_format,
        )
    if provider == "openai":
        return await service.generate_image(
            prompt=prompt, model=model_id, size=openai_size, n=num, save_local=False,
        )
    raise HTTPException(status_code=400, detail=f"不支持的图像模型服务商: {provider}")


async def persist_private_video_output(db: Any, job: Any, url: str, *, cover: bool) -> tuple[str, dict]:
    extra = dict(job.extra_data) if isinstance(job.extra_data, dict) else {}
    persisted = await persist_remote_media_url(
        url, media_type="image" if cover else "video", subdir="images" if cover else "videos",
        prefix=f"video-cover-{job.id[:8]}" if cover else f"video-{job.id[:8]}",
        max_bytes=20 * 1024 * 1024 if cover else 300 * 1024 * 1024,
    ) or url
    if persisted != url:
        extra["original_cover_url" if cover else "original_video_url"] = sanitize_provider_url(url).canonical_url
        if not cover:
            extra["video_persisted"] = True
    delivery = await resolve_and_register_media(
        db, user_id=job.user_id, project_id=job.project_id, canonical_url=persisted,
        media_kind="image" if cover else "video",
        lifecycle_class="process" if cover else "final",
        media_type="image" if cover else "video",
    )
    key = "cover_delivery" if cover else "video_delivery"
    extra[key] = {name: delivery.get(name) for name in (
        "delivery_method", "storage_config_id", "storage_config_name",
        "public_base_url", "object_key", "omitted_reason",
    ) if delivery.get(name) is not None}
    if delivery.get("provider_url") and delivery.get("provider_url") != persisted:
        extra["cover_public_delivery" if cover else "video_public_delivery"] = True
    if delivery.get("media_object_id"):
        extra["cover_media_object_id" if cover else "video_media_object_id"] = delivery["media_object_id"]
    extra[key]["canonical_local_url"] = persisted
    return persisted, extra
