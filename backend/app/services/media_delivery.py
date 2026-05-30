"""Resolve local media references into provider-accessible URLs."""

from __future__ import annotations

import ipaddress
from typing import Any, Optional
from urllib.parse import quote, urlparse

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_api import ExternalAPIConfig, ExternalAPIProvider
from app.services.media_persistence import is_local_static_url


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
) -> Optional[tuple[ExternalAPIConfig, ExternalAPIProvider]]:
    result = await db.execute(
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
        .order_by(
            desc(ExternalAPIConfig.is_default),
            desc(ExternalAPIConfig.updated_at),
            desc(ExternalAPIConfig.created_at),
        )
        .limit(1)
    )
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


async def resolve_provider_media_url(
    db: AsyncSession,
    user_id: str,
    media_url: Optional[str],
    *,
    media_type: str = "image",
) -> dict[str, Any]:
    """Resolve a media URL into a URL safe to send to cloud providers."""
    if not media_url:
        return {
            "source_url": media_url,
            "provider_url": None,
            "image_url_sent": False,
            "delivery_method": None,
            "omitted_reason": None,
        }

    source_url = media_url.strip()
    if is_cloud_accessible_http_url(source_url):
        return {
            "source_url": source_url,
            "provider_url": source_url,
            "image_url_sent": True,
            "delivery_method": "direct_public_url",
            "omitted_reason": None,
        }

    if not is_local_static_url(source_url):
        return {
            "source_url": source_url,
            "provider_url": None,
            "image_url_sent": False,
            "delivery_method": None,
            "omitted_reason": f"参考{media_type}不是公网 http(s) URL，云端模型无法直接访问",
        }

    storage = await _get_default_storage_config(db, user_id)
    if not storage:
        return {
            "source_url": source_url,
            "provider_url": None,
            "image_url_sent": False,
            "delivery_method": None,
            "omitted_reason": "参考图是本地静态资源，未配置对象存储/CDN公网出口，云端模型无法直接访问",
        }

    config, provider = storage
    extra = config.extra_config or {}
    if config.test_status not in READY_CONFIG_STATUSES and not extra.get("allow_unverified"):
        return {
            "source_url": source_url,
            "provider_url": None,
            "image_url_sent": False,
            "delivery_method": None,
            "storage_config_id": config.id,
            "omitted_reason": "对象存储/CDN配置尚未测试通过，未将本地参考图转换为公网 URL",
        }

    public_base_url = (extra.get("public_base_url") or config.custom_base_url or provider.base_url or "").strip()
    if not is_cloud_accessible_http_url(public_base_url):
        return {
            "source_url": source_url,
            "provider_url": None,
            "image_url_sent": False,
            "delivery_method": None,
            "storage_config_id": config.id,
            "omitted_reason": "对象存储/CDN公网基础地址无效，必须是云端可访问的 http(s) URL",
        }

    provider_url = _public_static_url(
        source_url,
        public_base_url=public_base_url,
        local_static_prefix=extra.get("local_static_prefix") or "/static/",
        public_static_prefix=extra.get("public_static_prefix") or "/static/",
    )
    if not provider_url or not is_cloud_accessible_http_url(provider_url):
        return {
            "source_url": source_url,
            "provider_url": None,
            "image_url_sent": False,
            "delivery_method": None,
            "storage_config_id": config.id,
            "omitted_reason": "对象存储/CDN配置无法映射当前本地静态资源路径",
        }

    return {
        "source_url": source_url,
        "provider_url": provider_url,
        "image_url_sent": True,
        "delivery_method": "public_static_base_url",
        "storage_config_id": config.id,
        "storage_config_name": config.name,
        "storage_provider_id": provider.id,
        "storage_provider_name": provider.name_cn or provider.name,
        "public_base_url": public_base_url,
        "omitted_reason": None,
    }
