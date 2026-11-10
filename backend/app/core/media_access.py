"""R02/R02b: private media access for exports and generated intermediates.

Files under PRIVATE_PREFIXES are never served anonymously from /static. API
endpoints that already enforce owner authorization return short-lived HMAC
signed URLs (``?exp=<unix>&sig=<hex>``); the static mount verifies them.
Persisted DB values stay unsigned; signing happens at response / outbound time.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

PRIVATE_PREFIXES = ("/static/exports/", "/static/generated/")
DEFAULT_TTL_SECONDS = 3600
CLOUD_RENDER_TTL_SECONDS = 86400  # external renderer needs longer fetch window


def _secret() -> bytes:
    key = os.getenv("MEDIA_SIGNING_KEY") or os.getenv("JWT_SECRET_KEY") or "dev-jwt-secret-change-in-production"
    return key.encode("utf-8")


def _ttl() -> int:
    try:
        return int(os.getenv("MEDIA_URL_TTL_SECONDS") or DEFAULT_TTL_SECONDS)
    except ValueError:
        return DEFAULT_TTL_SECONDS


def is_private_media_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PRIVATE_PREFIXES)


def _signature(path: str, exp: str) -> str:
    return hmac.new(_secret(), f"{path}\n{exp}".encode("utf-8"), hashlib.sha256).hexdigest()


def sign_media_url(url: Optional[str], ttl_seconds: Optional[int] = None) -> Optional[str]:
    """Sign a private /static/exports or /static/generated URL; others pass through."""
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc and parsed.hostname not in {"127.0.0.1", "localhost"}:
        return url
    if not is_private_media_path(parsed.path):
        return url
    # G4: uploaded objects get a provider-signed private-bucket URL.
    from app.core.object_storage import signed_url_for

    cloud_url = signed_url_for(parsed.path, ttl_seconds)
    if cloud_url:
        return cloud_url
    # Bucket expiry to 5 minutes so repeated polls yield cache-friendly URLs.
    ttl = _ttl() if ttl_seconds is None else ttl_seconds
    exp = str((int(time.time()) + ttl) // 300 * 300 if ttl > 0 else int(time.time()) + ttl)
    query = urlencode({"exp": exp, "sig": _signature(parsed.path, exp)})
    return parsed._replace(query=query).geturl()


def verify_media_signature(path: str, exp: Optional[str], sig: Optional[str]) -> bool:
    if not exp or not sig:
        return False
    try:
        if int(exp) < int(time.time()):
            return False
    except ValueError:
        return False
    return hmac.compare_digest(_signature(path, exp), sig)


def unsigned_media_url(url: Optional[str]) -> Optional[str]:
    """Strip exp/sig query params so only the bare path (or foreign URL) is stored."""
    if not url:
        return url
    parsed = urlparse(url)
    if not is_private_media_path(parsed.path):
        return url
    return parsed._replace(query="", fragment="").geturl()


def sign_media_urls_in_obj(value: object, *, ttl_seconds: Optional[int] = None) -> object:
    """Deep-copy dict/list structures, signing private media URL strings."""
    if isinstance(value, str):
        return sign_media_url(value, ttl_seconds=ttl_seconds)
    if isinstance(value, list):
        return [sign_media_urls_in_obj(item, ttl_seconds=ttl_seconds) for item in value]
    if isinstance(value, dict):
        return {key: sign_media_urls_in_obj(item, ttl_seconds=ttl_seconds) for key, item in value.items()}
    return value


def unsigned_media_urls_in_obj(value: object) -> object:
    if isinstance(value, str):
        return unsigned_media_url(value)
    if isinstance(value, list):
        return [unsigned_media_urls_in_obj(item) for item in value]
    if isinstance(value, dict):
        return {key: unsigned_media_urls_in_obj(item) for key, item in value.items()}
    return value


class PrivateAwareStaticFiles(StaticFiles):
    """StaticFiles that refuses private paths without a valid signature."""

    def __init__(self, *args, mount_path: str = "/static", **kwargs):
        super().__init__(*args, **kwargs)
        self._mount_path = mount_path.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            full_path = self._mount_path + "/" + self.get_path(scope).lstrip("/")
            if is_private_media_path(full_path):
                query = parse_qs((scope.get("query_string") or b"").decode("latin-1"))
                exp = (query.get("exp") or [None])[0]
                sig = (query.get("sig") or [None])[0]
                if not verify_media_signature(full_path, exp, sig):
                    response = JSONResponse({"detail": "media_access_denied"}, status_code=403)
                    await response(scope, receive, send)
                    return
            query = parse_qs((scope.get("query_string") or b"").decode("latin-1"))
            if (query.get("download") or [""])[0] in {"1", "true"}:
                send = _attachment_send(send, full_path.rsplit("/", 1)[-1])
        await super().__call__(scope, receive, send)


def _attachment_send(send, filename: str):
    """?download=1 → Content-Disposition: attachment, so cross-origin「下载视频」saves instead of opening a tab."""
    from urllib.parse import quote

    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "download"
    value = f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(filename)}".encode("latin-1")

    async def wrapped(message):
        if message.get("type") == "http.response.start":
            headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"content-disposition"]
            headers.append((b"content-disposition", value))
            message = {**message, "headers": headers}
        await send(message)

    return wrapped


def _serialize_signed(value: Optional[str]) -> Optional[str]:
    return sign_media_url(value)


# Response-model field type: stored value stays raw, API output is signed.
from typing import Annotated  # noqa: E402

from pydantic import PlainSerializer  # noqa: E402

SignedMediaUrl = Annotated[Optional[str], PlainSerializer(_serialize_signed, return_type=Optional[str])]
SignedMediaStr = Annotated[str, PlainSerializer(_serialize_signed, return_type=str)]


_UNSIGNED_PRIVATE_JSON = re.compile(rb'"(/static/(?:exports|generated)/[^"?\\\s]+)"')


def sign_export_urls_in_json(body: bytes) -> bytes:
    """Sign every bare private media path embedded in a JSON body (nested artifacts, metadata)."""
    if b"/static/exports/" not in body and b"/static/generated/" not in body:
        return body
    return _UNSIGNED_PRIVATE_JSON.sub(
        lambda m: b'"' + sign_media_url(m.group(1).decode()).encode() + b'"', body
    )


class SignExportUrlsMiddleware:
    """ASGI middleware: owner-scoped API JSON responses get signed private export URLs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return
        start: dict = {}
        chunks: list[bytes] = []
        passthrough = False

        async def _send(message):
            nonlocal passthrough
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers") or [])
                if b"application/json" not in headers.get(b"content-type", b""):
                    passthrough = True
                    await send(message)
                else:
                    start.update(message)
                return
            if passthrough:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return
            body = sign_export_urls_in_json(b"".join(chunks))
            headers = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode()))
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, _send)
