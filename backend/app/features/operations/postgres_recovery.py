"""Fail-closed PostgreSQL backup and restore primitives."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse


Runner = Callable[..., subprocess.CompletedProcess[str]]
_LABEL_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_POSTGRES_VERSION_PATTERN = re.compile(r"PostgreSQL\)\s+(\d+)(?:\.\d+)?")


@dataclass(frozen=True)
class BackupManifest:
    archive_path: Path
    manifest_path: Path
    created_at: str
    release_sha: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class _PostgresTarget:
    database: str
    command_options: tuple[str, ...]
    environment: dict[str, str]


def _parse_target(database_url: str) -> _PostgresTarget:
    parsed = urlparse(str(database_url or "").strip())
    scheme = parsed.scheme.split("+", 1)[0].lower()
    database = unquote(parsed.path.lstrip("/"))
    if scheme not in {"postgres", "postgresql"} or not database:
        raise ValueError("备份与恢复仅支持 PostgreSQL 数据库")

    options: list[str] = []
    if parsed.hostname:
        options.extend(["--host", parsed.hostname])
    if parsed.port:
        options.extend(["--port", str(parsed.port)])
    if parsed.username:
        options.extend(["--username", unquote(parsed.username)])
    options.extend(["--dbname", database])

    environment = dict(os.environ)
    if parsed.password:
        environment["PGPASSWORD"] = unquote(parsed.password)
    sslmode = parse_qs(parsed.query).get("sslmode", [None])[0]
    if sslmode:
        environment["PGSSLMODE"] = sslmode
    return _PostgresTarget(database, tuple(options), environment)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    runner: Runner,
    command: list[str],
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _require_client_major(
    runner: Runner,
    executable: str,
    environment: dict[str, str],
    expected_major: int,
) -> None:
    result = _run(runner, [executable, "--version"], environment)
    match = _POSTGRES_VERSION_PATTERN.search(result.stdout or "")
    actual = int(match.group(1)) if match else None
    if actual != expected_major:
        detected = str(actual) if actual is not None else "未知版本"
        raise ValueError(
            f"当前数据库要求 PostgreSQL {expected_major} 客户端，"
            f"检测到 {executable} {detected}；已停止操作"
        )


def _require_recovery_clients(
    runner: Runner,
    environment: dict[str, str],
    expected_major: int,
) -> None:
    for executable in ("pg_dump", "pg_restore"):
        _require_client_major(runner, executable, environment, expected_major)


def _safe_label(value: str) -> str:
    normalized = _LABEL_PATTERN.sub("-", str(value or "backup").strip()).strip("-._")
    return normalized[:48] or "backup"


def create_postgres_backup(
    database_url: str,
    output_dir: str | Path,
    *,
    runner: Runner = subprocess.run,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    release_sha: str = "unknown",
    label: str = "backup",
    expected_client_major: int = 15,
) -> BackupManifest:
    target = _parse_target(database_url)
    _require_recovery_clients(runner, target.environment, expected_client_major)
    created = clock().astimezone(timezone.utc)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    timestamp = created.strftime("%Y%m%dT%H%M%SZ")
    archive = destination / f"ai-video-{timestamp}-{_safe_label(label)}.dump"
    manifest_path = archive.with_suffix(".dump.json")
    partial_archive = archive.with_suffix(".dump.partial")
    partial_manifest = archive.with_suffix(".dump.json.partial")
    lock_path = archive.with_suffix(".dump.lock")
    if archive.exists() or manifest_path.exists():
        raise FileExistsError("同名备份已存在，未覆盖原备份")
    try:
        lock_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError("同名备份正在生成，未启动重复备份") from exc
    os.close(lock_descriptor)

    try:
        command = ["pg_dump", "--format=custom", "--no-owner", "--no-acl"]
        command.extend(target.command_options)
        command.extend(["--file", str(partial_archive)])
        _run(runner, command, target.environment)
        partial_archive.chmod(0o600)
        _run(runner, ["pg_restore", "--list", str(partial_archive)], target.environment)
        os.replace(partial_archive, archive)
        archive.chmod(0o600)

        payload = {
            "archive_name": archive.name,
            "created_at": created.isoformat(),
            "release_sha": str(release_sha or "unknown"),
            "sha256": _sha256(archive),
            "size_bytes": archive.stat().st_size,
        }
        partial_manifest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        partial_manifest.chmod(0o600)
        os.replace(partial_manifest, manifest_path)
        manifest_path.chmod(0o600)
        return BackupManifest(
            archive_path=archive,
            manifest_path=manifest_path,
            **{key: payload[key] for key in ("created_at", "release_sha", "sha256", "size_bytes")},
        )
    finally:
        partial_archive.unlink(missing_ok=True)
        partial_manifest.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)


def restore_postgres_backup(
    database_url: str,
    archive_path: str | Path,
    manifest_path: str | Path,
    *,
    confirmation: str,
    runner: Runner = subprocess.run,
    expected_client_major: int = 15,
) -> None:
    target = _parse_target(database_url)
    if confirmation != target.database:
        raise ValueError("目标数据库确认不匹配，已停止恢复")

    archive = Path(archive_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    valid = (
        manifest.get("archive_name") == archive.name
        and manifest.get("size_bytes") == archive.stat().st_size
        and manifest.get("sha256") == _sha256(archive)
    )
    if not valid:
        raise ValueError("备份校验失败，已停止恢复")

    _require_recovery_clients(runner, target.environment, expected_client_major)
    _run(runner, ["pg_restore", "--list", str(archive)], target.environment)
    command = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--exit-on-error",
    ]
    command.extend(target.command_options)
    command.append(str(archive))
    _run(runner, command, target.environment)
