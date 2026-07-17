# Disable Provider Video Watermark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every future provider video-generation request disables the visible supplier watermark.

**Architecture:** Own the default once in the video-generation constants module. Route the direct API, workflow adapter, legacy Volcano service, provider-content builder, and model-configuration probe through that constant without changing request/response schemas or historical media.

**Tech Stack:** FastAPI, Python, pytest, Volcano Ark content-generation API.

## Global Constraints

- Preserve existing routes, database records, provider selection, native-audio behavior, subtitles, budgets, and retry semantics.
- Do not post-process, crop, or inpaint historical videos.
- Keep `video.py` and `llm_config.py` at or below their task-start line counts.
- Do not commit or stage the dirty worktree.

---

### Task 1: Lock the no-watermark contract with failing tests

**Files:**
- Modify: `backend/tests/test_reference_package.py`
- Modify: `backend/tests/test_seedance_native_audio_submission.py`
- Modify: `backend/test_workflow_routes.py`
- Modify: `backend/test_volcano_service.py`

**Interfaces:**
- Consumes: existing video provider builders and request capture fixtures.
- Produces: assertions that provider prompt text and SDK kwargs use `watermark=false`.

- [x] Change the existing provider-content expectations from `--watermark true` to `--watermark false`.
- [x] Assert workflow `_create_kwargs()` returns `watermark is False`.
- [x] Assert direct `/video/generate` passes `watermark is False`.
- [x] Assert legacy `VolcanoService.generate_video()` emits `--watermark false` by default.
- [x] Run the four targeted tests and confirm they fail specifically because production still enables the watermark.

### Task 2: Introduce one default and route every production entry through it

**Files:**
- Modify: `backend/app/features/video_generation/constants.py`
- Modify: `backend/app/features/video_generation/public.py`
- Modify: `backend/app/features/video_generation/domain/provider_contract.py`
- Modify: `backend/app/services/video_reference_adapter.py`
- Modify: `backend/app/features/workflow_media/adapters/video_submission.py`
- Modify: `backend/app/api/v1/endpoints/video.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py`
- Modify: `backend/app/services/volcano_service.py`

**Interfaces:**
- Produces: `PROVIDER_VIDEO_WATERMARK_ENABLED: bool = False` and `PROVIDER_VIDEO_WATERMARK_ARG: str = "false"`.
- Consumers: all provider-facing video payload builders and probes.

- [x] Add the two constants to the video-generation constants module and public facade.
- [x] Replace every production `watermark=True`, `--watermark true`, and legacy default `"true"` with the shared no-watermark default.
- [x] Preserve explicit caller overrides in `build_video_provider_content()` and `VolcanoService.generate_video()` while making their default false.
- [x] Re-run the targeted tests and confirm they pass.

### Task 3: Verify repository and frontend-originated behavior

**Files:**
- Test only; no additional production paths.

**Interfaces:**
- Consumes: backend test suite, source scan, running frontend/backend.
- Produces: reproducible evidence that future frontend-created tasks reach provider adapters with watermark disabled.

- [x] Run the relevant backend tests, code-health check, and `git diff --check` (no code-health tool exists in this checkout; hotspot line-count ratchet was checked manually).
- [x] Search production code and confirm no provider video path contains `watermark=True` or `--watermark true`.
- [x] Restart backend if required and verify frontend/backend health.
- [x] Trigger a front-end development request intercepted by the existing deterministic/test boundary and verify persisted/request metadata reports watermark disabled without spending real-model budget.
