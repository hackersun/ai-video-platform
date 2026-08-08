"""Resolve local media references into provider-accessible URLs."""

from __future__ import annotations

import ipaddress
import base64
import hashlib
import hmac
import json
import mimetypes
import time
from typing import Any, Optional
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

import httpx
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_api import ExternalAPIConfig, ExternalAPIProvider
from app.services.media_persistence import is_local_static_url, local_static_path_for_url


READY_CONFIG_STATUSES = {"success", "configured"}


def is_cloud_accessible_http_url(url: Optional[str]) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    host = hostname.lower()
    if host in {"localhost", "local"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return ip.is_global


async def _get_default_storage_config(
    db: AsyncSession,
    user_id: str,
    storage_config_id: Optional[str] = None,
) -> Optional[tuple[ExternalAPIConfig, ExternalAPIProvider]]:
    query = (
        select(ExternalAPIConfig, ExternalAPIProvider)
        .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
        .where(
            and_(
                ExternalAPIConfig.user_id == user_id,
                ExternalAPIConfig.is_active == True,
                ExternalAPIProvider.is_active == True,
                ExternalAPIProvider.api_type == "storage",
            )
        )
    )
    if storage_config_id:
        query = query.where(ExternalAPIConfig.id == storage_config_id)
    else:
        query = query.order_by(
            desc(ExternalAPIConfig.is_default),
            desc(ExternalAPIConfig.updated_at),
            desc(ExternalAPIConfig.created_at),
        )
    result = await db.execute(query.limit(1))
    row = result.first()
    if not row:
        return None
    return row[0], row[1]


def _public_static_url(
    local_url: str,
    *,
    public_base_url: str,
    local_static_prefix: str = "/static/",
    public_static_prefix: str = "/static/",
) -> Optional[str]:
    parsed = urlparse(local_url)
    path = parsed.path or local_url
    local_prefix = f"/{local_static_prefix.strip('/')}/"
    public_prefix = f"/{public_static_prefix.strip('/')}"
    if not path.startswith(local_prefix):
        return None
    suffix = path[len(local_prefix) :]
    encoded_suffix = quote(suffix, safe="/-._~")
    public_url = f"{public_base_url.rstrip('/')}{public_prefix}/{encoded_suffix}"
    if parsed.query:
        public_url = f"{public_url}?{parsed.query}"
    return public_url


def _static_object_key(
    local_url: str,
    *,
    local_static_prefix: str = "/static/",
    public_static_prefix: str = "/static/",
) -> Optional[str]:
    parsed = urlparse(local_url)
    path = parsed.path or local_url
    local_prefix = f"/{local_static_prefix.strip('/')}/"
    if not path.startswith(local_prefix):
        return None
    suffix = path[len(local_prefix) :].lstrip("/")
    public_prefix = str(public_static_prefix or "").strip("/")
    return f"{public_prefix}/{suffix}".strip("/")


def _qiniu_upload_token(access_key: str, secret_key: str, bucket: str, object_key: str) -> str:
    deadline = int(time.time()) + 3600
    policy = {"scope": f"{bucket}:{object_key}", "deadline": deadline}
    encoded_policy = base64.urlsafe_b64encode(
        json.dumps(policy, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    digest = hmac.new(secret_key.encode("utf-8"), encoded_policy.encode("ascii"), hashlib.sha1).digest()
    encoded_sign = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{access_key}:{encoded_sign}:{encoded_policy}"


def _qiniu_private_download_url(
    public_url: str,
    *,
    access_key: str,
    secret_key: str,
    ttl_seconds: int,
) -> str:
    separator = "&" if "?" in public_url else "?"
    # Qiniu private source domains reject large `e` deltas; keep delivery URLs short-lived.
    safe_ttl_seconds = min(max(ttl_seconds, 60), 300)
    deadline = int(time.time()) + safe_ttl_seconds
    url_with_deadline = f"{public_url}{separator}e={deadline}"
    digest = hmac.new(secret_key.encode("utf-8"), url_with_deadline.encode("utf-8"), hashlib.sha1).digest()
    encoded_sign = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{url_with_deadline}&token={access_key}:{encoded_sign}"


def _without_qiniu_signature(public_url: str) -> str:
    parsed = urlparse(public_url)
    query = urlencode([(key, value) for key, value in parse_qsl(parsed.query) if key not in {"e", "token"}])
    return urlunparse(parsed._replace(query=query))


async def upload_local_static_to_qiniu(
    local_url: str,
    *,
    access_key: str,
    secret_key: str,
    public_base_url: str,
    params: dict[str, Any],
    object_key_override: str | None = None,
    timeout: float = 60,
) -> dict[str, Any]:
    access_key = str(access_key or "").strip()
    secret_key = str(secret_key or "").strip()
    bucket = str(params.get("bucket") or params.get("bucket_name") or "").strip()
    if not access_key or not secret_key or not bucket:
        return {
            "provider_url": None,
            "omitted_reason": "七牛对象存储需要配置 Access Key、Secret Key 和 bucket，不能仅映射公网域名",
        }
    if object_key_override and not (params.get("private_download") or params.get("private_bucket")):
        return {
            "provider_url": None,
            "omitted_reason": "正式媒体必须使用七牛私有桶并启用短时下载签名",
        }

    local_path = local_static_path_for_url(local_url)
    if not local_path or not local_path.exists() or not local_path.is_file():
        return {
            "provider_url": None,
            "omitted_reason": "本地静态参考图文件不存在，无法上传到七牛对象存储",
        }
    object_key = object_key_override or _static_object_key(
        local_url, local_static_prefix=str(params.get("local_static_prefix") or "/static/"),
        public_static_prefix=str(params.get("public_static_prefix") or "/static/"),
    )
    if not object_key:
        return {
            "provider_url": None,
            "omitted_reason": "对象存储配置无法映射当前本地静态资源路径",
        }

    upload_url = str(params.get("upload_url") or "https://upload.qiniup.com").strip()
    content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    token = _qiniu_upload_token(access_key, secret_key, bucket, object_key)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.post(
            upload_url,
            data={"token": token, "key": object_key},
            files={"file": (local_path.name, local_path.read_bytes(), content_type)},
        )
        response.raise_for_status()

    public_url = f"{public_base_url.rstrip('/')}/{quote(object_key, safe='/-._~')}"
    if params.get("private_download") or params.get("private_bucket"):
        public_url = _qiniu_private_download_url(
            public_url,
            access_key=access_key,
            secret_key=secret_key,
            ttl_seconds=int(params.get("download_url_ttl_seconds") or 3600),
        )
    return {
        "provider_url": public_url,
        "object_key": object_key,
        "omitted_reason": None,
    }


async def refresh_existing_qiniu_media_url(
    db: AsyncSession,
    user_id: str,
    media_url: Optional[str],
    *,
    storage_config_id: Optional[str] = None,
    object_key: str | None = None,
) -> dict[str, Any]:
    """Create a fresh download URL for an already-uploaded static object."""
    source_url = str(media_url or "").strip()
    storage = await _get_default_storage_config(db, user_id, storage_config_id)
    if not source_url or not storage:
        return {"provider_url": None, "delivery_method": None}
    config, provider = storage
    extra = config.extra_config or {}
    storage_provider = str(extra.get("storage_provider") or extra.get("provider") or "").strip().lower()
    if storage_provider not in {"qiniu", "kodo", "qiniu_kodo"}:
        return {"provider_url": None, "delivery_method": None}
    public_base_url = str(extra.get("public_base_url") or config.custom_base_url or provider.base_url or "").strip()
    public_url = (
        f"{public_base_url.rstrip('/')}/{quote(object_key, safe='/-._~')}" if object_key else
        _public_static_url(
            source_url, public_base_url=public_base_url,
            local_static_prefix=extra.get("local_static_prefix") or "/static/",
            public_static_prefix=extra.get("public_static_prefix") or "/static/",
        )
    )
    if not public_url or not is_cloud_accessible_http_url(public_url):
        return {"provider_url": None, "delivery_method": None}
    if extra.get("private_download") or extra.get("private_bucket"):
        access_key = config.get_api_key_decrypted()
        secret_key = config.get_api_secret_decrypted()
        if not access_key or not secret_key:
            return {"provider_url": None, "delivery_method": None}
        public_url = _without_qiniu_signature(public_url)
        public_url = _qiniu_private_download_url(
            public_url,
            access_key=access_key,
            secret_key=secret_key,
            ttl_seconds=int(extra.get("download_url_ttl_seconds") or 3600),
        )
    return {
        "provider_url": public_url,
        "delivery_method": "qiniu_signed_refresh",
        "storage_config_id": config.id,
    }


def _unavailable_delivery(
    source_url: str | None, reason: str | None, *, config: Any = None,
    provider: Any = None, public_base_url: str | None = None,
) -> dict[str, Any]:
    result = {
        "source_url": source_url, "provider_url": None, "image_url_sent": False,
        "delivery_method": None, "omitted_reason": reason,
    }
    if config is not None:
        result.update(storage_config_id=config.id, storage_config_name=config.name)
    if provider is not None:
        result.update(
            storage_provider_id=provider.id,
            storage_provider_name=provider.name_cn or provider.name,
        )
    if public_base_url:
        result["public_base_url"] = public_base_url
    return result


async def _resolve_qiniu_delivery(
    source_url: str, *, config: Any, provider: Any, extra: dict[str, Any],
    public_base_url: str, object_key_override: str | None,
) -> dict[str, Any]:
    upload = await upload_local_static_to_qiniu(
        source_url, access_key=config.get_api_key_decrypted(),
        secret_key=config.get_api_secret_decrypted(), public_base_url=public_base_url,
        params=extra, object_key_override=object_key_override,
        timeout=float(getattr(config, "timeout", None) or 60),
    )
    provider_url = upload.get("provider_url")
    if not provider_url or not is_cloud_accessible_http_url(provider_url):
        return _unavailable_delivery(
            source_url, upload.get("omitted_reason") or "七牛对象存储上传失败，未生成可用公网 URL",
            config=config, provider=provider, public_base_url=public_base_url,
        )
    return {
        "source_url": source_url, "provider_url": provider_url, "image_url_sent": True,
        "delivery_method": "qiniu_object_upload", "storage_config_id": config.id,
        "storage_config_name": config.name, "storage_provider_id": provider.id,
        "storage_provider_name": provider.name_cn or provider.name,
        "public_base_url": public_base_url, "object_key": upload.get("object_key"),
        "omitted_reason": None,
    }


async def _resolve_local_delivery(
    db: AsyncSession, user_id: str, source_url: str, *,
    storage_config_id: str | None, object_key_override: str | None,
) -> dict[str, Any]:
    storage = (
        await _get_default_storage_config(db, user_id, storage_config_id=storage_config_id)
        if storage_config_id else await _get_default_storage_config(db, user_id)
    )
    if not storage:
        return _unavailable_delivery(
            source_url, "参考图是本地静态资源，未配置对象存储/CDN公网出口，云端模型无法直接访问",
        )
    config, provider = storage
    extra = config.extra_config or {}
    if config.test_status not in READY_CONFIG_STATUSES and not extra.get("allow_unverified"):
        return _unavailable_delivery(
            source_url, "对象存储/CDN配置尚未测试通过，未将本地参考图转换为公网 URL", config=config,
        )
    public_base_url = (extra.get("public_base_url") or config.custom_base_url or provider.base_url or "").strip()
    if not is_cloud_accessible_http_url(public_base_url):
        return _unavailable_delivery(
            source_url, "对象存储/CDN公网基础地址无效，必须是云端可访问的 http(s) URL", config=config,
        )
    provider_url = _public_static_url(
        source_url, public_base_url=public_base_url,
        local_static_prefix=extra.get("local_static_prefix") or "/static/",
        public_static_prefix=extra.get("public_static_prefix") or "/static/",
    )
    if not provider_url or not is_cloud_accessible_http_url(provider_url):
        return _unavailable_delivery(
            source_url, "对象存储/CDN配置无法映射当前本地静态资源路径", config=config,
        )
    storage_provider = str(extra.get("storage_provider") or extra.get("provider") or "").strip().lower()
    if storage_provider in {"qiniu", "kodo", "qiniu_kodo"}:
        return await _resolve_qiniu_delivery(
            source_url, config=config, provider=provider, extra=extra,
            public_base_url=public_base_url, object_key_override=object_key_override,
        )
    return {
        "source_url": source_url, "provider_url": provider_url, "image_url_sent": True,
        "delivery_method": "public_static_base_url", "storage_config_id": config.id,
        "storage_config_name": config.name, "storage_provider_id": provider.id,
        "storage_provider_name": provider.name_cn or provider.name,
        "public_base_url": public_base_url, "omitted_reason": None,
    }


async def resolve_provider_media_url(
    db: AsyncSession, user_id: str, media_url: Optional[str], *,
    media_type: str = "image", storage_config_id: Optional[str] = None,
    object_key_override: str | None = None,
) -> dict[str, Any]:
    """Resolve a media URL into a URL safe to send to cloud providers."""
    if not media_url:
        return _unavailable_delivery(media_url, None)
    source_url = media_url.strip()
    if is_cloud_accessible_http_url(source_url):
        return {
            "source_url": source_url, "provider_url": source_url, "image_url_sent": True,
            "delivery_method": "direct_public_url", "omitted_reason": None,
        }
    if not is_local_static_url(source_url):
        return _unavailable_delivery(
            source_url, f"参考{media_type}不是公网 http(s) URL，云端模型无法直接访问",
        )
    return await _resolve_local_delivery(
        db, user_id, source_url, storage_config_id=storage_config_id,
        object_key_override=object_key_override,
    )
