from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.features.private_media.integration import persist_private_video_output, resolve_and_register_media


@pytest.mark.asyncio
async def test_local_media_uses_private_user_lifecycle_object_key(monkeypatch) -> None:
    captured = {}

    async def resolve(_db, _user_id, media_url, **kwargs):
        captured.update(kwargs)
        return {
            "provider_url": "https://private.test/object?e=1900000000&token=hidden",
            "object_key": kwargs["object_key_override"],
            "delivery_method": "qiniu_object_upload",
        }

    async def register(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.features.private_media.integration.resolve_provider_media_url", resolve)
    monkeypatch.setattr("app.features.private_media.integration.register_persisted_media", register)

    await resolve_and_register_media(
        object(), user_id="user-1", canonical_url="/static/generated/ref.jpg",
        media_kind="image", lifecycle_class="original", media_type="图",
    )

    assert captured["object_key_override"].startswith("private/original/user-1/")
    assert captured["object_key_override"].endswith("-ref.jpg")


@pytest.mark.asyncio
async def test_production_rejects_unsigned_local_media_delivery(monkeypatch) -> None:
    async def resolve(*_args, **_kwargs):
        return {"provider_url": "https://public.test/ref.jpg", "image_url_sent": True}

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr("app.features.private_media.integration.resolve_provider_media_url", resolve)
    delivery = await resolve_and_register_media(
        object(), user_id="user-1", canonical_url="/static/generated/ref.jpg",
        media_kind="image", lifecycle_class="original", media_type="图",
    )

    assert delivery["provider_url"] is None
    assert delivery["image_url_sent"] is False
    assert delivery["omitted_reason"] == "对象存储未启用私有短时下载，正式环境拒绝发送媒体"


@pytest.mark.asyncio
async def test_video_output_metadata_never_persists_provider_signature(monkeypatch) -> None:
    async def persist(*_args, **_kwargs):
        return "/static/generated/videos/final.mp4"

    async def resolve(*_args, **_kwargs):
        return {"media_object_id": "media-final-1", "delivery_method": "qiniu_object_upload"}

    monkeypatch.setattr("app.features.private_media.integration.persist_remote_media_url", persist)
    monkeypatch.setattr("app.features.private_media.integration.resolve_and_register_media", resolve)
    job = SimpleNamespace(id="job-1", user_id="user-1", project_id="project-1", extra_data={})
    stored, extra = await persist_private_video_output(
        object(), job, "https://provider.test/final.mp4?e=1900000000&token=secret", cover=False,
    )

    assert stored == "/static/generated/videos/final.mp4"
    assert extra["original_video_url"] == "https://provider.test/final.mp4"
    assert "token=" not in str(extra)
    assert "secret" not in str(extra)
