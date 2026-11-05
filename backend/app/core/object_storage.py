"""G4: private object storage for final exports / publications / generated media.

Selected by ``STORAGE_PROVIDER`` (``local`` default | ``s3`` | ``qiniu``).

* Persisted DB values always stay bare ``/static/exports/...`` or
  ``/static/generated/...`` paths; the local file remains the working copy.
* ``persist_private_media`` uploads a private path to the private bucket at
  publication time and drops a marker under ``<static>/.object-store/``.
* ``signed_url_for`` (called from ``media_access.sign_media_url`` at response
  time, after owner authz) returns a provider-signed short-TTL URL only for
  uploaded objects; anything else falls back to the local HMAC-signed URL.

Credentials are read from env only and never logged or returned.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as _dt
import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

PRIVATE_PREFIXES = ("/static/exports/", "/static/generated/")
_TRUTHY = {"1", "true", "yes", "on"}
_MARKER_DIR = ".object-store"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def storage_provider() -> str:
    value = _env("STORAGE_PROVIDER", "local").lower()
    return {"kodo": "qiniu", "qiniu_kodo": "qiniu", "minio": "s3", "r2": "s3"}.get(value, value)


def static_root() -> Path:
    configured = _env("MEDIA_STATIC_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "static"


def object_key_for(path: str) -> Optional[str]:
    if not any(path.startswith(prefix) for prefix in PRIVATE_PREFIXES):
        return None
    rel = path[len("/static/"):]
    if ".." in rel.split("/"):
        return None
    prefix = _env("STORAGE_KEY_PREFIX").strip("/")
    return f"{prefix}/{rel}" if prefix else rel


def _ttl(ttl_seconds: Optional[int]) -> int:
    if ttl_seconds is not None and ttl_seconds > 0:
        base = ttl_seconds
    else:
        try:
            base = int(_env("STORAGE_SIGNED_URL_TTL_SECONDS") or _env("MEDIA_URL_TTL_SECONDS") or 900)
        except ValueError:
            base = 900
    return max(60, min(base, 7 * 86400))


# --------------------------------------------------------------------- S3 SigV4
def _sigv4_key(secret: str, date: str, region: str) -> bytes:
    k = hmac.new(("AWS4" + secret).encode(), date.encode(), hashlib.sha256).digest()
    for part in (region, "s3", "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    return k


def s3_presign(
    method: str,
    *,
    endpoint: str,
    bucket: str,
    key: str,
    access_key: str,
    secret_key: str,
    region: str,
    expires: int,
    now: Optional[_dt.datetime] = None,
    path_style: bool = True,
) -> str:
    """AWS SigV4 query-string presign (works for S3, MinIO, R2, COS/OSS S3 APIs)."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    endpoint = endpoint.rstrip("/")
    scheme, host = endpoint.split("://", 1)
    encoded_key = quote(key, safe="/~")
    if path_style:
        canonical_uri = f"/{bucket}/{encoded_key}"
    else:
        host = f"{bucket}.{host}"
        canonical_uri = f"/{encoded_key}"
    scope = f"{date}/{region}/s3/aws4_request"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    query = "&".join(f"{quote(k, safe='~')}={quote(v, safe='~')}" for k, v in sorted(params.items()))
    canonical = "\n".join([method, canonical_uri, query, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )
    signature = hmac.new(_sigv4_key(secret_key, date, region), to_sign.encode(), hashlib.sha256).hexdigest()
    return f"{scheme}://{host}{canonical_uri}?{query}&X-Amz-Signature={signature}"


# ------------------------------------------------------------------ backends
class StorageBackend:
    name = "local"

    def signed_url(self, key: str, ttl: int) -> Optional[str]:
        return None

    async def upload(self, key: str, file_path: Path, content_type: str) -> None:  # pragma: no cover
        raise NotImplementedError


class S3Backend(StorageBackend):
    name = "s3"

    def __init__(self) -> None:
        self.endpoint = _env("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        self.bucket = _env("S3_BUCKET")
        self.region = _env("S3_REGION", "us-east-1")
        self.access_key = _env("S3_ACCESS_KEY_ID")
        self.secret_key = _env("S3_SECRET_ACCESS_KEY")
        self.path_style = _env("S3_FORCE_PATH_STYLE", "true").lower() in _TRUTHY

    def configured(self) -> bool:
        return bool(self.bucket and self.access_key and self.secret_key)

    def _presign(self, method: str, key: str, ttl: int) -> str:
        return s3_presign(
            method, endpoint=self.endpoint, bucket=self.bucket, key=key, access_key=self.access_key,
            secret_key=self.secret_key, region=self.region, expires=ttl, path_style=self.path_style,
        )

    def signed_url(self, key: str, ttl: int) -> Optional[str]:
        return self._presign("GET", key, ttl)

    async def upload(self, key: str, file_path: Path, content_type: str) -> None:
        import httpx

        url = self._presign("PUT", key, 900)
        async with httpx.AsyncClient(timeout=600) as client:
            with file_path.open("rb") as fh:
                resp = await client.put(url, content=fh.read(), headers={"content-type": content_type})
        if resp.status_code >= 300:
            raise RuntimeError(f"s3 upload failed: HTTP {resp.status_code}")


class QiniuBackend(StorageBackend):
    name = "qiniu"

    def __init__(self) -> None:
        self.bucket = _env("QINIU_BUCKET")
        self.access_key = _env("QINIU_ACCESS_KEY")
        self.secret_key = _env("QINIU_SECRET_KEY")
        self.domain = _env("QINIU_DOMAIN").rstrip("/")
        self.upload_url = _env("QINIU_UPLOAD_URL", "https://upload.qiniup.com")

    def configured(self) -> bool:
        return bool(self.bucket and self.access_key and self.secret_key and self.domain)

    def signed_url(self, key: str, ttl: int) -> Optional[str]:
        from app.services.media_delivery import _qiniu_private_download_url

        domain = self.domain if "://" in self.domain else f"https://{self.domain}"
        return _qiniu_private_download_url(
            f"{domain}/{quote(key, safe='/~')}", access_key=self.access_key,
            secret_key=self.secret_key, ttl_seconds=ttl,
        )

    async def upload(self, key: str, file_path: Path, content_type: str) -> None:
        import httpx

        from app.services.media_delivery import _qiniu_upload_token

        token = _qiniu_upload_token(self.access_key, self.secret_key, self.bucket, key)
        async with httpx.AsyncClient(timeout=600) as client:
            with file_path.open("rb") as fh:
                resp = await client.post(
                    self.upload_url, data={"token": token, "key": key},
                    files={"file": (file_path.name, fh.read(), content_type)},
                )
        if resp.status_code >= 300:
            raise RuntimeError(f"qiniu upload failed: HTTP {resp.status_code}")


_FACTORIES: dict[str, Callable[[], StorageBackend]] = {
    "local": StorageBackend, "s3": S3Backend, "qiniu": QiniuBackend,
}


def get_backend() -> StorageBackend:
    provider = storage_provider()
    factory = _FACTORIES.get(provider)
    if factory is None:
        raise RuntimeError(f"Unsupported STORAGE_PROVIDER={provider!r} (local|s3|qiniu)")
    return factory()


# ------------------------------------------------------------- markers / API
def _marker(key: str) -> Path:
    return static_root() / _MARKER_DIR / f"{key}.json"


def is_stored(key: str, provider: str) -> bool:
    try:
        data = json.loads(_marker(key).read_text("utf-8"))
    except (OSError, ValueError):
        return False
    return data.get("provider") == provider


def signed_url_for(path: str, ttl_seconds: Optional[int] = None) -> Optional[str]:
    """Provider-signed URL for an uploaded private path, else None (caller uses HMAC)."""
    provider = storage_provider()
    if provider == "local":
        return None
    key = object_key_for(path)
    if not key or not is_stored(key, provider):
        return None
    try:
        return get_backend().signed_url(key, _ttl(ttl_seconds))
    except Exception:  # pragma: no cover - never break serialization
        logger.warning("object storage signing failed for %s", key)
        return None


def _content_type(path: Path) -> str:
    import mimetypes

    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


async def persist_private_media(path: str) -> bool:
    """Upload one private /static path to the configured private bucket (idempotent)."""
    provider = storage_provider()
    if provider == "local":
        return False
    key = object_key_for(path.split("?", 1)[0])
    if not key:
        return False
    if is_stored(key, provider):
        return True
    local = static_root() / path.split("?", 1)[0][len("/static/"):]
    if not local.is_file():
        return False
    backend = get_backend()
    await backend.upload(key, local, _content_type(local))
    marker = _marker(key)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"provider": provider, "uploaded_at": int(time.time())}), "utf-8")
    return True


