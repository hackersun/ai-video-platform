# Four-Chapter Series Orchestrator And Live Consistency Validation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task. Use `superpowers:test-driven-development` for every behavior change, `superpowers:systematic-debugging` for unexpected failures, and `superpowers:verification-before-completion` before any completion claim.

**Goal:** Let a signed-in user start from the novel workbench and drive a four-chapter novel through a resumable whole-book animation run, then generate only selected anchor shots with `sunqy`'s verified model configurations and produce auditable evidence for style, character, scene/prop, event/story, voice, and delivery consistency.

**Architecture:** Keep the current `Novel -> SeriesPlan -> per-episode Workflow -> Script -> Storyboard -> Shot -> Media -> QualityGate` path. Add a thin, persistent book-level orchestrator above it; do not replace the existing single-episode producer. The orchestrator snapshots approved Story Bible facts, chapter-aware state, model bindings, selected anchor shots, budget, and stage results. It stops at hard gates, resumes idempotently, and delegates media creation to existing batch endpoints. All acceptance actions originate from visible frontend controls.

**Tech Stack:** FastAPI, async SQLAlchemy, SQLite/PostgreSQL-compatible additive models, Next.js 14, React 18, TypeScript, Playwright, pytest, current MiniMax/Volcano/HappyHorse provider adapters.

---

## 1. Confirmed Baseline And Problem Statement

The current four-chapter browser validation proved the following:

- The novel workbench can display four chapters and generate four planned episodes.
- Only episode 1 reached `shots_ready`; episodes 2-4 stayed `planned` with no workflow, storyboard, or shots.
- Continuing production requires one manual click per episode. There is no persisted whole-book run, retry boundary, pause/resume state, or book-level budget.
- Studio readiness was 25%, with hard blockers `missing_story_bible` and `missing_asset_locks`; voice count was zero and `carry_over_state` was empty.
- Entity extraction produced at least one semantic error (`沈砚在废弃灯` classified as a prop), omitted events, and exposed signs of future-chapter information leaking into earlier summaries.
- Producer supports selecting multiple shots inside one workflow, but there is no cross-episode anchor-shot selection surface.
- The selected-shot video configuration request is already wired and covered by one passing E2E case.
- No real video artifacts were generated in the baseline, so visual and voice consistency remain unverified.
- A combined E2E suite has one harness-only failure because the mock does not answer `GET /api/v1/video/models`.
- Isolated Next.js E2E runs can mutate tracked `frontend/tsconfig.json` with temporary `.next-*` type paths unless the runner restores it.

This plan fixes those root causes before claiming that the frontend can automatically finish a four-chapter novel.

---

## 2. Execution Contract

### Intent Lock

Make four-chapter production a resumable, budgeted, frontend-operated workflow whose consistency claims are backed by persisted artifacts and evaluator evidence.

### Scope Boundaries

In scope:

- One whole-book run for a four-chapter/four-episode novel.
- Automatic creation and execution of missing episode workflows through shot readiness.
- Chapter-aware approved facts, Story Bible, state machine, carry-over snapshots, and locked assets/voices.
- Cross-episode recommendation and selection of 2-shot smoke or 6-shot anchor sets.
- `sunqy` verified text, image, TTS, and Seedance 1.5 Pro model configurations.
- Six consistency dimensions plus delivery integrity, repair suggestions, and limited retry.
- Deterministic isolated E2E and explicitly enabled real-provider canaries.

Out of scope:

- Full-length generation of every shot in every episode during the first live acceptance.
- Automatic publication.
- Fine-tuning or training a custom model.
- Promoting Seedance 2.x or HappyHorse reference modes without adapter-specific live evidence.
- Destructive migration of current JSON metadata or existing workflows.

### Constraints

