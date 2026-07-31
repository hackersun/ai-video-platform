# Native Audio Subtitle And Wardrobe Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make native-audio shots use one immutable dialogue contract, render subtitles exactly once, and block cross-chapter generation when a character has no explicit inherited wardrobe lock.

**Architecture:** Preserve canonical spoken text while sanitizing only visual prompt content. Keep subtitle rendering idempotent and provider video text-free, while retaining the current truthful pending-audio-verification state. Resolve wardrobe from explicit character/story evidence and carry it into the shot prompt; placeholder wardrobe values cannot satisfy final-quality preflight.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Next.js 14, Playwright, FFmpeg.

## Global Constraints

- Preserve existing TTS workflows and historical media.
- Do not call paid providers in code-level tests.
- Do not mark native audio as synchronized without transcript evidence.
- Do not mutate canonical dialogue during provider safety rewriting.
- Do not accept placeholder wardrobe text as a cross-chapter lock.

---

### Task 1: Immutable native-audio dialogue

**Files:**
- Modify: `backend/app/services/provider_prompt_safety.py`
- Modify: `backend/app/features/workflow_media/adapters/video_submission.py`
- Modify: `backend/app/features/workflow_media/application/prepare_separate_media.py`
- Test: `backend/tests/test_seedance_native_audio_submission.py`

**Interfaces:**
- Consumes: `dialogue_sync_contract.spoken_text` and provider-facing visual prompt.
- Produces: a sanitized prompt whose canonical spoken text is byte-for-byte unchanged and whose visual instructions prohibit generated captions.

- [x] Add a failing test proving `失踪` remains unchanged inside canonical spoken text while visual occurrences may be rewritten.
- [x] Run the focused test and confirm it fails because the current sanitizer changes the dialogue.
- [x] Protect canonical dialogue during safety rewriting and add the no-generated-text instruction.
- [x] Re-run the focused test module.

### Task 2: Idempotent subtitle rendering

**Files:**
- Modify: `backend/app/services/native_audio_subtitle_renderer.py`
- Modify: `backend/app/features/series_anchor_generation/media_reconciliation.py`
- Test: `backend/tests/test_native_audio_subtitle_renderer.py`
- Test: `backend/tests/test_series_anchor_async_reconciliation.py`

**Interfaces:**
- Consumes: reviewed subtitle segments and existing render evidence.
- Produces: one normalized subtitle event per unique timing/text tuple and reuses an existing burned artifact for the same track/dialogue hash.

- [x] Add failing tests for duplicate segment normalization and repeat reconciliation.
- [x] Verify both tests fail for the current implementation.
- [x] Deduplicate subtitle events and skip a second burn when the same track/hash is already attached.
- [x] Re-run both focused modules.

### Task 3: Explicit inherited wardrobe lock

**Files:**
- Modify: `backend/app/services/asset_visual_contract.py`
- Modify: `backend/app/features/workflow_media/application/prepare_separate_media.py`
- Test: `backend/tests/test_asset_visual_contract.py`
- Test: `backend/tests/test_seedance_native_audio_submission.py`

**Interfaces:**
- Consumes: explicit prose such as `沈砚穿着深蓝旧呢大衣` and continuity metadata.
- Produces: `wardrobe=深蓝旧呢大衣` in downstream visual constraints; placeholders remain invalid.

- [x] Add a failing regression for `深蓝旧呢大衣` extraction and inherited prompt constraint.
- [x] Verify the test fails because the explicit wearing phrase is currently reduced to a placeholder wardrobe.
- [x] Extend deterministic extraction and visual-contract fallback so the explicit wardrobe enters downstream character DNA.
- [x] Re-run focused tests and existing story-state regressions.

### Task 4: Frontend acceptance and truthful gate

**Files:**
- Modify only if required by the failing contract: `frontend/src/features/series-runs/series-run-view.tsx`
- Test: `frontend/e2e/four-chapter-live-continuation.spec.ts`

**Interfaces:**
- Consumes: subtitle/audio verification and wardrobe-lock evidence.
- Produces: a visible pending/blocked state instead of a false synchronized/consistent success state.

- [x] Add non-paid frontend assertions for unique subtitle delivery and explicit pending audio verification.
- [x] Run backend focused suites, frontend checks, Playwright media-player contract, and `git diff --check`.
- [x] Do not rerun paid video generation until all local gates pass and a new explicit live-model authorization exists.
