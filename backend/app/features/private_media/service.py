"""Authorized media playback, provider evidence and deletion lifecycle."""

from __future__ import annotations

import hashlib
import inspect
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Awaitable, Callable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.private_media.domain import is_private_delivery_url, lifecycle_policy, sanitize_provider_url
from app.models.private_media import (
    MediaDeletionReceipt,
    MediaDeletionRequest,
    MediaObject,
    ProviderMediaInput,
)
from app.services.media_delivery import refresh_existing_qiniu_media_url
from app.services.media_persistence import local_static_path_for_url


@dataclass(frozen=True)
class PlaybackDelivery:
    url: str
    expires_at: datetime | None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def get_owned_media(db: AsyncSession, *, user_id: str, media_object_id: str) -> MediaObject:
    media = await db.scalar(select(MediaObject).where(
        MediaObject.id == media_object_id,
        MediaObject.user_id == user_id,
        MediaObject.status == "active",
    ))
    if media is None:
        raise HTTPException(status_code=404, detail="媒体不存在或你无权访问")
    return media


async def get_playback_delivery(
    db: AsyncSession, *, user_id: str, media_object_id: str,
) -> PlaybackDelivery:
    media = await get_owned_media(db, user_id=user_id, media_object_id=media_object_id)
    refreshed = await refresh_existing_qiniu_media_url(
        db, user_id, media.canonical_url, storage_config_id=media.storage_config_id,
        object_key=media.object_key,
    )
    url = str(refreshed.get("provider_url") or "").strip()
    if not url:
        raise HTTPException(status_code=409, detail="媒体暂时无法播放，请检查对象存储配置后重试")
    if not is_private_delivery_url(url):
        raise HTTPException(status_code=409, detail="对象存储未启用私有短时下载，无法安全播放该媒体")
    sanitized = sanitize_provider_url(url)
    return PlaybackDelivery(url=url, expires_at=sanitized.expires_at)


async def register_media_object(
    db: AsyncSession, *, user_id: str, media_kind: str, lifecycle_class: str,
    canonical_url: str, storage_provider: str, object_key: str,
    sha256: str, size_bytes: int, content_type: str,
    project_id: str | None = None, storage_config_id: str | None = None,
) -> MediaObject:
    policy = lifecycle_policy(
        lifecycle_class, user_id=user_id,
        filename=PurePosixPath(object_key).name,
    )
    expected_prefix = policy.object_key.rsplit("/", 1)[0] + "/"
    if not object_key.startswith(expected_prefix):
        raise HTTPException(status_code=409, detail="媒体对象键不属于当前用户和生命周期的私有前缀")
    existing = await db.scalar(select(MediaObject).where(
        MediaObject.storage_provider == storage_provider,
        MediaObject.object_key == object_key,
    ))
    if existing is not None:
        if existing.user_id != user_id:
            raise HTTPException(status_code=409, detail="媒体存储键已被其他用户占用")
        if existing.sha256 != sha256 or existing.size_bytes != size_bytes:
            raise HTTPException(status_code=409, detail="媒体对象键已存在但内容校验不一致")
        return existing
    media = MediaObject(
        id=str(uuid4()), user_id=user_id, project_id=project_id,
        media_kind=media_kind, lifecycle_class=lifecycle_class,
        storage_provider=storage_provider, storage_config_id=storage_config_id,
        object_key=object_key or policy.object_key, canonical_url=canonical_url,
        sha256=sha256, size_bytes=size_bytes, content_type=content_type,
        retention_until=utc_now() + timedelta(days=policy.retention_days),
    )
    db.add(media)
    await db.flush()
    return media


async def record_provider_input(
    db: AsyncSession, *, user_id: str, media_object_id: str,
    provider_task_id: str | None, submission_id: str, purpose: str, input_order: int,
    delivered_url: str, delivery_method: str,
) -> ProviderMediaInput:
    media = await get_owned_media(db, user_id=user_id, media_object_id=media_object_id)
    existing = await db.scalar(select(ProviderMediaInput).where(
        ProviderMediaInput.media_object_id == media.id,
        ProviderMediaInput.submission_id == submission_id,
        ProviderMediaInput.purpose == purpose,
        ProviderMediaInput.input_order == input_order,
    ))
    if existing is not None:
        return existing
    sanitized = sanitize_provider_url(delivered_url)
    row = ProviderMediaInput(
        id=str(uuid4()), media_object_id=media.id, user_id=user_id,
        project_id=media.project_id, submission_id=submission_id,
        provider_task_id=provider_task_id,
        purpose=purpose, input_order=input_order, delivery_method=delivery_method,
        canonical_url=sanitized.canonical_url,
        url_fingerprint=sanitized.url_fingerprint, expires_at=sanitized.expires_at,
    )
    db.add(row)
    await db.flush()
    return row