- Additive database changes only; export new models through `backend/app/models/__init__.py` and rely on `backend/init_db.py` `create_all()`.
- Existing episode and producer routes stay backward compatible.
- Only `approved` facts enter production snapshots; candidates and rejected entities remain excluded.
- Every generated artifact records chapter, episode, workflow, shot, Story Bible version, state-machine version, asset versions, voice binding, model config ID, provider model ID, effective parameters, cost, and retry lineage.
- API keys and decrypted secrets must never appear in stdout, screenshots, Playwright traces, fixtures, or reports.
- Standard E2E writes only to an isolated database. Live configurations are copied by allowlist into a mode-`0600` temporary database and deleted after the run.
- Real calls require `PRODUCTION_OS_LIVE=1` and a finite positive RMB ceiling. The backend checks remaining budget before each job, not only the frontend.
- A failed hard gate pauses the run; it must not silently skip an episode or generate downstream media.
- No completion claim until actions are initiated through the frontend and persisted state is verified from the API/database.

### Acceptance Criteria

1. From `/novels/{id}?tab=series-plan`, one visible action creates a run covering exactly four ordered episodes.
2. The run reaches `shots_ready` for all four episodes without additional per-episode clicks, or stops with a specific resolvable blocker.
3. Repeating or resuming the same command does not duplicate workflows, scripts, storyboards, shots, or media jobs.
4. Earlier-episode prompts contain no fact whose first evidence belongs to a later chapter.
5. Story Bible, state machine, canonical character/scene/prop assets, and character voice bindings are locked before live media generation.
6. The frontend recommends and can select either 2 smoke shots or 6 cross-episode anchor shots; only selected shot IDs are submitted.
7. Live canary uses only verified `sunqy` configurations and stops before exceeding budget.
8. Each anchor artifact receives fresh, artifact-bound evaluations for narrative truth, character visual, scene/prop state, style/cinematography, voice/dialogue, and delivery integrity.
9. The final frontend report distinguishes `通过`, `失败`, `阻塞`, and `未验证`; missing artifacts can never be reported as passing.
10. `frontend/tsconfig.json` is byte-identical before and after isolated browser verification.

### No-Confirmation Decision Rules During Execution

- Automatically retry transient provider errors at most once with the same immutable snapshot.
- Automatically choose the smallest repair scope: prompt-only, one asset binding, one audio segment, or one selected shot.
- Do not auto-repair approved story facts; pause with a review task instead.
- Stop live generation when the RMB ceiling would be exceeded, when a secret-safe config cannot be resolved, or when a hard gate fails.
- Do not enable six-shot live generation merely because the two-shot smoke passes; six-shot mode requires a separately supplied larger budget ceiling.

---

## 3. `sunqy` Live Model Matrix

Use IDs in persisted bindings and requests; never embed credentials in code or tests.

| Capability | Primary verified config | Role | Fallback / restriction |
| --- | --- | --- | --- |
| Text/reasoning | `18e068a4-200b-4f17-9ffa-c8b1ee108caa` (`MM-M3` / `MiniMax-M3`) | entity normalization, screenplay, event/state extraction, semantic judge | `598dd40b-2a9b-470c-b6c6-8ea91efa7303` (`MiniMax-2.7-text`) only after a recorded primary failure |
| Image | `5f20af31-3cda-48e3-a6eb-fc766ba14549` (`Minimax-2.7-img` / `image-01`) | canonical character sheets, scene/prop anchors, selected-shot reference images | no pending test config |
| TTS | `5a8d3813-ee43-4ed2-b40b-4935368e784e` (`Minimax-2.7-HD` / `speech-2.6-hd`) | voice audition and selected dialogue | use Story Bible character voice binding; no implicit random voice |
| Video | `980cb5db-0281-4835-9486-a739fcb35d98` (`豆包Seedance-1.5-pro` / `doubao-seedance-1-5-pro-251215`) | primary selected-shot video canary | keep current supported duration/resolution contract |
| Video experimental | verified HappyHorse T2V/I2V/R2V configs already owned by `sunqy` | adapter-specific comparison canary | R2V/I2V must remain blocked until their adapters prove real reference delivery; never use as primary acceptance |

