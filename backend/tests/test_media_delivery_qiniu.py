import asyncio
from types import SimpleNamespace


def test_resolve_provider_media_url_uploads_local_static_to_qiniu(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.services import media_delivery

    static_root = tmp_path / "static"
    image_path = static_root / "generated" / "images" / "ref.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-jpeg-bytes")
    monkeypatch.setattr(media_persistence, "STATIC_ROOT", static_root)

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"key": "static/generated/images/ref.jpg", "hash": "fakehash"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, files=None):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            return FakeResponse()

    async def fake_storage_config(db, user_id):
        config = SimpleNamespace(
            id="storage-qiniu-1",
            name="七牛 Kodo",
            test_status="success",
            custom_base_url="https://cdn.example.com",
            extra_config={
                "storage_provider": "qiniu",
                "bucket": "ai-video-test",
                "upload_url": "https://upload-z2.qiniup.com",
                "public_base_url": "https://cdn.example.com",
                "local_static_prefix": "/static/",
                "public_static_prefix": "/static/",
            },
            get_api_key_decrypted=lambda: "ak-test",
            get_api_secret_decrypted=lambda: "sk-test",
        )
        provider = SimpleNamespace(id="object_storage", name="object_storage", name_cn="对象存储 / CDN")
        return config, provider

    monkeypatch.setattr(media_delivery, "_get_default_storage_config", fake_storage_config)
    monkeypatch.setattr(media_delivery.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        media_delivery.resolve_provider_media_url(
            db=None,
            user_id="user-1",
            media_url="/static/generated/images/ref.jpg",
            media_type="图",
        )
    )

    assert result["provider_url"] == "https://cdn.example.com/static/generated/images/ref.jpg"
    assert result["delivery_method"] == "qiniu_object_upload"
    assert result["image_url_sent"] is True
    assert result["storage_config_id"] == "storage-qiniu-1"
    assert captured["url"] == "https://upload-z2.qiniup.com"
    assert captured["data"]["key"] == "static/generated/images/ref.jpg"
    assert captured["data"]["token"].startswith("ak-test:")
    file_name, file_bytes, content_type = captured["files"]["file"]
    assert file_name == "ref.jpg"
    assert file_bytes == b"fake-jpeg-bytes"
    assert content_type == "image/jpeg"


def test_resolve_provider_media_url_does_not_fake_qiniu_mapping_without_credentials(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.services import media_delivery

    static_root = tmp_path / "static"
    image_path = static_root / "generated" / "images" / "ref.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-jpeg-bytes")
    monkeypatch.setattr(media_persistence, "STATIC_ROOT", static_root)

    async def fake_storage_config(db, user_id):
        config = SimpleNamespace(
            id="storage-qiniu-missing",
            name="七牛 Kodo",
            test_status="success",
            custom_base_url="https://cdn.example.com",
            extra_config={
                "storage_provider": "qiniu",
                "bucket": "",
                "public_base_url": "https://cdn.example.com",
                "local_static_prefix": "/static/",
                "public_static_prefix": "/static/",
            },
            get_api_key_decrypted=lambda: "",
            get_api_secret_decrypted=lambda: "",
        )
        provider = SimpleNamespace(id="object_storage", name="object_storage", name_cn="对象存储 / CDN")
        return config, provider

    monkeypatch.setattr(media_delivery, "_get_default_storage_config", fake_storage_config)

    result = asyncio.run(
        media_delivery.resolve_provider_media_url(
            db=None,
            user_id="user-1",
            media_url="/static/generated/images/ref.jpg",
            media_type="图",
        )
    )

    assert result["provider_url"] is None
    assert result["image_url_sent"] is False
    assert result["delivery_method"] is None
    assert "七牛对象存储需要配置 Access Key、Secret Key 和 bucket" in result["omitted_reason"]


def test_resolve_provider_media_url_signs_private_qiniu_download_url(tmp_path, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.services import media_persistence
    from app.services import media_delivery

    static_root = tmp_path / "static"
    image_path = static_root / "generated" / "images" / "private-ref.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-private-jpeg-bytes")
    monkeypatch.setattr(media_persistence, "STATIC_ROOT", static_root)
    monkeypatch.setattr(media_delivery.time, "time", lambda: 1_700_000_000)

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, files=None):
            return FakeResponse()

    async def fake_storage_config(db, user_id):
        config = SimpleNamespace(
            id="storage-qiniu-private",
            name="七牛 Kodo 私有桶",
            test_status="success",
            custom_base_url="https://private-bucket.kodo-cn-north-1.qiniucs.com",
            extra_config={
                "storage_provider": "qiniu",
                "bucket": "private-bucket",
                "upload_url": "https://upload-z1.qiniup.com",
                "public_base_url": "https://private-bucket.kodo-cn-north-1.qiniucs.com",
                "local_static_prefix": "/static/",
                "public_static_prefix": "/static/",
                "private_download": True,
                "download_url_ttl_seconds": 1800,
            },
            get_api_key_decrypted=lambda: "ak-test",
            get_api_secret_decrypted=lambda: "sk-test",
        )
        provider = SimpleNamespace(id="object_storage", name="object_storage", name_cn="对象存储 / CDN")
        return config, provider

    monkeypatch.setattr(media_delivery, "_get_default_storage_config", fake_storage_config)
    monkeypatch.setattr(media_delivery.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        media_delivery.resolve_provider_media_url(
            db=None,
            user_id="user-1",
            media_url="/static/generated/images/private-ref.jpg",
            media_type="图",
        )
    )

    assert result["image_url_sent"] is True
    assert result["delivery_method"] == "qiniu_object_upload"
    signed_url = result["provider_url"]
    assert signed_url.startswith("https://private-bucket.kodo-cn-north-1.qiniucs.com/static/generated/images/private-ref.jpg?")
    query = parse_qs(urlparse(signed_url).query)
    assert query["e"] == ["1700000300"]
    assert query["token"][0].startswith("ak-test:")


