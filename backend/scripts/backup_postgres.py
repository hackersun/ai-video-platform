#!/usr/bin/env python3
"""Create a verified PostgreSQL custom archive and manifest."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.features.operations.postgres_recovery import create_postgres_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="创建可校验的 PostgreSQL 备份")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--label", default="pre-release")
    parser.add_argument("--release-sha", default=os.getenv("RELEASE_SHA", "unknown"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("缺少 DATABASE_URL，未执行备份")
    result = create_postgres_backup(
        args.database_url,
        args.output_dir,
        label=args.label,
        release_sha=args.release_sha,
    )
    print(f"备份完成：{result.archive_path}")
    print(f"校验清单：{result.manifest_path}")
    print(f"SHA-256：{result.sha256}")


if __name__ == "__main__":
    main()