Do not use pending configurations. Do not claim that `sunqy` has a verified Seedance 2.x configuration.

Recommended cost waves:

- Wave 0: deterministic/contract tests, RMB 0.
- Wave 1: 2 smoke shots, one image reference per required entity, short TTS segments, and two short Seedance jobs; require `PRODUCTION_OS_LIVE_MAX_RMB`, recommended initial ceiling RMB 10.
- Wave 2: 6 cross-episode anchor shots only after Wave 1 passes; require a new explicit ceiling, recommended maximum RMB 30. This wave remains disabled by default.

---

## 4. File Map

### New focused units

- `backend/app/models/series_production_run.py`: book run and per-episode stage state.
- `backend/app/services/series_run_orchestrator.py`: idempotent run creation, resume, gate checks, and delegation.
- `backend/app/services/chapter_fact_timeline.py`: evidence chapter and availability projection.
- `backend/app/services/anchor_shot_service.py`: deterministic cross-episode recommendations.
- `backend/app/services/live_canary_budget.py`: server-authoritative budget reservation and accounting.
- `backend/app/api/v1/endpoints/series_runs.py`: create/read/resume/pause/select/run endpoints.
- `backend/tests/test_series_run_orchestrator.py`.
- `backend/tests/test_chapter_fact_timeline.py`.
- `backend/tests/test_anchor_shot_service.py`.
- `backend/tests/test_live_canary_budget.py`.
- `backend/scripts/prepare_isolated_live_model_configs.py`.
- `backend/tests/test_prepare_isolated_live_model_configs.py`.
- `frontend/src/components/novels/series-run-panel.tsx`.
- `frontend/src/components/novels/anchor-shot-selector.tsx`.
- `frontend/e2e/four-chapter-series-run.spec.ts`.
- `frontend/e2e/four-chapter-live-canary.spec.ts`.
- `scripts/run-four-chapter-acceptance.mjs`.

### Existing units to extend narrowly

- `backend/app/models/__init__.py`
- `backend/init_db.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/endpoints/novels.py`
- `backend/app/services/series_production.py`
- `backend/app/services/entity_extraction_service.py`
- `backend/app/services/entity_extraction_schema.py`
- `backend/app/services/story_entity_lifecycle.py`
- `backend/app/services/story_state_machine.py`
- `backend/app/services/production_bible.py`
- `backend/app/services/provider_asset_binding_service.py`
- `backend/app/services/quality_evaluation_service.py`
- `backend/app/services/repair_planner.py`
- `backend/app/api/v1/endpoints/workflow.py`
- `frontend/src/app/novels/[id]/page.tsx`
- `frontend/src/app/producer/page.tsx`
- `frontend/src/lib/api-client.ts`
- `frontend/src/lib/studio-types.ts`
- `frontend/src/lib/episode-preview-production.ts`
- `frontend/e2e/series-studio-multi-episode.spec.ts`
- `frontend/e2e/production-os-live-canary.spec.ts`
- `scripts/run-isolated-production-os.mjs`
- `scripts/run-isolated-frontend-e2e.mjs`

---

## Task 1: Freeze The Four-Chapter Contract And Repair The Test Harness

**Files:**

- Create: `backend/tests/fixtures/four_chapter_novel.py`
- Create: `frontend/e2e/helpers/four-chapter-fixture.ts`
- Modify: `frontend/e2e/series-studio-multi-episode.spec.ts`
- Modify: `frontend/e2e/production-os-live-canary.spec.ts`
- Modify: `scripts/run-isolated-production-os.mjs`
- Modify: `scripts/run-isolated-frontend-e2e.mjs`

- [ ] **Step 1: Add one canonical four-chapter fixture**

Use four ordered chapters with facts deliberately introduced at different times: protagonist and coat in chapter 1, copper bell in chapter 2, damaged lantern in chapter 3, final location/event consequence in chapter 4. Include stable IDs and expected first-evidence chapter for every entity/event.

- [ ] **Step 2: Write failing baseline assertions**

