"""Exercise real HTTPX request streams without any network or cloud credentials."""
import pytest
import httpx
from app.core import object_storage


@pytest.mark.asyncio
@pytest.mark.parametrize("backend_cls", [object_storage.S3Backend, object_storage.QiniuBackend])
async def test_cloud_upload_streams_bounded_chunks(tmp_path, monkeypatch, backend_cls):
    path = tmp_path / "movie.mp4"
    path.write_bytes(b"stream-test-" * 300000)
    chunks = []
    captured_headers = {}
    class InspectingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            captured_headers.update(request.headers)
            async for chunk in request.stream:
                assert len(chunk) <= 1024 * 1024, "cloud upload buffered entire file"
                chunks.append(chunk)
            return httpx.Response(200)
    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client(transport=InspectingTransport(), **kwargs))
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("QINIU_BUCKET", "test-bucket")
    monkeypatch.setenv("QINIU_ACCESS_KEY", "test-access")
    monkeypatch.setenv("QINIU_SECRET_KEY", "test-secret")
    await backend_cls().upload("generated/movie.mp4", path, "video/mp4")
    body = b"".join(chunks)
    assert path.read_bytes() in body
    assert len(chunks) > 2
    assert int(captured_headers["content-length"]) == len(body)
