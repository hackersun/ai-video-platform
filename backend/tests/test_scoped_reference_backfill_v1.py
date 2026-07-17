"""RED tests for explicit TOCTOU-safe scoped-reference backfill."""

from __future__ import annotations

import copy
import importlib
import json
import os
from pathlib import Path

import pytest


def _api():
    return importlib.import_module(
        "app.features.series_run_story_locks.application.backfill_scoped_refs"
    )


def _state(**changes):
    refs = [{
        "shot_id": f"shot-{index}", "entity_type": "character" if index < 2 else "prop",
        "source_entity_id": f"source-{index}", "chapter_id": "chapter-1" if index < 5 else "chapter-4",
        "legacy_ref": {"entity_id": f"source-{index}", "entity_type": "character" if index < 2 else "prop"},
        "eligible": True, "reason_code": "eligible_verified_chapter_evidence",
    } for index in range(11)]
    value = {
        "database_identity": "diagnostic-copy-1", "run_id": "run-1",
        "user_id": "user-1", "novel_id": "novel-1", "run_row_version": 7,
        "series_plan_version": "plan-1", "source_version": "source-1",
        "lock_contract_version": "required_entity_closure_v1",
        "chapters": {"chapter-1": {"row_version": 2, "content_hash": "a" * 64},
                     "chapter-4": {"row_version": 3, "content_hash": "d" * 64}},
        "shots": {f"shot-{index}": {"row_version": 1, "refs_version": "legacy"}
                  for index in range(11)},
        "legacy_refs": refs, "audit": [],
    }
    value.update(changes)
    return value


class MemoryBackfillRepository:
    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.original = copy.deepcopy(state)
        self.commits = 0
        self.read_only_calls = 0

    def snapshot(self, *, read_only):
        if read_only:
            self.read_only_calls += 1
        return copy.deepcopy(self.state)

    def transaction(self):
        return _Transaction(self)


class _Transaction:
    def __init__(self, repository):
        self.repository = repository

    def __enter__(self):
        self.before = copy.deepcopy(self.repository.state)
        return self.repository.state

    def __exit__(self, error_type, _error, _traceback):
        if error_type:
            self.repository.state = self.before
        else:
            self.repository.commits += 1
        return False


def _dry_run(tmp_path, state=None):
    api = _api()
    repository = MemoryBackfillRepository(state or _state())
    manifest_path = tmp_path / "scoped-ref-backfill-manifest.json"
    result = api.dry_run_backfill(repository, run_id="run-1", manifest_path=manifest_path)
    return api, repository, manifest_path, result


def test_dry_run_writes_0600_canonical_manifest_and_no_database_rows(tmp_path):
    api, repository, path, result = _dry_run(tmp_path)

    assert path.stat().st_mode & 0o777 == 0o600
    assert repository.state == repository.original
    assert repository.commits == 0 and repository.read_only_calls == 1
    assert result["manifest_sha256"] == api.manifest_sha256(json.loads(path.read_text()))


def test_manifest_binds_database_run_versions_rows_histories_and_every_ref_decision(tmp_path):
    _api_value, _repository, path, _result = _dry_run(tmp_path)
    manifest = json.loads(path.read_text())

    assert manifest["manifest_version"] == "scoped-ref-backfill-manifest-v1"
    assert set(manifest) >= {
        "manifest_hash_version", "database_identity", "run_id", "user_id", "novel_id",
        "run_row_version", "series_plan_version", "source_version",
        "lock_contract_version", "chapters", "shots", "history_fingerprints",
        "ref_decisions", "preapply_fingerprint", "manifest_sha256",
    }
    assert len(manifest["ref_decisions"]) == 11
    assert all(set(item) >= {"reason_code", "legacy_ref_hash", "proposed_ref"}
               for item in manifest["ref_decisions"])


def test_manifest_canonical_payload_excludes_raw_names_prompts_and_secrets(tmp_path):
    _api_value, _repository, path, _result = _dry_run(tmp_path)
    encoded = path.read_text().casefold()

    assert "api_key" not in encoded
    assert "password" not in encoded
    assert "prompt" not in encoded
    assert "canonical_name" not in encoded
    assert "aliases" not in encoded


@pytest.mark.parametrize("tamper", ["body", "expected_hash"])
def test_apply_rejects_manifest_body_or_expected_hash_tamper_before_writes(tmp_path, tamper):
    api, repository, path, result = _dry_run(tmp_path)
    expected = result["manifest_sha256"]
    if tamper == "body":
        data = json.loads(path.read_text())
        data["run_row_version"] += 1
        path.write_text(json.dumps(data))
    else:
        expected = "f" * 64

    with pytest.raises(ValueError, match="manifest.*hash"):
        api.apply_backfill(repository, manifest_path=path, expected_manifest_hash=expected)

    assert repository.state == repository.original and repository.commits == 0


