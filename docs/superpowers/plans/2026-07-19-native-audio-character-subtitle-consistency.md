# Native Audio Character And Subtitle Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent cross-chapter character identity drift and prevent native-audio videos from being presented as subtitle-synchronized without matching character, dialogue, reference-frame, and verification evidence.

**Architecture:** Normalize character and speaker identity before story locks are built, then require a shot-owned first frame for Seedance native-audio generation. Build the provider prompt from one canonical dialogue contract, and keep post-generation delivery in an explicit unverified state until trusted audio evidence exists.

**Tech Stack:** FastAPI, SQLAlchemy, Python regex parsers, pytest, Next.js 14, React, TypeScript, Playwright.

## Global Constraints

- Preserve existing TTS mode and all stored historical media.
- Do not send the composite character/style board as a Seedance first frame.
- Do not call paid models during code-level regression testing.
- Do not mark script-derived subtitles as audio-verified.
- Keep changes out of oversized endpoint/page hotspots when a focused service can own the rule.

---

### Task 1: Canonical character and speaker normalization

**Files:**
- Modify: `backend/app/services/entity_extraction_service.py`
- Modify: `backend/app/services/dialogue_lineage_service.py`
- Modify: `backend/app/services/dialogue_parser.py`
- Test: `backend/tests/test_entity_extraction_classification.py`
- Test: `backend/tests/test_dialogue_lineage_service.py`

**Interfaces:**
- Consumes: chapter prose and shot dialogue strings.
- Produces: canonical person names such as `顾言`, never speech verbs such as `喊道` or object/action fragments such as `密钥` and `顾言答`.

- [ ] Add failing regressions for the chapter-four prose and the malformed `喊道：能源接通，转动密钥！` shot dialogue.
- [ ] Run the two focused test modules and confirm failures identify the current parser behavior.
- [ ] Add one shared speaker-label normalization rule and apply it at extraction and dialogue-contract boundaries.
- [ ] Re-run the focused tests and confirm the expected canonical characters and speaker.

### Task 2: Native-audio first-frame and single-dialogue contract

**Files:**
- Modify: `backend/app/features/workflow_media/application/prepare_separate_media.py`
- Modify: `backend/app/features/workflow_media/adapters/video_submission.py`
- Test: `backend/tests/test_seedance_native_audio_submission.py`

**Interfaces:**
- Consumes: canonical dialogue contract, `Shot.image_url`, consistency package metadata.
- Produces: a provider prompt containing exactly the approved spoken text and a Seedance request containing a shot-owned first frame.

- [ ] Add failing tests proving native-audio final-quality generation rejects composite-only references and strips unrelated quoted dialogue.
- [ ] Run the focused test and confirm both failures.
- [ ] Require `reference_image_source == "shot_image"` for native-audio real generation and return an actionable error code.
- [ ] Sanitize the provider-facing visual prompt so only the canonical dialogue contract remains speakable.
- [ ] Re-run the focused test module.

### Task 3: Truthful subtitle/audio verification state

**Files:**
- Modify: `backend/app/features/series_anchor_generation/media_reconciliation.py`
- Modify: `backend/app/features/series_anchor_generation/quality_status.py`
- Test: `backend/tests/test_series_anchor_quality_status.py`
- Test: `backend/tests/test_native_audio_subtitle_renderer.py`

**Interfaces:**
- Consumes: script-derived subtitle track and rendered native-audio media.
- Produces: burned subtitle media marked `script_aligned_pending_audio_verification`, never `audio_verified` without trusted transcript/timing evidence.

- [ ] Add failing tests for evidence status and delivery readiness.
- [ ] Persist subtitle provenance, expected dialogue hash, and `audio_verification_required=true`.
- [ ] Keep trusted multimodal evaluation as a hard delivery gate.
- [ ] Re-run the focused tests.

### Task 4: Frontend repair path and acceptance

**Files:**
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/features/series-runs/use-anchor-generation.ts`
- Modify: `frontend/src/features/series-runs/series-run-view.tsx`
- Test: `frontend/e2e/series-native-audio-consistency.spec.ts`

**Interfaces:**
- Consumes: selected anchor metadata and actionable backend error details.
- Produces: a visible first-frame preparation state, direct Studio/shot repair link, and truthful “字幕待音频核验” status.

- [ ] Add a failing Playwright contract for missing first frame and pending audio verification.
- [ ] Surface the exact blocked shot, reason, and repair action without claiming completion.
- [ ] Run Playwright, TypeScript typecheck, backend focused suites, and `git diff --check`.
- [ ] From the frontend, confirm the current two cross-chapter anchors cannot be regenerated without shot-owned first frames and cannot be accepted as audio-synchronized without trusted evidence.
