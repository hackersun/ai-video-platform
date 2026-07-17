# Live Canary TTS Failure Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a stale MiniMax voice from reaching paid video submission, settle explicit TTS rejection safely, and retain secret-safe recovery evidence when a live browser run fails.

**Architecture:** Keep the network-free series preflight contract and narrow its MiniMax live-canary voices to a current, explicitly documented system-voice set. Translate MiniMax `base_resp` rejections into a typed provider error so the workflow adapter can release only confirmed pre-acceptance reservations. Before the runner deletes its isolated database, export a mode-0600 manifest containing only run, operation, task, job, and budget identifiers.

**Tech Stack:** FastAPI/Python, async SQLAlchemy, Node.js runner, Playwright, pytest, node:test.

## Global Constraints

- No paid provider calls in this implementation batch.
- Preserve the RMB 10 / two-anchor / zero-Playwright-retry Wave 1 contract.
- Unknown provider outcomes retain reservations; only typed explicit rejection releases them.
- Failure evidence must never contain API keys, prompts, authorization headers, raw media, or decrypted configuration.
- Preserve current API routes and stored run/operation schemas.
- Do not commit from the shared dirty worktree.

---

### Task 1: MiniMax live-canary voice contract

**Files:**
- Create: `backend/app/core/minimax_voice_contract.py`
- Modify: `backend/app/features/series_run_story_locks/application/voice_contract.py`
- Modify: `backend/app/core/minimax_config.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py`
- Test: `backend/tests/test_series_run_live_preflight_plan.py`

**Interfaces:**
- Produces: `MINIMAX_LIVE_CANARY_VOICES`, `DEFAULT_MINIMAX_TTS_VOICE`, and `minimax_live_canary_voice_ids() -> tuple[str, ...]`.
- Consumes: provider ID `minimax` from the existing binding snapshot.

- [x] Add a failing test proving the live plan excludes `female-shaonv` and exposes `Chinese (Mandarin)_Reliable_Executive`.
- [x] Run the exact test and confirm it fails on the stale static catalog.
- [x] Add the focused MiniMax voice contract and route Story Lock voice selection through it.
- [x] Update the MiniMax default/test voice to the same documented ID without changing unrelated providers.
- [x] Run the focused voice and live-preflight tests.

### Task 2: Confirmed TTS rejection accounting

**Files:**
- Modify: `backend/app/services/minimax_service.py`
- Modify: `backend/app/features/workflow_media/adapters/tts_submission.py`
- Test: `backend/tests/test_tts_provider_rejection.py`

**Interfaces:**
- Produces: `MiniMaxProviderRejected(operation: str, status_code: str, message: str)`.
- Consumes: `finish_live_provider_attempt(..., submission_failed=True)` for a reservation with no provider task ID.

- [x] Add a failing adapter test where MiniMax raises an explicit 2054 rejection after reservation.
- [x] Assert the reservation is released once and the public error is a controlled `WorkflowMediaError(422)`.
- [x] Assert an untyped/unknown exception does not release the reservation.
- [x] Implement the typed MiniMax rejection and the narrow adapter catch.
- [x] Run the focused rejection and live-canary budget tests.

### Task 3: Secret-safe failure evidence before isolated cleanup

**Files:**
- Create: `backend/scripts/export_live_canary_failure_evidence.py`
- Modify: `scripts/run-four-chapter-acceptance.mjs`
- Modify: `docs/operations/four-chapter-live-canary.md`
- Test: `backend/tests/test_export_live_canary_failure_evidence.py`
- Test: `scripts/run-four-chapter-acceptance.test.mjs`

**Interfaces:**
- Produces: `failure-evidence.json` with schema `live-canary-failure-evidence-v1` and mode `0600`.
- Consumes: isolated SQLite path, canary user ID, and runner output directory.

- [x] Add a failing exporter test with one reconciled reference operation, one accepted video task, and one confirmed TTS rejection.
- [x] Assert identifiers, operation states, and aggregate budget survive while secrets and prompt/media payloads do not.
- [x] Implement a read-only exporter over current ORM tables.
- [x] Add a runner failure hook that exports before lifecycle cleanup and still deletes the isolated database.
- [x] Run Python and Node runner tests.

### Task 4: Integrated verification

**Files:**
- Verify only; no additional production scope.

- [x] Run targeted MiniMax, voice-selection, TTS adapter, budget, exporter, staging, and series-run tests.
- [x] Run `npm --prefix frontend run typecheck` and `npm --prefix frontend run build`.
- [x] Run the deterministic four-chapter browser acceptance from the frontend.
- [x] Run code-health/diff checks and confirm no hotspot grew beyond its task-start baseline.
- [x] Report that a new paid live canary still requires fresh authorization.
