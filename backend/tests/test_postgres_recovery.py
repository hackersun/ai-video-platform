from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest


DATABASE_URL = "postgresql://backup_user:very-secret@db.example.test:5433/app_restore_drill?sslmode=require"


class FakePostgresRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(
        self,
        command: list[str],
        *,
        env: dict[str, str],
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        self.calls.append((command, env))
        if command[-1:] == ["--version"]:
            return subprocess.CompletedProcess(
                command, 0, stdout=f"{command[0]} (PostgreSQL) 15.13", stderr=""
            )
        if command[0] == "pg_dump":
            output = Path(command[command.index("--file") + 1])
            output.write_bytes(b"postgres-custom-archive")
        return subprocess.CompletedProcess(command, 0, stdout="archive-list", stderr="")


def _recovery_module():
    return importlib.import_module("app.features.operations.postgres_recovery")


def test_backup_writes_atomic_private_archive_and_credential_free_manifest(tmp_path: Path) -> None:
    recovery = _recovery_module()
    runner = FakePostgresRunner()

    manifest = recovery.create_postgres_backup(
        DATABASE_URL,
        tmp_path / "backups",
        runner=runner,
        clock=lambda: datetime(2026, 8, 11, 4, 30, tzinfo=timezone.utc),
        release_sha="release-572ec1f6",
        label="pre-release",
    )

    assert manifest.archive_path.name == "ai-video-20260811T043000Z-pre-release.dump"
    assert manifest.archive_path.read_bytes() == b"postgres-custom-archive"
    assert manifest.sha256 == hashlib.sha256(b"postgres-custom-archive").hexdigest()
    assert manifest.size_bytes == len(b"postgres-custom-archive")
    assert stat_mode(manifest.archive_path) == 0o600
    assert stat_mode(manifest.manifest_path) == 0o600
    assert stat_mode(manifest.archive_path.parent) == 0o700

    payload = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    assert payload == {
        "archive_name": manifest.archive_path.name,
        "created_at": "2026-08-11T04:30:00+00:00",
        "release_sha": "release-572ec1f6",
        "sha256": manifest.sha256,
        "size_bytes": manifest.size_bytes,
    }
    serialized = manifest.manifest_path.read_text(encoding="utf-8")
    assert "very-secret" not in serialized
    assert "db.example.test" not in serialized

    dump_command, dump_env = next(call for call in runner.calls if "--file" in call[0])
    assert dump_command[:2] == ["pg_dump", "--format=custom"]
    assert "very-secret" not in " ".join(dump_command)
    assert dump_env["PGPASSWORD"] == "very-secret"
    assert dump_env["PGSSLMODE"] == "require"
    assert any(call[0][0:2] == ["pg_restore", "--list"] for call in runner.calls)
    assert not list(manifest.archive_path.parent.glob("*.partial"))


def test_backup_rejects_non_postgresql_database_before_running_command(tmp_path: Path) -> None:
    recovery = _recovery_module()
    runner = FakePostgresRunner()

    with pytest.raises(ValueError, match="仅支持 PostgreSQL"):
        recovery.create_postgres_backup(
            "sqlite:///unsafe.db",
            tmp_path,
            runner=runner,
        )

    assert runner.calls == []


def test_backup_rejects_client_major_that_does_not_match_current_server(tmp_path: Path) -> None:
    recovery = _recovery_module()

    class MismatchedRunner(FakePostgresRunner):
        def __call__(self, command: list[str], **kwargs):
            result = super().__call__(command, **kwargs)
            if command[-1:] == ["--version"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout=f"{command[0]} (PostgreSQL) 17.10", stderr=""
                )
            return result

    runner = MismatchedRunner()
    with pytest.raises(ValueError, match="PostgreSQL 15"):
        recovery.create_postgres_backup(DATABASE_URL, tmp_path, runner=runner)

    assert not any("--file" in command for command, _env in runner.calls)


def test_backup_never_overwrites_an_existing_archive(tmp_path: Path) -> None:
    recovery = _recovery_module()
    destination = tmp_path / "backups"
    destination.mkdir()
    existing = destination / "ai-video-20260811T043000Z-pre-release.dump"
    existing.write_bytes(b"immutable-existing-backup")
    runner = FakePostgresRunner()

    with pytest.raises(FileExistsError, match="已存在"):
        recovery.create_postgres_backup(
            DATABASE_URL,
            destination,
            runner=runner,
            clock=lambda: datetime(2026, 8, 11, 4, 30, tzinfo=timezone.utc),
            label="pre-release",
        )

    assert existing.read_bytes() == b"immutable-existing-backup"
    assert not any("--file" in command for command, _env in runner.calls)


def test_restore_requires_matching_target_confirmation_and_checksum(tmp_path: Path) -> None:
    recovery = _recovery_module()
    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"known-backup")
    manifest = tmp_path / "backup.dump.json"
    manifest.write_text(
        json.dumps(
            {
                "archive_name": archive.name,
                "created_at": "2026-08-11T04:30:00+00:00",
                "release_sha": "release-572ec1f6",
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "size_bytes": archive.stat().st_size,
            }
        ),
        encoding="utf-8",
    )
    runner = FakePostgresRunner()

    with pytest.raises(ValueError, match="目标数据库确认不匹配"):
        recovery.restore_postgres_backup(
            DATABASE_URL,
            archive,
            manifest,
            confirmation="wrong_database",
            runner=runner,
        )
    assert runner.calls == []

    archive.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="备份校验失败"):
        recovery.restore_postgres_backup(
            DATABASE_URL,
            archive,
            manifest,
            confirmation="app_restore_drill",
            runner=runner,
        )
    assert runner.calls == []


def test_restore_uses_safe_pg_restore_flags_after_validation(tmp_path: Path) -> None:
    recovery = _recovery_module()
    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"known-backup")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = tmp_path / "backup.dump.json"
    manifest.write_text(
        json.dumps(
            {
                "archive_name": archive.name,
                "created_at": "2026-08-11T04:30:00+00:00",
                "release_sha": "release-572ec1f6",
                "sha256": digest,
                "size_bytes": archive.stat().st_size,
            }
        ),
        encoding="utf-8",
    )
    runner = FakePostgresRunner()

    recovery.restore_postgres_backup(
        DATABASE_URL,
        archive,
        manifest,
        confirmation="app_restore_drill",
        runner=runner,
    )

    command, env = runner.calls[-1]
    assert command[0] == "pg_restore"
    assert {"--clean", "--if-exists", "--no-owner", "--no-acl", "--exit-on-error"} <= set(command)
    assert "--dbname" in command
    assert command[command.index("--dbname") + 1] == "app_restore_drill"
    assert "very-secret" not in " ".join(command)
    assert env["PGPASSWORD"] == "very-secret"


def stat_mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777