Assert four episodes but only one current workflow, missing Story Bible/state machine/voice locks, and no cross-episode shot selection. These tests document the observed gap rather than disguising it.

- [ ] **Step 3: Fix the stale `/video/models` mock**

In `frontend/e2e/series-studio-multi-episode.spec.ts`, answer `GET /api/v1/video/models` with the same explicit contract used by current producer tests. Keep assertions for provider binding, ledger, and quality intact.

- [ ] **Step 4: Make temporary Next.js configuration reversible**

Before starting Next.js, snapshot `frontend/tsconfig.json` bytes and checksum. Restore them in `finally` and on SIGINT/SIGTERM. Fail the runner if the post-run checksum differs. Prefer a stable `.next-playwright/types/**/*.ts` include rather than accumulating unique directory names.

- [ ] **Step 5: Verify the repaired baseline**

```bash
cd backend
python3 -m pytest -q \
  test_series_production.py \
  tests/test_series_plan_service.py \
  tests/test_quality_gate_integration.py \
  tests/test_provider_binding_integration.py

cd ../frontend
npx playwright test e2e/series-studio-multi-episode.spec.ts \
  e2e/production-os-live-canary.spec.ts \
  --project=chromium --workers=1 --grep-invert='budget-gated'
```

Expected: deterministic checks pass and `git diff --exit-code -- frontend/tsconfig.json` passes after the runner exits.

---

## Task 2: Add A Persistent, Idempotent Whole-Book Run

**Files:**

- Create: `backend/app/models/series_production_run.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/init_db.py`
- Create: `backend/app/services/series_run_orchestrator.py`
- Create: `backend/app/api/v1/endpoints/series_runs.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/test_series_run_orchestrator.py`

- [ ] **Step 1: Write failing model and API tests**

Define `SeriesProductionRun` with `id`, `user_id`, `novel_id`, `series_plan_version`, `status`, `current_episode_number`, `requested_stages`, `model_bindings`, `budget_policy`, `cost_summary`, `gate_summary`, `run_metadata`, timestamps, and optimistic `version`. Store episode state as ordered JSON entries only for orchestration metadata; keep canonical scripts/storyboards/shots in their existing tables.

Required routes:

```text
POST /api/v1/series-runs
GET  /api/v1/series-runs/{run_id}
POST /api/v1/series-runs/{run_id}/resume
POST /api/v1/series-runs/{run_id}/pause
```

Test that the same `(novel_id, series_plan_version, idempotency_key)` returns one run and that another user's run is inaccessible.

- [ ] **Step 2: Implement a finite state machine**

Use explicit run states `created -> preflight -> planning -> facts_ready -> assets_ready -> episodes_building -> shots_ready -> anchor_ready -> media_running -> evaluating -> completed`, plus `paused`, `blocked`, and `failed`. Each episode records the same stage, canonical IDs, attempt count, blocker, and immutable input hash.

- [ ] **Step 3: Reuse existing episode workflow operations**

For each ordered episode, create or resolve exactly one workflow, script, storyboard, and shot set. Delegate to existing service functions/routes; do not duplicate prompt builders in the orchestrator. Commit after each stage so resume starts from the last durable boundary.

- [ ] **Step 4: Prove idempotency and recovery**

Inject a failure while building episode 3. Assert episodes 1-2 are not rebuilt, episode 3 resumes once, episode 4 then proceeds, and entity/workflow/media row counts contain no duplicates.

- [ ] **Step 5: Verify**

```bash
cd backend
python3 -m pytest -q tests/test_series_run_orchestrator.py test_series_production.py
```

---

## Task 3: Fix Entity Semantics And Future-Chapter Leakage

**Files:**

- Create: `backend/app/services/chapter_fact_timeline.py`
- Modify: `backend/app/services/entity_extraction_schema.py`
- Modify: `backend/app/services/entity_extraction_service.py`
- Modify: `backend/app/services/story_entity_lifecycle.py`
- Modify: `backend/app/services/story_state_machine.py`
- Modify: `backend/app/services/production_bible.py`
- Create: `backend/tests/test_chapter_fact_timeline.py`
- Modify: `backend/tests/test_entity_extraction_classification.py`
- Modify: `backend/tests/test_entity_extraction_quality.py`

