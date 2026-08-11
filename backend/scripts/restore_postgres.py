#!/usr/bin/env python3
"""Restore a verified PostgreSQL archive after exact target confirmation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.features.operations.postgres_recovery import restore_postgres_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="校验并恢复 PostgreSQL 备份")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--confirm-target", required=True, help="必须与目标数据库名称完全一致")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("缺少 DATABASE_URL，未执行恢复")
    restore_postgres_backup(
        args.database_url,
        args.archive,
        args.manifest,
        confirmation=args.confirm_target,
    )
    print(f"恢复完成：{args.confirm_target}")


if __name__ == "__main__":
    main()
