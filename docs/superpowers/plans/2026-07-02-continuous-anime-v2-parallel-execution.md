# Continuous Anime V2 Parallel Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the V2 continuous anime production plan with parallel agents while keeping hot files such as `backend/app/api/v1/endpoints/workflow.py` under controlled integration.

**Architecture:** The source implementation spec remains `docs/continuous-anime-production-implementation-plan-v2.md`. This plan converts that spec into execution waves: independent service/model/test slices run in parallel first, then shared workflow/router/frontend integration follows once contracts are stable.

**Tech Stack:** FastAPI, async SQLAlchemy, pytest, Next.js 14, TypeScript, Playwright, FFmpeg.

---

## Assumptions

- Work proceeds on the current `codex/...` branch. The existing dirty/untracked workspace state is treated as user or prior-run state and must not be cleaned by agents.
- S1 is the primary product milestone because it has no external dependency and is required by S3/S4.
- S2 SDK submission is blocked on the official Volcano Seedance 2.0 contract, but S2-A/B can be developed behind mocked tests.
- S5 local FFmpeg rendering can proceed in parallel with S1 because the core renderer service is independent; final route wiring touches `workflow.py` and is reserved for the integration wave.
- No schema migrations are allowed unless a later explicit requirement overrides the V2 document; use existing JSON fields.

## Success Criteria

- Strategy routing can select verified Seedance 2.0 configs automatically when no explicit `model_config_id` is supplied, and records `strategy_routing` in job metadata.
- Production cards expose read-only character/scene/prop readiness from existing Character, StoryEntity, Asset, StoryBible, and Shot data.
- S2 reference limits and reference-package builder are testable without calling real providers.
- Local FFmpeg renderer has an isolated service with structured `ffmpeg_not_installed` behavior and tests that skip when FFmpeg is unavailable.
- Integration changes to `workflow.py` are reviewed sequentially after parallel workers return.

## Wave 1: Parallel Foundation Work

### Task A: S1-A Strategy Routing Backend

**Files:**
- Create: `backend/app/services/production_strategy_routing.py`
- Modify: `backend/app/api/v1/endpoints/workflow.py`
- Modify: `backend/app/services/studio_snapshot.py`
- Modify: `frontend/src/lib/production-strategy.ts`
- Test: `backend/tests/test_production_strategy_routing.py`
- Test: `backend/test_workflow_routes.py`

- [ ] Write RED tests for draft, final, explicit override, and fallback routing.
- [ ] Implement `resolve_strategy_video_config_id()` using `LLMConfig` joined to `LLMModel`.
- [ ] Wire routing into media-batch video config resolution and job `extra_data`.
- [ ] Add `routing_enabled` metadata and frontend hint copy.
- [ ] Verify with `cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_production_strategy_routing.py test_workflow_routes.py`.

### Task B: S1-B Production Cards Backend Contract

**Files:**
- Create: `backend/app/services/production_card_service.py`
- Create: `backend/app/api/v1/endpoints/production_cards.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_production_cards.py`

- [ ] Write RED tests for character aggregation, type-specific required views, and novel summary counts.
- [ ] Implement read-only card aggregation from existing entities, assets, StoryBible voice data, and shot usage.
- [ ] Expose `GET /api/v1/production-cards/novel/{novel_id}` and `GET /api/v1/production-cards/entity/{entity_id}`.
- [ ] Keep workflow gate refactor out of this worker; integration wave will connect shared readiness to `_final_quality_lock_snapshots()`.
- [ ] Verify with `cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_production_cards.py`.

### Task C: S2-A/B Reference Capability Foundation

**Files:**
- Modify: `backend/app/core/model_registry.py`
- Create: `backend/app/services/reference_package_builder.py`
- Test: `backend/tests/test_reference_package.py`

- [ ] Write RED tests for `get_model_reference_limits()` including unknown-model defaults.
- [ ] Add reference capability fields to registered video model `limits`.
- [ ] Implement reference package assembly with deterministic prioritization and truncation metadata.
- [ ] Do not wire SDK submission or final-quality gates in this wave.
- [ ] Verify with `cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_reference_package.py`.

### Task D: S5 Local FFmpeg Renderer Service

**Files:**
- Create: `backend/app/services/ffmpeg_local_renderer.py`
- Test: `backend/tests/test_ffmpeg_local_render.py`

- [ ] Write RED tests for missing FFmpeg structured error.
- [ ] Write FFmpeg-dependent tests guarded with `pytest.mark.skipif(not shutil.which("ffmpeg"))`.
- [ ] Implement manifest rendering service that handles local `/static` files, audio fallback, concat, subtitle output, and ffprobe metadata.
- [ ] Do not wire `POST /workflow/{workflow_id}/render` in this worker; integration wave will add the `ffmpeg_local` backend.
- [ ] Verify with `cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_ffmpeg_local_render.py`.

## Wave 2: Sequential Hot-File Integration

### Task E: Workflow Integration

**Files:**
- Modify: `backend/app/api/v1/endpoints/workflow.py`
- Modify: `backend/test_workflow_routes.py`
- Modify: `backend/app/services/publication_readiness.py` only if S5 render metadata requires it.

- [ ] Merge S1-A routing changes with any existing media-batch behavior.
- [ ] Refactor final-quality readiness to call the production card helper without behavior changes.
- [ ] Add S2 reference package submission only after official Volcano contract fields are confirmed.
- [ ] Add S5 `ffmpeg_local` render backend after the renderer service passes isolated tests.
- [ ] Verify with `cd backend && DEV_MODE=true PYTHONPATH=. pytest -q test_workflow_routes.py tests/test_production_cards.py tests/test_reference_package.py tests/test_ffmpeg_local_render.py`.

### Task F: Studio Frontend Integration

**Files:**
- Modify: `frontend/src/lib/api-client.ts`
- Create: `frontend/src/app/studio/cards/page.tsx`
- Test: `frontend/e2e/studio-production-cards.spec.ts`

- [ ] Add production card API client methods and TypeScript types.
- [ ] Build the Studio cards page using existing UI primitives and asset deep links.
- [ ] Add mocked Playwright tests for card readiness, gaps, and fix links.
- [ ] Verify with `cd frontend && npm run typecheck && npm run build && npx playwright test e2e/studio-production-cards.spec.ts --project=chromium`.

## Wave 3: Product Milestone Expansion

- [ ] Start S3 shot review and regeneration after S1 routing/cards are merged.
- [ ] Start S4 audio route and supporting-character finalize after S1 cards define readiness semantics.
- [ ] Start S2 SDK submission after the S2-E Volcano contract checklist is confirmed.
- [ ] Start S6 visual consistency only after S2 references and S3 review surfaces exist.

## Global Verification

Run after the integrated milestone:

```bash
cd backend && DEV_MODE=true PYTHONPATH=. python3 -m compileall app && DEV_MODE=true PYTHONPATH=. pytest -q
cd frontend && npm run typecheck && npm run build && npx tsc --noEmit
cd frontend && npx playwright test e2e/onboarding-simplification.spec.ts e2e/studio-full-flow.spec.ts e2e/workflow-production-guidance.spec.ts e2e/synthesis-history.spec.ts --project=chromium --workers=1
git diff --check
```
