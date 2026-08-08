from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_existing_users_are_verified_and_session_schema_is_added(tmp_path) -> None:
    database_path = tmp_path / "legacy-auth.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id VARCHAR(36) PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, "
                "email VARCHAR(100) UNIQUE NOT NULL, hashed_password VARCHAR(128) NOT NULL, "
                "is_active BOOLEAN, created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, hashed_password, is_active) "
                "VALUES ('legacy-user', 'legacy', 'legacy@example.test', 'hash', 1)"
            )
        )

    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)
    result = subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "20260808_0002" in result.stdout
    assert inspect(engine).has_table("user_sessions")
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert {"account_status", "email_verified_at", "email_verification_token_hash"} <= user_columns
    with engine.connect() as connection:
        status, verified_at = connection.execute(
            text("SELECT account_status, email_verified_at FROM users WHERE id='legacy-user'")
        ).one()
    assert status == "active"
    assert verified_at is not None
