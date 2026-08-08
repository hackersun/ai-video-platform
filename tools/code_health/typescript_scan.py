"""Python wrapper around the repository TypeScript compiler scanner."""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from tools.code_health.models import FileMetrics, FunctionMetrics, Violation
from tools.code_health.policy import Policy


def _function(raw: dict) -> FunctionMetrics:
    return FunctionMetrics(
        name=str(raw["name"]),
        line=int(raw["line"]),
        end_line=int(raw["end_line"]),
        effective_lines=int(raw["effective_lines"]),
        is_route=bool(raw.get("is_route")),
    )


def _violation(raw: dict) -> Violation:
    return Violation(
        code=str(raw["code"]),
        path=str(raw["path"]),
        line=int(raw["line"]),
        actual=raw["actual"],
        allowed=raw["allowed"],
        message=str(raw["message"]),
        subject=str(raw.get("subject") or ""),
    )


def _metrics(raw: dict) -> FileMetrics:
    return FileMetrics(
        path=str(raw["path"]),
        language=str(raw["language"]),
        effective_lines=int(raw["effective_lines"]),
        functions=tuple(_function(item) for item in raw.get("functions", [])),
        route_count=int(raw.get("route_count", 0)),
        imports=tuple(str(item) for item in raw.get("imports", [])),
        violations=tuple(_violation(item) for item in raw.get("violations", [])),
    )


def scan_typescript_files(paths: list[Path], repo_root: Path, policy: Policy) -> tuple[FileMetrics, ...]:
    if not paths:
        return ()
    tool_root = Path(__file__).resolve().parents[2]
    with (
        tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as file_list,
        tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as policy_file,
    ):
        json.dump([str(path.resolve()) for path in paths], file_list)
        file_list.flush()
        json.dump(asdict(policy), policy_file)
        policy_file.flush()
        result = subprocess.run(
            [
                "node",
                str(tool_root / "tools/code_health/typescript_scan.mjs"),
                str(tool_root),
                str(repo_root),
                file_list.name,
                policy_file.name,
            ],
            cwd=tool_root,
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown TypeScript scanner error"
        raise RuntimeError(detail)
    payload = json.loads(result.stdout)
    return tuple(_metrics(item) for item in payload.get("files", []))


__all__ = ["scan_typescript_files"]
