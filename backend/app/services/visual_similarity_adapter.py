"""Local image similarity adapter for visual consistency evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

from PIL import Image


BACKEND_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = BACKEND_ROOT / "static"
SAMPLE_SIZE = (32, 32)


def score_local_visual_similarity(
    *,
    reference_url: str,
    frame_urls: List[str],
) -> Optional[Dict[str, Any]]:
    """Score local frame similarity against a local reference image."""
    reference_path = _local_static_path(reference_url)
    if reference_path is None or not reference_path.exists():
        return None

    frame_scores: List[float] = []
    for frame_url in frame_urls:
        frame_path = _local_static_path(frame_url)
        if frame_path is None or not frame_path.exists():
            continue
        score = _image_similarity_score(reference_path, frame_path)
        if score is not None:
            frame_scores.append(score)

    if not frame_scores:
        return None

    average_score = round(sum(frame_scores) / len(frame_scores), 2)
    return {
        "score": average_score,
        "model": "local-image-rgb",
        "method": "local_rgb_mean_absolute_difference",
        "frame_count": len(frame_scores),
        "frame_scores": [_compact_score(score) for score in frame_scores],
    }


def _compact_score(score: float) -> float | int:
    rounded = round(score, 2)
    return int(rounded) if rounded.is_integer() else rounded


def _image_similarity_score(reference_path: Path, frame_path: Path) -> Optional[float]:
    try:
        with Image.open(reference_path) as reference_image, Image.open(frame_path) as frame_image:
            reference_pixels = list(reference_image.convert("RGB").resize(SAMPLE_SIZE).getdata())
            frame_pixels = list(frame_image.convert("RGB").resize(SAMPLE_SIZE).getdata())
    except Exception:
        return None

    if not reference_pixels or len(reference_pixels) != len(frame_pixels):
        return None

    total_diff = 0
    channel_count = 0
    for reference_pixel, frame_pixel in zip(reference_pixels, frame_pixels):
        for reference_value, frame_value in zip(reference_pixel, frame_pixel):
            total_diff += abs(reference_value - frame_value)
            channel_count += 1

    if channel_count == 0:
        return None
    mean_diff = total_diff / channel_count
    return round(max(0.0, 100.0 * (1.0 - mean_diff / 255.0)), 2)


def _local_static_path(url: str) -> Optional[Path]:
    raw_url = str(url or "")
    parsed = urlparse(raw_url)
    if parsed.scheme in {"http", "https"}:
        if parsed.hostname not in {"localhost", "127.0.0.1", "0.0.0.0"}:
            return None
        path = parsed.path
    elif parsed.scheme:
        return None
    else:
        path = raw_url

    if not path.startswith("/static/"):
        return None

    static_root = STATIC_ROOT.resolve(strict=False)
    candidate = (static_root / Path(unquote(path).removeprefix("/static/"))).resolve(strict=False)
    try:
        candidate.relative_to(static_root)
    except ValueError:
        return None
    return candidate