- [ ] **Step 1: Add failing regression examples**

Assert `沈砚在废弃灯` cannot become a prop, an event contains actor/action/object/outcome, and a chapter-4 fact is absent from chapter-1 through chapter-3 prompt snapshots.

- [ ] **Step 2: Make provenance structural**

Every extracted fact must contain `entity_type`, normalized `canonical_name`, exact evidence span, `source_chapter_id`, `source_chapter_index`, confidence, extraction model/config, and review state. Reject a candidate when its canonical name is a sentence fragment, predicate phrase, or contains an actor/action pattern incompatible with its entity type.

- [ ] **Step 3: Build as-of-chapter projections**

`chapter_fact_timeline.py` returns approved facts whose first evidence chapter is less than or equal to the requested episode boundary. Production Bible and state-machine prompt composition must consume that projection, never the final whole-book summary directly.

- [ ] **Step 4: Separate state from future intent**

Persist `current_state`, `known_to_characters`, `introduced_at`, and `resolved_at`. Future plan/foreshadowing may be stored, but production prompts receive it only when the episode contract explicitly requires foreshadowing.

- [ ] **Step 5: Verify**

```bash
cd backend
python3 -m pytest -q \
  tests/test_chapter_fact_timeline.py \
  tests/test_entity_extraction_classification.py \
  tests/test_entity_extraction_quality.py \
  test_story_state_machine.py \
  test_story_prompt_context.py
```

---

## Task 4: Make Story Bible, Asset, And Voice Locks Mandatory Preflight Gates

**Files:**

- Modify: `backend/app/services/series_run_orchestrator.py`
- Modify: `backend/app/services/production_bible.py`
- Modify: `backend/app/services/provider_asset_binding_service.py`
- Modify: `backend/app/api/v1/endpoints/workflow.py`
- Modify: `backend/test_workflow_routes.py`
- Create: `backend/tests/test_series_run_preflight.py`

- [ ] **Step 1: Write failing gate tests**

Assert a run cannot enter `media_running` with missing Story Bible, missing state machine, unapproved entities, unlocked canonical assets, missing provider binding, or an unresolved speaking-character voice.

- [ ] **Step 2: Auto-build draft control artifacts, but require approval semantics**

The orchestrator may generate a draft Story Bible/state machine and canonical asset candidates. In automated acceptance, deterministic fixture approval is explicit and recorded; in normal production, unresolved semantic conflicts create review tasks and block live media.

- [ ] **Step 3: Lock versioned assets and voices**

Lock character front/three-quarter/full-body references, recurring scene anchors, continuity-critical props, global style board, and a voice binding per speaking character. Persist provider-specific bindings and public-media readiness.

- [ ] **Step 4: Snapshot every episode contract**

Record the as-of-chapter facts plus carry-over state from the prior episode. A later approved change marks affected downstream episodes/artifacts as `superseded_review_required` rather than silently rewriting old jobs.

- [ ] **Step 5: Verify**

```bash
cd backend
python3 -m pytest -q \
  tests/test_series_run_preflight.py \
  test_workflow_routes.py -k 'story_bible or voice or provider_binding or preflight'
```

---

## Task 5: Add Frontend Whole-Book Controls And Cross-Episode Anchor Selection

**Files:**

