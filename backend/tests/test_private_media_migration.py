from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.models.private_media import MediaDeletionReceipt, MediaObject


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_private_media_schema_and_immutable_receipts_are_created_by_alembic(tmp_path) -> None:
    database_path = tmp_path / "private-media.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)

    result = subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"], cwd=BACKEND_ROOT,
        env=environment, check=True, capture_output=True, text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    assert "Database migration complete: 20260809_0006" in result.stdout
    assert {
        "media_objects", "provider_media_inputs", "media_deletion_requests",
        "media_deletion_receipts",
    }.issubset(tables)

    with Session(engine) as session:
        media = MediaObject(
            id="media-1", user_id="user-1", media_kind="image",
            lifecycle_class="original", storage_provider="qiniu",
            object_key="private/original/user-1/ref.jpg", sha256="a" * 64,
            size_bytes=10, content_type="image/jpeg",
        )
        receipt = MediaDeletionReceipt(
            id="receipt-1", media_object_id=media.id, request_id="request-1",
            outcome="deleted", object_key_sha256="b" * 64,
            detail="对象已删除",
        )
        session.add_all([media, receipt])
        session.commit()
        with pytest.raises(DatabaseError, match="append-only"):
            session.execute(update(MediaDeletionReceipt).values(detail="被篡改"))
