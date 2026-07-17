"""RED characterization for closure-v2 locking and v1 compatibility."""

from __future__ import annotations

import copy
import hashlib
import importlib

import pytest

from app.features.series_run_story_locks.domain.closure_v2 import edge
from app.features.series_run_story_locks.domain.scoped_reference import (
    build_scoped_reference, sign_merge_edge,
)


def _api():
    return importlib.import_module(
        "app.features.series_run_story_locks.application.closure_versioning"
    )


def _state(**changes):
    value = {
        "current_pointer": "bible-v1", "bibles": {
            "bible-v1": {
                "version": 1, "closure_contract_version": "required_entity_closure_v1",
                "source_hash": "source-v1", "closure_hash": "closure-v1",
                "snapshot_hash": "snapshot-v1", "immutable_payload": {"legacy": True},
            },
        },
        "run_story_locks": {"story_bible_id": "bible-v1"},
        "episode_contracts": {"episode-1": {"story_bible_id": "bible-v1"}},
        "audit": [],
    }
    value.update(changes)
    return value


def _scoped_inputs():
    kinds = ["character", "character", "scene", "scene", *(["prop"] * 4), *(["event"] * 3)]
    counters = {"character": 0, "scene": 0, "prop": 0, "event": 0}
    values, subjects = [], {}
    for index, kind in enumerate(kinds):
        ordinal = counters[kind]
        counters[kind] += 1
        canonical_id = "canonical-1" if kind == "character" else f"{kind}-{ordinal}"
        canonical_name = "沈砚" if kind == "character" else f"{kind}-{ordinal}"
        chapter_id = "chapter-1" if index < 5 else "chapter-4"
        content = f"第{index}条权威证据"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        source = {
            "id": f"source-{index}", "user_id": "user-1", "novel_id": "novel-1",
            "entity_type": kind, "canonical_name": canonical_name,
            "chapter_id": chapter_id, "first_seen_chapter_id": chapter_id,
            "evidence_contract": {"status": "verified", "chapter_id": chapter_id,
                                  "source_span": [0, len(content)], "content_hash": content_hash,
                                  "source_excerpt": content,
                                  "parser_version": "deterministic-extraction-v2"},
        }
        chapter = {"id": chapter_id, "chapter_number": 1 if chapter_id == "chapter-1" else 4,
                   "content": content, "content_hash": content_hash, "content_length": len(content)}
        context = {"run_id": "run-1", "shot_id": f"shot-{index}", "series_run_id": "run-1",
                   "episode_number": 1 if chapter_id == "chapter-1" else 4,
                   "episode_input_hash": f"input-{index}", "chapter_id": chapter_id,
                   "chapter_ids": [chapter_id], "script_id": f"script-{index}",
                   "storyboard_id": f"board-{index}", "prompt": content,
                   "dialogue": content, "visual_description": content,
                   "source_text": content, "shot_text": content}
        reference = build_scoped_reference(context=context, source=source, chapter=chapter)
        target = {**source, "id": canonical_id, "canonical_name": canonical_name}
        merge = sign_merge_edge({"source_entity_id": source["id"],
                                 "canonical_entity_id": canonical_id, "user_id": "user-1",
                                 "novel_id": "novel-1", "entity_type": kind,
                                 "canonical_identity_sha256": reference["canonical_identity_sha256"]})
        owned = {"user_id": "user-1", "novel_id": "novel-1", "run_id": "run-1",
                 "shot_id": f"shot-{index}", "chapter_id": chapter_id, "entity_type": kind,
                 "current_context": context, "authoritative_chapters": {chapter_id: chapter},
                 "source_rows": [source], "canonical_histories": [], "merge_edges": [merge],
                 "canonical_subjects": [source, target]}
        values.append({"reference": reference, "owned": owned, "canonical_entity_id": canonical_id})
        subjects[(kind, canonical_id)] = {"entity_type": kind, "canonical_entity_id": canonical_id,
                                          "canonical_identity_sha256": reference["canonical_identity_sha256"]}
    return values, list(subjects.values())