- Create: `backend/app/services/anchor_shot_service.py`
- Create: `backend/tests/test_anchor_shot_service.py`
- Modify: `backend/app/api/v1/endpoints/series_runs.py`
- Create: `frontend/src/components/novels/series-run-panel.tsx`
- Create: `frontend/src/components/novels/anchor-shot-selector.tsx`
- Modify: `frontend/src/app/novels/[id]/page.tsx`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/studio-types.ts`
- Create: `frontend/e2e/four-chapter-series-run.spec.ts`

- [ ] **Step 1: Write a failing browser test from the workbench**

The browser clicks `整书自动制作`, confirms four ordered episodes and model bindings, starts the run, watches each episode reach `shots_ready`, and never clicks a per-episode generation button.

- [ ] **Step 2: Add a focused run panel**

Show current stage, four episode rows, hard blockers, model bindings, projected/actual cost, pause/resume, and deep links to existing Studio/Producer pages. Do not hide failure details behind a generic progress percentage.

- [ ] **Step 3: Recommend anchors deterministically**

Score shots for first protagonist appearance, recurring character, major scene change, continuity prop, event turning point, dialogue/voice, and final consequence. Default smoke set: two shots from different episodes. Full anchor set: six shots covering all four episodes and all consistency dimensions.

- [ ] **Step 4: Persist cross-episode selection**

Add:

```text
GET  /api/v1/series-runs/{run_id}/anchor-shots
PUT  /api/v1/series-runs/{run_id}/anchor-shots
POST /api/v1/series-runs/{run_id}/generate-selected
```

The final POST resolves selected IDs grouped by workflow and calls existing batch generation with those exact `shot_ids`. Reject a shot outside the run.

- [ ] **Step 5: Verify request origin and exact selection**

Playwright must observe the frontend POST, assert six selected IDs in full mode, and then assert every generated job belongs to that set and no unselected shot has a new job.

```bash
cd frontend
npx playwright test e2e/four-chapter-series-run.spec.ts --project=chromium --workers=1
```

---

## Task 6: Add Secret-Safe `sunqy` Config Staging And Server-Side Budget Enforcement

**Files:**

- Create: `backend/scripts/prepare_isolated_live_model_configs.py`
- Create: `backend/tests/test_prepare_isolated_live_model_configs.py`
- Create: `backend/app/services/live_canary_budget.py`
- Create: `backend/tests/test_live_canary_budget.py`
- Modify: `backend/app/services/series_run_orchestrator.py`
- Modify: `backend/app/api/v1/endpoints/series_runs.py`

- [ ] **Step 1: Write secret-leak and allowlist tests**

The staging script accepts source DB, target DB, source user ID, target canary user ID, and an allowlist of config IDs. It copies only required provider/model/config rows, preserves encrypted/opaque secret fields, prints only IDs and checksums, creates the target with `0600`, and refuses pending/unverified configurations.

- [ ] **Step 2: Add budget reservation semantics**

Before job submission, atomically reserve estimated RMB. After completion, reconcile actual cost. Reject when `spent + reserved + next_estimate > max_rmb`. On failed submission, release the reservation; on unknown provider state, retain it until reconciliation.

- [ ] **Step 3: Enforce capability bindings**

Validate that text/image/TTS/video config IDs belong to the run user, match the required capability, and are verified. Persist the resolved provider/model snapshot. Never silently switch to a pending config.

Before the first paid generation, invoke the existing config-test path for each staged primary configuration and record only status, latency, provider/model ID, and redacted error class. A historical `verified` flag alone is not sufficient live evidence; any failed recheck blocks that capability instead of falling through to an unrelated provider.

- [ ] **Step 4: Verify**

```bash
cd backend
python3 -m pytest -q \
  tests/test_prepare_isolated_live_model_configs.py \
  tests/test_live_canary_budget.py
