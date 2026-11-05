"""R02: private media access for finished exports.

Files under PRIVATE_PREFIXES are never served anonymously from /static. API
endpoints that already enforce owner authorization return short-lived HMAC
signed URLs (``?exp=<unix>&sig=<hex>``); the static mount verifies them.
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

PRIVATE_PREFIXES = ("/static/exports/",)
DEFAULT_TTL_SECONDS = 3600


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
    """Sign a private /static/exports URL; other URLs pass through unchanged."""
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc and parsed.hostname not in {"127.0.0.1", "localhost"}:
        return url
    if not is_private_media_path(parsed.path):
        return url
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
        await super().__call__(scope, receive, send)


def _serialize_signed(value: Optional[str]) -> Optional[str]:
    return sign_media_url(value)


# Response-model field type: stored value stays raw, API output is signed.
from typing import Annotated  # noqa: E402

from pydantic import PlainSerializer  # noqa: E402

SignedMediaUrl = Annotated[Optional[str], PlainSerializer(_serialize_signed, return_type=Optional[str])]
SignedMediaStr = Annotated[str, PlainSerializer(_serialize_signed, return_type=str)]


_UNSIGNED_EXPORT_JSON = re.compile(rb'"(/static/exports/[^"?\\\s]+)"')


def sign_export_urls_in_json(body: bytes) -> bytes:
    """Sign every bare private export path embedded in a JSON body (nested artifacts, metadata)."""
    if b"/static/exports/" not in body:
        return body
    return _UNSIGNED_EXPORT_JSON.sub(
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
