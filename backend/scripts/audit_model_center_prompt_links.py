"""Print a read-only, redacted audit of legacy prompt-profile links."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SQLALCHEMY_DATABASE_URL
from app.features.model_config.prompt_recovery import audit_prompt_links


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit legacy prompt links without modifying data"
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--database-url")
    return parser.parse_args()


def _async_url(configured_url: str) -> str:
    url = make_url(configured_url)
    driver = {
        "sqlite": "sqlite+aiosqlite",
        "postgresql": "postgresql+asyncpg",
        "postgresql+psycopg2": "postgresql+asyncpg",
    }.get(url.drivername, url.drivername)
    return url.set(drivername=driver).render_as_string(hide_password=False)


async def _run(args: argparse.Namespace) -> dict[str, object]:
    engine = create_async_engine(
        _async_url(args.database_url or SQLALCHEMY_DATABASE_URL)
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            audit = await audit_prompt_links(db, args.user_id)
            return asdict(audit)
    finally:
        await engine.dispose()


def main() -> None:
    result = asyncio.run(_run(_parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