```

Also run the script against a synthetic source DB and assert no API-key-shaped value appears in captured stdout/stderr.

---

## Task 7: Make Consistency Evaluation Artifact-Bound And Repairable

**Files:**

- Modify: `backend/app/services/quality_evaluation_service.py`
- Modify: `backend/app/services/repair_planner.py`
- Modify: `backend/app/services/series_run_orchestrator.py`
- Modify: `backend/app/api/v1/endpoints/series_runs.py`
- Modify: `frontend/src/components/novels/series-run-panel.tsx`
- Create: `backend/tests/test_series_anchor_quality.py`

- [ ] **Step 1: Write failing stale-evidence tests**

An evaluation passes only when its `artifact_id`, shot ID, episode contract version, evaluator version, and creation time match the new job. Old evaluations and self-reported job metadata are not evidence.

- [ ] **Step 2: Evaluate exact dimensions**

Persist scores, thresholds, findings, evidence references, and blocking state for:

1. `narrative_truth`: chapter event, causality, and dialogue meaning.
2. `character_visual`: face, hair, clothing, body, and distinguishing marks against locked references.
3. `scene_prop_state`: scene topology, recurring objects, prop ownership/damage/position.
4. `style_cinematography`: global anime style, palette, line/render treatment, shot grammar, motion/camera.
5. `voice_dialogue`: speaker identity, voice binding, language, timing, intelligibility, and optional lip-sync evidence.
6. `delivery_integrity`: playable artifact, duration, resolution, audio stream, URL/manifest lineage.

The existing six-dimension names may remain internally for compatibility, but the frontend must map them explicitly and show missing evidence.

- [ ] **Step 3: Compare across episodes**

For recurring characters/scenes/props/voices, compare each anchor to both the canonical reference and the preceding accepted anchor. Narrative facts compare to the as-of-chapter contract, not the whole-book ending.

- [ ] **Step 4: Plan minimal repairs**

One failed dimension proposes the smallest affected operation. Retry at most once automatically for a transient or prompt-local failure; semantic fact conflicts block for review. Persist parent job/evaluation IDs.

- [ ] **Step 5: Verify**

```bash
cd backend
python3 -m pytest -q \
  tests/test_series_anchor_quality.py \
  tests/test_quality_gate_integration.py \
  tests/test_provider_binding_integration.py
```

---

## Task 8: Run Deterministic Frontend Acceptance Before Any Paid Call

**Files:**

- Create: `scripts/run-four-chapter-acceptance.mjs`
- Modify: `package.json`
- Modify: `frontend/package.json`
- Modify: `frontend/e2e/four-chapter-series-run.spec.ts`

- [ ] **Step 1: Create the isolated environment**

Use `/tmp/ai-video-platform-four-chapter.db`, backend port 8000, frontend port 3100, repository-external Playwright outputs, and a unique canary user. Record development DB size and protected row counts before and after.

- [ ] **Step 2: Run the full frontend path**

The test imports/creates four chapters from the UI, generates the series plan, clicks `整书自动制作`, waits for all four episodes to reach `shots_ready`, selects the recommended two-shot smoke set, submits deterministic image/TTS/video jobs, opens the result report, and verifies persisted lineage through browser-originated API reads.

- [ ] **Step 3: Verify no hidden regression**

```bash
cd /Users/sunqinyue/Documents/work/BJDEV/claude/ai-video-platform
npm run verify:four-chapter
git diff --exit-code -- frontend/tsconfig.json
```

The command must include backend focused tests, frontend typecheck/build, and Playwright. All statuses are printed as `通过`, `失败`, or `无法运行`.

---

## Task 9: Run The Budget-Gated Live Canary From The Frontend

**Files:**

- Create: `frontend/e2e/four-chapter-live-canary.spec.ts`
- Modify: `frontend/e2e/production-os-live-canary.spec.ts`
- Modify: `scripts/run-four-chapter-acceptance.mjs`
- Create: `docs/operations/four-chapter-live-canary.md`

- [ ] **Step 1: Stage only verified configurations**

Copy the allowlisted `sunqy` model configs to the temporary canary DB without emitting secrets. Bind MM-M3, image-01, speech-2.6-hd, and Seedance 1.5 Pro to the run.

- [ ] **Step 2: Execute Wave 1 from visible UI controls**

```bash
PRODUCTION_OS_LIVE=1 \
PRODUCTION_OS_LIVE_MAX_RMB=10 \
PRODUCTION_OS_LIVE_ANCHOR_COUNT=2 \
npm run verify:four-chapter:live
```

The browser opens the novel workbench, resumes the persisted run, selects two recommended anchors from different episodes, and clicks `生成所选关键镜头`. Direct API-only job submission is not acceptance.

- [ ] **Step 3: Poll and collect immutable evidence**

Require completed image/reference, TTS where dialogue exists, video artifact, actual/estimated cost, provider task ID, model/config snapshot, and fresh evaluation IDs. Capture screenshots of the workbench run panel, selected anchors, producer job states, and final quality report.

- [ ] **Step 4: Fail closed**

Mark the run `失败` or `阻塞`, not `通过`, for timeout, missing artifact, stale evaluation, over-budget reservation, unavailable public media, unverified config, or absent voice evidence on a dialogue shot.

- [ ] **Step 5: Keep Wave 2 disabled until separately budgeted**

When a larger budget is explicitly supplied, rerun with six anchors covering all four episodes. Do not infer approval from the Wave 1 ceiling.

- [ ] **Step 6: Clean up safely**

Delete temporary DB/config copies and local canary outputs after generating a redacted manifest/report. Keep only non-secret IDs, hashes, timings, costs, scores, screenshots, and artifact URLs allowed by the project's evidence policy.

---

## Task 10: Final Regression, Review, And Delivery Report

**Files:**

- Modify: `README.md`
- Modify: `docs/operations/four-chapter-live-canary.md`
- Create: `docs/reports/four-chapter-acceptance-template.md`

- [ ] **Step 1: Run fresh verification**

```bash
cd backend
python3 -m pytest -q \
  tests/test_series_run_orchestrator.py \
  tests/test_chapter_fact_timeline.py \
  tests/test_series_run_preflight.py \
  tests/test_anchor_shot_service.py \
  tests/test_prepare_isolated_live_model_configs.py \
  tests/test_live_canary_budget.py \
  tests/test_series_anchor_quality.py \
  test_series_production.py \
  test_workflow_routes.py

