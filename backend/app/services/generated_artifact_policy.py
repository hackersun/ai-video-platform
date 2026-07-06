"""Classify repository paths that are generated locally."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactClassification:
    path: str
    bucket: str
    should_ignore: bool


RUNTIME_GENERATED_PREFIXES = (
    "backend/static/dev/",
    "backend/static/generated/",
    "backend/static/exports/",
    "frontend/test-results/",
    "test-results/",
    ".playwright-cli/",
    ".codegraph/",
    ".logs/",
    ".superpowers/",
)

ACCEPTANCE_OUTPUT_PREFIXES = (
    "output/playwright/",
    "output/live-anime/",
)

SEED_ASSET_PREFIX = "backend/static/starter/"


def _normalize_path(path: Path) -> str:
    normalized = path.as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix.rstrip("/") or path.startswith(prefix)


def classify_generated_artifact(path: Path) -> ArtifactClassification:
    normalized = _normalize_path(path)

    if _matches_prefix(normalized, SEED_ASSET_PREFIX):
        return ArtifactClassification(normalized, "seed_asset_review_required", False)

    if normalized.endswith(".tsbuildinfo") or any(
        _matches_prefix(normalized, prefix) for prefix in RUNTIME_GENERATED_PREFIXES
    ):
        return ArtifactClassification(normalized, "runtime_generated", True)

    if any(_matches_prefix(normalized, prefix) for prefix in ACCEPTANCE_OUTPUT_PREFIXES):
        return ArtifactClassification(normalized, "acceptance_output", True)

    return ArtifactClassification(normalized, "source", False)