def _request(**changes):
    scoped_inputs, subjects = _scoped_inputs()
    value = {
        "closure_contract_version": "required_entity_closure_v2",
        "source_hash": "source-v2", "closure_hash": "closure-v2",
        "snapshot_hash": "snapshot-v2", "subjects": subjects,
        "evidence_edges": [edge(item["reference"], item["canonical_entity_id"])
                           for item in scoped_inputs],
        "scoped_inputs": scoped_inputs,
        "candidate_counts": {"character": 3, "scene": 3, "prop": 6, "event": 7},
    }
    value.update(changes)
    return value


class MemoryLockRepository:
    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.before = copy.deepcopy(state)
        self.commits = 0

    def transaction(self):
        return _MemoryTransaction(self)


class _MemoryTransaction:
    def __init__(self, repository):
        self.repository = repository

    def __enter__(self):
        self.snapshot = copy.deepcopy(self.repository.state)
        return self.repository.state

    def __exit__(self, error_type, _error, _traceback):
        if error_type:
            self.repository.state = self.snapshot
        else:
            self.repository.commits += 1
        return False


def test_v1_bible_is_audit_readable_but_never_reports_v2_readiness():
    api = _api()

    audit = api.read_lock_for_audit(_state(), "bible-v1")

    assert audit["closure_contract_version"] == "required_entity_closure_v1"
    assert audit["immutable_payload"] == {"legacy": True}
    assert audit["v2_ready"] is False


def test_v2_request_never_idempotently_reuses_v1_bible():
    api = _api()

    decision = api.classify_existing_lock(_state(), _request())

    assert decision.action == "supersede_and_create"
    assert decision.existing_story_bible_id == "bible-v1"


def test_first_v2_request_atomically_supersedes_pointer_and_preserves_v1_bytes():
    api = _api()
    repository = MemoryLockRepository(_state())
    original = copy.deepcopy(repository.state["bibles"]["bible-v1"])

    result = api.apply_v2_lock(repository, _request())

    assert repository.commits == 1
    assert result["story_bible_id"] != "bible-v1"
    assert repository.state["bibles"]["bible-v1"] == original
    assert repository.state["current_pointer"] == result["story_bible_id"]
    assert result["closure_contract_version"] == "required_entity_closure_v2"
    assert result["required_evidence_count"] == 11
    assert set(result) >= {"source_hash", "closure_hash", "snapshot_hash",
                           "required_counts", "evidence_edge_count"}
    assert "canonical_history_chapters" not in result


def test_exact_repeated_v2_request_is_idempotent_without_new_version():
    api = _api()
    repository = MemoryLockRepository(_state())
    first = api.apply_v2_lock(repository, _request())
    commits = repository.commits

    repeated = api.apply_v2_lock(repository, _request())

    assert repeated["story_bible_id"] == first["story_bible_id"]
    assert repeated["idempotent"] is True
    assert repository.commits == commits


@pytest.mark.parametrize("field", [
    "closure_contract_version", "source_hash", "closure_hash", "snapshot_hash",
    "subjects", "evidence_edges",
])
def test_exact_reuse_recomputes_persisted_tuple_and_rejects_tamper(field):
    api = _api()
    repository = MemoryLockRepository(_state())
    first = api.apply_v2_lock(repository, _request())
    repository.state["bibles"][first["story_bible_id"]][field] = "tampered"

    second = api.apply_v2_lock(repository, _request())

    assert second["story_bible_id"] != first["story_bible_id"]


@pytest.mark.parametrize("field", [
    "source_hash", "closure_hash", "snapshot_hash",
])
def test_v2_idempotency_requires_exact_version_source_closure_and_snapshot_hash(field):
    api = _api()
    repository = MemoryLockRepository(_state())
    first = api.apply_v2_lock(repository, _request())
    changed = _request(**{field: f"changed-{field}"})

    second = api.apply_v2_lock(repository, changed)

    assert second["story_bible_id"] != first["story_bible_id"]
    assert second["idempotent"] is False


