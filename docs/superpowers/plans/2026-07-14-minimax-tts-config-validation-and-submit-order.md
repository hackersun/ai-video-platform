# MiniMax TTS Config Validation And Submit Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject MiniMax HTTP-200 business failures during configuration testing and prevent a TTS rejection from occurring after an expensive video submission.

**Architecture:** Keep MiniMax business-response interpretation in the focused provider-error module and consume it from both the service and configuration tester. Preserve the existing separate-media response and persistence contracts while changing only the external submission order to TTS-first. The next paid canary must run an exact model/region/voice configuration probe before any reference or video request.

**Tech Stack:** FastAPI, httpx/aiohttp, async SQLAlchemy, pytest, Next.js/Playwright.

## Global Constraints

- No paid provider call in this implementation batch.
- Preserve existing API response models and live-canary RMB 10 / two-anchor / zero-retry rules.
- Treat HTTP 200 plus nonzero MiniMax `base_resp.status_code` as provider rejection.
- Do not expose raw provider messages, request content, API keys, or response payloads.
- TTS must be submitted before video for `separate_video_tts`.
- Unknown provider outcomes remain fail-closed and retain their reservation.
- Do not commit from the shared dirty worktree.

---

### Task 1: MiniMax business-response configuration validation

**Files:**
- Modify: `backend/app/services/minimax_errors.py`
- Modify: `backend/app/services/minimax_service.py`
- Modify: `backend/app/core/minimax_voice_contract.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py`
- Modify: `backend/scripts/prepare_isolated_live_model_configs.py`
- Test: `backend/test_text_model_config.py`
- Test: `backend/test_minimax_service.py`
- Test: `backend/tests/test_prepare_isolated_live_model_configs.py`

**Interfaces:**
- Produces: `minimax_provider_rejection(payload, operation) -> MiniMaxProviderRejected | None`.
- Consumes: MiniMax `base_resp.status_code` and `base_resp.status_msg` without returning raw response content.

- [x] Add a failing test proving HTTP 200 plus `base_resp.status_code=2054` returns `success=false`.
- [x] Add a success test proving `base_resp.status_code=0` remains successful.
- [x] Add a failing staging test proving an old generic MiniMax TTS success record cannot enter a paid canary.
- [x] Implement the shared MiniMax response interpreter and use it from the service and config tester.
- [x] Use the official China T2A example voice as the single candidate, but require an exact current verification marker before staging.
- [x] Verify the focused MiniMax service and configuration tests.

### Task 2: TTS-first separate-media submission

**Files:**
- Modify: `backend/app/features/workflow_media/application/generate_separate_media.py`
- Create: `backend/tests/test_separate_media_submission_order.py`

**Interfaces:**
- Preserves: `generate_separate_media_batch(context, request) -> WorkflowMediaBatchResponse`.
- Changes: provider-call order only; TTS rejection occurs before `submit_video`.

- [x] Add a failing unit test where TTS raises `WorkflowMediaError(422)` and video call count remains zero.
- [x] Reorder TTS and video submission without changing response or persistence schemas.
- [x] Verify the focused unit test and existing workflow route contracts.

### Task 3: Integrated non-live verification

**Files:**
- Verify only; no production expansion.

- [x] Run MiniMax, TTS rejection, live-budget, and workflow-media regression tests.
- [x] Run Python compilation and `git diff --check`.
- [x] Run frontend typecheck and production build.
- [x] Run deterministic four-chapter browser acceptance from the frontend.
- [x] Report the exact next-live precondition: fresh exact TTS configuration probe must succeed before any paid media request.
