"""Focused transaction coordinator for closure-v2 compatibility semantics."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from ..domain.closure_v2 import build_closure_v2, edge
from ..domain.scoped_reference import canonical_json_sha256, resolve_scoped_reference


CLOSURE_VERSION = "required_entity_closure_v2"
HASH_VERSION = "story-lock-source-cjson-v2"
ENTITY_TYPES = ("character", "scene", "prop", "event")


@dataclass(frozen=True)
class LockDecision:
    action: str
    existing_story_bible_id: str | None


def _current_bible(state: Mapping[str, Any]) -> tuple[str | None, Mapping[str, Any] | None]:
    bible_id = state.get("current_pointer")
    return (str(bible_id), (state.get("bibles") or {}).get(bible_id)) if bible_id else (None, None)


def read_lock_for_audit(state: Mapping[str, Any], bible_id: str) -> dict[str, Any]:
    bible = copy.deepcopy((state.get("bibles") or {}).get(bible_id))
    if bible is None:
        raise ValueError("story bible missing")
    bible["v2_ready"] = bible.get("closure_contract_version") == CLOSURE_VERSION
    return bible


def _validate_request(request: Mapping[str, Any]) -> None:
    if request.get("closure_contract_version") != CLOSURE_VERSION:
        raise ValueError("closure contract version must be required_entity_closure_v2")
    subjects = list(request.get("subjects") or [])
    edges = list(request.get("evidence_edges") or [])
    if not subjects or not edges:
        raise ValueError("missing closure subjects or evidence edges")
    _prepared_closure(request)


def _prepared_closure(request: Mapping[str, Any]):
    inputs = list(request.get("scoped_inputs") or [])
    if not inputs:
        raise ValueError("missing authoritative scoped inputs")
    resolved = [resolve_scoped_reference(item["reference"], item["owned"]) for item in inputs]
    derived_edges = [edge(item["reference"], value.canonical_entity_id)
                     for item, value in zip(inputs, resolved, strict=True)]
    if canonical_json_sha256(derived_edges) != canonical_json_sha256(request.get("evidence_edges")):
        raise ValueError("evidence edges mismatch authoritative resolution")
    return build_closure_v2(
        subjects=list(request.get("subjects") or []), edges=derived_edges,
        candidate_counts=dict(request.get("candidate_counts") or {}),
    )


def _required_counts(subjects: list[Mapping[str, Any]]) -> dict[str, int]:
    return {kind: sum(item.get("entity_type") == kind for item in subjects) for kind in ENTITY_TYPES}


def _bound_hashes(request: Mapping[str, Any]) -> dict[str, str]:
    closure = _prepared_closure(request)
    versions = {
        "closure_contract_version": CLOSURE_VERSION, "hash_version": HASH_VERSION,
        "ref_contract_version": "chapter_evidence_ref_v1",
        "ref_hash_version": "scoped-ref-sha256-cjson-v1",
        "identity_hash_version": "canonical-identity-key-v1",
    }
    source_hash = canonical_json_sha256({
        **versions, "input_source_hash": request.get("source_hash"),
        "subjects": list(closure.approval_subjects), "edges": list(closure.evidence_edges),
        "drift_factors": request.get("drift_factors") or {},
    })
    closure_hash = canonical_json_sha256({
        **versions, "input_closure_hash": request.get("closure_hash"),
        "subjects": list(closure.approval_subjects), "edges": list(closure.evidence_edges),
        "drift_factors": request.get("drift_factors") or {},
    })
    snapshot_hash = canonical_json_sha256({
        **versions, "input_snapshot_hash": request.get("snapshot_hash"),
        "source_hash": source_hash, "closure_hash": closure_hash,
    })
    return {"source_hash": source_hash, "closure_hash": closure_hash, "snapshot_hash": snapshot_hash}


def _request_fingerprint(request: Mapping[str, Any]) -> str:
    closure = _prepared_closure(request)
    return canonical_json_sha256({
        "closure_contract_version": CLOSURE_VERSION, "hashes": _bound_hashes(request),
        "subjects": list(closure.approval_subjects), "edges": list(closure.evidence_edges),
        "candidate_counts": request.get("candidate_counts"),
    })


def classify_existing_lock(state: Mapping[str, Any], request: Mapping[str, Any]) -> LockDecision:
    bible_id, bible = _current_bible(state)
    if bible is None or bible.get("closure_contract_version") != CLOSURE_VERSION:
        return LockDecision("supersede_and_create", bible_id)
    closure = _prepared_closure(request)
    expected = {
        "closure_contract_version": CLOSURE_VERSION, **_bound_hashes(request),
        "subjects": list(closure.approval_subjects), "evidence_edges": list(closure.evidence_edges),
    }
    persisted = {key: bible.get(key) for key in expected}
    if persisted == expected and bible.get("request_fingerprint") == _request_fingerprint(request):
        return LockDecision("reuse_exact_v2", bible_id)
    return LockDecision("supersede_and_create", bible_id)


def preview_v2_lock(request: Mapping[str, Any]) -> dict[str, Any]:
    _validate_request(request)
    closure = _prepared_closure(request)
    subjects = list(closure.approval_subjects)
    edges = list(closure.evidence_edges)
    candidates = {key: int(value) for key, value in request.get("candidate_counts", {}).items()}
    required_counts = _required_counts(subjects)
    return {
        "closure_contract_version": CLOSURE_VERSION,
        "candidate_counts": candidates, "required_counts": required_counts,
        "evidence_edge_count": len(edges), "required_evidence_count": len(edges),
        "unrelated_candidate_count": closure.unrelated_candidate_count,
        **_bound_hashes(request),
    }


def _safe_result(bible_id: str, request: Mapping[str, Any], *, idempotent: bool) -> dict[str, Any]:
    preview = preview_v2_lock(request)
    return {
        "story_bible_id": bible_id, "idempotent": idempotent,
        "closure_contract_version": CLOSURE_VERSION,
        "source_hash": preview["source_hash"], "closure_hash": preview["closure_hash"],
        "snapshot_hash": preview["snapshot_hash"],
        "required_counts": preview["required_counts"],
        "evidence_edge_count": preview["evidence_edge_count"],
        "required_evidence_count": preview["required_evidence_count"],
    }


def _fail(fail_at: str | None, point: str) -> None:
    if fail_at == point:
        raise RuntimeError(f"injected failure at {point}")


def apply_v2_lock(repository: Any, request: Mapping[str, Any], *, fail_at: str | None = None) -> dict[str, Any]:
    _validate_request(request)
    decision = classify_existing_lock(repository.state, request)
    if decision.action == "reuse_exact_v2":
        return _safe_result(str(decision.existing_story_bible_id), request, idempotent=True)
    fingerprint = _request_fingerprint(request)
    with repository.transaction() as state:
        old_id = state.get("current_pointer")
        if old_id:
            state.setdefault("audit", []).append({
                "event": "story_lock_superseded", "story_bible_id": old_id,
                "closure_contract_version": CLOSURE_VERSION, "request_fingerprint": fingerprint,
            })
        _fail(fail_at, "after_supersede")
        version = max((int(item.get("version", 0)) for item in state["bibles"].values()), default=0) + 1
        bible_id = f"bible-v{version}-{uuid4()}"
        closure = _prepared_closure(request)
        state.setdefault("bibles", {})[bible_id] = {
            "version": version,
            "closure_contract_version": CLOSURE_VERSION,
            "request_fingerprint": fingerprint, **_bound_hashes(request),
            "subjects": list(closure.approval_subjects),
            "evidence_edges": list(closure.evidence_edges),
        }
        _fail(fail_at, "after_bible_insert")
        state["current_pointer"] = bible_id
        state["run_story_locks"] = {
            "story_bible_id": bible_id, "closure_contract_version": CLOSURE_VERSION,
            "request_fingerprint": fingerprint, **_bound_hashes(request),
        }
        _fail(fail_at, "after_run_pointer")
        state["episode_contracts"] = {
            key: {**value, "story_bible_id": bible_id,
                  "closure_contract_version": CLOSURE_VERSION,
                  "snapshot_hash": _bound_hashes(request)["snapshot_hash"]}
            for key, value in (state.get("episode_contracts") or {}).items()
        }
        state["shot_lineage"] = {
            "story_bible_id": bible_id, "closure_contract_version": CLOSURE_VERSION,
            "evidence_edge_count": len(request.get("evidence_edges") or []),
        }
        _fail(fail_at, "after_episode_contracts")
        _fail(fail_at, "before_commit")
    return _safe_result(bible_id, request, idempotent=False)


def request_with_drift(request: Mapping[str, Any], drift: Mapping[str, Any]) -> dict[str, Any]:
    changed = copy.deepcopy(request)
    changed["source_hash"] = canonical_json_sha256({"prior": changed.get("source_hash"), "drift": dict(drift)})
    return changed


def request_with_attack(request: Mapping[str, Any], attack: str) -> dict[str, Any]:
    changed = copy.deepcopy(request)
    if attack == "missing":
        changed.pop("scoped_inputs", None)
    elif attack == "mismatch":
        changed["candidate_counts"]["character"] = 0
    elif attack == "future":
        changed["scoped_inputs"][0]["owned"]["authoritative_chapters"] = {}
    elif attack == "forged":
        changed["scoped_inputs"][0]["reference"]["evidence_ref_id"] = "f" * 64
    elif attack == "ambiguous":
        changed["subjects"].append(copy.deepcopy(changed["subjects"][0]))
    elif attack == "cross_owner":
        changed["scoped_inputs"][0]["owned"]["source_rows"][0]["user_id"] = "user-2"
    else:
        raise ValueError("unknown attack fixture")
    return changed


def project_request_as_of(request: Mapping[str, Any], *, shot_id: str) -> dict[str, Any]:
    edge = next((item for item in request.get("evidence_edges", []) if item.get("shot_id") == shot_id), None)
    if edge is None:
        raise ValueError("shot evidence edge missing")
    chapter_id = str(edge.get("as_of_chapter_id"))
    history = list(request.get("canonical_history_chapters") or [])
    try:
        rank = history.index(chapter_id)
    except ValueError as error:
        raise ValueError("as-of chapter missing from canonical history") from error
    return {"bound_evidence_chapter_id": chapter_id, "visible_history_chapter_ids": history[:rank + 1]}
