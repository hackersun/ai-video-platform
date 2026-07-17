# Series Anchor Async Media Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a frontend-started selected-anchor run submit real asynchronous video plus TTS jobs, poll them without duplicate provider calls, aggregate completed source jobs into one truthful `MediaGenerationJob` per shot, and only then enter quality review.

**Architecture:** Keep provider submission in `workflow_media` and provider refresh in the existing video job endpoint. The selected-anchor application stores a resumable `provider_pending` submission, exposes a feature-owned reconcile endpoint, and creates aggregate media rows only after every owned source job is terminal and successful. The frontend polls video jobs, calls reconcile idempotently, and displays waiting/failed/completed state.

**Tech Stack:** FastAPI, async SQLAlchemy, Pydantic, Next.js 14, React 18, TypeScript, Playwright, pytest.

## Global Constraints

- No paid provider calls in implementation or verification; use deterministic adapters and isolated SQLite databases.
- Preserve existing deterministic acceptance behavior and the `/series-runs/{run_id}/generate-selected` route.
- A real run must use `separate_video_tts`; `direct_av_first` remains deterministic/development-only.
- Never create a successful aggregate from pending, failed, missing, foreign-user, or lineage-mismatched source jobs.
- Reconciliation is idempotent and must not resubmit video or TTS provider operations.
- Preserve budget reservations and provider operation evidence; aggregate rows reference source jobs rather than inventing costs.
- New production files stay below 300 lines and functions below 80 lines.
- Existing hotspot endpoints receive only compatibility delegation and must not gain business logic.

---

### Task 1: Persist a resumable provider-pending generation response

**Files:**
- Modify: `backend/app/api/v1/endpoints/series_runs.py`
- Modify: `backend/app/features/series_anchor_generation/generation.py`
- Test: `backend/tests/test_series_anchor_async_reconciliation.py`

**Interfaces:**
- Consumes: `WorkflowMediaBatchResponse.pending_video_job_ids`, `pending_tts_job_ids`, `video_job_ids`, and `tts_job_ids`.
- Produces: generation response field `status: "provider_pending" | "completed"` and persisted submission status `provider_pending`.

- [x] Write an integration test whose batch returns one pending video job and assert generation returns `provider_pending`, persists source IDs, and does not run quality evaluation.
- [x] Run `pytest -q backend/tests/test_series_anchor_async_reconciliation.py -k pending` and confirm it fails because generation immediately evaluates quality.
- [x] Route non-deterministic selected-anchor work through `strategy="separate_video_tts"` and have `generate_selected` persist and return the pending response before quality evaluation.
- [x] Re-run the focused test and confirm it passes.

### Task 2: Aggregate terminal source jobs truthfully and idempotently

**Files:**
- Create: `backend/app/features/series_anchor_generation/media_reconciliation.py`
- Modify: `backend/app/features/series_anchor_generation/__init__.py`
- Test: `backend/tests/test_series_anchor_async_reconciliation.py`

**Interfaces:**
- Consumes: `reconcile_selected_media(db, *, run_id: str, user_id: str) -> dict`.
- Produces: one `MediaGenerationJob` per selected shot with `source_job_ids`, output URLs, locked lineage, reference/video/TTS provider calls, and terminal status.

- [x] Write tests for pending, failed, successful, foreign-owned, missing-source, repeated reconciliation, and mixed reused/new cases.
- [x] Run the focused tests and confirm they fail because the reconciliation use case does not exist.
- [x] Implement owned submission loading, terminal-state validation, aggregate construction, workflow/shot linkage, and idempotent reuse.
- [x] Run the focused tests and confirm all reconciliation cases pass.

### Task 3: Expose the reconcile contract through a thin feature API

**Files:**
- Create: `backend/app/features/series_anchor_generation/api.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_series_anchor_async_reconciliation.py`

**Interfaces:**
- Produces: `POST /series-runs/{run_id}/reconcile-selected` returning `provider_pending`, `failed`, or `completed`, including source job IDs and quality status.

- [x] Write API tests for ownership, pending response, failed response, and completed idempotent response.
- [x] Run the API tests and confirm 404 because the route is absent.
- [x] Add a thin router that calls the feature application and maps `SeriesAnchorError` without importing another endpoint.
- [x] Register the feature router and re-run the API tests.

### Task 4: Poll from the frontend and preserve visible waiting state

**Files:**
- Create: `frontend/src/features/series-runs/poll-anchor-generation.ts`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/components/novels/series-run-panel.tsx`
- Modify: `frontend/src/features/series-runs/series-run-view.tsx`
- Test: `frontend/e2e/four-chapter-series-run.spec.ts`

**Interfaces:**
- Consumes: generation response batches and `refreshVideoJob(jobId)`.
- Produces: `pollAnchorGeneration({ runId, initial, onStatus })` and visible `provider_pending`/`failed`/`completed` state.

- [x] Add a browser contract test that delays one video job and verifies refresh plus reconciliation complete without a second generation POST.
- [x] Run the focused Playwright test and confirm it fails because the polling module is absent.
- [x] Add typed API methods for reconciliation, implement bounded polling with no generation retry, and wire status into the existing panel/view.
- [x] Re-run the focused browser test and confirm it passes.

### Task 5: Regression and safety verification

**Files:**
- Modify only if a test exposes a direct regression.

- [x] Run focused backend tests on a fresh isolated SQLite database.
- [x] Run `npm run verify:four-chapter` from the repository root.
- [x] Confirm frontend typecheck, production build, four browser cases, SQLite lineage audit, development database counts, and `tsconfig` checksums all pass.
- [x] Inspect the final diff for provider retry, budget, ownership, API compatibility, hotspot growth, and accidental development database changes.

## Execution Contract

**Intent Lock:** Complete only the selected-anchor asynchronous media submission, polling, aggregation, and quality handoff.

**Out of Scope:** Trusted multimodal scoring implementation, full-episode rendering, provider changes, schema migrations, paid live-model reruns, and unrelated cleanup.

**Acceptance Criteria:**

1. A real selected-anchor request creates owned `VideoJob`/`TTSJob` rows and returns a truthful waiting response while any source is pending.
2. Frontend polling refreshes existing source jobs and never repeats `/generate-selected`.
3. Successful source jobs produce exactly one active aggregate per selected shot with immutable source IDs and provider evidence.
4. Pending/failed/missing/foreign source jobs never produce a successful aggregate.
5. Reconcile calls are idempotent across refresh and retry.
6. Existing deterministic four-chapter acceptance remains green.

**Verification Commands:**

```bash
DATABASE_URL=sqlite+aiosqlite:////tmp/series-anchor-reconcile.db \
  pytest -q backend/tests/test_series_anchor_async_reconciliation.py \
  backend/tests/test_workflow_media_public_contract.py
npm run verify:four-chapter
```

**Decision Points:** No additional confirmation is required for this offline batch. Stop before any paid provider call, destructive data operation, merge, push, or release.
