"""Pure closure-v2 subject and scoped-evidence edge hashing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .scoped_reference import canonical_json_sha256


CLOSURE_VERSION = "required_entity_closure_v2"
CLOSURE_HASH_VERSION = "closure-sha256-cjson-v2"
ENTITY_TYPES = ("character", "scene", "prop", "event")
SUBJECT_FIELDS = {"entity_type", "canonical_entity_id", "canonical_identity_sha256"}
EDGE_FIELDS = {
    "run_id", "shot_id", "entity_type", "canonical_entity_id", "as_of_chapter_id",
    "evidence_ref_id", "shot_input_sha256", "reference_context_sha256",
}


@dataclass(frozen=True)
class ClosureV2:
    candidate_counts: dict[str, int]
    required_counts: dict[str, int]
    approval_subjects: tuple[dict[str, str], ...]
    evidence_edges: tuple[dict[str, str], ...]
    unrelated_candidate_count: int
    hash: str


def edge(reference: Mapping[str, Any], canonical_entity_id: str) -> dict[str, str]:
    fields = (
        "run_id", "shot_id", "entity_type", "as_of_chapter_id", "evidence_ref_id",
        "shot_input_sha256", "reference_context_sha256",
    )
    value = {field: str(reference.get(field) or "") for field in fields}
    value["canonical_entity_id"] = str(canonical_entity_id)
    return value


def _ordered_subjects(subjects: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    for item in subjects:
        if set(item) != SUBJECT_FIELDS:
            raise ValueError("subject fields missing or extra")
        if item.get("entity_type") not in ENTITY_TYPES:
            raise ValueError("subject entity type unknown")
        if any(not str(item.get(field) or "") for field in SUBJECT_FIELDS):
            raise ValueError("subject field empty")
    values = [{
        "entity_type": str(item.get("entity_type") or ""),
        "canonical_entity_id": str(item.get("canonical_entity_id") or ""),
        "canonical_identity_sha256": str(item.get("canonical_identity_sha256") or ""),
    } for item in subjects]
    if len({(item["entity_type"], item["canonical_entity_id"]) for item in values}) != len(values):
        raise ValueError("duplicate canonical subject")
    return tuple(sorted(values, key=lambda item: (
        item["entity_type"], item["canonical_entity_id"], item["canonical_identity_sha256"],
    )))


def _ordered_edges(edges: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    for item in edges:
        if set(item) != EDGE_FIELDS:
            raise ValueError("edge fields missing or extra")
        if item.get("entity_type") not in ENTITY_TYPES:
            raise ValueError("edge entity type unknown")
        if any(not str(item.get(field) or "") for field in EDGE_FIELDS):
            raise ValueError("edge field empty")
    values = [dict(item) for item in edges]
    exact: set[tuple[str, str, str]] = set()
    targets: dict[tuple[str, str, str], tuple[str, str]] = {}
    for item in values:
        exact_key = (str(item.get("shot_id")), str(item.get("entity_type")), str(item.get("evidence_ref_id")))
        target_key = exact_key[:2] + (str(item.get("canonical_entity_id")),)
        target_value = (str(item.get("as_of_chapter_id")), str(item.get("evidence_ref_id")))
        if exact_key in exact:
            raise ValueError("duplicate evidence edge")
        if target_key in targets and targets[target_key] != target_value:
            raise ValueError("conflicting canonical target edge")
        exact.add(exact_key)
        targets[target_key] = target_value
    return tuple(sorted(values, key=lambda item: (
        str(item.get("shot_id")), str(item.get("entity_type")),
        str(item.get("canonical_entity_id")), str(item.get("as_of_chapter_id")),
        str(item.get("evidence_ref_id")),
    )))


def build_closure_v2(
    *, subjects: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]],
    candidate_counts: Mapping[str, int],
) -> ClosureV2:
    ordered_subjects = _ordered_subjects(subjects)
    ordered_edges = _ordered_edges(edges)
    subject_keys = {(item["entity_type"], item["canonical_entity_id"]) for item in ordered_subjects}
    if any((item["entity_type"], item["canonical_entity_id"]) not in subject_keys for item in ordered_edges):
        raise ValueError("edge canonical subject absent")
    required_counts = {
        kind: sum(item["entity_type"] == kind for item in ordered_subjects)
        for kind in ENTITY_TYPES
    }
    payload = {
        "closure_contract_version": CLOSURE_VERSION,
        "closure_hash_version": CLOSURE_HASH_VERSION,
        "ref_contract_version": "chapter_evidence_ref_v1",
        "ref_hash_version": "scoped-ref-sha256-cjson-v1",
        "identity_hash_version": "canonical-identity-key-v1",
        "subjects": list(ordered_subjects), "edges": list(ordered_edges),
    }
    if set(candidate_counts) != set(ENTITY_TYPES):
        raise ValueError("candidate count fields missing or extra")
    candidates = {key: int(value) for key, value in candidate_counts.items()}
    if any(value < 0 or value < required_counts[key] for key, value in candidates.items()):
        raise ValueError("candidate count mismatch")
    return ClosureV2(
        candidates, required_counts, ordered_subjects, ordered_edges,
        sum(candidates.values()) - len(ordered_subjects), canonical_json_sha256(payload),
    )


def closure_hash(
    *, subjects: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]],
) -> str:
    ordered_subjects = _ordered_subjects(subjects)
    ordered_edges = _ordered_edges(edges)
    subject_keys = {(item["entity_type"], item["canonical_entity_id"]) for item in ordered_subjects}
    if any((item["entity_type"], item["canonical_entity_id"]) not in subject_keys for item in ordered_edges):
        raise ValueError("edge canonical subject absent")
    return canonical_json_sha256({
        "closure_contract_version": CLOSURE_VERSION,
        "closure_hash_version": CLOSURE_HASH_VERSION,
        "ref_contract_version": "chapter_evidence_ref_v1",
        "ref_hash_version": "scoped-ref-sha256-cjson-v1",
        "identity_hash_version": "canonical-identity-key-v1",
        "subjects": list(ordered_subjects), "edges": list(ordered_edges),
    })
