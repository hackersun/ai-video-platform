import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def _sync_url(path: Path) -> str:
    return f"sqlite:///{path}"


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _upgrade(path: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)
    return subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_blank_database_is_bootstrapped_and_stamped(tmp_path) -> None:
    database_path = tmp_path / "blank.db"
    result = _upgrade(database_path)
    engine = create_engine(_sync_url(database_path))

    assert "Database migration complete: 20260809_0004" in result.stdout
    assert inspect(engine).has_table("users")
    assert inspect(engine).has_table("alembic_version")


def test_existing_database_keeps_data_and_is_stamped(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    engine = create_engine(_sync_url(database_path))
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE legacy_sentinel (value VARCHAR(40))"))
        connection.execute(text("INSERT INTO legacy_sentinel VALUES ('keep-me')"))

    result = _upgrade(database_path)
    with engine.connect() as connection:
        value = connection.execute(text("SELECT value FROM legacy_sentinel")).scalar_one()

    assert "Database migration complete: 20260809_0004" in result.stdout
    assert value == "keep-me"
