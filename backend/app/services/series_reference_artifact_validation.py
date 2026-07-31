"""Fetch and validate a generated composite series-reference image."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app.services.reference_layout_evaluator import (
    ReferenceLayoutValidationError,
    evaluate_reference_layout,
)


class ReferenceArtifactValidationError(ValueError):
    def __init__(self, message: str, *, failure_evidence: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.failure_evidence = failure_evidence


async def fetch_and_verify_reference_image(public_url: str) -> dict[str, Any]:
    max_bytes = 10 * 1024 * 1024
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, trust_env=False) as client:
            response = await client.get(public_url, headers={"Accept": "image/*"})
            response.raise_for_status()
    except (httpx.HTTPError, ValueError) as error:
        raise ReferenceArtifactValidationError("reference artifact URL is not fetchable") from error
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ReferenceArtifactValidationError("reference artifact content type is not an allowed image")
    content_length = response.headers.get("content-length")
    try:
        if content_length is not None and int(content_length) > max_bytes:
            raise ReferenceArtifactValidationError("reference artifact exceeds size limit")
    except ValueError as error:
        raise ReferenceArtifactValidationError("reference artifact content length is invalid") from error
    data = response.content
    if not data or len(data) > max_bytes:
        raise ReferenceArtifactValidationError("reference artifact bytes are missing or oversized")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            width, height = image.size
            image_format = str(image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ReferenceArtifactValidationError("reference artifact is not a decodable image") from error
    if width < 1024 or height < 768:
        raise ReferenceArtifactValidationError("reference artifact pixel dimensions are too small")
    try:
        layout_evidence = evaluate_reference_layout(data)
    except ReferenceLayoutValidationError as error:
        raise ReferenceArtifactValidationError(
            f"reference layout evidence failed: {error}",
            failure_evidence=error.summary,
        ) from error
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_size": len(data),
        "content_type": content_type,
        "width": width,
        "height": height,
        "format": image_format,
        "layout_evidence": layout_evidence,
    }


__all__ = ["ReferenceArtifactValidationError", "fetch_and_verify_reference_image"]
