"""Safe operator entry point for model-center legacy backfill."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import AsyncSessionLocal, SQLALCHEMY_DATABASE_URL
from app.features.model_config.backfill import backfill_model_center


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check-first model center backfill")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="report planned rows without writing (default)")
    modes.add_argument("--apply", action="store_true", help="apply additive backfill")
    modes.add_argument("--compare", action="store_true", help="reserved for sanitized shadow comparison")
    parser.add_argument("--user-id")
    parser.add_argument("--report")
    parser.add_argument("--ack-backup", action="store_true")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict[str, object]:
    if args.apply and make_url(SQLALCHEMY_DATABASE_URL).get_backend_name() != "sqlite" and not args.ack_backup:
        raise SystemExit("--apply on non-SQLite requires --ack-backup")
    if args.compare:
        return {"mode": "compare", "status": "not_run", "reason": "use runtime shadow evidence"}
    async with AsyncSessionLocal() as db:
        report = await backfill_model_center(db, apply=bool(args.apply), user_id=args.user_id)
        if args.apply:
            await db.commit()
    return {"mode": "apply" if args.apply else "check", "report": report.sanitized_dict()}


def main() -> None:
    args = _parse_args()
    result = asyncio.run(_run(args))
    body = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body + "\n", encoding="utf-8")
    print(body)


if __name__ == "__main__":
    main()
