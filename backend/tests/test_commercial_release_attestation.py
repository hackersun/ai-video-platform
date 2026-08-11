from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_commercial_release.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("commercial_release_gate", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gate(gate_id: str, *, status: str = "blocked") -> dict:
    payload = {
        "id": gate_id,
        "name_cn": f"{gate_id} 商业门禁",
        "status": status,
        "owner": "发布负责人",
        "summary_cn": "当前证据仍需补齐。" if status == "blocked" else "当前证据已经复核通过。",
        "evidence": ["docs/release/commercial-release-gates.md"],
    }
    if status == "blocked":
        payload["remediation_cn"] = "完成对应验收并补充可核验的证据。"
    else:
        payload["verified_at"] = "2026-08-11T00:00:00Z"
        payload["valid_until"] = "2026-09-11T00:00:00Z"
    return payload


def _manifest(*, status: str = "blocked") -> dict:
    return {
        "schema_version": 1,
        "candidate_version": "2026.08.11-rc1",
        "candidate_source": "releases",
        "generated_at": "2026-08-11T00:00:00Z",
        "gates": [_gate(f"G{index}", status=status) for index in range(9)],
    }


def _validate(manifest: dict, *, target: str = "releases", source: str = "dev") -> list[str]:
    module = _load_module()
    return module.validate_release_attestation(
        manifest,
        repo_root=REPO_ROOT,
        target_branch=target,
        source_branch=source,
        event_name="pull_request",
        now=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )


def test_candidate_branch_accepts_explicit_blockers() -> None:
    assert _validate(_manifest()) == []


def test_requires_exactly_one_of_each_commercial_gate() -> None:
    manifest = _manifest()
    manifest["gates"][-1]["id"] = "G7"

    errors = _validate(manifest)

    assert any("缺少门禁 G8" in error for error in errors)
    assert any("门禁 G7 重复" in error for error in errors)


def test_rejects_missing_local_evidence_and_insecure_external_link() -> None:
    manifest = _manifest()
    manifest["gates"][0]["evidence"] = ["docs/release/evidence/not-found.md"]
    manifest["gates"][1]["evidence"] = ["http://evidence.example.test/report"]

    errors = _validate(manifest)

    assert any("证据文件不存在" in error for error in errors)
    assert any("外部证据必须使用 HTTPS" in error for error in errors)


def test_blocker_requires_chinese_reason_and_remediation() -> None:
    manifest = _manifest()
    manifest["gates"][0]["summary_cn"] = "pending"
    manifest["gates"][0]["remediation_cn"] = "fix it"

    errors = _validate(manifest)

    assert any("状态说明必须使用中文" in error for error in errors)
    assert any("修复动作必须使用中文" in error for error in errors)


def test_main_pull_request_must_come_from_releases_and_have_no_blockers() -> None:
    errors = _validate(_manifest(), target="main", source="dev")

    assert any("合入 main 的 PR 必须来自 releases" in error for error in errors)
    assert any("G0 尚未通过" in error for error in errors)


def test_main_rejects_expired_attestation() -> None:
    manifest = _manifest(status="pass")
    manifest["gates"][3]["valid_until"] = "2026-08-11T01:00:00Z"

    errors = _validate(manifest, target="main", source="releases")

    assert any("G3 的证明已过期" in error for error in errors)


def test_main_accepts_complete_current_attestation_from_releases() -> None:
    assert _validate(_manifest(status="pass"), target="main", source="releases") == []


def test_repository_candidate_is_valid_but_still_blocks_main() -> None:
    manifest = json.loads(
        (REPO_ROOT / "docs/release/evidence/commercial-candidate.json").read_text(encoding="utf-8")
    )

    assert _validate(manifest) == []
    main_errors = _validate(manifest, target="main", source="releases")

    assert sum("尚未通过" in error for error in main_errors) == 7
