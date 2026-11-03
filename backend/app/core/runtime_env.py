"""Runtime environment helpers (production-aware defaults)."""

from __future__ import annotations

import os

_PRODUCTION_ENV_NAMES = frozenset({"production", "prod"})


def app_environment() -> str:
    """Return normalized APP_ENV / ENVIRONMENT, or empty when unset."""
    raw = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    return raw


def is_production_environment() -> bool:
    return app_environment() in _PRODUCTION_ENV_NAMES


def is_dev_mode() -> bool:
    """
    DEV_MODE resolution:

    - Explicit DEV_MODE always wins.
    - When unset: production/prod defaults to False (fail-closed); otherwise True for local/dev.
    """
    explicit = os.getenv("DEV_MODE")
    if explicit is not None and str(explicit).strip() != "":
        return str(explicit).strip().lower() in {"true", "1", "yes", "on"}
    if is_production_environment():
        return False
    return True


__all__ = ["app_environment", "is_dev_mode", "is_production_environment"]
