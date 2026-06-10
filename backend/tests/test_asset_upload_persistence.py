import pytest


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
