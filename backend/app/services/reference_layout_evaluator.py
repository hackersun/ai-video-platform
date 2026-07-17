"""Pixel-derived structural evidence for composite anime reference boards.

This evaluator proves only that the expected multi-panel layout contains
non-empty, related-but-non-identical character panels and a visually populated
style/palette board. It does not claim face or semantic identity.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from itertools import combinations
import math
from typing import Any

from PIL import Image, ImageFilter, ImageStat


EVALUATOR_VERSION = "reference-layout-pixels-v1"
MIN_LAYOUT_SCORE = 0.75


class ReferenceLayoutValidationError(ValueError):
    def __init__(self, message: str, *, failure_stage: str, evidence: dict[str, Any]):
        super().__init__(message)
        summary: dict[str, Any] = {"failure_stage": failure_stage}
        for field in ("layout_score", "threshold"):
            try:
                value = float(evidence.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                summary[field] = value
        version = str(evidence.get("evaluator_version") or "")[:80]
        if version:
            summary["evaluator_version"] = version
        self.summary = summary


def _invalid(message: str, stage: str, evidence: dict[str, Any]) -> None:
    raise ReferenceLayoutValidationError(message, failure_stage=stage, evidence=evidence)


def reference_layout_prompt_instruction() -> str:
    return (
        "画布固定为 3:2 横向构图。左侧严格占画布 60%，并分成三个等宽面板，依次只放角色正面、"
        "四分之三侧面、全身；右侧严格占画布 40%，只放全局动漫风格、色板、线条与光影规则。"
        "四个区域必须边界清晰、内容完整，不得跨区、拼贴或留白。"
    )


def _metrics(image: Image.Image) -> dict[str, float]:
    rgb = image.convert("RGB")
    stat = ImageStat.Stat(rgb)
    variance = sum(stat.var) / (3 * 255 * 255)
    edge = ImageStat.Stat(rgb.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0] / 255
    quantized = rgb.quantize(colors=16)
    colors = quantized.getcolors(maxcolors=16) or []
    dominant = max((count for count, _ in colors), default=rgb.width * rgb.height)
    foreground_ratio = 1 - dominant / max(1, rgb.width * rgb.height)
    return {
        "variance": round(variance, 6),
        "edge_density": round(edge, 6),
        "foreground_ratio": round(foreground_ratio, 6),
    }


def _dhash(image: Image.Image) -> int:
    gray = image.convert("L").resize((9, 8))
    pixels = list(gray.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def _hash_similarity(left: int, right: int) -> float:
    return round(1 - (left ^ right).bit_count() / 64, 6)


def _significant_palette_colors(image: Image.Image) -> int:
    quantized = image.convert("RGB").quantize(colors=12)
    total = max(1, image.width * image.height)
    return sum(1 for count, _ in (quantized.getcolors(maxcolors=12) or []) if count / total >= 0.015)


def validate_layout_evidence(evidence: dict[str, Any], *, expected_bytes_sha256: str) -> None:
    if evidence.get("evaluator_version") != EVALUATOR_VERSION:
        _invalid("reference layout evaluator version is not trusted", "evidence_version", evidence)
    if evidence.get("bytes_sha256") != expected_bytes_sha256:
        _invalid("reference layout evidence bytes hash mismatch", "evidence_binding", evidence)
    if float(evidence.get("layout_score") or 0) < MIN_LAYOUT_SCORE:
        _invalid("reference layout score is below threshold", "layout_scoring", evidence)
    if len(evidence.get("character_panels") or []) != 3:
        _invalid("reference layout requires three character panels", "layout_structure", evidence)
    if int((evidence.get("style_board") or {}).get("significant_palette_colors") or 0) < 4:
        _invalid("reference layout style palette is insufficient", "style_palette", evidence)


def evaluate_reference_layout(image_bytes: bytes) -> dict[str, Any]:
    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
    width, height = image.size
    split = int(width * 0.60)
    panel_width = split // 3
    panels = [image.crop((index * panel_width, 0, (index + 1) * panel_width, height)) for index in range(3)]
    panel_metrics = [_metrics(panel) for panel in panels]
    panel_hashes = [_dhash(panel) for panel in panels]
    similarities = [_hash_similarity(panel_hashes[a], panel_hashes[b]) for a, b in combinations(range(3), 2)]
    style = image.crop((split, 0, width, height))
    style_metrics = _metrics(style)
    palette_colors = _significant_palette_colors(style)

    panel_scores = [
        min(1.0, metrics["variance"] / 0.018)
        * min(1.0, metrics["edge_density"] / 0.025)
        * min(1.0, metrics["foreground_ratio"] / 0.10)
        for metrics in panel_metrics
    ]
    similarity_score = sum(1.0 if 0.35 <= item <= 0.95 else 0.0 for item in similarities) / len(similarities)
    style_score = (
        min(1.0, style_metrics["variance"] / 0.018)
        * min(1.0, style_metrics["edge_density"] / 0.018)
        * min(1.0, palette_colors / 4)
    )
    score = round((sum(panel_scores) / 3 * 0.55) + (similarity_score * 0.20) + (style_score * 0.25), 6)
    evidence = {
        "evidence_kind": "layout_evidence",
        "semantic_claims": [],
        "evaluator_version": EVALUATOR_VERSION,
        "bytes_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "layout_score": score,
        "threshold": MIN_LAYOUT_SCORE,
        "layout": {"character_region": [0.0, 0.0, 0.60, 1.0], "style_board_region": [0.60, 0.0, 1.0, 1.0]},
        "character_panels": [
            {"panel": index + 1, **metrics, "perceptual_hash": f"{panel_hashes[index]:016x}"}
            for index, metrics in enumerate(panel_metrics)
        ],
        "panel_structural_similarity": similarities,
        "style_board": {**style_metrics, "significant_palette_colors": palette_colors},
    }
    validate_layout_evidence(evidence, expected_bytes_sha256=evidence["bytes_sha256"])
    return evidence


__all__ = [
    "EVALUATOR_VERSION", "MIN_LAYOUT_SCORE", "ReferenceLayoutValidationError",
    "evaluate_reference_layout", "reference_layout_prompt_instruction", "validate_layout_evidence",
]