def _collect(value: Any, out: set[str]) -> None:
    if isinstance(value, str):
        bare = value.split("?", 1)[0]
        if object_key_for(bare):
            out.add(bare)
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, out)
    elif isinstance(value, list):
        for item in value:
            _collect(item, out)


async def persist_private_media_in_obj(value: Any) -> dict[str, bool]:
    """Upload every private path referenced in a payload; failures are logged, not raised."""
    if storage_provider() == "local":
        return {}
    paths: set[str] = set()
    _collect(value, paths)
    results: dict[str, bool] = {}
    for path in sorted(paths):
        try:
            results[path] = await persist_private_media(path)
        except Exception as exc:
            logger.warning("object storage upload failed for %s: %s", path, type(exc).__name__)
            results[path] = False
    return results


# ------------------------------------------------------------ production guard
def storage_production_problems() -> list[str]:
    provider = storage_provider()
    problems: list[str] = []
    allow_local = _env("ALLOW_LOCAL_STORAGE_IN_PRODUCTION").lower() in _TRUTHY
    if provider not in _FACTORIES:
        return [f"STORAGE_PROVIDER={provider} unsupported"]
    if provider == "local":
        if not allow_local:
            problems.append("STORAGE_PROVIDER=local (set s3|qiniu private bucket, or ALLOW_LOCAL_STORAGE_IN_PRODUCTION=1)")
        return problems
    backend = get_backend()
    if not backend.configured():  # type: ignore[attr-defined]
        problems.append(f"STORAGE_PROVIDER={provider} missing bucket/credentials")
    acl = _env("STORAGE_BUCKET_ACL", "private").lower()
    if acl != "private" or _env("STORAGE_PUBLIC_READ").lower() in _TRUTHY:
        problems.append("object storage bucket must be private (STORAGE_BUCKET_ACL=private, no STORAGE_PUBLIC_READ)")
    return problems


__all__ = [
    "get_backend", "is_stored", "object_key_for", "persist_private_media",
    "persist_private_media_in_obj", "s3_presign", "signed_url_for",
    "storage_production_problems", "storage_provider",
]
