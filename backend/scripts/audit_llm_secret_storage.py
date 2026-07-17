"""Read-only aggregate audit for LLM credential storage."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./ai_video.db"


def classify_secret(value: str | bytes | None) -> str:
    if not value:
        return "empty"
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return "encrypted" if value.startswith("gAAAAA") else "legacy_plaintext"


def _sync_database_url(database_url: str) -> str:
    url = make_url(database_url)
    driver = {"postgresql+asyncpg": "postgresql+psycopg2"}.get(url.drivername, url.drivername)
    return url.set(drivername=driver).render_as_string(hide_password=False)


def load_secret_columns_read_only(database_url: str | None = None) -> list[str | None]:
    url = make_url(database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    if url.get_backend_name() == "sqlite":
        if not url.database or url.database == ":memory:":
            raise RuntimeError("The LLM credential audit requires a persistent SQLite database")
        database_path = Path(url.database).expanduser().resolve()
        with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
            rows = connection.execute("SELECT api_key, api_secret FROM llm_configs").fetchall()
        return [value for row in rows for value in row]

    engine = create_engine(_sync_database_url(str(url)))
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                rows = connection.execute(text("SELECT api_key, api_secret FROM llm_configs")).all()
            finally:
                transaction.rollback()
        return [value for row in rows for value in row]
    finally:
        engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit LLM credential encryption without modifying data")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    parse_args(argv)
    counts = Counter(classify_secret(value) for value in load_secret_columns_read_only())
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
