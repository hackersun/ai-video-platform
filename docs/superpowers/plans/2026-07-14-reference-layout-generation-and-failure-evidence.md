# Reference Layout Generation And Failure Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align composite-reference generation geometry with the pixel evaluator and persist secret-safe layout failure evidence containing the actual score, threshold, and failure stage.

**Architecture:** `reference_layout_evaluator.py` owns the shared 60/40 geometry contract and raises a structured validation error with an allowlisted summary. A focused `reference_failure_evidence.py` module stores that summary under the run metadata, while the existing exporter adds it to failure evidence without exporting images, URLs, prompts, provider messages, or credentials.

**Tech Stack:** FastAPI application services, async SQLAlchemy, Pillow, SQLite, pytest.

## Global Constraints

- No live or paid provider calls in this batch.
- Preserve the RMB 10, two-anchor, zero-retry and fail-closed provider-operation rules.
- Preserve existing API response models and the `live-canary-failure-evidence-v1` schema identifier; new fields are additive.
- Do not lower `MIN_LAYOUT_SCORE` or bypass pixel-derived verification.
- Do not export image bytes, image URLs, prompts, provider messages, API keys, headers, or raw metadata.
- Keep `series_run_reference_preparation.py` at or below 500 lines.
- Do not commit from the shared dirty worktree.

---

### Task 1: Shared generation and scoring geometry contract

**Files:**
- Modify: `backend/app/services/reference_layout_evaluator.py`
- Modify: `backend/app/services/series_run_reference_preparation.py`
- Test: `backend/tests/test_reference_layout_evaluator.py`
- Test: `backend/tests/test_series_run_live_preflight_plan.py`

**Interfaces:**
- Produces: `reference_layout_prompt_instruction() -> str` and `ReferenceLayoutValidationError.summary -> dict[str, object]`.
- Consumes: the existing 60% character region, 40% style-board region, three equal character panels and `MIN_LAYOUT_SCORE`.

- [x] Add a failing evaluator test proving a below-threshold image exposes `failure_stage=layout_scoring`, actual `layout_score`, `threshold`, and evaluator version.
- [x] Add a failing preparation test proving the provider prompt includes the exact 3:2 canvas, 60/40 split, three equal left panels, and one right style panel.
- [x] Implement the structured evaluator error and shared prompt instruction without lowering the threshold.
- [x] Use the shared instruction in `prepare_series_reference` and verify both tests pass.

### Task 2: Persist and export allowlisted failure evidence

**Files:**
- Create: `backend/app/services/reference_failure_evidence.py`
- Modify: `backend/app/services/series_run_reference_preparation.py`
- Modify: `backend/scripts/export_live_canary_failure_evidence.py`
- Test: `backend/tests/test_series_run_live_preflight_plan.py`
- Test: `backend/tests/test_export_live_canary_failure_evidence.py`

**Interfaces:**
- Produces: `record_reference_failure_evidence(db, run, operation_id, evidence) -> None`.
- Persists only: `failure_stage`, `layout_score`, `threshold`, `evaluator_version`, and `recorded_at`.
- Exports the allowlisted summary as `operation.failure_evidence` when present.

- [x] Add a failing integration test proving a layout rejection persists actual score, threshold, stage, and no raw URL or prompt.
- [x] Add a failing exporter test proving the allowlisted summary is emitted while injected secrets and raw metadata are omitted.
- [x] Implement the focused persistence helper and connect it only to structured layout validation failures.
- [x] Add the optional failure summary to exporter operations while retaining schema v1 compatibility.
- [x] Verify reference-preparation and exporter regression tests.

### Task 3: Non-live integrated verification

**Files:**
- Verify only.

- [x] Run the focused evaluator, reference-preparation, exporter, provider-response, Qiniu binding and live-budget tests.
- [x] Run Python compilation and `git diff --check`.
- [x] Confirm production file-size ratchets and absence of unchecked plan items.
- [x] Report that another live run requires fresh authorization.
