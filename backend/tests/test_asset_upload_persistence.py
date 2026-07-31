import pytest


def _jpeg_bytes(size=(1024, 1024), color=(42, 120, 210)):
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def test_uploaded_asset_bytes_are_saved_as_static_url(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.services.media_persistence import persist_uploaded_media_bytes

    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path)

    url = persist_uploaded_media_bytes(
        b"image-bytes",
        media_type="image",
        content_type="image/png",
        subdir="assets/images",
        prefix="asset",
    )

    assert url.startswith("/static/generated/assets/images/asset-")
    assert url.endswith(".png")
    assert (tmp_path / url.removeprefix("/static/")).read_bytes() == b"image-bytes"


def test_uploaded_image_uses_detected_extension_when_header_is_wrong(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.services.media_persistence import persist_uploaded_media_bytes

    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path)

    url = persist_uploaded_media_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00",
        media_type="image",
        content_type="image/png",
        subdir="assets/images",
        prefix="asset",
    )

    assert url.endswith(".jpg")
    assert (tmp_path / url.removeprefix("/static/")).read_bytes().startswith(b"\xff\xd8\xff")


def test_uploaded_image_can_be_optimized_for_provider_fetching(tmp_path, monkeypatch):
    from PIL import Image

    from app.services import media_persistence
    from app.services.media_persistence import persist_uploaded_media_bytes

    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path)
    source = _jpeg_bytes()

    url = persist_uploaded_media_bytes(
        source,
        media_type="image",
        content_type="image/jpeg",
        subdir="images",
        prefix="shot",
        optimize_image=True,
        image_max_dimension=320,
        image_quality=72,
    )

    output = tmp_path / url.removeprefix("/static/")
    with Image.open(output) as image:
        assert max(image.size) <= 320
    assert url.endswith(".jpg")
    assert output.stat().st_size < len(source)


def test_uploaded_asset_bytes_reject_type_mismatch(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.services.media_persistence import persist_uploaded_media_bytes

    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path)

    with pytest.raises(ValueError, match="媒体类型不匹配"):
        persist_uploaded_media_bytes(
            b"not-an-image",
            media_type="image",
            content_type="text/plain",
            subdir="assets/images",
            prefix="asset",
        )


def test_remote_image_uses_detected_extension_when_header_is_wrong(tmp_path, monkeypatch):
    import asyncio

    from app.services import media_persistence

    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path)

    class FakeResponse:
        headers = {"content-type": "image/png"}
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00"

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            assert kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            return FakeResponse()

    monkeypatch.setattr(media_persistence.httpx, "AsyncClient", FakeAsyncClient)

    url = asyncio.run(
        media_persistence.persist_remote_media_url(
            "https://cdn.example.com/mislabelled-image",
            media_type="image",
            subdir="images",
            prefix="shot",
        )
    )

    assert url.endswith(".jpg")
    assert (tmp_path / url.removeprefix("/static/")).read_bytes().startswith(b"\xff\xd8\xff")
