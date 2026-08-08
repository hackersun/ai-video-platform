from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.features.private_media.service import (
    bind_provider_task,
    create_deletion_request,
    execute_deletion_request,
    get_playback_delivery,
    record_provider_inputs_for_urls,
    record_provider_input,
    register_media_object,
)
from app.models.private_media import MediaDeletionReceipt, MediaObject, ProviderMediaInput


def test_playback_is_owner_scoped_and_refreshes_short_lived_url(monkeypatch, tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'playback.db'}")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            db.add(MediaObject(
                id="media-1", user_id="owner", media_kind="video", lifecycle_class="final",
                storage_provider="qiniu", storage_config_id="storage-1",
                object_key="private/final/owner/movie.mp4", canonical_url="/static/generated/videos/movie.mp4",
                sha256="a" * 64, size_bytes=100, content_type="video/mp4",
            ))
            await db.commit()

            calls = 0

            async def fake_refresh(db, user_id, media_url, storage_config_id=None, object_key=None):
                nonlocal calls
                calls += 1
                assert user_id == "owner"
                assert storage_config_id == "storage-1"
                assert object_key == "private/final/owner/movie.mp4"
                deadline = int(datetime.now(timezone.utc).timestamp()) + 300 + calls
                return {"provider_url": f"https://private.test/movie.mp4?e={deadline}&token=hidden"}

            monkeypatch.setattr("app.features.private_media.service.refresh_existing_qiniu_media_url", fake_refresh)
            first = await get_playback_delivery(db, user_id="owner", media_object_id="media-1")
            second = await get_playback_delivery(db, user_id="owner", media_object_id="media-1")
            assert first.url != second.url
            assert first.expires_at != second.expires_at
            with pytest.raises(HTTPException) as error:
                await get_playback_delivery(db, user_id="other", media_object_id="media-1")
            assert error.value.status_code == 404
        await engine.dispose()

    asyncio.run(scenario())


def test_provider_manifest_is_sanitized_and_deletion_is_idempotent(monkeypatch, tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lifecycle.db'}")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            media = MediaObject(
                id="media-2", user_id="owner", media_kind="image", lifecycle_class="original",
                storage_provider="qiniu", object_key="private/original/owner/ref.jpg",
                canonical_url="/static/generated/images/ref.jpg", sha256="b" * 64,
                size_bytes=20, content_type="image/jpeg",
            )
            db.add(media)
            await db.commit()
            manifest = await record_provider_input(
                db, user_id="owner", media_object_id=media.id, provider_task_id="task-1",
                submission_id="shot-1:attempt-1", purpose="角色参考图", input_order=0,
                delivered_url="https://private.test/ref.jpg?e=1700000300&token=ak:secret",
                delivery_method="qiniu_signed_refresh",
            )
            await db.commit()
            assert isinstance(manifest, ProviderMediaInput)
            assert "token" not in manifest.url_fingerprint
            assert "secret" not in manifest.url_fingerprint
            assert not hasattr(manifest, "delivered_url")

            pending = await record_provider_input(
                db, user_id="owner", media_object_id=media.id, provider_task_id=None,
                submission_id="shot-1:attempt-2", purpose="角色参考图", input_order=1,
                delivered_url="https://private.test/ref.jpg?e=1700000301&token=hidden",
                delivery_method="qiniu_signed_refresh",
            )
            assert pending.provider_task_id is None
            assert await bind_provider_task(
                db, user_id="owner", submission_id="shot-1:attempt-2", provider_task_id="task-2",
            ) == 1
            assert pending.provider_task_id == "task-2"

            media.delivery_fingerprint = __import__("hashlib").sha256(
                b"https://private.test/ref.jpg"
            ).hexdigest()
            rows = await record_provider_inputs_for_urls(
                db, user_id="owner", delivered_urls=[
                    "https://private.test/ref.jpg?e=1700000400&token=do-not-store",
                    "https://unregistered.test/other.jpg",
                ], provider_task_id="task-3", submission_id="shot-1:task-3",
                purpose="镜头角色参考图",
            )
            assert len(rows) == 1
            assert rows[0].media_object_id == media.id
            assert rows[0].provider_task_id == "task-3"

            request = await create_deletion_request(
                db, user_id="owner", media_object_id=media.id,
                idempotency_key="delete-1", reason="用户申请删除素材",
            )
            duplicate = await create_deletion_request(
                db, user_id="owner", media_object_id=media.id,
                idempotency_key="delete-1", reason="用户申请删除素材",
            )
            assert duplicate.id == request.id

            other = MediaObject(
                id="media-other", user_id="owner", media_kind="image", lifecycle_class="original",
                storage_provider="qiniu", object_key="private/original/owner/other.jpg",
                canonical_url="/static/generated/images/other.jpg", sha256="c" * 64,
                size_bytes=10, content_type="image/jpeg",
            )
            db.add(other)
            await db.commit()
            with pytest.raises(HTTPException, match="幂等标识"):
                await create_deletion_request(
                    db, user_id="owner", media_object_id=other.id,
                    idempotency_key="delete-1", reason="另一个素材",
                )

            media.legal_hold = True
            await db.commit()
            with pytest.raises(HTTPException, match="法律保留"):
                await execute_deletion_request(db, request_id=request.id, delete_object=lambda _: None)
            media.legal_hold = False
            await db.commit()

            async def missing_object(_object_key: str) -> bool:
                return False

            receipt = await execute_deletion_request(db, request_id=request.id, delete_object=missing_object)
            again = await execute_deletion_request(db, request_id=request.id, delete_object=missing_object)
            assert receipt.id == again.id
            assert receipt.outcome == "already_missing"
            assert await db.get(MediaDeletionReceipt, receipt.id) is not None
            retried_request = await create_deletion_request(
                db, user_id="owner", media_object_id=media.id,
                idempotency_key="delete-1", reason="网络超时后重试",
            )
            assert retried_request.id == request.id
        await engine.dispose()

    asyncio.run(scenario())


def test_media_registration_rejects_wrong_prefix_and_content_collision(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'registration.db'}")
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            kwargs = dict(
                user_id="owner", media_kind="image", lifecycle_class="original",
                canonical_url="/static/generated/ref.jpg", storage_provider="qiniu",
                object_key="private/original/owner/ref.jpg", sha256="a" * 64,
                size_bytes=10, content_type="image/jpeg",
            )
            await register_media_object(db, **kwargs)
            with pytest.raises(HTTPException, match="内容校验不一致"):
                await register_media_object(db, **{**kwargs, "sha256": "b" * 64})
            with pytest.raises(HTTPException, match="私有前缀"):
                await register_media_object(db, **{
                    **kwargs, "object_key": "public/ref.jpg", "sha256": "c" * 64,
                })
        await engine.dispose()

    asyncio.run(scenario())
