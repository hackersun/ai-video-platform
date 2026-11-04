"""Explicit, reversible model-center read-mode selection."""

from __future__ import annotations

import os
from enum import Enum


class ModelCenterReadMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"


def model_center_read_mode() -> ModelCenterReadMode:
    """model_config is the runtime source of truth; ``legacy`` is the rollback switch."""
    value = os.getenv("MODEL_CENTER_READ_MODE")
    if value is None:
        value = os.getenv("MODEL_CENTER_CANONICAL_READS", ModelCenterReadMode.CANONICAL.value)
    try:
        return ModelCenterReadMode(value.strip().lower())
    except (AttributeError, ValueError):
        return ModelCenterReadMode.CANONICAL


def legacy_canonical_fallback_enabled() -> bool:
    return os.getenv("MODEL_CENTER_LEGACY_CANONICAL_FALLBACK", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def strict_canonical_enabled() -> bool:
    """When on, canonical reads never fall back to legacy rows for unbound tasks."""
    return os.getenv("MODEL_CENTER_STRICT_CANONICAL", "").strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "strict_canonical_enabled", "ModelCenterReadMode", "legacy_canonical_fallback_enabled", "model_center_read_mode",
]
