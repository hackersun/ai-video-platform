"""Pure versioned contracts for chapter-owned shot entity references."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import unicodedata
from typing import Any, Mapping


CONTRACT_VERSION = "chapter_evidence_ref_v1"
REF_HASH_VERSION = "scoped-ref-sha256-cjson-v1"
IDENTITY_HASH_VERSION = "canonical-identity-key-v1"
CONTEXT_HASH_VERSION = "shot-reference-context-v1"
SHOT_INPUT_VERSION = "shot-input-v1"
MERGE_AUDIT_VERSION = "normalized-merge-audit-v1"
ALLOWED_PARSERS = {"deterministic-extraction-v2", "explicit-dialogue-v1"}


@dataclass(frozen=True)
class ResolvedScopedReference:
    canonical_entity_id: str
    source_entity_id: str
    entity_type: str
    as_of_chapter_id: str
    evidence_ref_id: str


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_identity(value: object) -> str:
    normalized = unicodedata.normalize("NFC", str(value or "")).strip()
    return " ".join(normalized.split()).casefold()


def canonical_identity_sha256(*, entity_type: str, canonical_name: str) -> str:
    entity_type = str(entity_type).strip()
    key = f"{entity_type}:canonical:{_normalized_identity(canonical_name)}"
    return canonical_json_sha256({
        "identity_hash_version": IDENTITY_HASH_VERSION,
        "canonical_identity_key": key, "entity_type": entity_type,
    })


def _text_hash(value: object) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _shot_input_payload(context: Mapping[str, Any]) -> dict[str, object]:
    return {
        "version": SHOT_INPUT_VERSION, "run_id": context.get("run_id"),
        "shot_id": context.get("shot_id"), "series_run_id": context.get("series_run_id"),
        "episode_number": context.get("episode_number"),
        "episode_input_hash": context.get("episode_input_hash"),
        "chapter_id": context.get("chapter_id"), "script_id": context.get("script_id"),
        "storyboard_id": context.get("storyboard_id"),
        "prompt_sha256": _text_hash(context.get("prompt")),
        "dialogue_sha256": _text_hash(context.get("dialogue")),
        "visual_description_sha256": _text_hash(context.get("visual_description")),
    }


def _reference_context_payload(context: Mapping[str, Any]) -> dict[str, object]:
    return {
        "version": CONTEXT_HASH_VERSION, "run_id": context.get("run_id"),
        "shot_id": context.get("shot_id"), "episode_number": context.get("episode_number"),
        "chapter_ids": sorted(str(value) for value in context.get("chapter_ids", [])),
        "episode_input_hash": context.get("episode_input_hash"),
        "source_text_sha256": _text_hash(context.get("source_text")),
        "shot_text_sha256": _text_hash(context.get("shot_text")),
    }


def _ref_payload(reference: Mapping[str, Any]) -> dict[str, object]:
    fields = (
        "contract_version", "ref_hash_version", "identity_hash_version",
        "reference_context_hash_version", "run_id", "shot_id", "shot_input_sha256",
        "reference_context_sha256", "entity_type", "source_entity_id",
        "canonical_identity_sha256", "as_of_chapter_id", "evidence",
    )
    return {field: reference.get(field) for field in fields}


def evidence_ref_id(reference: Mapping[str, Any]) -> str:
    return canonical_json_sha256(_ref_payload(reference))


def _verified_evidence(source: Mapping[str, Any], chapter: Mapping[str, Any]) -> dict[str, object]:
    evidence = dict(source.get("evidence_contract") or {})
    span = evidence.get("source_span")
    content = str(chapter.get("content") or "")
    content_hash = _text_hash(content)
    valid = (
        evidence.get("status") == "verified"
        and evidence.get("chapter_id") == source.get("chapter_id") == chapter.get("id")
        and evidence.get("content_hash") == content_hash == chapter.get("content_hash")
        and chapter.get("content_length") == len(content)
        and evidence.get("parser_version") in ALLOWED_PARSERS
        and isinstance(span, list) and len(span) == 2
        and all(isinstance(value, int) for value in span) and 0 <= span[0] < span[1]
        and span[1] <= len(content)
        and evidence.get("source_excerpt") == content[span[0]:span[1]]
    )
    if not valid:
        raise ValueError("authoritative chapter evidence span excerpt or parser mismatch")
    return {
        "status": "verified", "chapter_id": evidence["chapter_id"], "source_span": list(span),
        "content_hash": evidence["content_hash"], "parser_version": evidence["parser_version"],
        "source_excerpt_sha256": _text_hash(evidence["source_excerpt"]),
        "source_entity_id": source.get("id"),
    }


def build_scoped_reference(
    *, context: Mapping[str, Any], source: Mapping[str, Any], chapter: Mapping[str, Any],
) -> dict[str, object]:
    evidence = _verified_evidence(source, chapter)
    reference: dict[str, object] = {
        "contract_version": CONTRACT_VERSION, "ref_hash_version": REF_HASH_VERSION,
        "identity_hash_version": IDENTITY_HASH_VERSION,
        "reference_context_hash_version": CONTEXT_HASH_VERSION,
        "run_id": context.get("run_id"), "shot_id": context.get("shot_id"),
        "shot_input_sha256": canonical_json_sha256(_shot_input_payload(context)),
        "reference_context_sha256": canonical_json_sha256(_reference_context_payload(context)),
        "entity_type": source.get("entity_type"), "source_entity_id": source.get("id"),
        "canonical_identity_sha256": canonical_identity_sha256(
            entity_type=str(source.get("entity_type") or ""),
            canonical_name=str(source.get("canonical_name") or source.get("name") or ""),
        ),
        "as_of_chapter_id": context.get("chapter_id"), "evidence": evidence,
    }
    reference["evidence_ref_id"] = evidence_ref_id(reference)
    return reference


def _merge_audit_payload(history: Mapping[str, Any]) -> dict[str, object]:
    audit = dict(history.get("merge_audit") or {})
    return {
        "merge_audit_version": MERGE_AUDIT_VERSION,
        "source_entity_id": history.get("source_entity_id"),
        "canonical_entity_id": history.get("canonical_entity_id"),
        "user_id": history.get("owner_user_id"), "novel_id": history.get("owner_novel_id"),
        "entity_type": history.get("owner_entity_type"),
        "canonical_identity_sha256": audit.get("canonical_identity_sha256"),
    }


def sign_history_record(record: Mapping[str, Any]) -> dict[str, Any]:
    signed = json.loads(json.dumps(record, ensure_ascii=False))
    audit = dict(signed.get("merge_audit") or {})
    audit.update(_merge_audit_payload(signed))
    audit["merge_audit_sha256"] = canonical_json_sha256({
        key: value for key, value in audit.items() if key != "merge_audit_sha256"
    })
    signed["merge_audit"] = audit
    signed["metadata_hash"] = canonical_json_sha256({
        "source_entity_id": signed.get("source_entity_id"),
        "chapter_id": signed.get("chapter_id"), "metadata": signed.get("metadata"),
    })
    return signed


def sign_merge_edge(record: Mapping[str, Any]) -> dict[str, Any]:
    signed = dict(record)
    signed["merge_audit_version"] = MERGE_AUDIT_VERSION
    signed["merge_audit_sha256"] = canonical_json_sha256({
        key: value for key, value in signed.items() if key != "merge_audit_sha256"
    })
    return signed


def _validate_reference_binding(reference: Mapping[str, Any], owned: Mapping[str, Any]) -> None:
    versions = (
        reference.get("contract_version") == CONTRACT_VERSION,
        reference.get("ref_hash_version") == REF_HASH_VERSION,
        reference.get("identity_hash_version") == IDENTITY_HASH_VERSION,
        reference.get("reference_context_hash_version") == CONTEXT_HASH_VERSION,
    )
    if not all(versions) or evidence_ref_id(reference) != reference.get("evidence_ref_id"):
        raise ValueError("reference forged or unsupported")
    context = owned.get("current_context") or {}
    expected_shot = canonical_json_sha256(_shot_input_payload(context))
    expected_context = canonical_json_sha256(_reference_context_payload(context))
    if (reference.get("run_id"), reference.get("shot_id")) != (owned.get("run_id"), owned.get("shot_id")):
        raise ValueError("reference replayed or stale")
    if reference.get("shot_input_sha256") != expected_shot or reference.get("reference_context_sha256") != expected_context:
        raise ValueError("reference replayed or stale")


def _evidence_matches(reference: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    expected = dict(reference.get("evidence") or {})
    actual = dict(source.get("evidence_contract") or {})
    return actual.get("status") == expected.get("status") == "verified" \
        and all(actual.get(key) == expected.get(key) for key in (
        "chapter_id", "source_span", "content_hash", "parser_version",
    )) and _text_hash(actual.get("source_excerpt")) == expected.get("source_excerpt_sha256") \
        and source.get("id") == expected.get("source_entity_id")


def _validate_source(reference: Mapping[str, Any], source: Mapping[str, Any], owned: Mapping[str, Any]) -> None:
    checks = (
        source.get("user_id") == owned.get("user_id"),
        source.get("novel_id") == owned.get("novel_id"),
        source.get("entity_type") == reference.get("entity_type") == owned.get("entity_type"),
        source.get("chapter_id") == reference.get("as_of_chapter_id") == owned.get("chapter_id"),
        _evidence_matches(reference, source),
        canonical_identity_sha256(
            entity_type=str(source.get("entity_type") or ""),
            canonical_name=str(source.get("canonical_name") or source.get("name") or ""),
        ) == reference.get("canonical_identity_sha256"),
    )
    if not all(checks):
        raise ValueError("present source ownership type chapter evidence or identity mismatch")


def _validate_chapter(reference: Mapping[str, Any], owned: Mapping[str, Any]) -> None:
    evidence = dict(reference.get("evidence") or {})
    chapter = dict((owned.get("authoritative_chapters") or {}).get(str(reference.get("as_of_chapter_id"))) or {})
    content = str(chapter.get("content") or "")
    span = evidence.get("source_span")
    valid_span = (isinstance(span, list) and len(span) == 2
                  and all(isinstance(value, int) for value in span)
                  and 0 <= span[0] < span[1] <= len(content))
    if not valid_span:
        raise ValueError("authoritative chapter evidence span invalid")
    excerpt_hash = _text_hash(content[span[0]:span[1]])
    if (chapter.get("id") != reference.get("as_of_chapter_id")
            or chapter.get("content_length") != len(content)
            or chapter.get("content_hash") != _text_hash(content)
            or evidence.get("content_hash") != _text_hash(content)
            or evidence.get("chapter_id") != chapter.get("id")
            or evidence.get("status") != "verified"
            or evidence.get("source_excerpt_sha256") != excerpt_hash
            or evidence.get("parser_version") not in ALLOWED_PARSERS):
        raise ValueError("authoritative chapter evidence forged or mismatched")


def _validate_history(reference: Mapping[str, Any], history: Mapping[str, Any], owned: Mapping[str, Any]) -> None:
    if history.get("owner_user_id") != owned.get("user_id") or history.get("owner_novel_id") != owned.get("novel_id"):
        raise ValueError("history owner mismatch")
    if history.get("owner_entity_type") != reference.get("entity_type"):
        raise ValueError("history type mismatch")
    expected_metadata = canonical_json_sha256({
        "source_entity_id": history.get("source_entity_id"),
        "chapter_id": history.get("chapter_id"), "metadata": history.get("metadata"),
    })
    if history.get("metadata_hash") != expected_metadata:
        raise ValueError("history metadata hash invalid")
    audit = dict(history.get("merge_audit") or {})
    if not audit or audit.get("merge_audit_version") != MERGE_AUDIT_VERSION:
        raise ValueError("merge audit missing")
    expected_audit = canonical_json_sha256({key: value for key, value in audit.items() if key != "merge_audit_sha256"})
    if audit.get("merge_audit_sha256") != expected_audit:
        raise ValueError("merge audit invalid")
    if (audit.get("source_entity_id") != history.get("source_entity_id")
            or audit.get("canonical_entity_id") != history.get("canonical_entity_id")
            or audit.get("user_id") != history.get("owner_user_id")
            or audit.get("novel_id") != history.get("owner_novel_id")
            or audit.get("entity_type") != history.get("owner_entity_type")
            or audit.get("canonical_identity_sha256") != reference.get("canonical_identity_sha256")):
        raise ValueError("merge audit history anchor invalid")
    nested = dict((history.get("metadata") or {}).get("evidence_contract") or {})
    if nested.get("status") != "verified" or (reference.get("evidence") or {}).get("status") != "verified":
        raise ValueError("history evidence status is not verified")
    if any(nested.get(key) != (reference.get("evidence") or {}).get(key) for key in (
        "chapter_id", "source_span", "content_hash", "parser_version", "source_excerpt_sha256",
    )):
        raise ValueError("history evidence mismatch")


def _validate_merge_shape(edges: list[Mapping[str, Any]], source_id: str) -> None:
    source_edges = [edge for edge in edges if edge.get("source_entity_id") == source_id]
    if len(source_edges) > 1:
        raise ValueError("duplicate or multiple merge edges for source")
    targets = {edge.get("canonical_entity_id") for edge in edges if edge.get("source_entity_id") == source_id}
    if len(targets) > 1:
        raise ValueError("canonical merge targets ambiguous")
    graph = {str(edge.get("source_entity_id")): str(edge.get("canonical_entity_id")) for edge in edges}
    seen: set[str] = set()
    current = source_id
    while current in graph:
        if current in seen:
            raise ValueError("merge cycle")
        seen.add(current)
        current = graph[current]
        if current in graph:
            raise ValueError("merge chain is not flattened")


def _canonical_subject(owned: Mapping[str, Any], canonical_id: str) -> Mapping[str, Any]:
    matches = [row for row in owned.get("canonical_subjects", []) if row.get("id") == canonical_id]
    if len(matches) != 1:
        raise ValueError("canonical subject missing or ambiguous")
    return matches[0]


def _validate_merge_edge(
    edge: Mapping[str, Any], source: Mapping[str, Any], target: Mapping[str, Any],
    reference: Mapping[str, Any], owned: Mapping[str, Any],
) -> None:
    expected_audit = canonical_json_sha256({
        key: value for key, value in edge.items() if key != "merge_audit_sha256"
    })
    target_hash = canonical_identity_sha256(
        entity_type=str(target.get("entity_type") or ""),
        canonical_name=str(target.get("canonical_name") or target.get("name") or ""),
    )
    checks = (
        edge.get("merge_audit_version") == MERGE_AUDIT_VERSION,
        edge.get("merge_audit_sha256") == expected_audit,
        edge.get("source_entity_id") == source.get("id"),
        edge.get("canonical_entity_id") == target.get("id"),
        edge.get("user_id") == source.get("user_id") == target.get("user_id") == owned.get("user_id"),
        edge.get("novel_id") == source.get("novel_id") == target.get("novel_id") == owned.get("novel_id"),
        edge.get("entity_type") == source.get("entity_type") == target.get("entity_type") == reference.get("entity_type"),
        edge.get("canonical_identity_sha256") == target_hash == reference.get("canonical_identity_sha256"),
    )
    if not all(checks):
        raise ValueError("merge audit canonical owner type or identity invalid")


def resolve_scoped_reference(
    reference: Mapping[str, Any], owned: Mapping[str, Any],
) -> ResolvedScopedReference:
    _validate_reference_binding(reference, owned)
    _validate_chapter(reference, owned)
    source_id = str(reference.get("source_entity_id") or "")
    edges = list(owned.get("merge_edges") or [])
    _validate_merge_shape(edges, source_id)
    sources = [row for row in owned.get("source_rows", []) if row.get("id") == source_id]
    histories = [row for row in owned.get("canonical_histories", []) if (
        row.get("source_entity_id"), row.get("chapter_id"), row.get("evidence_ref_id")
    ) == (source_id, reference.get("as_of_chapter_id"), reference.get("evidence_ref_id"))]
    if sources:
        if len(sources) != 1:
            raise ValueError("present source ambiguous")
        _validate_source(reference, sources[0], owned)
        for history in histories:
            nested = (history.get("metadata") or {}).get("evidence_contract") or {}
            if any(nested.get(key) != (reference.get("evidence") or {}).get(key) for key in (
                "chapter_id", "source_span", "content_hash", "parser_version", "source_excerpt_sha256",
            )):
                raise ValueError("current source and history conflict")
            _validate_history(reference, history, owned)
        source_edges = [edge for edge in edges if edge.get("source_entity_id") == source_id]
        canonical_id = str(source_edges[0].get("canonical_entity_id")) if source_edges else source_id
        target = _canonical_subject(owned, canonical_id)
        if source_edges:
            _validate_merge_edge(source_edges[0], sources[0], target, reference, owned)
        elif canonical_identity_sha256(
            entity_type=str(target.get("entity_type") or ""),
            canonical_name=str(target.get("canonical_name") or target.get("name") or ""),
        ) != reference.get("canonical_identity_sha256"):
            raise ValueError("canonical identity mismatch")
    else:
        if len({row.get("canonical_entity_id") for row in histories}) != 1 or not histories:
            raise ValueError("canonical history resolution ambiguous")
        for history in histories:
            _validate_history(reference, history, owned)
        canonical_id = str(histories[0].get("canonical_entity_id"))
        target = _canonical_subject(owned, canonical_id)
        if (target.get("user_id") != owned.get("user_id")
                or target.get("novel_id") != owned.get("novel_id")
                or target.get("entity_type") != reference.get("entity_type")
                or canonical_identity_sha256(
                    entity_type=str(target.get("entity_type") or ""),
                    canonical_name=str(target.get("canonical_name") or target.get("name") or ""),
                ) != reference.get("canonical_identity_sha256")):
            raise ValueError("canonical history owner type or identity invalid")
    return ResolvedScopedReference(
        canonical_id, source_id, str(reference.get("entity_type")),
        str(reference.get("as_of_chapter_id")), str(reference.get("evidence_ref_id")),
    )
