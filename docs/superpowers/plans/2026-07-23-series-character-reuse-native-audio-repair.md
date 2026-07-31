# Series Character Reuse And Native Audio Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make locked character multi-view assets the default cross-chapter reference source, retain an explicit single-shot first-frame regeneration path, and prevent inaudibly quiet Seedance native-audio videos from being accepted without local repair.

**Architecture:** Keep the existing composite series board as a backward-compatible style/fallback artifact, but prefer complete locked `entity_multiview` character assets by canonical entity ID. Filter references per shot so unrelated characters are not sent to the image model. Measure native-audio loudness during subtitle aggregation and normalize only quiet tracks locally, without another provider call.

**Tech Stack:** FastAPI, async SQLAlchemy, FFmpeg/FFprobe, Next.js 14, React 18, TypeScript, Playwright, pytest.

## Global Constraints

- Existing successful media and paid provider operations must remain intact.
- Do not add new paid provider calls during repair verification.
- Character assets are novel/entity scoped and reused across chapters by default.
- A shot-specific first frame may be regenerated without replacing canonical character assets.
- Legacy composite references remain readable but must not silently mix unrelated characters into a single-character shot.
- Do not grow the legacy `shots.py` endpoint hotspot; behavior belongs in focused services.

---

### Task 1: Prefer canonical entity multi-view assets

**Files:**
- Modify: `backend/app/features/series_run_media_preflight/public.py`
- Test: `backend/tests/test_series_run_preflight.py`

**Interfaces:**
- Consumes: active, final, locked `Asset` rows with `generation_params.source == "entity_multiview"` and `view_key` values `front`, `side`, `back`.
- Produces: media preflight `asset_locks` containing the exact character assets used across every episode.

- [ ] **Step 1: Write the failing tests**

Add tests proving that a complete locked front/side/back set is preferred over a multi-character composite and that incomplete sets remain blocked.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd backend
./venv/bin/pytest -q tests/test_series_run_preflight.py -k "multiview or incomplete"
```

Expected: the complete set is not selected by the current implementation.

- [ ] **Step 3: Implement minimal selection**

Derive canonical roles from `entity_multiview.view_key`, select one locked/final asset per required view and entity, preserve the global style selection, and use the legacy composite only when no complete individual set exists.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same pytest command and expect all selected tests to pass.

### Task 2: Resolve only the current shot's character references

**Files:**
- Modify: `backend/app/services/shot_reference_input_service.py`
- Test: `backend/tests/test_shot_reference_input_service.py`

**Interfaces:**
- Consumes: the shot's canonical character IDs and locked asset rows.
- Produces: provider-safe reference URLs ordered by current-shot character and view, excluding unrelated characters.

- [ ] **Step 1: Write the failing tests**

Add one test where two characters have locked three-view assets but a shot contains only one character. Assert that only that character's URLs are returned. Add one test that rejects an ambiguous legacy multi-character board for a single-character shot.

- [ ] **Step 2: Run tests to verify RED**

```bash
cd backend
./venv/bin/pytest -q tests/test_shot_reference_input_service.py
```

- [ ] **Step 3: Implement minimal filtering**

Select entity-bound assets matching `shot.character_refs`; keep a style-only board; reject a multi-character composite when it is the only character reference for a single-character shot.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same pytest command and expect all tests to pass.

### Task 3: Repair quiet native audio locally

**Files:**
- Modify: `backend/app/services/native_audio_subtitle_renderer.py`
- Modify: `backend/app/features/series_anchor_generation/media_reconciliation.py`
- Test: `backend/tests/test_native_audio_subtitle_renderer.py`

**Interfaces:**
- Produces: `audio_loudness` evidence containing mean/max dB and a `normalized` boolean.
- Produces: a subtitle-burned MP4 with AAC audio normalized when mean volume is below `-28 dB`.

- [ ] **Step 1: Write the failing tests**

Generate a quiet synthetic AAC source and assert that the renderer raises its resulting mean loudness above the acceptance threshold while retaining the audio stream.

- [ ] **Step 2: Run tests to verify RED**

```bash
cd backend
./venv/bin/pytest -q tests/test_native_audio_subtitle_renderer.py
```

- [ ] **Step 3: Implement minimal loudness repair**

Use FFmpeg `volumedetect`; when mean volume is below `-28 dB`, encode AAC with a bounded gain targeting `-20 dB`, otherwise stream-copy audio. Persist evidence and bump the aggregation contract to `native_audio_activity_v6`.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same pytest command and expect all tests to pass.

### Task 4: Expose explicit single-shot first-frame regeneration

**Files:**
- Modify: `frontend/src/features/series-runs/use-selected-first-frames.ts`
- Modify: `frontend/src/components/novels/anchor-shot-selector.tsx`
- Modify: `frontend/src/components/novels/series-run-panel.tsx`
- Modify: `frontend/src/features/series-runs/series-run-view.tsx`
- Test: `frontend/e2e/five-chapter-representative-series-run.spec.ts`

**Interfaces:**
- Produces: `regenerateShot(shotId)` which always calls the existing shot image endpoint for one selected shot.
- UI copy states that canonical character assets are reused by default and the action only replaces that shot's first frame.

- [ ] **Step 1: Add the failing Playwright assertion**

Assert that each selected anchor exposes `单独重做本镜头参考` and that clicking it calls only that shot's image endpoint.

- [ ] **Step 2: Run test to verify RED**

```bash
cd frontend
npx playwright test e2e/five-chapter-representative-series-run.spec.ts --project=chromium --workers=1
```

- [ ] **Step 3: Implement the focused UI action**

Add the button to each selected recommendation and route it through the existing hook without changing canonical assets.

- [ ] **Step 4: Run test and typecheck**

```bash
npm run typecheck
npx playwright test e2e/five-chapter-representative-series-run.spec.ts --project=chromium --workers=1
```

### Task 5: Repair and verify the existing Chapter 3 deliverable

**Files:**
- Runtime data only; no provider request.

- [ ] **Step 1: Reconcile completed native subtitles**

Run the existing `reconcile-selected` path after the v6 contract change so the quiet Chapter 3 audio is normalized from the persisted provider source.

- [ ] **Step 2: Verify media**

Use FFprobe and FFmpeg `volumedetect` to verify H.264 video, AAC audio, 720x1280 output, visible subtitles, and acceptable Chapter 3 loudness.

- [ ] **Step 3: Verify frontend**

Run the existing five-chapter continuation Playwright test and confirm that all three deliveries remain visible and playable.
