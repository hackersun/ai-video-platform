"""Explicit dry-run/apply workflow for legacy scoped-reference backfill."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ..domain.scoped_reference import canonical_json_sha256


MANIFEST_VERSION = "scoped-ref-backfill-manifest-v1"
MANIFEST_HASH_VERSION = "scoped-ref-backfill-sha256-cjson-v1"
IMMUTABLE_DIAGNOSTIC = Path("/tmp/wave1-20260713-third-live-latest.db")


def _without_hash(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key != "manifest_sha256"}


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    return canonical_json_sha256(_without_hash(manifest))


def _legacy_ref_hash(item: Mapping[str, Any]) -> str:
    legacy = dict(item.get("legacy_ref") or {})
    return canonical_json_sha256({
        "entity_id": legacy.get("entity_id"), "entity_type": legacy.get("entity_type"),
        "shot_id": item.get("shot_id"), "chapter_id": item.get("chapter_id"),
    })


def _proposed_ref(item: Mapping[str, Any]) -> dict[str, Any]:
    if item.get("proposed_ref"):
        return copy.deepcopy(dict(item["proposed_ref"]))
    legacy = dict(item.get("legacy_ref") or {})
    payload = {
        "contract_version": "chapter_evidence_ref_v1",
        "source_entity_id": item.get("source_entity_id"),
        "entity_type": item.get("entity_type"), "as_of_chapter_id": item.get("chapter_id"),
        "shot_id": item.get("shot_id"), "legacy_ref_sha256": _legacy_ref_hash(item),
    }
    return {**payload, "backfill_ref_sha256": canonical_json_sha256(payload)}


def _ref_decisions(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{
        "shot_id": item.get("shot_id"), "entity_type": item.get("entity_type"),
        "source_entity_id": item.get("source_entity_id"), "chapter_id": item.get("chapter_id"),
        "eligible": bool(item.get("eligible")), "reason_code": item.get("reason_code"),
        "legacy_ref_hash": _legacy_ref_hash(item), "proposed_ref": _proposed_ref(item),
    } for item in state.get("legacy_refs") or []]


def _snapshot_projection(state: Mapping[str, Any]) -> dict[str, Any]:
    legacy = [{key: item.get(key) for key in (
        "shot_id", "entity_type", "source_entity_id", "chapter_id", "eligible", "reason_code",
    )} | {"legacy_ref_hash": _legacy_ref_hash(item)} for item in state.get("legacy_refs") or []]
    return {
        "database_identity": state.get("database_identity"), "run_id": state.get("run_id"),
        "user_id": state.get("user_id"), "novel_id": state.get("novel_id"),
        "run_row_version": state.get("run_row_version"),
        "series_plan_version": state.get("series_plan_version"),
        "source_version": state.get("source_version"),
        "lock_contract_version": state.get("lock_contract_version"),
        "episode_fingerprint": state.get("episode_fingerprint"),
        "no_op": bool(state.get("no_op")),
        "chapters": state.get("chapters"), "shots": state.get("shots"),
        "history_fingerprints": state.get("history_fingerprints") or {},
        "merge_audit_fingerprints": state.get("merge_audit_fingerprints") or {},
        "legacy_refs": legacy,
    }


def _manifest(state: Mapping[str, Any]) -> dict[str, Any]:
    decisions = _ref_decisions(state)
    value = {
        "manifest_version": MANIFEST_VERSION, "manifest_hash_version": MANIFEST_HASH_VERSION,
        "database_identity": state.get("database_identity"), "run_id": state.get("run_id"),
        "user_id": state.get("user_id"), "novel_id": state.get("novel_id"),
        "run_row_version": state.get("run_row_version"),
        "series_plan_version": state.get("series_plan_version"),
        "source_version": state.get("source_version"),
        "lock_contract_version": state.get("lock_contract_version"),
        "episode_fingerprint": state.get("episode_fingerprint"),
        "no_op": bool(state.get("no_op")),
        "chapters": copy.deepcopy(state.get("chapters") or {}),
        "shots": copy.deepcopy(state.get("shots") or {}),
        "history_fingerprints": copy.deepcopy(state.get("history_fingerprints") or {}),
        "merge_audit_fingerprints": copy.deepcopy(state.get("merge_audit_fingerprints") or {}),
        "ref_decisions": decisions,
        "preapply_fingerprint": canonical_json_sha256(_snapshot_projection(state)),
    }
    value["manifest_sha256"] = manifest_sha256(value)
    return value


def _write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, (json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")) + "\n").encode())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def dry_run_backfill(repository: Any, *, run_id: str, manifest_path: Path) -> dict[str, Any]:
    state = repository.snapshot(read_only=True)
    if state.get("run_id") != run_id:
        raise ValueError("run ownership mismatch")
    manifest = _manifest(state)
    _write_manifest(Path(manifest_path), manifest)
    eligible = [item for item in manifest["ref_decisions"] if item["eligible"]]
    return {"eligible": len(eligible) == len(manifest["ref_decisions"]),
            "eligible_ref_count": len(eligible), "manifest_sha256": manifest["manifest_sha256"]}


def _read_manifest(path: Path, expected_hash: str) -> dict[str, Any]:
    if path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("manifest permissions must be 0600")
    manifest = json.loads(path.read_text())
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("manifest schema version mismatch")
    actual = manifest_sha256(manifest)
    if actual != expected_hash or manifest.get("manifest_sha256") != actual:
        raise ValueError("manifest hash mismatch")
    return manifest


def _already_applied(state: Mapping[str, Any], manifest_hash: str) -> bool:
    return any(item.get("manifest_sha256") == manifest_hash and item.get("outcome") == "applied"
               for item in state.get("audit") or [])


def _validate_current(state: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    if canonical_json_sha256(_snapshot_projection(state)) != manifest.get("preapply_fingerprint"):
        raise ValueError("stale manifest or repository drift")
    if any(not item.get("eligible") for item in manifest.get("ref_decisions") or []):
        raise ValueError("manifest contains ineligible edge")
    listed = {item.get("shot_id") for item in manifest.get("ref_decisions") or []}
    if not listed or not listed.issubset(set((state.get("shots") or {}).keys())):
        raise ValueError("shot ownership or resolvability drift")


def apply_backfill(
    repository: Any, *, manifest_path: Path, expected_manifest_hash: str,
    fail_at: str | None = None, database_path: Path | None = None,
) -> dict[str, Any]:
    if database_path is not None and Path(database_path).resolve() == IMMUTABLE_DIAGNOSTIC.resolve():
        raise ValueError("diagnostic original is immutable")
    manifest = _read_manifest(Path(manifest_path), expected_manifest_hash)
    if _already_applied(repository.state, expected_manifest_hash):
        return {"idempotent": True, "updated_ref_count": 0}
    with repository.transaction() as state:
        _validate_current(state, manifest)
        decisions = list(manifest["ref_decisions"])
        for index, item in enumerate(decisions):
            state["shots"][item["shot_id"]]["entity_refs"] = [copy.deepcopy(item["proposed_ref"])]
            state["shots"][item["shot_id"]]["refs_version"] = "chapter_evidence_ref_v1"
            if fail_at == "after_first_ref" and index == 0:
                raise RuntimeError("injected failure after_first_ref")
        if fail_at == "after_last_ref":
            raise RuntimeError("injected failure after_last_ref")
        state.setdefault("audit", []).append({"manifest_sha256": expected_manifest_hash,
                                               "outcome": "applied", "updated_ref_count": len(decisions)})
        if fail_at == "after_audit":
            raise RuntimeError("injected failure after_audit")
        if fail_at == "before_commit":
            raise RuntimeError("injected failure before_commit")
    return {"idempotent": False, "updated_ref_count": len(manifest["ref_decisions"])}


def inject_repository_drift(repository: Any, kind: str) -> None:
    if kind == "chapter":
        next(iter(repository.state["chapters"].values()))["row_version"] += 1
    elif kind == "shot":
        next(iter(repository.state["shots"].values()))["row_version"] += 1
    elif kind == "history":
        repository.state.setdefault("history_fingerprints", {})["changed"] = "drift"
    elif kind == "merge_audit":
        repository.state.setdefault("merge_audit_fingerprints", {})["changed"] = "drift"
    else:
        raise ValueError("unknown drift kind")
