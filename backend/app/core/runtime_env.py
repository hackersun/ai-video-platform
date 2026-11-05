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


_TRUTHY = {"true", "1", "yes", "on"}


def assert_production_safe() -> None:
    """Fail startup when dev auth shortcuts are enabled in a production environment."""
    if not is_production_environment():
        return
    problems = []
    if is_dev_mode():
        problems.append("DEV_MODE enabled")
    if (os.getenv("DEV_USER_ID") or "").strip():
        problems.append("DEV_USER_ID set (dev-token fallback)")
    for name in ("DEV_TOKEN", "DEV_AUTH_TOKEN", "ALLOW_DEV_TOKEN"):
        if (os.getenv(name) or "").strip().lower() not in {"", "0", "false", "no", "off"}:
            problems.append(f"{name} set")
    if (os.getenv("DETERMINISTIC_PROVIDER_FAKE") or "").strip() == "1":
        problems.append("DETERMINISTIC_PROVIDER_FAKE enabled")
    if problems:
        raise RuntimeError(
            f"Refusing to start: APP_ENV={app_environment()} but " + ", ".join(problems)
            + ". Unset dev settings (DEV_MODE=false) for production."
        )


__all__ = ["app_environment", "assert_production_safe", "is_dev_mode", "is_production_environment"]
