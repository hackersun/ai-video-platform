from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_current_user_id
from app.models.private_media import MediaObject
from main import app


def test_private_media_api_hides_cross_user_objects_and_queues_deletion(monkeypatch, tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def setup() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            db.add(MediaObject(
                id="media-api-1", user_id="owner", media_kind="video", lifecycle_class="final",
                storage_provider="qiniu", storage_config_id="storage-1",
                object_key="private/final/owner/movie.mp4", canonical_url="/static/generated/videos/movie.mp4",
                sha256="c" * 64, size_bytes=100, content_type="video/mp4",
            ))
            await db.commit()

    async def override_db():
        async with factory() as db:
            yield db

    current_user = {"id": "owner"}

    async def override_user() -> str:
        return current_user["id"]

    async def fake_refresh(*_args, **_kwargs):
        return {"provider_url": f"https://private.test/movie.mp4?e={int(time.time()) + 300}&token=hidden"}

    monkeypatch.setattr("app.features.private_media.service.refresh_existing_qiniu_media_url", fake_refresh)
    asyncio.run(setup())
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = override_user
    try:
        with TestClient(app) as client:
            playback = client.get("/api/v1/media-objects/media-api-1/playback-url")
            assert playback.status_code == 200
            assert playback.json()["url"].startswith("https://private.test/movie.mp4?")

            current_user["id"] = "other"
            hidden = client.get("/api/v1/media-objects/media-api-1/playback-url")
            assert hidden.status_code == 404
            assert hidden.json()["detail"] == "媒体不存在或你无权访问"

            current_user["id"] = "owner"
            queued = client.post("/api/v1/media-objects/media-api-1/deletion-requests", json={
                "idempotency_key": "api-delete-1", "reason": "用户要求删除成片",
            })
            assert queued.status_code == 202
            assert queued.json()["status"] == "queued"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user_id, None)
        asyncio.run(engine.dispose())
