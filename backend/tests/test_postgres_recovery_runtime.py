"""Assertions executed only against the isolated restored CI database."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.database import sync_engine


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_RECOVERY_DRILL") != "true",
    reason="requires an explicitly isolated restored PostgreSQL database",
)


def test_restored_database_contains_canary_and_current_migration_head() -> None:
    assert sync_engine.dialect.name == "postgresql"
    expected_canary = os.environ["POSTGRES_RECOVERY_CANARY"]
    with sync_engine.connect() as connection:
        canary = connection.execute(
            text("SELECT value FROM recovery_drill_canary WHERE id = 1")
        ).scalar_one()
        restored_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    expected_revision = ScriptDirectory.from_config(config).get_current_head()
    assert canary == expected_canary
    assert restored_revision == expected_revision