cd ../frontend
npm run typecheck
npm run build

cd ..
npm run verify:four-chapter
```

- [ ] **Step 2: Perform focused code review**

Review ownership filters, idempotency, concurrent resume, budget reservation races, API-key redaction, chapter boundary enforcement, exact shot selection, stale-evaluation rejection, and all temporary-file cleanup paths.

- [ ] **Step 3: Produce an issue-first Chinese acceptance report**

For each of four episodes and each selected anchor, report:

- workflow/script/storyboard/shot readiness;
- exact model/config used;
- job/task IDs and artifact availability;
- actual or estimated RMB cost;
- six dimension scores and evidence IDs;
- repairs/retries;
- final status: `通过`, `失败`, `阻塞`, or `未验证`.

- [ ] **Step 4: Apply the release claim rule**

The strongest allowed claim after Wave 1 is: “前端已可自动推进四章到镜头就绪，且两个跨集关键镜头通过/未通过实模验证.” Only after six anchors cover all four episodes may the report claim cross-episode anchor consistency. Neither result proves full-episode or whole-series consistency until every production shot has artifact-bound evidence.

---

## 5. Recommended Implementation Order And Parallel Boundaries

Execute Tasks 1-3 sequentially because they define the contract and data truth. After Task 3 passes:

- Task 4 (preflight/locks) and Task 6 (config/budget safety) are independent.
- Task 5 depends on Task 2 API shape and Task 4 gate semantics.
- Task 7 depends on Tasks 3-4 and existing quality infrastructure.
- Tasks 8-10 are integration/release work and remain sequential.

Do not parallel-edit `backend/app/services/series_run_orchestrator.py`, `frontend/src/app/novels/[id]/page.tsx`, or `frontend/e2e/production-os-live-canary.spec.ts` from multiple workers at once.

## 6. Definition Of Done

This plan is complete only when the deterministic four-chapter frontend acceptance passes, the live Wave 1 run either passes with artifact-bound evidence or fails with a precise actionable blocker, the development database and tracked `tsconfig.json` are unchanged by isolation tooling, and the final report does not overstate untested full-series consistency.