@pytest.mark.parametrize("drift", [
    ("run_row_version", 8), ("series_plan_version", "plan-2"),
    ("source_version", "source-2"), ("database_identity", "different-db"),
])
def test_apply_revalidates_manifest_top_level_snapshot_and_rejects_toctou(tmp_path, drift):
    api, repository, path, result = _dry_run(tmp_path)
    repository.state[drift[0]] = drift[1]

    with pytest.raises(ValueError, match="drift|stale"):
        api.apply_backfill(repository, manifest_path=path,
                           expected_manifest_hash=result["manifest_sha256"])

    assert repository.commits == 0


@pytest.mark.parametrize("kind", ["chapter", "shot", "history", "merge_audit"])
def test_apply_revalidates_every_row_version_and_fingerprint(tmp_path, kind):
    api, repository, path, result = _dry_run(tmp_path)
    api.inject_repository_drift(repository, kind)

    with pytest.raises(ValueError, match="drift|stale"):
        api.apply_backfill(repository, manifest_path=path,
                           expected_manifest_hash=result["manifest_sha256"])

    assert repository.commits == 0


def test_one_ineligible_edge_makes_whole_run_dry_run_ineligible(tmp_path):
    state = _state()
    state["legacy_refs"][10]["eligible"] = False
    state["legacy_refs"][10]["reason_code"] = "evidence_hash_mismatch"

    _api_value, repository, _path, result = _dry_run(tmp_path, state)

    assert result["eligible"] is False
    assert result["eligible_ref_count"] == 10
    assert repository.state == repository.original


def test_one_ineligible_edge_prevents_partial_apply(tmp_path):
    state = _state()
    state["legacy_refs"][10]["eligible"] = False
    state["legacy_refs"][10]["reason_code"] = "evidence_hash_mismatch"
    api, repository, path, result = _dry_run(tmp_path, state)

    with pytest.raises(ValueError, match="ineligible"):
        api.apply_backfill(repository, manifest_path=path,
                           expected_manifest_hash=result["manifest_sha256"])

    assert repository.state == repository.original and repository.commits == 0


def test_apply_updates_only_listed_refs_appends_one_audit_and_commits_once(tmp_path):
    api, repository, path, result = _dry_run(tmp_path)

    applied = api.apply_backfill(repository, manifest_path=path,
                                 expected_manifest_hash=result["manifest_sha256"])

    assert applied["updated_ref_count"] == 11
    assert repository.commits == 1
    assert len(repository.state["audit"]) == 1
    assert repository.state["audit"][0]["manifest_sha256"] == result["manifest_sha256"]


@pytest.mark.parametrize("failure_point", [
    "after_first_ref", "after_last_ref", "after_audit", "before_commit",
])
def test_apply_failure_at_any_write_point_rolls_back_entire_run(tmp_path, failure_point):
    api, repository, path, result = _dry_run(tmp_path)

    with pytest.raises(RuntimeError, match="injected"):
        api.apply_backfill(repository, manifest_path=path,
                           expected_manifest_hash=result["manifest_sha256"], fail_at=failure_point)

    assert repository.state == repository.original and repository.commits == 0


def test_exact_repeated_apply_is_idempotent_without_duplicate_audit(tmp_path):
    api, repository, path, result = _dry_run(tmp_path)
    first = api.apply_backfill(repository, manifest_path=path,
                               expected_manifest_hash=result["manifest_sha256"])

    repeated = api.apply_backfill(repository, manifest_path=path,
                                  expected_manifest_hash=result["manifest_sha256"])

    assert first["updated_ref_count"] == 11
    assert repeated["idempotent"] is True and repeated["updated_ref_count"] == 0
    assert len(repository.state["audit"]) == 1


def test_diagnostic_original_is_never_an_apply_target(tmp_path):
    api, repository, path, result = _dry_run(tmp_path)
    diagnostic = Path("/tmp/wave1-20260713-third-live-latest.db")
    before = diagnostic.read_bytes() if diagnostic.exists() else b""

    with pytest.raises(ValueError, match="diagnostic.*immutable"):
        api.apply_backfill(repository, manifest_path=path,
                           expected_manifest_hash=result["manifest_sha256"],
                           database_path=diagnostic)

    assert (diagnostic.read_bytes() if diagnostic.exists() else b"") == before
    assert repository.state == repository.original