async def record_provider_inputs_for_urls(
    db: AsyncSession, *, user_id: str, delivered_urls: list[str],
    provider_task_id: str | None, submission_id: str, purpose: str,
) -> list[ProviderMediaInput]:
    rows: list[ProviderMediaInput] = []
    for index, delivered_url in enumerate(delivered_urls):
        fingerprint = sanitize_provider_url(delivered_url).url_fingerprint
        media = await db.scalar(select(MediaObject).where(
            MediaObject.user_id == user_id,
            MediaObject.delivery_fingerprint == fingerprint,
            MediaObject.status == "active",
        ))
        if media is None:
            continue
        rows.append(await record_provider_input(
            db, user_id=user_id, media_object_id=media.id,
            provider_task_id=provider_task_id, submission_id=submission_id,
            purpose=purpose, input_order=index, delivered_url=delivered_url,
            delivery_method="provider_reference",
        ))
    return rows


async def register_persisted_media(
    db: AsyncSession, *, user_id: str, canonical_url: str,
    delivery: dict, media_kind: str, lifecycle_class: str,
    project_id: str | None = None,
) -> MediaObject | None:
    local_path = local_static_path_for_url(canonical_url)
    if local_path is None or not local_path.is_file():
        return None
    provider_url = str(delivery.get("provider_url") or "").strip()
    object_key = str(delivery.get("object_key") or canonical_url.removeprefix("/static/")).strip("/")
    storage_provider = "qiniu" if str(delivery.get("delivery_method") or "").startswith("qiniu") else "local"
    media = await register_media_object(
        db, user_id=user_id, project_id=project_id, media_kind=media_kind,
        lifecycle_class=lifecycle_class, canonical_url=canonical_url,
        storage_provider=storage_provider, storage_config_id=delivery.get("storage_config_id"),
        object_key=object_key,
        sha256=_file_sha256(local_path),
        size_bytes=local_path.stat().st_size,
        content_type=mimetypes.guess_type(local_path.name)[0] or "application/octet-stream",
    )
    if provider_url:
        media.delivery_fingerprint = sanitize_provider_url(provider_url).url_fingerprint
    await db.flush()
    return media


async def bind_provider_task(
    db: AsyncSession, *, user_id: str, submission_id: str, provider_task_id: str,
) -> int:
    rows = list((await db.scalars(select(ProviderMediaInput).where(
        ProviderMediaInput.user_id == user_id,
        ProviderMediaInput.submission_id == submission_id,
        ProviderMediaInput.provider_task_id.is_(None),
    ))).all())
    for row in rows:
        row.provider_task_id = provider_task_id
    await db.flush()
    return len(rows)


async def create_deletion_request(
    db: AsyncSession, *, user_id: str, media_object_id: str,
    idempotency_key: str, reason: str,
) -> MediaDeletionRequest:
    existing = await db.scalar(select(MediaDeletionRequest).where(
        MediaDeletionRequest.user_id == user_id,
        MediaDeletionRequest.idempotency_key == idempotency_key,
    ))
    if existing is not None:
        if existing.media_object_id != media_object_id:
            raise HTTPException(status_code=409, detail="该幂等标识已用于另一个媒体删除申请")
        return existing
    await get_owned_media(db, user_id=user_id, media_object_id=media_object_id)
    request = MediaDeletionRequest(
        id=str(uuid4()), media_object_id=media_object_id, user_id=user_id,
        idempotency_key=idempotency_key, reason=reason.strip(), status="queued",
    )
    db.add(request)
    await db.commit()
    return request


async def execute_deletion_request(
    db: AsyncSession, *, request_id: str,
    delete_object: Callable[[str], bool | Awaitable[bool]],
) -> MediaDeletionReceipt:
    existing = await db.scalar(select(MediaDeletionReceipt).where(
        MediaDeletionReceipt.request_id == request_id,
    ))
    if existing is not None:
        return existing
    request = await db.get(MediaDeletionRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="媒体删除申请不存在")
    media = await db.get(MediaObject, request.media_object_id)
    if media is None:
        raise HTTPException(status_code=404, detail="待删除媒体不存在")
    if media.legal_hold:
        raise HTTPException(status_code=409, detail="该媒体处于法律保留状态，暂时不能删除")
    result = delete_object(media.object_key)
    deleted = await result if inspect.isawaitable(result) else result
    outcome = "deleted" if deleted else "already_missing"
    receipt = MediaDeletionReceipt(
        id=str(uuid4()), media_object_id=media.id, request_id=request.id,
        outcome=outcome,
        object_key_sha256=hashlib.sha256(media.object_key.encode("utf-8")).hexdigest(),
        detail="对象已删除" if deleted else "对象已不存在，删除申请按幂等方式完成",
    )
    media.status = "deleted"
    request.status = "completed"
    request.completed_at = utc_now()
    db.add(receipt)
    await db.commit()
    return receipt
