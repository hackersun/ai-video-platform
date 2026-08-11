"""Fail CI when Git tracks common credential or database file types."""

from __future__ import annotations

import subprocess
from pathlib import PurePosixPath


_DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_PRIVATE_KEY_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}


def sensitive_reason(path: str) -> str | None:
    normalized = PurePosixPath(path)
    name = normalized.name.lower()
    suffix = normalized.suffix.lower()
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "环境变量文件"
    if name in {"id_rsa", "id_ed25519"} or suffix in _PRIVATE_KEY_SUFFIXES:
        return "私钥或证书密钥"
    if suffix in _DATABASE_SUFFIXES:
        return "数据库文件"
    return None


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings = [(path, sensitive_reason(path)) for path in tracked_paths()]
    blocked = [(path, reason) for path, reason in findings if reason]
    if not blocked:
        print("已跟踪敏感文件检查通过")
        return 0
    print("发现不应由 Git 跟踪的敏感文件：")
    for path, reason in blocked:
        print(f"- {path}：{reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
