"""Human and machine-readable code-health reports."""

from __future__ import annotations

import json
from pathlib import Path

from tools.code_health.models import ScanReport, Violation


def render_text_report(report: ScanReport, violations: tuple[Violation, ...]) -> str:
    effective_lines = sum(item.effective_lines for item in report.files)
    lines = [
        "代码健康检查",
        f"扫描文件: {len(report.files)}，有效代码行: {effective_lines}，阻塞项: {len(violations)}",
    ]
    if not violations:
        lines.append("结果: 未发现相对基线新增或恶化的问题。")
    else:
        lines.append("结果: 以下问题为新增或相对基线发生恶化：")
        lines.extend(
            f"- {item.code} {item.path}:{item.line} {item.message}"
            for item in violations
        )
    return "\n".join(lines)


def _violation_payload(item: Violation) -> dict[str, int | str]:
    return {
        "code": item.code,
        "path": item.path,
        "line": item.line,
        "subject": item.subject,
        "actual": item.actual,
        "allowed": item.allowed,
        "message": item.message,
    }


def write_json_report(path: Path, report: ScanReport, violations: tuple[Violation, ...]) -> None:
    payload = {
        "version": 1,
        "summary": {
            "scanned_files": len(report.files),
            "effective_lines": sum(item.effective_lines for item in report.files),
            "blocking_violations": len(violations),
        },
        "violations": [_violation_payload(item) for item in violations],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


__all__ = ["render_text_report", "write_json_report"]
