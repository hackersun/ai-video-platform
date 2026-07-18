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
from app.features.model_config.prompt_recovery import (
    apply_prompt_recovery,
    plan_prompt_recovery,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check-first model center backfill")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="report planned rows without writing (default)")
    modes.add_argument("--apply", action="store_true", help="apply additive backfill")
    modes.add_argument("--compare", action="store_true", help="reserved for sanitized shadow comparison")
    modes.add_argument(
        "--check-prompts",
        action="store_true",
        help="report legacy prompt recovery without writing",
    )
    modes.add_argument(
        "--apply-prompts",
        action="store_true",
        help="apply only legacy prompt recovery",
    )
    parser.add_argument("--user-id")
    parser.add_argument("--report")
    parser.add_argument("--ack-backup", action="store_true")
    parser.add_argument("--backup-ack", help="path to an existing database backup")
    return parser.parse_args()


def _validate_prompt_apply_backup(
    *, apply_prompts: bool, backup_ack: str | None,
) -> None:
    if not apply_prompts:
        return
    if not backup_ack or not Path(backup_ack).is_file():
        raise SystemExit("--apply-prompts requires an existing --backup-ack file")


async def _run(args: argparse.Namespace) -> dict[str, object]:
    if args.apply and make_url(SQLALCHEMY_DATABASE_URL).get_backend_name() != "sqlite" and not args.ack_backup:
        raise SystemExit("--apply on non-SQLite requires --ack-backup")
    if args.compare:
        return {"mode": "compare", "status": "not_run", "reason": "use runtime shadow evidence"}
    if args.check_prompts or args.apply_prompts:
        if not args.user_id:
            raise SystemExit("prompt recovery requires --user-id")
        _validate_prompt_apply_backup(
            apply_prompts=bool(args.apply_prompts),
            backup_ack=args.backup_ack,
        )
        async with AsyncSessionLocal() as db:
            if args.apply_prompts:
                report = await apply_prompt_recovery(db, user_id=args.user_id)
                await db.commit()
                payload = report.sanitized_dict()
            else:
                plan = await plan_prompt_recovery(db, user_id=args.user_id)
                payload = plan.sanitized_dict()
        return {
            "mode": "apply-prompts" if args.apply_prompts else "check-prompts",
            "report": payload,
        }
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
