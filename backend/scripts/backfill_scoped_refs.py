#!/usr/bin/env python3
"""Explicit scoped-reference backfill CLI; never selects a database implicitly."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.features.series_run_story_locks.repositories.scoped_ref_backfill_async import (
    apply_scoped_ref_manifest,
    write_scoped_ref_manifest,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dry-run", "apply"))
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--manifest-sha256")
    values = parser.parse_args()
    if values.mode == "dry-run" and not values.run_id:
        parser.error("dry-run requires --run-id")
    if values.mode == "apply" and not values.manifest_sha256:
        parser.error("apply requires --manifest-sha256")
    return values


async def _run(values: argparse.Namespace) -> dict[str, object]:
    database = values.database.expanduser().resolve()
    engine = create_async_engine(f"sqlite+aiosqlite:///{database}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as db:
            if values.mode == "dry-run":
                return await write_scoped_ref_manifest(
                    db, run_id=values.run_id, manifest_path=values.manifest, database_path=database)
            return await apply_scoped_ref_manifest(
                db, manifest_path=values.manifest, expected_manifest_hash=values.manifest_sha256,
                database_path=database)
    finally:
        await engine.dispose()


def main() -> None:
    print(json.dumps(asyncio.run(_run(_arguments())), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
