from sqlalchemy import create_engine, text

from app.db_migrations.script_chapter_lineage import (
    add_script_chapter_lineage,
    backfill_statement,
)


def test_postgresql_backfill_uses_native_json_operator() -> None:
    sql = str(backfill_statement("postgresql"))

    assert "extra_data ->> 'chapter_id'" in sql
    assert "json_extract" not in sql
    assert "json_valid" not in sql


def test_sqlite_backfill_preserves_legacy_json_validation() -> None:
    sql = str(backfill_statement("sqlite"))

    assert "json_extract(extra_data, '$.chapter_id')" in sql
    assert "json_valid(extra_data)" in sql


def test_sync_migration_backfills_valid_legacy_script(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'lineage.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE scripts (id VARCHAR(36) PRIMARY KEY, extra_data JSON)"
        ))
        connection.execute(text(
            "INSERT INTO scripts (id, extra_data) VALUES ('script-1', '{\"chapter_id\": \"chapter-1\"}')"
        ))

    add_script_chapter_lineage(engine)

    with engine.connect() as connection:
        chapter_id = connection.execute(text(
            "SELECT chapter_id FROM scripts WHERE id = 'script-1'"
        )).scalar_one()
    assert chapter_id == "chapter-1"
