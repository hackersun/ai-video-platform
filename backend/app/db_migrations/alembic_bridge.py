"""Transitional Alembic entry point for legacy databases.

The first managed release uses the existing idempotent bootstrap to converge the
schema, then records a baseline revision. Later revisions can migrate individual
compatibility functions without changing the deployment command.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect


BASELINE_REVISION = "20260808_0001"


def _config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    return Config(str(backend_root / "alembic.ini"))


def _current_revision() -> str | None:
    from app.core.database import sync_engine

    with sync_engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade_database() -> str:
    """Converge a legacy/blank schema, stamp it once, then upgrade to head."""
    from app.core.database import sync_engine

    config = _config()
    if not inspect(sync_engine).has_table("alembic_version"):
        from init_db import init_db

        init_db()
        command.stamp(config, BASELINE_REVISION)
    elif _current_revision() is None:
        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")
    revision = _current_revision()
    if not revision:
        raise RuntimeError("database migration finished without an Alembic revision")
    return revision


__all__ = ["BASELINE_REVISION", "upgrade_database"]
