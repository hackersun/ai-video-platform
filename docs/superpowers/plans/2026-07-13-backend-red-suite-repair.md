# Backend Red Suite Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the isolated backend suite to green without weakening entity review gates, transaction atomicity, or scoped-reference safety.

**Architecture:** Keep review-first extraction as the default for `/entities/analyze`, while restoring legacy generation entrypoints through an explicit trusted-deterministic compatibility option. Implement scoped-reference backfill as a feature-owned, repository-protocol-based application service with canonical hashed manifests and transactional apply. Preserve the already-correct top-level Story Lock transaction wrapper that appeared during diagnosis.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, pytest/pytest-asyncio, canonical JSON SHA-256.

## Global Constraints

- Do not modify live/dev databases; every verification uses an isolated SQLite file under `/tmp`.
- Do not call external providers or run live-canary workflows.
- Preserve candidate review behavior for `/api/v1/story-bibles/entities/analyze` unless `allow_auto_approve` is explicitly true.
- Preserve route shapes, persisted IDs, and atomic rollback semantics.
- Do not grow legacy hotspot endpoints for new reusable rules; place reusable behavior in feature/service modules.
- Do not clean unrelated working-tree changes or generated artifacts in this repair.

---

### Task 1: Restore deterministic generation compatibility

**Files:**
- Modify: `backend/app/api/v1/endpoints/story_bible.py`
- Modify: `backend/app/services/consistency_context.py`
- Modify only if the shared policy is the confirmed owner: `backend/app/services/entity_review_service.py`
- Test: `backend/test_character_scope.py`
- Test: `backend/test_novel_import_story_bible.py`
- Test: `backend/test_storyboard_templates.py`

**Interfaces:**
- Consumes: `run_candidate_entity_extraction(..., allow_auto_approve: bool)` and production-visible lifecycle queries.
- Produces: legacy generation entrypoints persist high-confidence deterministic entities as production-visible; review analysis continues to create candidates.

- [ ] **Step 1: Confirm the current RED split**

Run the three failing generation tests together with one candidate-lifecycle guard:

```bash
cd backend
python3 -m pytest \
  test_character_scope.py::test_shot_entity_context_prefers_same_novel_character \
  test_novel_import_story_bible.py::test_story_bible_generate_sync_and_consistency \
  test_storyboard_templates.py::test_smart_storyboard_binds_entities_and_video_keeps_context \
  tests/test_entity_review_api.py -q
```

Expected: the three legacy-generation assertions fail with empty production refs/rules; candidate review tests pass.

- [ ] **Step 2: Add a characterization assertion for the compatibility boundary**

Extend the smallest existing review API test so the same explicit labeled character remains `candidate` through `/entities/analyze`, while the legacy generation helper explicitly opts into auto-approval for quality decisions marked `auto_approve`.

- [ ] **Step 3: Verify the characterization test is RED for legacy generation only**

Run the exact test added in Step 2 and confirm its review half passes while its legacy-generation half fails because the entity is not production-visible.

- [ ] **Step 4: Implement the minimal compatibility flag propagation**

Pass `allow_auto_approve=True` only from existing trusted deterministic generation paths (`_extract_and_optionally_persist` and generation-time `load_or_extract_story_entities`). Do not change the default in `run_candidate_entity_extraction` and do not enable it for `/entities/analyze`.

- [ ] **Step 5: Verify generation and review behavior**

Run the command from Step 1. Expected: all selected tests pass.

### Task 2: Correct exact entity scope ownership

**Files:**
- Modify: `backend/app/api/v1/endpoints/story_bible.py`
- Test: `backend/test_story_entity_production_pack.py`

**Interfaces:**
- Consumes: `StoryEntity.novel_id`, `chapter_id`, and `script_id` ownership columns.
- Produces: `scope=novel|chapter|script|global` returns mutually exclusive exact-scope rows; omitted scope retains inclusive fallback behavior.

- [ ] **Step 1: Reproduce and inspect the inserted rows**

Run `test_entity_stats_match_scope_filters_and_ignore_list_type_filter` with `-vv --showlocals`, then use its existing API setup to verify that the event counted in chapter scope carries a non-null `script_id`.

- [ ] **Step 2: Add an exact-scope regression assertion**

