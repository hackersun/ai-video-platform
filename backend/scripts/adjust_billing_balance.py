"""Operator-only customer balance adjustment with an immutable audit entry."""

import argparse
import asyncio
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.features.billing.domain import micros_to_rmb_text, rmb_to_micros
from app.features.billing.service import credit_account
from app.models.billing import BillingAccount


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="由运营人员为客户账户增加余额并写入不可变流水")
    parser.add_argument("--user-id", required=True, help="客户用户 ID")
    parser.add_argument("--amount-rmb", required=True, help="增加的人民币金额")
    parser.add_argument("--actor-user-id", required=True, help="执行调账的运营人员 ID")
    parser.add_argument("--reason", required=True, help="至少两个字的中文调账原因")
    parser.add_argument("--idempotency-key", required=True, help="本次调账唯一幂等键")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict[str, str]:
    amount = rmb_to_micros(args.amount_rmb, positive=True)
    async with AsyncSessionLocal() as db:
        account = await db.scalar(select(BillingAccount).where(
            BillingAccount.owner_type == "user", BillingAccount.owner_id == args.user_id,
        ))
        if account is None:
            account = BillingAccount(owner_type="user", owner_id=args.user_id)
            db.add(account)
            await db.commit()
        entry = await credit_account(
            db, account_id=account.id, amount_micros=amount,
            actor_user_id=args.actor_user_id, reason=args.reason,
            idempotency_key=args.idempotency_key,
        )
        await db.refresh(account)
        return {
            "account_id": account.id, "entry_id": entry.id,
            "added_rmb": micros_to_rmb_text(amount),
            "available_rmb": micros_to_rmb_text(account.available_micros),
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(_run(_arguments())), ensure_ascii=False, sort_keys=True))
