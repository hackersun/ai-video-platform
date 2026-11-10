"""Uploads must use bounded reads, enforce limits, and remove partial files."""
from io import BytesIO
import asyncio
import pytest
from fastapi import UploadFile, HTTPException
from starlette.datastructures import Headers


class ChunkedUpload(UploadFile):
    def __init__(self, data: bytes):
        super().__init__(BytesIO(data), filename="sample.png", headers=Headers({"content-type": "image/png"}))
        self.read_sizes = []

    async def read(self, size=-1):
        assert 0 < size <= 1024 * 1024, "upload must not read the entire file"
        self.read_sizes.append(size)
        return await super().read(size)


@pytest.mark.asyncio
async def test_copy_is_bounded_and_accepts_exact_limit(tmp_path):
    from app.core.upload_stream import copy_upload
    data = b"x" * (2 * 1024 * 1024 + 5)
    upload = ChunkedUpload(data)
    target = tmp_path / "upload.bin"
    assert await copy_upload(upload, target, max_bytes=len(data)) == len(data)
    assert target.read_bytes() == data
    assert len(upload.read_sizes) >= 4


@pytest.mark.asyncio
@pytest.mark.parametrize("data,limit,message", [(b"", 5, "为空"), (b"123456", 5, "大小限制")])
async def test_rejected_copy_removes_partial_file(tmp_path, data, limit, message):
    from app.core.upload_stream import copy_upload
    target = tmp_path / "partial"
    with pytest.raises(ValueError, match=message):
        await copy_upload(ChunkedUpload(data), target, max_bytes=limit)
    assert not target.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [OSError("disconnected"), asyncio.CancelledError()])
async def test_interrupted_copy_removes_partial_file(tmp_path, error):
    from app.core.upload_stream import copy_upload
    class Interrupted(ChunkedUpload):
        async def read(self, size=-1):
            if self.read_sizes:
                raise error
            return await super().read(size)
    target = tmp_path / "partial"
    with pytest.raises(type(error)):
        await copy_upload(Interrupted(b"some data"), target, max_bytes=100)
    assert not target.exists()


@pytest.mark.asyncio
async def test_asset_route_streams_and_detects_image_extension(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.api.v1.endpoints.assets import upload_asset_file
    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path)
    upload = ChunkedUpload(b"\xff\xd8\xff" + b"x" * (1024 * 1024))
    result = await upload_asset_file(asset_type="image", kind="resource", file=upload, user_id="test-user")
    assert result.url.endswith(".jpg")
    assert result.size == 1024 * 1024 + 3
    assert upload.file.closed
    assert (tmp_path / result.url.removeprefix("/static/")).stat().st_size == result.size


@pytest.mark.asyncio
async def test_asset_route_size_limit_closes_and_cleans(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.api.v1.endpoints import assets
    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path)
    monkeypatch.setattr(assets, "_asset_upload_limit", lambda _: 4)
    upload = ChunkedUpload(b"12345")
    with pytest.raises(HTTPException) as exc:
        await assets.upload_asset_file(asset_type="image", kind="resource", file=upload, user_id="test-user")
    assert exc.value.status_code == 400
    assert upload.file.closed
    assert not list(tmp_path.rglob("*.*"))


@pytest.mark.asyncio
async def test_voice_clone_streams_and_closes_sample(tmp_path, monkeypatch):
    from app.api.v1.endpoints import tts
    monkeypatch.setattr(tts, "STATIC_ROOT", tmp_path)
    monkeypatch.setattr(tts, "VOICE_CLONE_DIR", tmp_path / "generated/voice-clones")
    upload = ChunkedUpload(b"audio" * 300000)
    upload.filename = "voice.wav"
    url = await tts._save_voice_clone_upload(upload, "voice-test")
    assert (tmp_path / url.removeprefix("/static/")).stat().st_size == len(b"audio" * 300000)
    assert upload.file.closed


@pytest.mark.asyncio
async def test_novel_import_bounds_bytes_before_parser_and_closes_upload(tmp_path, monkeypatch):
    from app.services import upload_persistence
    monkeypatch.setattr(upload_persistence, "NOVEL_IMPORT_MAX_BYTES", 4)
    upload = ChunkedUpload(b"12345")
    upload.filename = "novel.txt"
    with pytest.raises(ValueError, match="大小限制"):
        await upload_persistence.parse_uploaded_novel(upload)
    assert upload.file.closed


@pytest.mark.asyncio
async def test_empty_novel_preserves_validation_message():
    from app.services.upload_persistence import parse_uploaded_novel
    upload = ChunkedUpload(b"")
    upload.filename = "novel.txt"
    with pytest.raises(ValueError, match="上传文件为空"):
        await parse_uploaded_novel(upload)
    assert upload.file.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,status_code", [(b"", 422), (b"x" * (30 * 1024 * 1024 + 1), 413)])
async def test_voice_rejected_sample_is_closed_and_not_persisted(tmp_path, monkeypatch, payload, status_code):
    from app.api.v1.endpoints import tts
    monkeypatch.setattr(tts, "STATIC_ROOT", tmp_path)
    monkeypatch.setattr(tts, "VOICE_CLONE_DIR", tmp_path / "generated/voice-clones")
    upload = ChunkedUpload(payload)
    upload.filename = "sample.wav"
    with pytest.raises(HTTPException) as error:
        await tts._save_voice_clone_upload(upload, "voice-test")
    assert error.value.status_code == status_code
    assert upload.file.closed
    assert not list(tmp_path.rglob("*.wav"))
