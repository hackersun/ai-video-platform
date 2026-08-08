"""PostgreSQL-only schema and migration contract.

The main regression suite intentionally uses isolated SQLite databases. This file
uses production-sized identifiers and verifies the PostgreSQL path against a real
service in CI.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.database import sync_engine
from app.db_migrations.script_chapter_lineage import add_script_chapter_lineage


pytestmark = pytest.mark.skipif(
    sync_engine.dialect.name != "postgresql",
    reason="requires the PostgreSQL contract job",
)


def test_postgresql_schema_and_json_lineage_backfill() -> None:
    assert os.environ["DATABASE_URL"].startswith("postgresql")
    user_id = str(uuid4())
    novel_id = str(uuid4())
    chapter_id = str(uuid4())
    script_id = str(uuid4())

    with sync_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO novels (id, user_id, title) VALUES (:id, :user_id, :title)"),
            {"id": novel_id, "user_id": user_id, "title": "PostgreSQL contract novel"},
        )
        connection.execute(
            text(
                "INSERT INTO chapters "
                "(id, novel_id, user_id, title, chapter_number) "
                "VALUES (:id, :novel_id, :user_id, :title, 1)"
            ),
            {
                "id": chapter_id,
                "novel_id": novel_id,
                "user_id": user_id,
                "title": "Contract chapter",
            },
        )
        connection.execute(
            text(
                "INSERT INTO scripts (id, user_id, novel_id, title, extra_data) "
                "VALUES (:id, :user_id, :novel_id, :title, CAST(:extra_data AS JSON))"
            ),
            {
                "id": script_id,
                "user_id": user_id,
                "novel_id": novel_id,
                "title": "Legacy lineage script",
                "extra_data": f'{{"chapter_id": "{chapter_id}"}}',
            },
        )

    add_script_chapter_lineage(sync_engine)

    with sync_engine.connect() as connection:
        stored_chapter_id = connection.execute(
            text("SELECT chapter_id FROM scripts WHERE id = :id"),
            {"id": script_id},
        ).scalar_one()
    assert stored_chapter_id == chapter_id
