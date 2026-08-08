from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_backfill_is_dry_run_by_default_and_apply_is_verified_and_idempotent(tmp_path) -> None:
    database_path = tmp_path / "backfill.db"
    source_root = tmp_path / "source"
    destination_root = tmp_path / "private-store"
    manifest_path = tmp_path / "manifest.json"
    source_file = source_root / "images" / "reference.png"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"private-reference-bytes")
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)
    subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"], cwd=BACKEND_ROOT,
        env=environment, check=True, capture_output=True, text=True,
    )
    command = [
        sys.executable, "scripts/migrate_private_media.py",
        "--source-root", str(source_root), "--destination-root", str(destination_root),
        "--manifest", str(manifest_path), "--user-id", "user-1",
        "--lifecycle-class", "original", "--storage-provider", "private-stage",
    ]

    dry_run = subprocess.run(
        command, cwd=BACKEND_ROOT, env=environment,
        check=True, capture_output=True, text=True,
    )
    assert "试运行：发现 1 个媒体文件，不会复制或修改数据库" in dry_run.stdout
    assert not destination_root.exists()
    assert source_file.is_file()

    applied = subprocess.run(
        [*command, "--apply"], cwd=BACKEND_ROOT, env=environment,
        check=True, capture_output=True, text=True,
    )
    assert "已复制并校验 1 个，已登记 1 个，跳过 0 个" in applied.stdout
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    copied = destination_root / manifest[0]["object_key"]
    assert copied.read_bytes() == source_file.read_bytes()
    assert manifest[0]["sha256"]
    assert source_file.is_file()

    repeated = subprocess.run(
        [*command, "--apply"], cwd=BACKEND_ROOT, env=environment,
        check=True, capture_output=True, text=True,
    )
    assert "已复制并校验 1 个，已登记 0 个，跳过 1 个" in repeated.stdout
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM media_objects")).scalar_one() == 1