Keep the existing assertions that a script-owned event appears in the default inclusive query and script scope, but not chapter or novel scope.

- [ ] **Step 3: Verify RED**

Run:

```bash
cd backend
python3 -m pytest test_story_entity_production_pack.py::test_entity_stats_match_scope_filters_and_ignore_list_type_filter -q
```

Expected: chapter scope incorrectly counts the script-owned event.

- [ ] **Step 4: Fix the shared exact-scope predicate**

Ensure `scope=chapter` requires `chapter_id IS NOT NULL AND script_id IS NULL`; ensure create/update scope resolution retains the explicitly supplied `script_id`. Apply the rule once in `_apply_story_entity_scope_filters`, without duplicating it in list and stats handlers.

- [ ] **Step 5: Verify all entity scope tests**

Run the failing test plus other tests containing `scope` in `test_story_entity_production_pack.py`. Expected: all pass.

### Task 3: Implement the scoped-reference backfill application service

**Files:**
- Create: `backend/app/features/series_run_story_locks/application/backfill_scoped_refs.py`
- Modify only for exports if required: `backend/app/features/series_run_story_locks/application/__init__.py`
- Test: `backend/tests/test_scoped_reference_backfill_v1.py`

**Interfaces:**
- Consumes repository methods `snapshot(read_only=...)` and `transaction()` plus the in-transaction mutable state contract exercised by the test repository.
- Produces `manifest_sha256(payload)`, `dry_run_backfill(repository, run_id, manifest_path)`, `apply_backfill(repository, manifest_path, expected_manifest_hash, fail_at=None, database_path=None)`, and `inject_repository_drift(repository, kind)`.

- [ ] **Step 1: Keep the existing 22 contract tests as RED evidence**

Run:

```bash
cd backend
python3 -m pytest tests/test_scoped_reference_backfill_v1.py -q
```

Expected: import failure for the missing application module.

- [ ] **Step 2: Implement canonical manifest hashing and 0600 write**

Canonicalize JSON with sorted keys and compact separators, exclude `manifest_sha256` from its own digest, write via an exclusive file descriptor with mode `0o600`, and bind database/run/owner/novel/version/chapter/shot/history/ref-decision fingerprints into the manifest.

- [ ] **Step 3: Implement fail-closed dry-run eligibility**

Build one decision per legacy ref using hashes rather than raw names/prompts/secrets. Mark the whole run ineligible if any decision is ineligible. Do not enter a write transaction during dry-run.

- [ ] **Step 4: Implement TOCTOU-safe transactional apply**

Before mutation, verify the expected hash, embedded manifest hash, diagnostic-path prohibition, top-level snapshot fields, chapter/shot/history/merge-audit fingerprints, and full-run eligibility. Inside one repository transaction update only listed refs, append one audit row, support injected rollback points, and return idempotently when that manifest was already applied.

- [ ] **Step 5: Implement deterministic drift injection used by contract tests**

`inject_repository_drift` must mutate exactly one chapter, shot, history fingerprint, or merge-audit fingerprint so apply rejects it before commit.

- [ ] **Step 6: Verify the backfill contract**

Run the command from Step 1. Expected: all 22 tests pass.

### Task 4: Integrate and verify the repaired baseline

**Files:**
- Verify only: all changed files from Tasks 1-3.

**Interfaces:**
- Produces a green isolated backend suite and unchanged green frontend static verification.

- [ ] **Step 1: Run the previously failing cluster**

Run the 26-test targeted command recorded during diagnosis. Expected: all pass.

- [ ] **Step 2: Run the complete isolated backend suite**

```bash
npm run verify:backend
```

Expected: zero failures; skipped tests and non-fatal warnings are reported separately.

- [ ] **Step 3: Run frontend typecheck and production build**

```bash
npm run verify:frontend
```

Expected: TypeScript and Next.js production build pass.

- [ ] **Step 4: Run structural checks**

```bash
git diff --check
python3 -m compileall -q backend/app/features/series_run_story_locks backend/app/services
```

Expected: both commands exit zero.

- [ ] **Step 5: Review the final diff**

Confirm every changed line maps to one of the three failure roots, no live/provider code was invoked, no default database file changed, and no unrelated user work was reformatted or removed.
