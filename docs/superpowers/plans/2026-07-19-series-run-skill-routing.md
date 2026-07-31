# Series Run Skill Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make whole-book production resolve the active entity-extraction and script-generation Skills and persist exact Skill/version evidence instead of silently bypassing the Skill system.

**Architecture:** Add a focused series-run Skill routing service that owns canonical prompt selection and audit evidence. The existing episode persistence compatibility service calls this owner; deterministic persistence remains backward compatible, while every created script declares whether a Skill was selected and which version. Story-lock preparation uses the same owner when producing entity evidence so the two paths cannot drift.

**Tech Stack:** FastAPI, async SQLAlchemy, pytest, Next.js/React.

## Global Constraints

- Preserve existing series-run routes, identifiers, stages and persisted user data.
- Do not call paid providers during automated tests.
- Do not import API endpoints from services or feature modules.
- Start every behavior change with a failing test.
- Existing scripts without Skill evidence remain readable; newly created or stale-input records must carry evidence.

---

### Task 1: Canonical series-run Skill routing

**Files:**
- Create: `backend/app/services/series_run_skill_routing.py`
- Modify: `backend/app/services/episode_production_service.py`
- Test: `backend/tests/test_series_run_skill_routing.py`

**Interfaces:**
- Produces: `resolve_series_run_skill(db, *, user_id, task, stage, context, internal_prompt) -> dict`.
- Produces: `skill_audit_evidence(route) -> dict` containing ID, name, version, profile version, routing reason and execution mode.

- [ ] Write a failing test asserting that an active user `script_generation` Skill is selected and persisted in a newly created series-run script.
- [ ] Run `python3 -m pytest -q tests/test_series_run_skill_routing.py` and confirm it fails because the audit evidence is absent.
- [ ] Implement the routing owner with `select_prompt_skill_for_model` and fail closed when no active Skill is available for the required task.
- [ ] Call it from `create_or_resolve_script_stage` and persist `prompt_skill` evidence beside dialogue lineage.
- [ ] Run the targeted test and the existing orchestrator/story-lock contract tests.

### Task 2: Entity extraction Skill evidence in story-lock preparation

**Files:**
- Modify: `backend/app/features/series_run_story_locks/application/story_transaction.py`
- Test: `backend/tests/test_series_run_skill_routing.py`

**Interfaces:**
- Consumes: `resolve_series_run_skill` and `skill_audit_evidence` from Task 1.
- Produces: run metadata `skill_evidence.entity_extraction` bound to the exact selected Skill/version.

- [ ] Add a failing test proving story-lock preparation cannot report production entities without entity-extraction Skill evidence.
- [ ] Resolve `entity_extraction` at stage `analysis` using the complete ordered chapter source.
- [ ] Persist the evidence in run metadata without changing entity IDs or approval semantics.
- [ ] Run story-lock and live-preflight tests.

### Task 3: Frontend evidence and current four-chapter rerun

**Files:**
- Modify: `frontend/src/features/series-runs/series-run-view.tsx`
- Test: `frontend/e2e/four-chapter-live-canary.spec.ts`

**Interfaces:**
- Consumes: `run.run_metadata.skill_evidence` from Tasks 1-2.
- Produces: visible Skill name/version/execution-mode labels in the whole-book panel.

- [ ] Add a failing UI test for Script Skill and entity-extraction Skill evidence.
- [ ] Render concise evidence without duplicating backend routing rules.
- [ ] Run the focused frontend test and `npm run build`.
- [ ] From the signed-in frontend, rerun the current 3D four-chapter project and verify the selected anchor shots contain correct speaker and subtitle text before any paid video submission.
