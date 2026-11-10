# Publication Pipeline P2–P4 (Front → Shots → Quality → Commercial Gates) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extend NovelPublicationPipeline so one `POST /novels/{id}/publication-pipelines` can ensure series plan + Series Run through `shots_ready`, automate media/quality to Run `completed`, then reuse P1 render/publish — with fail-closed commercial gates (auth/DEV_MODE production defaults, readiness, private media, evidence summary). No Douyin.

**Architecture:** Keep Layer-A SeriesProductionRun FSM unchanged. Extend Layer-B orchestrator stages: `accepted → ensuring_plan → ensuring_run → run_front_to_shots → run_media_quality → episode_rendering → … → succeeded`. Inject service callables for plan/run/media so tests stay unit-level. Commercial gates run inside `publication_gating` when `gates.require_commercial_gates` or env `PUBLICATION_PIPELINE_REQUIRE_COMMERCIAL_GATES=true`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, pytest-asyncio; reuse `create_run`, `SeriesRunOrchestrator`, `generate_selected`, `close_media_tail`, `evaluate_publication_readiness`, `create_platform_publication`.

## Global Constraints

- Stay within design `docs/superpowers/specs/2026-11-03-novel-to-publication-one-click-pipeline-design.md`.
- No Douyin/Bilibili/external distribution.
- Do **not** change Series Run `ACTIVE_STATES` / `transition_run` +1 rules.
- Prefer extending publication-pipelines into full novel→publication one request.
- TDD; relevant pytest green before commit/push.
- Branch: `feat/series-run-redis-queue-and-tail-fsm`.
- Default `media_policy.shot_scope=all_episode_shots`; commercial rejects `anchor_shots_only`.
- Redis fail-closed unchanged (P1).

## File map

| Path | Role |
|---|---|
| `backend/app/core/runtime_env.py` | Production-aware `is_dev_mode()` / `app_environment()` |
| `backend/app/core/dev_generation.py` | Delegate `is_dev_mode` to runtime_env |
| `backend/app/core/security.py` | Use shared `is_dev_mode` |
| `backend/app/core/credential_encryption.py` | Use shared `is_dev_mode` |
| `backend/app/services/publication_pipeline_front.py` | ensure plan + create/reuse run + execute to shots_ready |
| `backend/app/services/publication_pipeline_media.py` | shot scope policy + media/quality automation hooks |
| `backend/app/services/publication_pipeline_gates.py` | commercial fail-closed gates + evidence summary |
| `backend/app/services/publication_pipeline_orchestrator.py` | Wire new stages before episode_rendering |
| `backend/app/api/v1/endpoints/publication_pipelines.py` | Queue without completed run; store model_bindings/budget; resume P2 |
| `backend/tests/test_runtime_env_dev_mode.py` | DEV_MODE production defaults |
| `backend/tests/test_publication_pipeline_front_to_shots.py` | P2 |
| `backend/tests/test_publication_pipeline_media_quality.py` | P3 |
| `backend/tests/test_publication_pipeline_commercial_gates.py` | P4 |
| `docs/superpowers/plans/2026-11-03-publication-pipeline-p2-p4.md` | This plan |

---

### Task 1: Production-aware DEV_MODE defaults

