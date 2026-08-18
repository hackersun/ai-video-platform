"""
Persist generated remote media into local static storage.

Many image/video providers return temporary URLs. Production storage can later
replace this module with object storage, but local static files give the current
platform stable history playback and cover display.
"""

from __future__ import annotations

import base64
from io import BytesIO
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from PIL import Image


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


def _image_extension_from_bytes(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    return None


def _extension_for_payload(content_type: str, media_type: str, data: bytes) -> str:
    if media_type == "image":
        detected = _image_extension_from_bytes(data)
        if detected:
            return detected
    return _extension_from_content_type(content_type, media_type)


def _optimize_image_payload(
    data: bytes,
    *,
    max_dimension: int,
    quality: int,
) -> tuple[bytes, str]:
    """Return provider-friendly JPEG bytes for generated reference images."""
    with Image.open(BytesIO(data)) as image:
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            alpha = image.getchannel("A") if "A" in image.getbands() else None
            background.paste(image.convert("RGBA"), mask=alpha)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="JPEG", quality=max(1, min(95, int(quality))), optimize=True)
        return output.getvalue(), "image/jpeg"


def _safe_static_path(subdir: str, filename: str) -> Path:
    target_dir = (STATIC_ROOT / "generated" / subdir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / filename).resolve()
    target_path.relative_to(STATIC_ROOT.resolve())
    return target_path


def persist_uploaded_media_bytes(
    data: bytes,
    *,
    media_type: str,
    content_type: str,
    subdir: str,
    prefix: str = "upload",
    max_bytes: int = 100 * 1024 * 1024,
    optimize_image: bool = False,
    image_max_dimension: int = 512,
    image_quality: int = 78,
) -> str:
    """Save uploaded media bytes into local static storage."""
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"不支持的媒体类型: {media_type}")
    if not data:
        raise ValueError("媒体文件为空")
    if len(data) > max_bytes:
        raise ValueError("媒体文件超过本地持久化大小限制")

    clean_type = (content_type or "").split(";", 1)[0].strip().lower()
    if clean_type and clean_type not in ALLOWED_CONTENT_TYPES[media_type]:
        raise ValueError(f"媒体类型不匹配: {clean_type}")

    if media_type == "image" and optimize_image:
        data, clean_type = _optimize_image_payload(
            data,
            max_dimension=image_max_dimension,
            quality=image_quality,
        )
        if len(data) > max_bytes:
            raise ValueError("媒体文件超过本地持久化大小限制")

    safe_subdir = subdir.strip("/")
    ext = _extension_for_payload(clean_type, media_type, data)
    filename = f"{prefix}-{uuid4().hex}{ext}"
    target_path = _safe_static_path(safe_subdir, filename)
    target_path.write_bytes(data)
    return f"/static/generated/{safe_subdir}/{filename}"


def persist_local_media_file(
    source: str | Path,
    *,
    media_type: str,
    subdir: str,
    prefix: str = "media",
) -> str:
    """Copy a generated local artifact into persistent static storage."""
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"不支持的媒体类型: {media_type}")
    source_path = Path(source)
    if not source_path.is_file():
        raise ValueError("本地媒体文件不存在")
    suffix = source_path.suffix.lower() or DEFAULT_EXTENSIONS[media_type]
    target_path = _safe_static_path(subdir.strip("/"), f"{prefix}-{uuid4().hex}{suffix}")
    shutil.copy2(source_path, target_path)
    return f"/static/generated/{subdir.strip('/')}/{target_path.name}"


def _persist_data_url(
    url: str,
    *,
    media_type: str,
    subdir: str,
    prefix: str,
    max_bytes: int,
    optimize_image: bool,
    image_max_dimension: int,
    image_quality: int,
) -> Optional[str]:
    match = re.match(r"^data:([^;,]+);base64,(.+)$", url, flags=re.DOTALL)
    if not match:
        return url
    content_type, encoded = match.groups()
    clean_type = content_type.split(";", 1)[0].strip().lower()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"不支持的媒体类型: {media_type}")
    if clean_type not in ALLOWED_CONTENT_TYPES[media_type]:
        raise ValueError(f"媒体类型不匹配: {clean_type}")
    data = base64.b64decode(re.sub(r"\s+", "", encoded), validate=True)
    return persist_uploaded_media_bytes(
        data,
        media_type=media_type,
        content_type=clean_type,
        subdir=subdir,
        prefix=prefix,
        max_bytes=max_bytes,
        optimize_image=optimize_image,
        image_max_dimension=image_max_dimension,
        image_quality=image_quality,
    )


async def persist_remote_media_url(
    url: Optional[str],
    *,
    media_type: str,
    subdir: str,
    prefix: str = "media",
    timeout_seconds: float = 60.0,
    max_bytes: int = 100 * 1024 * 1024,
    optimize_image: bool = False,
    image_max_dimension: int = 512,
    image_quality: int = 78,
) -> Optional[str]:
    """Download a remote media URL and return a stable /static/... URL.

    Returns the original URL if it is already local/static or not HTTP(S).
    Raises on HTTP, content-type, or size failures so callers can decide whether
    to fall back to the provider URL.
    """
    if not url:
        return None
    if is_local_static_url(url):
        return url
    if url.startswith("data:"):
        return _persist_data_url(
            url,
            media_type=media_type,
            subdir=subdir,
            prefix=prefix,
            max_bytes=max_bytes,
            optimize_image=optimize_image,
            image_max_dimension=image_max_dimension,
            image_quality=image_quality,
        )

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"不支持的媒体类型: {media_type}")

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, trust_env=False) as client:
        response = await client.get(url, headers={"Accept": f"{media_type}/*"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in ALLOWED_CONTENT_TYPES[media_type]:
            raise ValueError(f"媒体类型不匹配: {content_type}")
        data = response.content

    if len(data) > max_bytes:
        raise ValueError("媒体文件超过本地持久化大小限制")

    if media_type == "image" and optimize_image:
        data, content_type = _optimize_image_payload(
            data,
            max_dimension=image_max_dimension,
            quality=image_quality,
        )
        if len(data) > max_bytes:
            raise ValueError("媒体文件超过本地持久化大小限制")

    ext = _extension_for_payload(content_type, media_type, data)
    filename = f"{prefix}-{uuid4().hex}{ext}"
    target_path = _safe_static_path(subdir, filename)
    target_path.write_bytes(data)
    return f"/static/generated/{subdir}/{filename}"
