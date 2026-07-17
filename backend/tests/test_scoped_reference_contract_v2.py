"""RED contract tests for versioned chapter-owned shot references."""

from __future__ import annotations

import copy
import hashlib
import importlib

import pytest


def _api():
    return importlib.import_module(
        "app.features.series_run_story_locks.domain.scoped_reference"
    )


def _closure_api():
    return importlib.import_module(
        "app.features.series_run_story_locks.domain.closure_v2"
    )


def _context(**changes):
    value = {
        "run_id": "run-1", "shot_id": "shot-1", "series_run_id": "run-1",
        "episode_number": 1, "episode_input_hash": "episode-input-1",
        "chapter_id": "chapter-1", "chapter_ids": ["chapter-1"],
        "script_id": "script-1", "storyboard_id": "board-1",
        "prompt": "镜头提示", "dialogue": "沈砚：别碰铜铃。",
        "visual_description": "雨夜城门", "source_text": "第一章来源文本",
        "shot_text": "第一章来源文本 沈砚：别碰铜铃。",
    }
    value.update(changes)
    return value


def _source(**changes):
    content = "第一章来源文本"
    value = {
        "id": "source-1", "user_id": "user-1", "novel_id": "novel-1",
        "entity_type": "character", "canonical_name": " 沈\u3000砚 ",
        "chapter_id": "chapter-1", "first_seen_chapter_id": "chapter-1",
        "evidence_contract": {
            "status": "verified", "chapter_id": "chapter-1",
            "source_span": [0, 2], "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "source_excerpt": content[0:2],
            "parser_version": "deterministic-extraction-v2",
        },
    }
    value.update(changes)
    return value


def _chapter(**changes):
    content = "第一章来源文本"
    value = {
        "id": "chapter-1", "chapter_number": 1, "content": content,
        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "content_length": len(content),
    }
    value.update(changes)
    return value


def _build_ref(context=None, source=None, chapter=None):
    api = _api()
    source = source or _source()
    return api.build_scoped_reference(
        context=context or _context(), source=source,
        chapter=chapter or _chapter(id=source["chapter_id"]),
    )


def _history(ref, **changes):
    value = {
        "owner_user_id": "user-1", "owner_novel_id": "novel-1",
        "owner_entity_type": "character", "canonical_entity_id": "canonical-1",
        "source_entity_id": "source-1", "chapter_id": "chapter-1",
        "evidence_ref_id": ref["evidence_ref_id"],
        "metadata": {"evidence_contract": copy.deepcopy(ref["evidence"])},
        "metadata_hash": "computed-by-helper",
        "merge_audit": {
            "merge_audit_version": "normalized-merge-audit-v1",
            "source_entity_id": "source-1", "canonical_entity_id": "canonical-1",
            "user_id": "user-1", "novel_id": "novel-1",
            "entity_type": "character",
            "canonical_identity_sha256": ref["canonical_identity_sha256"],
            "merge_audit_sha256": "computed-by-helper",
        },
    }
    value.update(changes)
    return value


def _owned(ref, **changes):
    source = _source()
    value = {
        "user_id": "user-1", "novel_id": "novel-1",
        "run_id": "run-1", "shot_id": "shot-1", "chapter_id": "chapter-1",
        "entity_type": "character", "current_context": _context(),
        "authoritative_chapters": {"chapter-1": _chapter()},
        "source_rows": [source], "canonical_histories": [], "merge_edges": [],
        "canonical_subjects": [
            {**source, "id": "source-1"}, {**source, "id": "canonical-1"},
        ],
    }
    value.update(changes)
    return value


def test_ref_v1_contains_every_versioned_run_shot_context_and_evidence_field():
    ref = _build_ref()

    assert set(ref) >= {
        "contract_version", "ref_hash_version", "identity_hash_version",
        "reference_context_hash_version", "run_id", "shot_id",
        "shot_input_sha256", "reference_context_sha256", "entity_type",
        "source_entity_id", "canonical_identity_sha256", "as_of_chapter_id",
        "evidence_ref_id", "evidence",
    }


def test_ref_hash_uses_deterministic_canonical_json_and_versioned_identity_normalization():
    api = _api()
    first = _build_ref()
    second = _build_ref(source=_source(canonical_name="沈 砚"))

    assert first == second
    assert first["canonical_identity_sha256"] == api.canonical_identity_sha256(
        entity_type="character", canonical_name="沈\u3000砚",
    )
    assert first["evidence_ref_id"] == api.evidence_ref_id(first)


