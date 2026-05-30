"""
Persist generated remote media into local static storage.

Many image/video providers return temporary URLs. Production storage can later
replace this module with object storage, but local static files give the current
platform stable history playback and cover display.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx


STATIC_ROOT = Path(__file__).resolve().parents[2] / "static"

ALLOWED_CONTENT_TYPES = {
    "image": {"image/jpeg", "image/png", "image/webp", "image/gif"},
    "video": {"video/mp4", "video/webm", "video/quicktime"},
    "audio": {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/aac", "audio/ogg"},
    "artifact": {
        "application/json",
        "text/plain",
        "text/html",
        "text/vtt",
        "application/x-subrip",
        "application/octet-stream",
    },
}

DEFAULT_EXTENSIONS = {
    "image": ".png",
    "video": ".mp4",
    "audio": ".mp3",
    "artifact": ".txt",
}


def is_local_static_url(url: Optional[str]) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return not parsed.scheme and (parsed.path or url).startswith("/static/")


def local_static_path_for_url(url: Optional[str]) -> Optional[Path]:
    """Resolve /static URLs to local filesystem paths when possible."""
    if not url:
        return None
    parsed = urlparse(url)
    media_path = parsed.path if parsed.scheme else url
    if not media_path.startswith("/static/"):
        return None
    relative = media_path.removeprefix("/static/").lstrip("/")
    target = (STATIC_ROOT / relative).resolve()
    try:
        target.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return None
    return target


def audit_media_url(url: Optional[str]) -> dict:
    """Return a lightweight persistence status for a media URL."""
    if not url:
        return {"status": "missing", "persistent": False, "exists": False}
    if url.startswith("data:"):
        return {"status": "embedded_data", "persistent": True, "exists": True}
    parsed = urlparse(url)
    local_path = local_static_path_for_url(url)
    if local_path is not None:
        exists = local_path.exists() and local_path.is_file()
        return {
            "status": "local_ok" if exists else "local_missing",
            "persistent": exists,
            "exists": exists,
            "path": str(local_path),
        }
    if parsed.scheme in {"http", "https"}:
        return {"status": "remote", "persistent": False, "exists": None}
    return {"status": "external_reference", "persistent": False, "exists": None}


def _extension_from_content_type(content_type: str, media_type: str) -> str:
    clean_type = (content_type or "").split(";", 1)[0].strip().lower()
    guessed = mimetypes.guess_extension(clean_type) if clean_type else None
    if guessed == ".jpe":
        guessed = ".jpg"
    return guessed or DEFAULT_EXTENSIONS[media_type]


def _safe_static_path(subdir: str, filename: str) -> Path:
    target_dir = (STATIC_ROOT / "generated" / subdir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / filename).resolve()
    target_path.relative_to(STATIC_ROOT.resolve())
    return target_path


async def persist_remote_media_url(
    url: Optional[str],
    *,
    media_type: str,
    subdir: str,
    prefix: str = "media",
    timeout_seconds: float = 60.0,
    max_bytes: int = 100 * 1024 * 1024,
) -> Optional[str]:
    """Download a remote media URL and return a stable /static/... URL.

    Returns the original URL if it is already local/static or not HTTP(S).
    Raises on HTTP, content-type, or size failures so callers can decide whether
    to fall back to the provider URL.
    """
    if not url:
        return None
    if is_local_static_url(url) or url.startswith("data:"):
        return url

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"不支持的媒体类型: {media_type}")

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(url, headers={"Accept": f"{media_type}/*"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in ALLOWED_CONTENT_TYPES[media_type]:
            raise ValueError(f"媒体类型不匹配: {content_type}")
        data = response.content

    if len(data) > max_bytes:
        raise ValueError("媒体文件超过本地持久化大小限制")

    ext = _extension_from_content_type(content_type, media_type)
    filename = f"{prefix}-{uuid4().hex}{ext}"
    target_path = _safe_static_path(subdir, filename)
    target_path.write_bytes(data)
    return f"/static/generated/{subdir}/{filename}"