def test_qiniu_private_download_url_caps_ttl_to_provider_safe_window(monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.services import media_delivery

    monkeypatch.setattr(media_delivery.time, "time", lambda: 1_700_000_000)

    signed_url = media_delivery._qiniu_private_download_url(
        "https://private-bucket.kodo-cn-north-1.qiniucs.com/static/ref.jpg",
        access_key="ak-test",
        secret_key="sk-test",
        ttl_seconds=86400,
    )

    query = parse_qs(urlparse(signed_url).query)
    assert query["e"] == ["1700000300"]
    assert query["token"][0].startswith("ak-test:")


def test_refresh_existing_private_qiniu_media_signs_without_reupload(monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.services import media_delivery

    monkeypatch.setattr(media_delivery.time, "time", lambda: 1_700_000_000)

    async def fake_storage_config(db, user_id, storage_config_id=None):
        config = SimpleNamespace(
            id="storage-qiniu-private",
            name="七牛 Kodo 私有桶",
            test_status="success",
            custom_base_url="https://private-bucket.kodo-cn-north-1.qiniucs.com",
            extra_config={
                "storage_provider": "qiniu",
                "public_base_url": "https://private-bucket.kodo-cn-north-1.qiniucs.com",
                "local_static_prefix": "/static/",
                "public_static_prefix": "/static/",
                "private_download": True,
                "download_url_ttl_seconds": 1800,
            },
            get_api_key_decrypted=lambda: "ak-test",
            get_api_secret_decrypted=lambda: "sk-test",
        )
        provider = SimpleNamespace(id="object_storage", name="object_storage", name_cn="对象存储 / CDN")
        return config, provider

    monkeypatch.setattr(media_delivery, "_get_default_storage_config", fake_storage_config)

    result = asyncio.run(media_delivery.refresh_existing_qiniu_media_url(
        db=None,
        user_id="user-1",
        media_url="/static/generated/videos/final.mp4",
    ))

    query = parse_qs(urlparse(result["provider_url"]).query)
    assert query["e"] == ["1700000300"]
    assert query["token"][0].startswith("ak-test:")
    assert result["delivery_method"] == "qiniu_signed_refresh"


def test_refresh_existing_private_qiniu_media_replaces_expired_signature(monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.services import media_delivery

    monkeypatch.setattr(media_delivery.time, "time", lambda: 1_700_000_000)

    async def fake_storage_config(db, user_id, storage_config_id=None):
        config = SimpleNamespace(
            id="storage-qiniu-private",
            custom_base_url="https://private-bucket.example.com",
            extra_config={
                "storage_provider": "qiniu",
                "public_base_url": "https://private-bucket.example.com",
                "local_static_prefix": "/static/",
                "public_static_prefix": "/static/",
                "private_download": True,
            },
            get_api_key_decrypted=lambda: "ak-test",
            get_api_secret_decrypted=lambda: "sk-test",
        )
        return config, SimpleNamespace(base_url="https://private-bucket.example.com")

    monkeypatch.setattr(media_delivery, "_get_default_storage_config", fake_storage_config)
    result = asyncio.run(media_delivery.refresh_existing_qiniu_media_url(
        db=None,
        user_id="user-1",
        media_url="https://private-bucket.example.com/static/generated/final.mp4?e=1600000000&token=expired",
    ))

    query = parse_qs(urlparse(result["provider_url"]).query)
    assert query["e"] == ["1700000300"]
    assert len(query["e"]) == 1
    assert len(query["token"]) == 1
    assert query["token"][0].startswith("ak-test:")


def test_object_storage_config_requires_qiniu_upload_fields_for_qiniu_provider():
    import asyncio

    from app.api.v1.endpoints.external_api import _test_external_config

    config = SimpleNamespace(
        custom_base_url="https://cdn.example.com",
        extra_config={"storage_provider": "qiniu", "public_base_url": "https://cdn.example.com"},
        timeout=60,
        get_api_key_decrypted=lambda: "",
        get_api_secret_decrypted=lambda: "",
    )
    provider = SimpleNamespace(name="object_storage")

    status, message = asyncio.run(_test_external_config(config, provider))

    assert status == "failed"
    assert "七牛对象存储需要配置 Access Key、Secret Key 和 bucket" in message
