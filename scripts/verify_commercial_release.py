#!/usr/bin/env python3
"""校验商业发布证明；只有完整证据可以进入 main。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REQUIRED_GATES = tuple(f"G{index}" for index in range(9))
ALLOWED_STATUSES = {"pass", "blocked"}
CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
DEFAULT_MANIFEST = Path("docs/release/evidence/commercial-candidate.json")


def _has_chinese(value: Any) -> bool:
    return isinstance(value, str) and bool(CHINESE_PATTERN.search(value))


def _parse_timestamp(value: Any, field_label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field_label} 不能为空。")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field_label} 必须是带时区的 ISO 时间。")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field_label} 必须包含时区。")
        return None
    return parsed.astimezone(timezone.utc)


def _validate_evidence(gate_id: str, evidence: Any, repo_root: Path, errors: list[str]) -> None:
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{gate_id} 至少需要一条可核验的证据。")
        return
    root = repo_root.resolve()
    for item in evidence:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{gate_id} 包含空证据地址。")
            continue
        parsed = urlparse(item)
        if parsed.scheme:
            if parsed.scheme != "https":
                errors.append(f"{gate_id} 的外部证据必须使用 HTTPS：{item}")
            continue
        path = (root / item).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"{gate_id} 的证据路径不能越出仓库：{item}")
            continue
        if not path.is_file():
            errors.append(f"{gate_id} 的证据文件不存在：{item}")


def _validate_gate(
    gate: Any,
    *,
    repo_root: Path,
    strict_main: bool,
    now: datetime,
    errors: list[str],
) -> str | None:
    if not isinstance(gate, dict):
        errors.append("门禁条目必须是 JSON 对象。")
        return None
    gate_id = gate.get("id")
    if not isinstance(gate_id, str) or not gate_id:
        errors.append("门禁条目缺少 id。")
        return None
    if gate_id not in REQUIRED_GATES:
        errors.append(f"发现未知门禁 {gate_id}。")

    if not _has_chinese(gate.get("name_cn")):
        errors.append(f"{gate_id} 的门禁名称必须使用中文。")
    if not isinstance(gate.get("owner"), str) or not gate["owner"].strip():
        errors.append(f"{gate_id} 必须填写责任人。")
    if not _has_chinese(gate.get("summary_cn")):
        errors.append(f"{gate_id} 的状态说明必须使用中文。")

    status = gate.get("status")
    if status not in ALLOWED_STATUSES:
        errors.append(f"{gate_id} 的状态只能是 pass 或 blocked。")
    _validate_evidence(gate_id, gate.get("evidence"), repo_root, errors)

    if status == "blocked":
        if not _has_chinese(gate.get("remediation_cn")):
            errors.append(f"{gate_id} 的修复动作必须使用中文。")
        if strict_main:
            remediation = gate.get("remediation_cn") or "补齐验收证据并重新提交。"
            errors.append(f"{gate_id} 尚未通过：{remediation}")
        return gate_id

    if status == "pass":
        verified_at = _parse_timestamp(gate.get("verified_at"), f"{gate_id}.verified_at", errors)
        valid_until = _parse_timestamp(gate.get("valid_until"), f"{gate_id}.valid_until", errors)
        if verified_at and valid_until and valid_until <= verified_at:
            errors.append(f"{gate_id} 的有效期必须晚于核验时间。")
        if strict_main and valid_until and valid_until <= now:
            errors.append(f"{gate_id} 的证明已过期，请重新验收并更新有效期。")
    return gate_id


def validate_release_attestation(
    manifest: Any,
    *,
    repo_root: Path,
    target_branch: str,
    source_branch: str,
    event_name: str,
    now: datetime | None = None,
) -> list[str]:
    """返回全部中文错误；空列表表示当前目标分支允许继续。"""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["发布证明清单必须是 JSON 对象。"]
    if manifest.get("schema_version") != 1:
        errors.append("schema_version 必须为 1。")
    for field, label in (
        ("candidate_version", "候选版本"),
        ("candidate_source", "候选来源"),
    ):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            errors.append(f"{label}不能为空。")
    _parse_timestamp(manifest.get("generated_at"), "generated_at", errors)

    strict_main = target_branch == "main"
    if strict_main and event_name == "pull_request" and source_branch != "releases":
        errors.append("合入 main 的 PR 必须来自 releases 分支。")
    if strict_main and manifest.get("candidate_source") != "releases":
        errors.append("商业候选来源必须标记为 releases。")

    gates = manifest.get("gates")
    if not isinstance(gates, list):
        errors.append("gates 必须是数组。")
        return errors
    gate_ids = [gate.get("id") for gate in gates if isinstance(gate, dict)]
    counts = Counter(gate_ids)
    for gate_id in REQUIRED_GATES:
        if counts[gate_id] == 0:
            errors.append(f"缺少门禁 {gate_id}。")
        elif counts[gate_id] > 1:
            errors.append(f"门禁 {gate_id} 重复。")

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for gate in gates:
        _validate_gate(
            gate,
            repo_root=repo_root,
            strict_main=strict_main,
            now=current_time,
            errors=errors,
        )
    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验商业发布 G0-G8 证明")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--source-branch", default="")
    parser.add_argument("--event-name", default="local")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = args.manifest if args.manifest.is_absolute() else repo_root / args.manifest
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"商业发布门禁未通过：证明清单不存在：{manifest_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"商业发布门禁未通过：证明清单不是有效 JSON（第 {exc.lineno} 行）。", file=sys.stderr)
        return 1

    errors = validate_release_attestation(
        manifest,
        repo_root=repo_root,
        target_branch=args.target_branch,
        source_branch=args.source_branch,
        event_name=args.event_name,
    )
    if errors:
        print("商业发布门禁未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    blocked = sum(gate.get("status") == "blocked" for gate in manifest["gates"])
    if args.target_branch == "main":
        print("商业发布证明完整：G0-G8 均已通过，可以进入 main 合并审核。")
    else:
        print(f"商业候选证明结构有效：当前仍有 {blocked} 个阻塞门禁，候选分支可以继续完善。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
