import subprocess
import sys
from pathlib import Path

from tools.code_health.baseline import write_baseline
from tools.code_health.models import FileMetrics, ScanReport


REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK = REPO_ROOT / "tools/code_health/check.py"
POLICY = REPO_ROOT / "tools/code_health/policy.json"


def _write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"value_{index} = {index}\n" for index in range(count)), encoding="utf-8")


def _baseline(path: Path, *, effective_lines: int) -> None:
    report = ScanReport(
        files=(FileMetrics("backend/app/legacy.py", "python", effective_lines, (), 0, (), ()),),
        new_file_lines=500,
    )
    write_baseline(report, path, commit_sha="fixture")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _run(root: Path, baseline: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "--repo-root",
            str(root),
            "--policy",
            str(POLICY),
            "--baseline",
            str(baseline),
            *extra,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_is_read_only_and_returns_one_for_growth(tmp_path: Path) -> None:
    source = tmp_path / "backend/app/legacy.py"
    baseline = tmp_path / "baseline.json"
    _write_lines(source, 11)
    _baseline(baseline, effective_lines=10)
    before = _snapshot(tmp_path)

    result = _run(tmp_path, baseline)

    assert result.returncode == 1
    assert "legacy_file_grew" in result.stdout
    assert _snapshot(tmp_path) == before


def test_report_only_returns_zero_with_visible_violations(tmp_path: Path) -> None:
    source = tmp_path / "backend/app/legacy.py"
    baseline = tmp_path / "baseline.json"
    _write_lines(source, 11)
    _baseline(baseline, effective_lines=10)

    result = _run(tmp_path, baseline, "--report-only")

    assert result.returncode == 0
    assert "legacy_file_grew" in result.stdout


def test_json_report_writes_only_the_requested_file(tmp_path: Path) -> None:
    source = tmp_path / "backend/app/legacy.py"
    baseline = tmp_path / "baseline.json"
    report = tmp_path / "reports/health.json"
    _write_lines(source, 10)
    _baseline(baseline, effective_lines=10)

    result = _run(tmp_path, baseline, "--json-report", str(report))

    assert result.returncode == 0
    assert report.is_file()
    assert '"blocking_violations": 0' in report.read_text(encoding="utf-8")
