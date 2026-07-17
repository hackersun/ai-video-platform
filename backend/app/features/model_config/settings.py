"""Explicit, reversible model-center read-mode selection."""

from __future__ import annotations

import os
from enum import Enum


class ModelCenterReadMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"


def model_center_read_mode() -> ModelCenterReadMode:
    """Read the mode defensively; legacy remains the safe production default."""
    value = os.getenv("MODEL_CENTER_READ_MODE")
    if value is None:
        value = os.getenv("MODEL_CENTER_CANONICAL_READS", ModelCenterReadMode.LEGACY.value)
    try:
        return ModelCenterReadMode(value.strip().lower())
    except (AttributeError, ValueError):
        return ModelCenterReadMode.LEGACY


def legacy_canonical_fallback_enabled() -> bool:
    return os.getenv("MODEL_CENTER_LEGACY_CANONICAL_FALLBACK", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


__all__ = [
    "ModelCenterReadMode", "legacy_canonical_fallback_enabled", "model_center_read_mode",
]
