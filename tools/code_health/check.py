#!/usr/bin/env python3
"""Read-only repository code-health ratchet command."""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path


TOOL_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(TOOL_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_REPO_ROOT))

from tools.code_health.baseline import Baseline, compare_to_baseline, load_baseline, write_baseline
from tools.code_health.models import FileMetrics, ScanReport
from tools.code_health.policy import Policy, load_policy
from tools.code_health.python_scan import scan_python_file
from tools.code_health.report import render_text_report, write_json_report
from tools.code_health.typescript_scan import scan_typescript_files


SOURCE_SUFFIXES = {".py", ".ts", ".tsx"}


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.replace("**/", ""))


def discover_source_files(repo_root: Path, policy: Policy) -> tuple[Path, ...]:
    discovered: list[Path] = []
    for root_name in policy.roots:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            relative = path.relative_to(repo_root).as_posix()
            if any(_matches(relative, pattern) for pattern in policy.exclude):
                continue
            discovered.append(path)
    return tuple(sorted(set(discovered), key=lambda value: value.as_posix()))


def scan_repository(paths: tuple[Path, ...], repo_root: Path, policy: Policy) -> ScanReport:
    python_files = [path for path in paths if path.suffix == ".py"]
    typescript_files = [path for path in paths if path.suffix in {".ts", ".tsx"}]
    files: list[FileMetrics] = [scan_python_file(path, repo_root, policy) for path in python_files]
    files.extend(scan_typescript_files(typescript_files, repo_root, policy))
    return ScanReport(
        files=tuple(sorted(files, key=lambda value: value.path)),
        new_file_lines=policy.limits.new_file_lines,
    )


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout.strip()


def _snapshot(report: ScanReport, repo_root: Path, output: Path) -> int:
    if _git(repo_root, "status", "--porcelain=v1"):
        raise RuntimeError("工作区存在未提交改动，不能生成权威基线。请先提交或清理后重试。")
    syntax_errors = [
        violation
        for item in report.files
        for violation in item.violations
        if violation.code.endswith("syntax_error")
    ]
    if syntax_errors:
        raise RuntimeError("源码存在语法错误，不能将其写入权威基线。")
    commit = _git(repo_root, "rev-parse", "HEAD")
    write_baseline(report, output, commit_sha=commit)
    print(f"已生成代码健康基线: {output}（提交 {commit}）")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查代码健康规则相对基线是否恶化")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--policy", type=Path, default=Path("tools/code_health/policy.json"))
    parser.add_argument("--baseline", type=Path, default=Path("tools/code_health/baseline.json"))
    parser.add_argument("--report-only", action="store_true", help="只报告，不因问题返回失败")
    parser.add_argument("--json-report", type=Path, help="把机器报告写入指定文件")
    parser.add_argument("--snapshot", action="store_true", help="从干净工作区生成权威基线")
    parser.add_argument("--output", type=Path, help="基线输出路径，默认使用 --baseline")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    policy = load_policy(args.policy.resolve())
    report = scan_repository(discover_source_files(repo_root, policy), repo_root, policy)
    if args.snapshot:
        return _snapshot(report, repo_root, (args.output or args.baseline).resolve())
    baseline = load_baseline(args.baseline.resolve()) if args.baseline.is_file() else Baseline.empty(
        new_file_lines=policy.limits.new_file_lines,
    )
    violations = compare_to_baseline(report, baseline)
    print(render_text_report(report, violations))
    if args.json_report:
        write_json_report(args.json_report.resolve(), report, violations)
    return 0 if args.report_only or not violations else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"代码健康检查失败: {error}", file=sys.stderr)
        raise SystemExit(2) from error


__all__ = ["discover_source_files", "main", "scan_repository"]
