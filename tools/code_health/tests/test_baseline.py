import json
from pathlib import Path

from tools.code_health.baseline import (
    Baseline,
    compare_to_baseline,
    load_baseline,
    write_baseline,
)
from tools.code_health.models import FileMetrics, ScanReport, Violation


def _metrics(
    path: str,
    effective_lines: int,
    violations: tuple[Violation, ...] = (),
) -> FileMetrics:
    return FileMetrics(path, "python", effective_lines, (), 0, (), violations)


def _report(*files: FileMetrics) -> ScanReport:
    return ScanReport(files=tuple(files), new_file_lines=500)


def _baseline(path: str, effective_lines: int, violations: tuple[Violation, ...] = ()) -> Baseline:
    return Baseline.from_report(_report(_metrics(path, effective_lines, violations)), commit="abc123")


def test_legacy_hotspot_may_shrink_but_not_grow() -> None:
    baseline = _baseline("legacy.py", 900)

    assert compare_to_baseline(_report(_metrics("legacy.py", 899)), baseline) == ()
    violations = compare_to_baseline(_report(_metrics("legacy.py", 901)), baseline)

    assert [item.code for item in violations] == ["legacy_file_grew"]


def test_new_file_uses_hard_limit() -> None:
    violations = compare_to_baseline(_report(_metrics("new.py", 501)), Baseline.empty())

    assert [item.code for item in violations] == ["new_file_too_long"]


def test_known_violation_is_suppressed_until_it_worsens() -> None:
    known = Violation(
        code="function_too_long",
        path="legacy.py",
        line=10,
        actual=90,
        allowed=80,
        message="legacy has 90 effective lines",
        subject="legacy",
    )
    baseline = _baseline("legacy.py", 100, (known,))
    unchanged = known.__class__(**{**known.__dict__, "line": 20})
    worsened = known.__class__(**{**known.__dict__, "actual": 91})

    assert compare_to_baseline(_report(_metrics("legacy.py", 100, (unchanged,))), baseline) == ()
    violations = compare_to_baseline(_report(_metrics("legacy.py", 100, (worsened,))), baseline)

    assert [item.code for item in violations] == ["function_too_long"]


def test_baseline_round_trip_is_sorted_and_versioned(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    report = _report(_metrics("z.py", 2), _metrics("a.py", 1))

    write_baseline(report, path, commit_sha="deadbeef")
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert raw["version"] == 1
    assert raw["commit"] == "deadbeef"
    assert list(raw["files"]) == ["a.py", "z.py"]
    assert load_baseline(path).commit == "deadbeef"
