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
async def test_media_playback_url_prefers_existing_local_static_file(monkeypatch, tmp_path):
    local_file = tmp_path / "final.mp4"
    local_file.write_bytes(b"video")
    job = SimpleNamespace(
        id="media-local",
        output_video_url="/static/generated/videos/final.mp4",
        extra_data={"subtitle_delivery": {"storage_config_id": "storage-1"}},
    )
    refresh_called = False

    async def fake_refresh(*_args, **_kwargs):
        nonlocal refresh_called
        refresh_called = True
        return {
            "provider_url": "http://private.example/final.mp4?e=1700000300&token=fresh",
            "delivery_method": "qiniu_signed_refresh",
        }

    monkeypatch.setattr(media, "local_static_path_for_url", lambda _url: local_file, raising=False)
    monkeypatch.setattr(media, "refresh_existing_qiniu_media_url", fake_refresh)

    response = await media.get_media_playback_url("media-local", db=_Db(job), user_id="user-1")

    assert response == {
        "job_id": "media-local",
        "url": "/static/generated/videos/final.mp4",
        "delivery_method": "local_static",
    }
    assert refresh_called is False


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
