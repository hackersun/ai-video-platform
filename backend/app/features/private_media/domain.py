"""Pure private-media policies."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlsplit, urlunsplit


RETENTION_DAYS = {"original": 30, "process": 90, "final": 365}


@dataclass(frozen=True)
class LifecyclePolicy:
    object_key: str
    retention_days: int


@dataclass(frozen=True)
class SanitizedProviderUrl:
    canonical_url: str
    url_fingerprint: str
    expires_at: datetime | None


def lifecycle_policy(lifecycle_class: str, *, user_id: str, filename: str) -> LifecyclePolicy:
    if lifecycle_class not in RETENTION_DAYS:
        raise ValueError("媒体生命周期分类必须是 original、process 或 final")
    safe_user = PurePosixPath(str(user_id)).name
    safe_name = PurePosixPath(str(filename)).name
    if not safe_user or not safe_name:
        raise ValueError("媒体用户和文件名不能为空")
    return LifecyclePolicy(
        object_key=f"private/{lifecycle_class}/{safe_user}/{safe_name}",
        retention_days=RETENTION_DAYS[lifecycle_class],
    )


def sanitize_provider_url(url: str, *, now: datetime | None = None) -> SanitizedProviderUrl:
    del now
    parsed = urlsplit(str(url or "").strip())
    canonical = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    query = parse_qs(parsed.query)
    expires_at = None
    if query.get("e"):
        try:
            expires_at = datetime.fromtimestamp(int(query["e"][0]), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            expires_at = None
    return SanitizedProviderUrl(
        canonical_url=canonical,
        url_fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        expires_at=expires_at,
    )


def is_private_delivery_url(
    url: str, *, now: datetime | None = None, max_ttl_seconds: int = 600,
) -> bool:
    parsed = urlsplit(str(url or "").strip())
    query = parse_qs(parsed.query)
    if not parsed.scheme or not parsed.netloc or not query.get("token") or not query.get("e"):
        return False
    try:
        deadline = datetime.fromtimestamp(int(query["e"][0]), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return False
    current = now or datetime.now(timezone.utc)
    remaining = (deadline - current).total_seconds()
    return 0 < remaining <= max_ttl_seconds
