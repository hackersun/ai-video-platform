import asyncio
import datetime as dt
from urllib.parse import parse_qs, urlparse

import pytest

from app.core import object_storage
from app.core.media_access import sign_media_url


@pytest.fixture
def static_dir(tmp_path, monkeypatch):
    for name in ("STORAGE_PROVIDER", "STORAGE_KEY_PREFIX", "STORAGE_BUCKET_ACL", "STORAGE_PUBLIC_READ",
                 "ALLOW_LOCAL_STORAGE_IN_PRODUCTION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MEDIA_STATIC_DIR", str(tmp_path))
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "final.mp4").write_bytes(b"mp4")
    return tmp_path


def _s3_env(monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv("S3_BUCKET", "avp-private")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "AKIDTEST")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "s3cr3t-value")


def test_sigv4_presign_matches_aws_reference_vector():
    url = object_storage.s3_presign(
        "GET", endpoint="https://s3.amazonaws.com", bucket="examplebucket", key="test.txt",
        access_key="AKIAIOSFODNN7EXAMPLE", secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1", expires=86400, now=dt.datetime(2013, 5, 24, tzinfo=dt.timezone.utc),
        path_style=False,
    )
    assert url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404")


def test_local_default_keeps_hmac_signing(static_dir):
    signed = sign_media_url("/static/exports/final.mp4")
    assert signed.startswith("/static/exports/final.mp4?exp=") and "sig=" in signed


def test_s3_upload_then_presigned_url_and_no_secret_leak(static_dir, monkeypatch):
    _s3_env(monkeypatch)
    uploads = []

    async def fake_upload(self, key, file_path, content_type):
        uploads.append((key, file_path.read_bytes(), content_type))

    monkeypatch.setattr(object_storage.S3Backend, "upload", fake_upload)
    # not yet uploaded -> HMAC fallback
    assert "sig=" in sign_media_url("/static/exports/final.mp4")
    result = asyncio.run(object_storage.persist_private_media_in_obj(
        {"video_url": "/static/exports/final.mp4?exp=1&sig=x", "other": "https://cdn/x", "missing": "/static/generated/nope.png"}
    ))
    assert result == {"/static/exports/final.mp4": True, "/static/generated/nope.png": False}
    assert uploads == [("exports/final.mp4", b"mp4", "video/mp4")]
    url = sign_media_url("/static/exports/final.mp4", ttl_seconds=600)
    parsed = urlparse(url)
    assert parsed.netloc == "s3.example.com" and parsed.path == "/avp-private/exports/final.mp4"
    q = parse_qs(parsed.query)
    assert q["X-Amz-Expires"] == ["600"] and "X-Amz-Signature" in q
    assert "s3cr3t-value" not in url
    # idempotent
    asyncio.run(object_storage.persist_private_media("/static/exports/final.mp4"))
    assert len(uploads) == 1


def test_qiniu_private_signed_url(static_dir, monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "qiniu")
    monkeypatch.setenv("QINIU_BUCKET", "avp")
    monkeypatch.setenv("QINIU_ACCESS_KEY", "ak")
    monkeypatch.setenv("QINIU_SECRET_KEY", "sk-secret")
    monkeypatch.setenv("QINIU_DOMAIN", "media.example.cn")
    seen = []

    async def fake_upload(self, key, file_path, content_type):
        seen.append(key)

    monkeypatch.setattr(object_storage.QiniuBackend, "upload", fake_upload)
    asyncio.run(object_storage.persist_private_media("/static/exports/final.mp4"))
    url = sign_media_url("/static/exports/final.mp4")
    assert url.startswith("https://media.example.cn/exports/final.mp4?e=") and "&token=ak:" in url
    assert "sk-secret" not in url and seen == ["exports/final.mp4"]


def test_upload_failure_falls_back_to_hmac(static_dir, monkeypatch):
    _s3_env(monkeypatch)

    async def boom(self, *a):
        raise RuntimeError("network")

    monkeypatch.setattr(object_storage.S3Backend, "upload", boom)
    assert asyncio.run(object_storage.persist_private_media_in_obj(["/static/exports/final.mp4"])) == {
        "/static/exports/final.mp4": False}
    assert "sig=" in sign_media_url("/static/exports/final.mp4")


def test_path_traversal_rejected():
    assert object_storage.object_key_for("/static/exports/../secrets") is None
    assert object_storage.object_key_for("/static/uploads/x.png") is None


def test_production_guard(static_dir, monkeypatch):
    from app.core.runtime_env import assert_production_safe

    for name in ("DEV_MODE", "DEV_USER_ID", "DEV_TOKEN", "DEV_AUTH_TOKEN", "ALLOW_DEV_TOKEN", "DETERMINISTIC_PROVIDER_FAKE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="STORAGE_PROVIDER=local"):
        assert_production_safe()
    monkeypatch.setenv("ALLOW_LOCAL_STORAGE_IN_PRODUCTION", "1")
    assert_production_safe()
    monkeypatch.delenv("ALLOW_LOCAL_STORAGE_IN_PRODUCTION")
    _s3_env(monkeypatch)
    assert_production_safe()
    monkeypatch.setenv("STORAGE_BUCKET_ACL", "public-read")
    with pytest.raises(RuntimeError, match="must be private"):
        assert_production_safe()
    monkeypatch.setenv("STORAGE_BUCKET_ACL", "private")
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY")
    with pytest.raises(RuntimeError, match="missing bucket/credentials"):
        assert_production_safe()
