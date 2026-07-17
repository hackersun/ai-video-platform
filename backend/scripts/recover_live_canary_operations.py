#!/usr/bin/env python3
"""One-shot, secret-safe recovery for stale live canary provider operations."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - register operation/run mappings
from app.services.live_canary_budget import recover_provider_operations


async def _run(database_url: str, user_id: str | None, stale_minutes: int) -> dict:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        raise ValueError("recovery currently requires an explicit SQLite database URL")
    engine = create_async_engine(url.set(drivername="sqlite+aiosqlite"))
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with maker() as db:
            # Registered adapters are intentionally empty until a provider exposes a documented,
            # server-safe status/idempotency lookup contract. Unsupported recovery blocks and retains.
            return await recover_provider_operations(
                db, adapters={}, user_id=user_id,
                stale_before=datetime.now(timezone.utc) - timedelta(minutes=stale_minutes),
            )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--user-id")
    parser.add_argument("--stale-minutes", type=int, default=15)
    args = parser.parse_args()
    if args.stale_minutes < 1:
        parser.error("--stale-minutes must be positive")
    try:
        manifest = asyncio.run(_run(args.database_url, args.user_id, args.stale_minutes))
    except Exception as error:
        print(json.dumps({"status": "refused", "error_class": type(error).__name__}, sort_keys=True))
        return 2
    print(json.dumps({"status": "ok", **manifest}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