@pytest.mark.parametrize("attack", ["hash", "bounds", "excerpt", "verified", "parser"])
def test_builder_recomputes_authoritative_chapter_evidence_and_rejects_attack(attack):
    source, chapter = _source(), _chapter()
    if attack == "hash":
        source["evidence_contract"]["content_hash"] = "f" * 64
    elif attack == "bounds":
        source["evidence_contract"]["source_span"] = [0, 999]
    elif attack == "excerpt":
        source["evidence_contract"]["source_excerpt"] = "伪造"
    elif attack == "verified":
        source["evidence_contract"]["status"] = "candidate"
    else:
        source["evidence_contract"]["parser_version"] = "unknown-parser"

    with pytest.raises(ValueError, match="chapter|evidence|span|excerpt|parser"):
        _build_ref(source=source, chapter=chapter)


def test_forged_ref_with_recomputed_self_hash_still_fails_authoritative_chapter_validation():
    api = _api()
    ref = _build_ref()
    ref["evidence"]["content_hash"] = "f" * 64
    ref["evidence_ref_id"] = api.evidence_ref_id(ref)

    with pytest.raises(ValueError, match="chapter|evidence|forged"):
        api.resolve_scoped_reference(ref, _owned(ref))


def test_forged_identity_with_recomputed_ref_hash_fails_authoritative_source_identity():
    api = _api()
    ref = _build_ref()
    ref["canonical_identity_sha256"] = "f" * 64
    ref["evidence_ref_id"] = api.evidence_ref_id(ref)

    with pytest.raises(ValueError, match="identity"):
        api.resolve_scoped_reference(ref, _owned(ref))


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("run_id", "run-2"), ("shot_id", "shot-2"),
        ("prompt", "changed"), ("dialogue", "changed"),
        ("visual_description", "changed"), ("source_text", "changed"),
        ("shot_text", "changed"), ("episode_input_hash", "changed"),
    ],
)
def test_ref_binding_changes_for_cross_run_cross_shot_or_authoritative_input_drift(field, replacement):
    original = _build_ref()
    changed = _build_ref(context=_context(**{field: replacement}))

    assert changed["evidence_ref_id"] != original["evidence_ref_id"]


def test_present_source_is_authoritative_and_validates_without_history_fallback():
    api = _api()
    ref = _build_ref()

    resolved = api.resolve_scoped_reference(ref, _owned(ref))

    assert resolved.canonical_entity_id == "source-1"
    assert resolved.as_of_chapter_id == "chapter-1"


@pytest.mark.parametrize(
    "source_change",
    [
        {"user_id": "user-2"}, {"novel_id": "novel-2"},
        {"entity_type": "scene"}, {"chapter_id": "chapter-2"},
        {"evidence_contract": {"status": "verified", "chapter_id": "chapter-1",
                               "source_span": [1, 3], "content_hash": "a" * 64,
                               "parser_version": "deterministic-extraction-v2"}},
    ],
)
def test_present_wrong_source_fails_immediately_even_if_valid_history_exists(source_change):
    api = _api()
    ref = _build_ref()
    history = api.sign_history_record(_history(ref))
    owned = _owned(ref, source_rows=[_source(**source_change)], canonical_histories=[history])

    with pytest.raises(ValueError, match="source"):
        api.resolve_scoped_reference(ref, owned)


def test_missing_source_resolves_exactly_one_owned_verified_history():
    api = _api()
    ref = _build_ref()
    history = api.sign_history_record(_history(ref))

    resolved = api.resolve_scoped_reference(
        ref, _owned(ref, source_rows=[], canonical_histories=[history]),
    )

    assert resolved.canonical_entity_id == "canonical-1"


@pytest.mark.parametrize(
    "history_change,error",
    [
        ({"metadata_hash": "forged"}, "history"),
        ({"owner_user_id": "user-2"}, "owner"),
        ({"owner_entity_type": "scene"}, "type"),
        ({"merge_audit": {}}, "audit"),
    ],
)
def test_missing_source_rejects_invalid_history_audit_owner_or_type(history_change, error):
    api = _api()
    ref = _build_ref()
    history = api.sign_history_record(_history(ref))
    history.update(history_change)

    with pytest.raises(ValueError, match=error):
        api.resolve_scoped_reference(
            ref, _owned(ref, source_rows=[], canonical_histories=[history]),
        )


def test_missing_source_rejects_histories_owned_by_multiple_canonical_subjects():
    api = _api()
    ref = _build_ref()
    first = api.sign_history_record(_history(ref))
    second = api.sign_history_record(_history(ref, canonical_entity_id="canonical-2"))

    with pytest.raises(ValueError, match="ambiguous"):
        api.resolve_scoped_reference(
            ref, _owned(ref, source_rows=[], canonical_histories=[first, second]),
        )


