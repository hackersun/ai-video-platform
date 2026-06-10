"""
Development-mode media generation helpers.

These helpers make the local novel-to-video flow verifiable without cloud
provider keys. Production paths still require configured provider credentials.
"""

from __future__ import annotations

import base64
import hashlib
import math
import os
import struct
import zlib
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
DEV_DIR = STATIC_DIR / "dev"
DEV_PREVIEW_VIDEO = Path(__file__).resolve().parents[1] / "static_assets" / "dev_preview.mp4"
DEV_VIDEO_MIN_BYTES = 10_000
DEV_IMAGE_MIN_BYTES = 100

_DEV_PLACEHOLDER_MP4_B64 = """
AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAB3NtZGF0AAACrQYF//+p3EXpvebZSLeWLNgg2SPu
73gyNjQgLSBjb3JlIDE2NCByMzE5MCA3ZWQ3NTNiIC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMt
MjAyNCAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9j
az0xOjA6MCBhbmFseXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3Jl
Zj0xIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0
X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTYgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFk
cz0wIG5yPTAgZGVjaW1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZy
YW1lcz0zIGJfcHlyYW1pZD0yIGJfYWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9MCB3ZWln
aHRwPTIga2V5aW50PTI1MCBrZXlpbnRfbWluPTYgc2NlbmVjdXQ9NDAgaW50cmFfcmVmcmVzaD0wIHJjX2xvb2thaGVhZD00
MCByYz1jcmYgbWJ0cmVlPTEgY3JmPTIzLjAgcWNvbXA9MC42MCBxcG1pbj0wIHFwbWF4PTY5IHFwc3RlcD00IGlwX3JhdGlv
PTEuNDAgYXE9MToxLjAwAIAAAAD4ZYiEABH//ufj/AptgQHv9Zl6045UXRrw6uMQp5BdGYyP6+oAC94lWL6tvpweS/wKKAAA
hoCgVqU2rZsFa313crwioQcskVXQiSsSqJthwuqZxhTei8akJ0ssm3AOxxXOJMpq76f+6SzKj+4DZByplRo96/kKOyKx+75y
shBSdF/1BCHgtepNByjfIwAxtrz8/9NxiJ0xvtSKyQYQCtNR6pjDSq5EjCss3x8aesEn9L206eprkC/UfiiLiX3NmybcEx0K
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
TGF2ZjYxLjcuMTAw
"""


def _ensure_dev_video_file(filename: str) -> None:
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    video_path = DEV_DIR / filename
    if video_path.exists() and video_path.stat().st_size >= DEV_VIDEO_MIN_BYTES:
        return
    if DEV_PREVIEW_VIDEO.exists():
        video_path.write_bytes(DEV_PREVIEW_VIDEO.read_bytes())
    else:
        video_path.write_bytes(base64.b64decode("".join(_DEV_PLACEHOLDER_MP4_B64.split())))


def _ensure_dev_audio_file(filename: str) -> None:
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = DEV_DIR / filename
    if not audio_path.exists():
        # A tiny placeholder payload is enough for local artifact/link tests. It is
        # intentionally not presented as production-quality generated speech.
        audio_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")


def _ensure_dev_wav_file(filename: str, frequency: int = 440, duration_seconds: float = 1.0) -> None:
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = DEV_DIR / filename
    if audio_path.exists() and audio_path.stat().st_size > 1024:
        return
    sample_rate = 16_000
    sample_count = int(sample_rate * duration_seconds)
    frames = bytearray()
    for index in range(sample_count):
        envelope = min(1.0, index / 800, (sample_count - index) / 800)
        sample = int(18000 * envelope * math.sin(2 * math.pi * frequency * index / sample_rate))
        frames.extend(struct.pack("<h", sample))

    data_size = len(frames)
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", data_size)
    )
    audio_path.write_bytes(header + frames)


def _safe_token(value: str, fallback: str = "media") -> str:
    token = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(value))
    token = token.strip("-_")[:80]
    return token or fallback


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _build_dev_png(label: str, width: int = 512, height: int = 512) -> bytes:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    base = (digest[0], digest[1], digest[2])
    accent = (digest[3], digest[4], digest[5])
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            diagonal = (x + y) % 128 < 64
            blend = (x + y) / max(1, width + height - 2)
            r = int(base[0] * (1 - blend) + accent[0] * blend)
            g = int(base[1] * (1 - blend) + accent[1] * blend)
            b = int(base[2] * (1 - blend) + accent[2] * blend)
            if diagonal:
                r = min(255, r + 24)
                g = min(255, g + 24)
                b = min(255, b + 24)
            if 40 < x < width - 40 and 40 < y < height - 40:
                r = int(r * 0.86)
                g = int(g * 0.90)
                b = min(255, int(b * 1.08) + 10)
            row.extend((r, g, b))
        rows.append(b"\x00" + bytes(row))

    compressed = zlib.compress(b"".join(rows), level=9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _ensure_dev_image_file(filename: str, label: str) -> None:
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    image_path = DEV_DIR / filename
    if image_path.exists() and image_path.stat().st_size >= DEV_IMAGE_MIN_BYTES:
        return
    image_path.write_bytes(_build_dev_png(label or filename))


def is_dev_mode() -> bool:
    return os.getenv("DEV_MODE", "true").lower() in {"true", "1", "yes"}


def dev_image_url(job_id: str, label: str = "AI Video") -> str:
    token = _safe_token(job_id, "image")
    filename = f"image-{token}.png"
    _ensure_dev_image_file(filename, f"{label}-{job_id}")
    return f"/static/dev/{filename}"


def dev_audio_url(job_id: str) -> str:
    _ensure_dev_audio_file(f"audio-{job_id}.mp3")
    return f"/static/dev/audio-{job_id}.mp3"


def dev_tts_audio_url(job_id: str) -> str:
    token = _safe_token(job_id, "tts")
    _ensure_dev_wav_file(f"tts-{token}.wav")
    return f"/static/dev/tts-{token}.wav"


def dev_video_url(job_id: str) -> str:
    _ensure_dev_video_file(f"video-{job_id}.mp4")
    return f"/static/dev/video-{job_id}.mp4"


def dev_synthesis_url(job_id: str) -> str:
    _ensure_dev_video_file(f"final-{job_id}.mp4")
    return f"/static/dev/final-{job_id}.mp4"


def estimate_tts_duration_seconds(text: str, speed: float = 1.0) -> float:
    clean_text = text.strip()
    if not clean_text:
        return 0.0
    chars_per_second = max(2.0, 4.5 * max(speed, 0.1))
    return round(max(1.0, len(clean_text) / chars_per_second), 2)
