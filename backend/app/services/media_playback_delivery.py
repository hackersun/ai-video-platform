"""Resolve safe local playback fallbacks for development deliveries."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


def dev_local_static_delivery_url(
    media_url: str | None, local_path: Path | None, *, enabled: bool,
) -> str | None:
    if not enabled or local_path is None or not local_path.is_file() or not media_url:
        return None
    path = urlparse(media_url).path
    if not path.startswith("/static/"):
        return None
    return f"http://127.0.0.1:8000{path}"
