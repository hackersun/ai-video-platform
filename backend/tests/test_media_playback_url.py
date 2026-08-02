from types import SimpleNamespace

import pytest

from app.api.v1.endpoints import media


class _Result:
    def __init__(self, job):
        self.job = job

    def scalar_one_or_none(self):
        return self.job


class _Db:
    def __init__(self, job):
        self.job = job

    async def execute(self, _statement):
        return _Result(self.job)


@pytest.mark.asyncio
async def test_media_playback_url_prefers_fresh_qiniu_url_when_local_copy_exists(monkeypatch, tmp_path):
    local_file = tmp_path / "final.mp4"
    local_file.write_bytes(b"video")
    job = SimpleNamespace(
        id="media-local",
        output_video_url="/static/generated/videos/final.mp4",
        extra_data={"subtitle_delivery": {
            "method": "qiniu_object_upload",
            "object_key": "static/generated/videos/final.mp4",
        }},
    )
    async def fake_refresh(*_args, **_kwargs):
        return {
            "provider_url": "http://private.example/final.mp4?e=1700000300&token=fresh",
            "delivery_method": "qiniu_signed_refresh",
        }

    monkeypatch.setattr(media, "local_static_path_for_url", lambda _url: local_file, raising=False)
    monkeypatch.setattr(media, "refresh_existing_qiniu_media_url", fake_refresh)

    response = await media.get_media_playback_url("media-local", db=_Db(job), user_id="user-1")

    assert response == {
        "job_id": "media-local",
        "url": "http://private.example/final.mp4?e=1700000300&token=fresh",
        "delivery_method": "qiniu_signed_refresh",
    }


@pytest.mark.asyncio
async def test_media_playback_url_refreshes_private_qiniu_signature(monkeypatch):
    job = SimpleNamespace(
        id="media-1",
        output_video_url="/static/generated/videos/final.mp4",
        extra_data={"subtitle_delivery": {"storage_config_id": "storage-1"}},
    )

    async def fake_refresh(db, user_id, media_url, *, storage_config_id=None):
        assert media_url == job.output_video_url
        assert storage_config_id == "storage-1"
        return {
            "provider_url": "https://private.example/final.mp4?e=1700000300&token=fresh",
            "delivery_method": "qiniu_signed_refresh",
        }

    monkeypatch.setattr(media, "refresh_existing_qiniu_media_url", fake_refresh, raising=False)

    response = await media.get_media_playback_url("media-1", db=_Db(job), user_id="user-1")

    assert response == {
        "job_id": "media-1",
        "url": "https://private.example/final.mp4?e=1700000300&token=fresh",
        "delivery_method": "qiniu_signed_refresh",
    }


@pytest.mark.asyncio
async def test_media_playback_url_refreshes_remote_signature_even_when_local_copy_exists(monkeypatch, tmp_path):
    local_file = tmp_path / "final.mp4"
    local_file.write_bytes(b"video")
    job = SimpleNamespace(
        id="media-remote",
        output_video_url="https://private.example/static/generated/final.mp4?e=1&token=expired",
        extra_data={},
    )

    async def fake_refresh(*_args, **_kwargs):
        return {
            "provider_url": "https://private.example/static/generated/final.mp4?e=1700000300&token=fresh",
            "delivery_method": "qiniu_signed_refresh",
        }

    monkeypatch.setattr(media, "local_static_path_for_url", lambda _url: local_file, raising=False)
    monkeypatch.setattr(media, "is_dev_mode", lambda: False)
    monkeypatch.setattr(media, "refresh_existing_qiniu_media_url", fake_refresh, raising=False)

    response = await media.get_media_playback_url("media-remote", db=_Db(job), user_id="user-1")

    assert response["url"].endswith("e=1700000300&token=fresh")
    assert response["delivery_method"] == "qiniu_signed_refresh"


@pytest.mark.asyncio
async def test_media_playback_url_uses_local_delivery_fallback_in_dev_when_qiniu_copy_exists(
    monkeypatch, tmp_path,
):
    local_file = tmp_path / "final.mp4"
    local_file.write_bytes(b"video")
    job = SimpleNamespace(
        id="media-dev-fallback",
        output_video_url="http://private.example/static/generated/videos/final.mp4?token=signed",
        extra_data={},
    )
    refresh_called = False

    async def fake_refresh(*_args, **_kwargs):
        nonlocal refresh_called
        refresh_called = True
        return {}

    monkeypatch.setattr(media, "is_dev_mode", lambda: True)
    monkeypatch.setattr(media, "local_static_path_for_url", lambda _url: local_file)
    monkeypatch.setattr(media, "refresh_existing_qiniu_media_url", fake_refresh)

    response = await media.get_media_playback_url(
        "media-dev-fallback", db=_Db(job), user_id="user-1",
    )

    assert response == {
        "job_id": "media-dev-fallback",
        "url": "http://127.0.0.1:8000/static/generated/videos/final.mp4",
        "delivery_method": "local_static_fallback",
    }
    assert refresh_called is False
