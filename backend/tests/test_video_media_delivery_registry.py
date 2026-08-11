import pytest

from app.features.video_generation.adapters.media_delivery import resolve_provider_image_delivery


@pytest.mark.asyncio
async def test_video_reference_delivery_registers_local_private_media(monkeypatch) -> None:
    registered = {}

    async def resolve(_db, _user_id, canonical_url, **kwargs):
        kwargs["canonical_url"] = canonical_url
        registered.update(kwargs)
        return {
            "provider_url": "https://private.test/ref.jpg?e=1900000000&token=hidden",
            "delivery_method": "qiniu_object_upload", "storage_config_id": "storage-1",
            "object_key": "private/original/user-1/ref.jpg", "omitted_reason": None,
        }

    monkeypatch.setattr(
        "app.features.video_generation.adapters.media_delivery.resolve_original_image", resolve,
    )

    result = await resolve_provider_image_delivery(
        object(), "user-1", "/static/generated/images/ref.jpg",
    )

    assert result["provider_image_url"].startswith("https://private.test/ref.jpg?")
    assert registered["canonical_url"] == "/static/generated/images/ref.jpg"