def test_non_v2_request_version_is_rejected_without_mutation():
    api = _api()
    repository = MemoryLockRepository(_state())

    with pytest.raises(ValueError, match="closure.*version"):
        api.apply_v2_lock(repository, _request(closure_contract_version="required_entity_closure_v1"))

    assert repository.state == repository.before and repository.commits == 0


@pytest.mark.parametrize("drift", [
    {"chapter_content_hash": "changed"}, {"shot_input_sha256": "changed"},
    {"evidence_ref_id": "changed"}, {"canonical_target": "changed"},
    {"ref_hash_version": "changed"}, {"identity_hash_version": "changed"},
])
def test_material_v2_source_or_edge_drift_invalidates_exact_reuse(drift):
    api = _api()
    repository = MemoryLockRepository(_state())
    first = api.apply_v2_lock(repository, _request())
    changed = api.request_with_drift(_request(), drift)

    second = api.apply_v2_lock(repository, changed)

    assert second["story_bible_id"] != first["story_bible_id"]


def test_a_to_b_to_a_creates_three_append_only_v2_versions_without_overwrite():
    api = _api()
    repository = MemoryLockRepository(_state())
    request_a = _request()
    request_b = api.request_with_drift(_request(), {"chapter_content_hash": "changed"})

    first = api.apply_v2_lock(repository, request_a)
    second = api.apply_v2_lock(repository, request_b)
    third = api.apply_v2_lock(repository, request_a)

    assert len({first["story_bible_id"], second["story_bible_id"], third["story_bible_id"]}) == 3
    assert [repository.state["bibles"][item["story_bible_id"]]["version"]
            for item in (first, second, third)] == [2, 3, 4]


@pytest.mark.parametrize("failure_point", [
    "after_supersede", "after_bible_insert", "after_run_pointer",
    "after_episode_contracts", "before_commit",
])
def test_failed_v1_to_v2_upgrade_rolls_back_every_lineage_write(failure_point):
    api = _api()
    repository = MemoryLockRepository(_state())

    with pytest.raises(RuntimeError, match="injected"):
        api.apply_v2_lock(repository, _request(), fail_at=failure_point)

    assert repository.state == repository.before
    assert repository.commits == 0


def test_retained_shape_closure_has_required_subjects_edges_and_unrelated_counts():
    api = _api()

    result = api.preview_v2_lock(_request())

    assert result["candidate_counts"] == {"character": 3, "scene": 3, "prop": 6, "event": 7}
    assert result["required_counts"] == {"character": 1, "scene": 2, "prop": 4, "event": 3}
    assert result["evidence_edge_count"] == 11
    assert result["required_evidence_count"] == 11
    assert result["unrelated_candidate_count"] == 9


@pytest.mark.parametrize("attack", [
    "missing", "mismatch", "future", "forged", "ambiguous", "cross_owner",
])
def test_v2_prevalidation_attack_is_full_state_zero_write(attack):
    api = _api()
    repository = MemoryLockRepository(_state())

    with pytest.raises(ValueError):
        api.apply_v2_lock(repository, api.request_with_attack(_request(), attack))

    assert repository.state == repository.before
    assert repository.commits == 0


def test_episode1_uses_chapter1_edge_while_canonical_history_keeps_chapters_1_2_4():
    api = _api()
    request = _request()
    request["canonical_history_chapters"] = ["chapter-1", "chapter-2", "chapter-4"]

    projection = api.project_request_as_of(request, shot_id="shot-0")

    assert projection["bound_evidence_chapter_id"] == "chapter-1"
    assert projection["visible_history_chapter_ids"] == ["chapter-1"]
    assert request["canonical_history_chapters"] == ["chapter-1", "chapter-2", "chapter-4"]
