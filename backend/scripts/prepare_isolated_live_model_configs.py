#!/usr/bin/env python3
"""Build a minimal, secret-safe SQLite database for an isolated live canary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from app.core.database import Base
from app.core.minimax_voice_contract import has_current_minimax_tts_verification
import app.models  # noqa: F401 - register the complete current application schema
from app.services.live_canary_staging_proof import PROOF_KEY, build_staging_proof


class StagingError(ValueError):
    pass


def _sqlite_path(raw: str, *, must_exist: bool) -> Path:
    path = Path(raw).expanduser().resolve()
    if path.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise StagingError("database path must use a SQLite extension")
    if must_exist and (not path.is_file() or path.read_bytes()[:16] != b"SQLite format 3\x00"):
        raise StagingError("source is not a SQLite database")
    return path


def _row(connection: sqlite3.Connection, query: str, values: tuple[Any, ...]) -> sqlite3.Row:
    result = connection.execute(query, values).fetchone()
    if result is None:
        raise StagingError("requested configuration is missing or not owned by source user")
    return result


def _create_current_schema(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def _verify_current_schema(target: sqlite3.Connection) -> None:
    actual_tables = {row[0] for row in target.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}
    expected_tables = set(Base.metadata.tables)
    if not expected_tables.issubset(actual_tables):
        raise StagingError("target is missing current application tables")
    for table_name, table in Base.metadata.tables.items():
        actual_columns = {row[1] for row in target.execute(f'PRAGMA table_info("{table_name}")')}
        if set(table.columns.keys()) != actual_columns:
            raise StagingError(f"target column parity failed: {table_name}")
        expected_indexes = {index.name for index in table.indexes if index.name}
        actual_indexes = {row[1] for row in target.execute(f'PRAGMA index_list("{table_name}")')}
        if not expected_indexes.issubset(actual_indexes):
            raise StagingError(f"target index parity failed: {table_name}")


def _insert_row(target: sqlite3.Connection, table: str, row: sqlite3.Row, **changes: Any) -> None:
    source_values = dict(row)
    target_info = target.execute(f'PRAGMA table_info("{table}")').fetchall()
    target_columns = {column[1] for column in target_info}
    values = {key: value for key, value in source_values.items() if key in target_columns}
    values.update(changes)
    for column in target_info:
        name, declared_type, not_null, default_value, primary_key = column[1], column[2], column[3], column[4], column[5]
        if name in values or default_value is not None:
            continue
        if not_null or primary_key:
            values[name] = 0 if any(token in declared_type.upper() for token in ("INT", "REAL", "NUM")) else ""
    columns = list(values)
    quoted = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    target.execute(
        f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
        tuple(values[column] for column in columns),
    )


def _insert_synthetic_user(target: sqlite3.Connection, target_user_id: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    short_id = "".join(character for character in target_user_id.lower() if character.isalnum())[:16] or "user"
    safe = {
        "id": target_user_id,
        "username": f"canary_{short_id}",
        "email": f"canary_{short_id}@example.invalid",
        "hashed_password": "$2b$12$000000000000000000000uG4aJnzKjLh5Uj8l3WZz9x0R7TnH3v2e",
        "reset_token_hash": None,
        "reset_token_expires_at": None,
        "avatar": None,
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
    }
    values: dict[str, Any] = {}
    for column in target.execute("PRAGMA table_info(users)").fetchall():
        name, declared_type, not_null, default_value, primary_key = column[1], column[2], column[3], column[4], column[5]
        if name in safe:
            values[name] = safe[name]
        elif default_value is not None:
            continue
        elif not_null or primary_key:
            values[name] = 0 if any(token in declared_type.upper() for token in ("INT", "REAL", "NUM")) else ""
    columns = list(values)
    target.execute(
        f"INSERT INTO users ({', '.join(chr(34)+name+chr(34) for name in columns)}) VALUES ({', '.join('?' for _ in columns)})",
        tuple(values[name] for name in columns),
    )


def _staged_extra_params(
    config: sqlite3.Row, *, provider_id: str, target_user_id: str, staged_at: datetime,
) -> str:
    raw = config["extra_params"] if "extra_params" in config.keys() else None
    try:
        params = json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError) as error:
        raise StagingError("configuration extra_params is malformed") from error
    if not isinstance(params, dict):
        raise StagingError("configuration extra_params must be an object")
    params[PROOF_KEY] = build_staging_proof(
        staged_at=staged_at,
        source_test_status=str(config["test_status"]),
        source_tested_at=config["tested_at"],
        config_id=str(config["id"]),
        model_id=str(config["model_id"]),
        provider_id=provider_id,
        target_user_id=target_user_id,
    )
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def _copy_storage_config(
    source: sqlite3.Connection, target: sqlite3.Connection, *, source_user_id: str,
    target_user_id: str, storage_config_id: str | None,
) -> tuple[list[str], list[str]]:
    if not storage_config_id:
        return [], []
    config = _row(source, "SELECT * FROM external_api_configs WHERE id = ? AND user_id = ?",
                  (storage_config_id, source_user_id))
    provider = _row(source, "SELECT * FROM external_api_providers WHERE id = ?", (config["provider_id"],))
    try:
        extra = json.loads(config["extra_config"] or "{}")
    except (TypeError, json.JSONDecodeError) as error:
        raise StagingError("storage configuration extra_config is malformed") from error
    if (
        not bool(config["is_active"]) or config["test_status"] != "success"
        or not bool(provider["is_active"]) or provider["api_type"] != "storage"
        or extra.get("storage_provider") not in {"qiniu", "kodo", "qiniu_kodo"}
        or not config["api_key"] or not config["api_secret"] or not extra.get("bucket")
        or not extra.get("public_base_url")
    ):
        raise StagingError("allowlisted Qiniu storage configuration is incomplete or unverified")
    _insert_row(target, "external_api_providers", provider)
    _insert_row(target, "external_api_configs", config, user_id=target_user_id)
    return [str(config["id"])], [str(provider["id"])]


def _copy_staged_rows(
    source_path: Path, temporary_path: Path, *, source_user_id: str,
    target_user_id: str, config_ids: list[str], storage_config_id: str | None,
) -> tuple[set[str], set[str], list[str], list[str], list[str]]:
    with sqlite3.connect(
        f"file:{source_path}?mode=ro", uri=True
    ) as source, sqlite3.connect(temporary_path) as target:
        source.row_factory = sqlite3.Row
        source_tables = {row[0] for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        unknown_tables = sorted(source_tables - set(Base.metadata.tables))
        _verify_current_schema(target)
        _row(source, "SELECT id FROM users WHERE id = ?", (source_user_id,))
        _insert_synthetic_user(target, target_user_id)
        configs = [
            _row(
                source, "SELECT * FROM llm_configs WHERE id = ? AND user_id = ?",
                (config_id, source_user_id),
            )
            for config_id in config_ids
        ]
        if any(
            not bool(config["is_active"])
            or config["test_status"] != "success"
            or not config["tested_at"]
            for config in configs
        ):
            raise StagingError(
                "allowlisted configuration is inactive or not successfully tested"
            )
        model_ids = {str(config["model_id"]) for config in configs}
        models = [
            _row(source, "SELECT * FROM llm_models WHERE id = ?", (model_id,))
            for model_id in sorted(model_ids)
        ]
        if any(not bool(model["is_active"]) for model in models):
            raise StagingError("allowlisted model is inactive")
        provider_ids = {str(model["provider_id"]) for model in models}
        providers = [
            _row(source, "SELECT * FROM llm_providers WHERE id = ?", (provider_id,))
            for provider_id in sorted(provider_ids)
        ]
        if any(not bool(provider["is_active"]) for provider in providers):
            raise StagingError("allowlisted provider is inactive")
        for provider in providers:
            _insert_row(target, "llm_providers", provider)
        for model in models:
            _insert_row(target, "llm_models", model)
        provider_by_model = {
            str(model["id"]): str(model["provider_id"]) for model in models
        }
        model_by_id = {str(model["id"]): model for model in models}
        for config in configs:
            model = model_by_id[str(config["model_id"])]
            if (
                str(model["provider_id"]) == "minimax"
                and str(model["model_type"] or "") == "tts"
                and not has_current_minimax_tts_verification(config["test_message"], str(model["model_id"]))
            ):
                raise StagingError("MiniMax TTS configuration requires a current exact voice verification")
        staged_at = datetime.now(timezone.utc)
        for config in configs:
            _insert_row(
                target, "llm_configs", config, user_id=target_user_id,
                extra_params=_staged_extra_params(
                    config, provider_id=provider_by_model[str(config["model_id"])],
                    target_user_id=target_user_id, staged_at=staged_at,
                ),
            )
        storage_config_ids, storage_provider_ids = _copy_storage_config(
            source, target, source_user_id=source_user_id, target_user_id=target_user_id,
            storage_config_id=storage_config_id,
        )
        target.commit()
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise StagingError("target integrity check failed")
        if target.execute("PRAGMA foreign_key_check").fetchall():
            raise StagingError("target foreign key check failed")
    return model_ids, provider_ids, unknown_tables, storage_config_ids, storage_provider_ids


def stage_database(
    source_path: Path,
    target_path: Path,
    *,
    source_user_id: str,
    target_user_id: str,
    config_ids: list[str],
    storage_config_id: str | None = None,
) -> dict[str, Any]:
    if source_path == target_path:
        raise StagingError("source and target databases must differ")
    if target_path.exists():
        raise StagingError("target database already exists")
    if not config_ids or len(config_ids) != len(set(config_ids)):
        raise StagingError("config allowlist must be non-empty and unique")

    if not target_path.parent.is_dir():
        raise StagingError("target parent directory must already exist")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.", suffix=".sqlite", dir=target_path.parent
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    published_by_this_process = False
    try:
        os.chmod(temporary_path, 0o600)
        _create_current_schema(temporary_path)
        model_ids, provider_ids, unknown_source_tables, storage_config_ids, storage_provider_ids = _copy_staged_rows(
            source_path, temporary_path, source_user_id=source_user_id,
            target_user_id=target_user_id, config_ids=config_ids, storage_config_id=storage_config_id,
        )

        manifest = {
            "config_ids": sorted(config_ids),
            "model_ids": sorted(model_ids),
            "provider_ids": sorted(provider_ids),
            "storage_config_ids": storage_config_ids,
            "storage_provider_ids": storage_provider_ids,
            "counts": {
                "configs": len(config_ids), "models": len(model_ids),
                "providers": len(provider_ids), "users": 1,
                "storage_configs": len(storage_config_ids), "storage_providers": len(storage_provider_ids),
            },
            "unrecognized_source_tables": unknown_source_tables,
        }
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        manifest["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        try:
            os.link(temporary_path, target_path)
            published_by_this_process = True
        except FileExistsError as error:
            raise StagingError("target database already exists") from error
        os.chmod(target_path, 0o600)
        temporary_path.unlink()
        return manifest
    except Exception:
        if published_by_this_process:
            try:
                if target_path.stat().st_ino == temporary_path.stat().st_ino:
                    target_path.unlink()
            except FileNotFoundError:
                pass
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--source-user-id", required=True)
    parser.add_argument("--target-user-id", required=True)
    parser.add_argument("--config-id", nargs="+", required=True)
    parser.add_argument("--storage-config-id")
    args = parser.parse_args()
    try:
        source = _sqlite_path(args.source_db, must_exist=True)
        target = _sqlite_path(args.target_db, must_exist=False)
        manifest = stage_database(
            source, target, source_user_id=args.source_user_id,
            target_user_id=args.target_user_id, config_ids=args.config_id,
            storage_config_id=args.storage_config_id,
        )
    except Exception as error:
        print(f"staging refused: {type(error).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
