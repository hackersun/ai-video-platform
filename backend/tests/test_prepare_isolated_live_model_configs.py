from __future__ import annotations

import sqlite3
import stat
import subprocess
import sys
import os
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.database import Base
import app.models  # noqa: F401 - register the complete application metadata
from app.core.minimax_voice_contract import minimax_tts_verification_message


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_isolated_live_model_configs.py"


def _source(path: Path) -> bytes:
    secret = b"opaque-secret-bytes-not-for-output"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO users (id,username,email,hashed_password,reset_token_hash,avatar,is_active) VALUES (?,?,?,?,?,?,1)",
            ("source-user", "real_identity", "real@example.com", "source-password-hash", "source-reset", "source-avatar"),
        )
        db.execute("INSERT INTO llm_providers (id,name,is_active) VALUES (?, ?, ?)", ("provider-text", "synthetic", 1))
        db.execute(
            "INSERT INTO llm_models (id,provider_id,model_id,model_name,capabilities,is_active) VALUES (?, ?, ?, ?, ?, ?)",
            ("model-text", "provider-text", "synthetic-text", "Synthetic", '["chat"]', 1),
        )
        db.execute(
            "INSERT INTO llm_configs (id,user_id,model_id,name,api_key,api_secret,is_active,test_status,tested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("config-text", "source-user", "model-text", "primary", secret, secret[::-1], 1, "success", "2099-01-01T00:00:00"),
        )
        db.execute(
            "INSERT INTO llm_configs (id,user_id,model_id,name,api_key,api_secret,is_active,test_status,tested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("config-not-allowed", "source-user", "model-text", "other", b"other", b"other", 1, "success", "2099-01-01T00:00:00"),
        )
        db.execute(
            "INSERT INTO external_api_providers (id,name,api_type,base_url,is_active) VALUES (?, ?, ?, ?, ?)",
            ("object-storage", "object_storage", "storage", "https://cdn.example.com", 1),
        )
        db.execute(
            """INSERT INTO external_api_configs
            (id,user_id,provider_id,name,api_key,api_secret,is_active,is_default,test_status,extra_config)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("storage-qiniu", "source-user", "object-storage", "Qiniu", secret, secret[::-1], 1, 1, "success",
             '{"storage_provider":"qiniu","bucket":"bucket","public_base_url":"https://cdn.example.com"}'),
        )
    return secret


def _run(
    source: Path, target: Path, *config_ids: str, storage_config_id: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    storage_args = ["--storage-config-id", storage_config_id] if storage_config_id else []
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-db", str(source),
            "--target-db", str(target),
            "--source-user-id", "source-user",
            "--target-user-id", "canary-user",
            "--config-id", *config_ids,
            *storage_args,
        ],
        capture_output=True,
        check=False,
    )


def test_staging_copies_only_allowlisted_qiniu_storage_for_target_user(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    secret = _source(source)

    result = _run(source, target, "config-text", storage_config_id="storage-qiniu")

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert secret not in result.stdout + result.stderr
    manifest = json.loads(result.stdout)
    assert manifest["storage_config_ids"] == ["storage-qiniu"]
    with sqlite3.connect(target) as db:
        provider = db.execute("SELECT id,api_type FROM external_api_providers").fetchone()
        config = db.execute(
            "SELECT id,user_id,provider_id,api_key,api_secret,test_status,extra_config FROM external_api_configs"
        ).fetchone()
    assert provider == ("object-storage", "storage")
    assert config[:6] == ("storage-qiniu", "canary-user", "object-storage", secret, secret[::-1], "success")
    assert json.loads(config[6])["storage_provider"] == "qiniu"


def test_staging_copies_only_allowlisted_verified_owner_rows_without_secret_output(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    secret = _source(source)

    result = _run(source, target, "config-text")

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    combined = result.stdout + result.stderr
    assert secret not in combined
    assert secret[::-1] not in combined
    assert b"config-text" in result.stdout
    assert b"model-text" in result.stdout
    assert b"provider-text" in result.stdout
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with sqlite3.connect(target) as db:
        config = db.execute(
            "SELECT user_id, api_key, api_secret, test_status, tested_at, extra_params FROM llm_configs"
        ).fetchone()
        assert config[:5] == (
            "canary-user", secret, secret[::-1], "success", "2099-01-01T00:00:00"
        )
        proof = json.loads(config[5])["canary_staging_v1"]
        assert proof["source_test_status"] == "success"
        assert proof["source_tested_at"] == "2099-01-01T00:00:00"
        assert proof["config_id"] == "config-text"
        assert proof["model_id"] == "model-text"
        assert proof["provider_id"] == "provider-text"
        assert proof["target_user_id"] == "canary-user"
        assert len(proof["canonical_sha256"]) == 64
        assert db.execute("SELECT id FROM llm_configs").fetchall() == [("config-text",)]
        assert db.execute("SELECT id FROM llm_models").fetchall() == [("model-text",)]
        assert db.execute("SELECT id FROM llm_providers").fetchall() == [("provider-text",)]
        user = db.execute("SELECT id,username,email,hashed_password,reset_token_hash,avatar,is_active FROM users").fetchone()
        assert user[0] == "canary-user"
        assert user[1].startswith("canary_")
        assert user[2].endswith("@example.invalid")
        assert user[3] != "source-password-hash"
        assert user[4:6] == (None, None)
        assert user[6] == 1
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='series_production_runs'").fetchone()
        assert db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_llm_configs_user_id'").fetchone()
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_staging_rejects_legacy_minimax_tts_success_without_exact_voice_proof(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    secret = _source(source)
    with sqlite3.connect(source) as db:
        db.execute(
            "UPDATE llm_providers SET id='minimax', name='minimax' WHERE id='provider-text'"
        )
        db.execute(
            """UPDATE llm_models
            SET provider_id='minimax', model_id='speech-2.6-hd', model_name='MiniMax-speech-2.6-hd',
                model_type='tts', capabilities='[\"text-to-speech\"]'
            WHERE id='model-text'"""
        )
        db.execute(
            "UPDATE llm_configs SET test_message='MiniMax API 连接成功！' WHERE id='config-text'"
        )

    result = _run(source, target, "config-text")

    assert result.returncode != 0
    assert not target.exists()
    assert secret not in result.stdout + result.stderr


def test_staging_accepts_current_exact_minimax_tts_voice_proof(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    _source(source)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE llm_providers SET id='minimax', name='minimax' WHERE id='provider-text'")
        db.execute(
            """UPDATE llm_models
            SET provider_id='minimax', model_id='speech-2.6-hd', model_name='MiniMax-speech-2.6-hd',
                model_type='tts', capabilities='[\"text-to-speech\"]'
            WHERE id='model-text'"""
        )
        db.execute(
            "UPDATE llm_configs SET test_message=? WHERE id='config-text'",
            (minimax_tts_verification_message("speech-2.6-hd"),),
        )

    result = _run(source, target, "config-text")

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("invalid_status", ["pending", "failed", None])
def test_staging_rejects_unverified_config_and_cleans_target(tmp_path: Path, invalid_status: str | None) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    secret = _source(source)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE llm_configs SET test_status = ? WHERE id = 'config-text'", (invalid_status,))

    result = _run(source, target, "config-text")

    assert result.returncode != 0
    assert not target.exists()
    assert secret not in result.stdout + result.stderr


def test_staging_rejects_same_path_non_sqlite_and_non_owner(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    _source(source)
    assert _run(source, source, "config-text").returncode != 0

    bad_target = tmp_path / "target.txt"
    assert _run(source, bad_target, "config-text").returncode != 0
    assert not bad_target.exists()

    with sqlite3.connect(source) as db:
        db.execute("UPDATE llm_configs SET user_id = 'other-user' WHERE id = 'config-text'")
    target = tmp_path / "target.db"
    assert _run(source, target, "config-text").returncode != 0
    assert not target.exists()


def test_staging_requires_existing_parent_and_never_clobbers_existing_target(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    _source(source)
    missing_parent = tmp_path / "missing" / "target.db"
    assert _run(source, missing_parent, "config-text").returncode != 0
    assert not missing_parent.parent.exists()

    target = tmp_path / "target.db"
    target.write_bytes(b"owned by another process")
    result = _run(source, target, "config-text")
    assert result.returncode != 0
    assert target.read_bytes() == b"owned by another process"


def test_staging_upgrades_old_source_schema_to_current_operation_model_and_recovery_reads(tmp_path: Path) -> None:
    source = tmp_path / "old-source.db"
    target = tmp_path / "current-target.db"
    _source(source)
    with sqlite3.connect(source) as db:
        db.execute("DROP TABLE live_canary_provider_operations")
        db.execute(
            """CREATE TABLE live_canary_provider_operations (
            id VARCHAR(36) PRIMARY KEY, run_id VARCHAR(36) NOT NULL, user_id VARCHAR(36) NOT NULL,
            reservation_id VARCHAR(200) NOT NULL, capability VARCHAR(20) NOT NULL,
            job_type VARCHAR(40) NOT NULL, job_id VARCHAR(100) NOT NULL,
            provider_task_id VARCHAR(200), status VARCHAR(30) NOT NULL,
            actual_rmb VARCHAR(50), created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )"""
        )
        db.execute("CREATE TABLE retired_application_table (id TEXT PRIMARY KEY)")

    staged = _run(source, target, "config-text")
    assert staged.returncode == 0, staged.stderr.decode("utf-8", "replace")
    manifest = __import__("json").loads(staged.stdout)
    assert manifest["unrecognized_source_tables"] == ["retired_application_table"]
    with sqlite3.connect(target) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(live_canary_provider_operations)")}
        assert {"artifact_id", "cost_source", "recovery_reason"}.issubset(columns)
        assert db.execute("SELECT COUNT(*) FROM live_canary_provider_operations").fetchone() == (0,)
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []

    recovery_env = dict(os.environ)
    recovery_env.pop("E2E_REQUIRE_ISOLATED_DB", None)
    recovery_env["DATABASE_URL"] = f"sqlite+aiosqlite:///{target}"
    recovery = subprocess.run(
        [sys.executable, str(SCRIPT.parent / "recover_live_canary_operations.py"),
         "--database-url", f"sqlite+aiosqlite:///{target}", "--stale-minutes", "15"],
        env=recovery_env,
        capture_output=True,
        check=False,
    )
    assert recovery.returncode == 0, recovery.stderr.decode("utf-8", "replace")
    assert b'"scanned":0' in recovery.stdout