**Files:**
- Create: `backend/app/core/runtime_env.py`
- Modify: `backend/app/core/dev_generation.py` (`is_dev_mode`)
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/core/credential_encryption.py`
- Test: `backend/tests/test_runtime_env_dev_mode.py`

**Interfaces:**
- Produces: `app_environment() -> str`, `is_dev_mode() -> bool`
- Rule: if `DEV_MODE` unset and `APP_ENV`/`ENVIRONMENT` in `{production,prod}` → False; if `DEV_MODE` unset otherwise → True; explicit `DEV_MODE` always wins.

- [x] **Step 1: Write failing tests** for production default false / local default true / explicit override
- [x] **Step 2: Implement runtime_env + wire callers**
- [x] **Step 3: pytest green + commit**

---

### Task 2: Front-to-shots service (P2)

**Files:**
- Create: `backend/app/services/publication_pipeline_front.py`
- Test: `backend/tests/test_publication_pipeline_front_to_shots.py`

**Interfaces:**
- `async def ensure_series_plan_for_pipeline(db, *, user_id, novel_id, ensure: bool, series_plan_version: str | None) -> dict`  
  Returns `{series_plan_version, episodes}` or raises `PipelineFrontBlocked(code, detail)`.
- `async def ensure_series_run_for_pipeline(db, *, user_id, novel_id, series_plan_version, idempotency_key, episodes, model_bindings, budget_policy, requested_stages) -> SeriesProductionRun`  
  Uses `create_run` with key `pubpipe:{idempotency_key}`.
- `async def run_front_to_shots(db, run, *, execute_fn) -> SeriesProductionRun`  
  Calls `SeriesRunOrchestrator.execute` (injectable) until `shots_ready`; blocks on missing chapters/plan.

- [x] **Step 1: Failing tests** — missing plan/chapters → blocked codes; happy path reaches shots_ready via injected execute
- [x] **Step 2: Implement front helpers**
- [x] **Step 3: pytest green + commit**

---

### Task 3: Media/quality automation helpers (P3)

**Files:**
- Create: `backend/app/services/publication_pipeline_media.py`
- Test: `backend/tests/test_publication_pipeline_media_quality.py`

**Interfaces:**
- `def resolve_shot_scope(media_policy, gates) -> str` — default `all_episode_shots`; raise/return blocker if commercial + `anchor_shots_only`
- `async def run_media_quality_for_pipeline(db, run, pipeline, *, enter_media_fn, generate_fn, list_shots_fn) -> SeriesProductionRun`  
  Enters media, selects shots by scope, generates, expects `status==completed` and `media_tail.result==passed`; else block `quality_gate_incomplete` / `trusted_multimodal_evaluation_required`.

- [x] **Step 1: Failing tests** — commercial rejects anchor_shots_only; incomplete quality blocks; ready reports → completed
- [x] **Step 2: Implement**
- [x] **Step 3: pytest green + commit**

---

### Task 4: Commercial gates + evidence (P4)

**Files:**
- Create: `backend/app/services/publication_pipeline_gates.py`
- Test: `backend/tests/test_publication_pipeline_commercial_gates.py`

**Interfaces:**
- `def commercial_gates_required(pipeline, env=None) -> bool`
- `def evaluate_commercial_gates(pipeline, *, run, readiness, queue_evidence=None) -> dict`  
  Returns `{passed: bool, blockers: [...], evidence_summary: {...}}`  
  Checks: identity (`user_id`/`novel_id`), media_tail passed, readiness publishable, budget_policy present when live, delivery visibility private (default), final_video_url final, no preview.
- Private media: under commercial, `delivery.visibility` must be `private` (scaffolded default); record in evidence.

- [x] **Step 1: Failing tests**
- [x] **Step 2: Implement**
- [x] **Step 3: pytest green + commit**

---

### Task 5: Wire orchestrator + API (one-request novel→publication)

**Files:**
- Modify: `backend/app/services/publication_pipeline_orchestrator.py`
- Modify: `backend/app/api/v1/endpoints/publication_pipelines.py`
- Extend tests in Task 2–4 + keep P1 tests green

**Behavior:**
1. Create API: if no completed run, still `status=queued` (do **not** permanently block `series_run_not_completed`); store `model_bindings`/`budget_policy`/`ensure_series_plan` in `pipeline_metadata`.
2. Orchestrator `execute`:
   - If associated run already `completed` with media_tail passed → existing P1 path from `episode_rendering`.
   - Else advance `ensuring_plan` → `ensuring_run` → `run_front_to_shots` → `run_media_quality`, then P1 stages.
3. Resume: allow resume when previous blocker was `series_run_not_completed` once P2 enabled (clear and requeue).
4. `publication_gating`: after readiness, if commercial required, run `evaluate_commercial_gates`; on failure block without Publication; on success attach `evidence_summary` to `gate_summary`.

- [x] **Step 1: Failing integration-style orchestrator tests with injected front/media**
- [x] **Step 2: Implement wiring**
- [x] **Step 3: Run all publication_pipeline + runtime_env pytest green**
- [x] **Step 4: Commit + push**

---

## Spec coverage checklist

- P2 success: one request to shots_ready without manual execute-async — Task 2+5
- P2 missing plan/chapters stable blockers — Task 2
- P3 all_episode_shots default + ready reports auto — Task 3
- P3 untrusted/incomplete quality fail-closed — Task 3
- P3 commercial rejects anchor_shots_only — Task 3+4
- P4 require_commercial_gates fail-closed + evidence summary — Task 4+5
- P4 DEV_MODE production defaults — Task 1
- P4 readiness fail-closed — existing P1 + Task 4
- P4 private media scaffolding — Task 4 visibility gate
- No Douyin — keep P1 external platform reject
