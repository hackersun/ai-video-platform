"""Liveness / readiness probes for commercial gate (Wave 4).

``/health`` stays a cheap process-alive signal for load balancers that only
need uptime. ``/ready`` checks DB (always) and Redis when ``REDIS_URL`` is set,
so Compose / k8s can refuse traffic when dependencies are down.
"""

from __future__ import annotations

import os
import time
from typing import Any

from sqlalchemy import text


async def check_database() -> dict[str, Any]:
    started = time.monotonic()
    try:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"ok": True, "latency_ms": int((time.monotonic() - started) * 1000)}
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        return {
            "ok": False,
            "error": type(exc).__name__,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }


async def check_redis() -> dict[str, Any] | None:
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return None
    started = time.monotonic()
    client = None
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        pong = await client.ping()
        return {
            "ok": bool(pong),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": type(exc).__name__,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass


def check_storage_config() -> dict[str, Any] | None:
    """Optional advisory: only when APP_ENV looks like production."""
    app_env = (os.getenv("APP_ENV") or "").strip().lower()
    if app_env not in {"production", "prod", "staging"}:
        return None
    try:
        from app.core.object_storage import storage_production_problems, storage_provider

        problems = storage_production_problems()
        return {
            "ok": not problems,
            "provider": storage_provider(),
            "problems": problems,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "problems": []}


async def build_readiness() -> dict[str, Any]:
    database = await check_database()
    redis = await check_redis()
    storage = check_storage_config()
    checks: dict[str, Any] = {"database": database}
    if redis is not None:
        checks["redis"] = redis
    if storage is not None:
        checks["storage"] = storage
    required_ok = database.get("ok") is True
    if redis is not None:
        required_ok = required_ok and redis.get("ok") is True
    # Storage is advisory in readiness body; production boot still uses assert_production_safe.
    status = "ready" if required_ok else "not_ready"
    return {
        "status": status,
        "service": "AI视频平台",
        "version": "1.0.0",
        "checks": checks,
    }


__all__ = [
    "build_readiness",
    "check_database",
    "check_redis",
    "check_storage_config",
]
