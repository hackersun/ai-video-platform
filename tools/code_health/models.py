"""Serializable metrics shared by code-health scanners."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionMetrics:
    name: str
    line: int
    end_line: int
    effective_lines: int
    is_route: bool


@dataclass(frozen=True)
class Violation:
    code: str
    path: str
    line: int
    actual: int | str
    allowed: int | str
    message: str
    subject: str = ""


@dataclass(frozen=True)
class FileMetrics:
    path: str
    language: str
    effective_lines: int
    functions: tuple[FunctionMetrics, ...]
    route_count: int
    imports: tuple[str, ...]
    violations: tuple[Violation, ...]


@dataclass(frozen=True)
class ScanReport:
    files: tuple[FileMetrics, ...]
    new_file_lines: int


__all__ = ["FileMetrics", "FunctionMetrics", "ScanReport", "Violation"]