@pytest.mark.parametrize("change", [
    {"user_id": "user-2"}, {"entity_type": "scene"},
    {"canonical_name": "另一个人物"},
])
def test_merge_target_must_match_authoritative_canonical_subject(change):
    api = _api()
    ref = _build_ref()
    target = {**_source(), "id": "canonical-1", **change}
    edge = api.sign_merge_edge({
        "source_entity_id": "source-1", "canonical_entity_id": "canonical-1",
        "user_id": "user-1", "novel_id": "novel-1", "entity_type": "character",
        "canonical_identity_sha256": ref["canonical_identity_sha256"],
    })

    with pytest.raises(ValueError, match="canonical|owner|type|identity"):
        api.resolve_scoped_reference(
            ref, _owned(ref, merge_edges=[edge], canonical_subjects=[target]),
        )


def test_invalid_merge_audit_hash_fails_even_when_source_and_target_exist():
    api = _api()
    ref = _build_ref()
    edge = api.sign_merge_edge({
        "source_entity_id": "source-1", "canonical_entity_id": "canonical-1",
        "user_id": "user-1", "novel_id": "novel-1", "entity_type": "character",
        "canonical_identity_sha256": ref["canonical_identity_sha256"],
    })
    edge["merge_audit_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="audit"):
        api.resolve_scoped_reference(
            ref, _owned(ref, merge_edges=[edge], canonical_subjects=[{**_source(), "id": "canonical-1"}]),
        )


def test_any_conflicting_history_representation_fails_not_only_first_match():
    api = _api()
    ref = _build_ref()
    good = api.sign_history_record(_history(ref))
    bad = api.sign_history_record(_history(ref))
    bad["metadata"]["evidence_contract"]["source_span"] = [2, 4]

    with pytest.raises(ValueError, match="conflict"):
        api.resolve_scoped_reference(
            ref, _owned(ref, canonical_histories=[good, bad]),
        )


@pytest.mark.parametrize("status", ["candidate", "rejected", "", None])
def test_present_source_requires_verified_status_even_when_other_evidence_is_hash_consistent(status):
    api = _api()
    ref = _build_ref()
    source = _source()
    source["evidence_contract"]["status"] = status

    with pytest.raises(ValueError, match="verified|evidence|status"):
        api.resolve_scoped_reference(ref, _owned(ref, source_rows=[source]))


@pytest.mark.parametrize("status", ["candidate", "rejected", "", None])
def test_history_only_requires_verified_status_even_when_metadata_hash_is_recomputed(status):
    api = _api()
    ref = _build_ref()
    history = _history(ref)
    history["metadata"]["evidence_contract"]["status"] = status
    history = api.sign_history_record(history)

    with pytest.raises(ValueError, match="verified|evidence|status"):
        api.resolve_scoped_reference(
            ref, _owned(ref, source_rows=[], canonical_histories=[history]),
        )


def test_present_source_conflicting_history_fails_closed():
    api = _api()
    ref = _build_ref()
    history = api.sign_history_record(_history(ref))
    history["metadata"]["evidence_contract"]["source_span"] = [2, 4]

    with pytest.raises(ValueError, match="conflict"):
        api.resolve_scoped_reference(
            ref, _owned(ref, canonical_histories=[history]),
        )


@pytest.mark.parametrize("merge_edges", [
    [{"source_entity_id": "source-1", "canonical_entity_id": "middle"},
     {"source_entity_id": "middle", "canonical_entity_id": "canonical-1"}],
    [{"source_entity_id": "source-1", "canonical_entity_id": "canonical-1"},
     {"source_entity_id": "canonical-1", "canonical_entity_id": "source-1"}],
    [{"source_entity_id": "source-1", "canonical_entity_id": "canonical-1"},
     {"source_entity_id": "source-1", "canonical_entity_id": "canonical-2"}],
])
def test_resolution_rejects_merge_chain_cycle_and_multiple_targets(merge_edges):
    api = _api()
    ref = _build_ref()

    with pytest.raises(ValueError, match="merge|canonical|ambiguous"):
        api.resolve_scoped_reference(ref, _owned(ref, merge_edges=merge_edges))


@pytest.mark.parametrize("variant", [
    "identical", "valid_then_forged", "forged_then_valid", "different_target",
])
def test_any_two_raw_merge_edges_for_same_source_fail_before_edge_validation(variant):
    api = _api()
    ref = _build_ref()
    valid = api.sign_merge_edge({
        "source_entity_id": "source-1", "canonical_entity_id": "canonical-1",
        "user_id": "user-1", "novel_id": "novel-1", "entity_type": "character",
        "canonical_identity_sha256": ref["canonical_identity_sha256"],
    })
    forged = copy.deepcopy(valid)
    forged["merge_audit_sha256"] = "f" * 64
    if variant == "identical": edges = [valid, copy.deepcopy(valid)]
    elif variant == "valid_then_forged": edges = [valid, forged]
    elif variant == "forged_then_valid": edges = [forged, valid]
    else:
        other = copy.deepcopy(valid)
        other["canonical_entity_id"] = "canonical-2"
        edges = [valid, other]

    with pytest.raises(ValueError, match="duplicate|multiple|ambiguous"):
        api.resolve_scoped_reference(ref, _owned(ref, merge_edges=edges))


def test_closure_v2_has_one_subject_two_edges_and_stable_hash():
    api = _closure_api()
    ref1 = _build_ref()
    chapter4 = _chapter(id="chapter-4", chapter_number=4, content="第四章来源文本")
    chapter4["content_hash"] = hashlib.sha256(chapter4["content"].encode()).hexdigest()
    chapter4["content_length"] = len(chapter4["content"])
    ref4 = _build_ref(context=_context(
        shot_id="shot-4", chapter_id="chapter-4", chapter_ids=["chapter-4"],
        episode_number=4, episode_input_hash="episode-input-4",
    ), source=_source(id="source-4", chapter_id="chapter-4", first_seen_chapter_id="chapter-4",
                      evidence_contract={"status": "verified", "chapter_id": "chapter-4",
                                         "source_span": [0, 2], "content_hash": chapter4["content_hash"],
                                         "source_excerpt": chapter4["content"][0:2],
                                         "parser_version": "deterministic-extraction-v2"}), chapter=chapter4)
    subjects = [{"entity_type": "character", "canonical_entity_id": "canonical-1",
                 "canonical_identity_sha256": ref1["canonical_identity_sha256"]}]
    edges = [api.edge(ref1, "canonical-1"), api.edge(ref4, "canonical-1")]

    closure = api.build_closure_v2(subjects=subjects, edges=list(reversed(edges)),
                                   candidate_counts={"character": 3, "scene": 3, "prop": 6, "event": 7})

    assert closure.required_counts["character"] == 1
    assert len(closure.evidence_edges) == 2
    assert closure.hash == api.build_closure_v2(subjects=subjects, edges=edges,
                                                candidate_counts=closure.candidate_counts).hash


@pytest.mark.parametrize("kind", ["exact", "conflicting"])
def test_closure_v2_rejects_duplicate_and_conflicting_edges_before_hashing(kind):
    api = _closure_api()
    ref = _build_ref()
    edge = api.edge(ref, "canonical-1")
    duplicate = copy.deepcopy(edge)
    if kind == "conflicting":
        duplicate["evidence_ref_id"] = "f" * 64

    with pytest.raises(ValueError, match="duplicate|conflict"):
        api.build_closure_v2(subjects=[], edges=[edge, duplicate], candidate_counts={})


@pytest.mark.parametrize("attack", [
    "subject_extra", "subject_missing", "subject_empty", "subject_unknown_type",
    "edge_extra", "edge_missing", "edge_empty", "edge_unknown_type", "edge_subject_absent",
    "negative_candidate", "candidate_mismatch",
])
def test_closure_v2_rejects_noncanonical_fields_missing_subjects_and_invalid_counts(attack):
    api = _closure_api()
    ref = _build_ref()
    subject = {"entity_type": "character", "canonical_entity_id": "source-1",
               "canonical_identity_sha256": ref["canonical_identity_sha256"]}
    scoped_edge = api.edge(ref, "source-1")
    counts = {"character": 1, "scene": 0, "prop": 0, "event": 0}
    if attack == "subject_extra": subject["name"] = "display"
    elif attack == "subject_missing": subject.pop("canonical_identity_sha256")
    elif attack == "subject_empty": subject["canonical_entity_id"] = ""
    elif attack == "subject_unknown_type": subject["entity_type"] = "vehicle"
    elif attack == "edge_extra": scoped_edge["name"] = "display"
    elif attack == "edge_missing": scoped_edge.pop("evidence_ref_id")
    elif attack == "edge_empty": scoped_edge["shot_id"] = ""
    elif attack == "edge_unknown_type": scoped_edge["entity_type"] = "vehicle"
    elif attack == "edge_subject_absent": scoped_edge["canonical_entity_id"] = "missing"
    elif attack == "negative_candidate": counts["character"] = -1
    else: counts["character"] = 0

    with pytest.raises(ValueError, match="field|missing|empty|type|subject|count|candidate"):
        api.build_closure_v2(subjects=[subject], edges=[scoped_edge], candidate_counts=counts)


def test_closure_hash_ignores_nothing_because_extra_fields_are_rejected():
    api = _closure_api()
    ref = _build_ref()
    subject = {"entity_type": "character", "canonical_entity_id": "source-1",
               "canonical_identity_sha256": ref["canonical_identity_sha256"]}
    scoped_edge = api.edge(ref, "source-1")
    closure = api.build_closure_v2(subjects=[subject], edges=[scoped_edge],
                                   candidate_counts={"character": 1, "scene": 0, "prop": 0, "event": 0})

    assert closure.hash == api.closure_hash(subjects=[subject], edges=[scoped_edge])
