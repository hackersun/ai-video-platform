"""Stable repository baseline and new-regression comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.code_health.models import FileMetrics, ScanReport, Violation


class BaselineError(ValueError):
    """Raised when a baseline cannot be trusted."""


@dataclass(frozen=True)
class KnownViolation:
    code: str
    subject: str
    actual: int | str


@dataclass(frozen=True)
class BaselineFile:
    effective_lines: int
    max_function_lines: int
    route_count: int
    known_violations: tuple[KnownViolation, ...]


@dataclass(frozen=True)
class Baseline:
    version: int
    commit: str
    generated_at: str
    new_file_lines: int
    files: dict[str, BaselineFile]

    @classmethod
    def empty(cls, *, new_file_lines: int = 500) -> "Baseline":
        return cls(1, "", "", new_file_lines, {})

    @classmethod
    def from_report(cls, report: ScanReport, *, commit: str) -> "Baseline":
        generated_at = datetime.now(timezone.utc).isoformat()
        files = {item.path: _baseline_file(item) for item in sorted(report.files, key=lambda value: value.path)}
        return cls(1, commit, generated_at, report.new_file_lines, files)


def _known_violation(item: Violation) -> KnownViolation:
    return KnownViolation(item.code, item.subject or item.path, item.actual)


def _baseline_file(item: FileMetrics) -> BaselineFile:
    known = tuple(
        sorted(
            (_known_violation(value) for value in item.violations if not value.code.endswith("syntax_error")),
            key=lambda value: (value.code, value.subject, str(value.actual)),
        )
    )
    return BaselineFile(
        effective_lines=item.effective_lines,
        max_function_lines=max((function.effective_lines for function in item.functions), default=0),
        route_count=item.route_count,
        known_violations=known,
    )


def _worsened(current: int | str, previous: int | str) -> bool:
    if isinstance(current, int) and isinstance(previous, int):
        return current > previous
    return current != previous


def _is_new_or_worse(item: Violation, previous: BaselineFile) -> bool:
    identity = (item.code, item.subject or item.path)
    known = {
        (value.code, value.subject): value.actual
        for value in previous.known_violations
    }
    return identity not in known or _worsened(item.actual, known[identity])


def _new_violation(code: str, item: FileMetrics, allowed: int, message: str) -> Violation:
    return Violation(code, item.path, 1, item.effective_lines, allowed, message, item.path)


def compare_to_baseline(report: ScanReport, baseline: Baseline) -> tuple[Violation, ...]:
    violations: list[Violation] = []
    for item in sorted(report.files, key=lambda value: value.path):
        previous = baseline.files.get(item.path)
        if previous is None:
            if item.effective_lines > report.new_file_lines:
                violations.append(_new_violation(
                    "new_file_too_long", item, report.new_file_lines,
                    f"{item.path} has {item.effective_lines} effective lines; new-file limit is {report.new_file_lines}",
                ))
            violations.extend(item.violations)
            continue
        if item.effective_lines > previous.effective_lines:
            violations.append(_new_violation(
                "legacy_file_grew", item, previous.effective_lines,
                f"{item.path} grew from {previous.effective_lines} to {item.effective_lines} effective lines",
            ))
        violations.extend(
            value
            for value in item.violations
            if value.code.endswith("syntax_error") or _is_new_or_worse(value, previous)
        )
    return tuple(sorted(violations, key=lambda value: (value.path, value.code, value.subject, value.line)))


def _serialize(baseline: Baseline) -> dict[str, Any]:
    return {
        "version": baseline.version,
        "commit": baseline.commit,
        "generated_at": baseline.generated_at,
        "limits": {"new_file_lines": baseline.new_file_lines},
        "files": {
            path: {
                "effective_lines": item.effective_lines,
                "max_function_lines": item.max_function_lines,
                "route_count": item.route_count,
                "known_violations": [
                    {"code": value.code, "subject": value.subject, "actual": value.actual}
                    for value in item.known_violations
                ],
            }
            for path, item in sorted(baseline.files.items())
        },
    }


def write_baseline(report: ScanReport, path: Path, commit_sha: str) -> None:
    baseline = Baseline.from_report(report, commit=commit_sha)
    path.write_text(json.dumps(_serialize(baseline), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> Baseline:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != 1:
            raise BaselineError("baseline version must be 1")
        limit = int(raw["limits"]["new_file_lines"])
        files = {
            name: BaselineFile(
                effective_lines=int(value["effective_lines"]),
                max_function_lines=int(value["max_function_lines"]),
                route_count=int(value["route_count"]),
                known_violations=tuple(
                    KnownViolation(str(item["code"]), str(item["subject"]), item["actual"])
                    for item in value.get("known_violations", [])
                ),
            )
            for name, value in raw["files"].items()
        }
        return Baseline(1, str(raw["commit"]), str(raw["generated_at"]), limit, files)
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        if isinstance(error, BaselineError):
            raise
        raise BaselineError(f"cannot load baseline: {error}") from error


__all__ = ["Baseline", "BaselineError", "compare_to_baseline", "load_baseline", "write_baseline"]
