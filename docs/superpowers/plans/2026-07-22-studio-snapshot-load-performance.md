# Studio Snapshot Load Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the time that Studio shows “正在加载工作台快照” without changing the snapshot response shape or production behavior.

**Architecture:** Use the complete series plan already persisted in `Novel.extra_data.series_plan` for Studio's read-only overview instead of rebuilding production-bible and production-graph snapshots for every episode on every page load. Prevent the React bootstrap effect from issuing duplicate workflow-list requests in development Strict Mode.

**Tech Stack:** FastAPI, async SQLAlchemy, Next.js 14, React 18, pytest, Playwright.

## Global Constraints

- Preserve stored data, snapshot response fields, workflow state, and all external-provider safety gates.
- Do not add external model calls or writes to the read-only Studio snapshot endpoint.
- Keep changes surgical in the existing dirty workspace; do not modify unrelated user work.
- Start each behavior change with a failing targeted test.

---

### Task 1: Fast persisted series-plan projection

**Files:**
- Modify: `backend/app/services/studio_snapshot.py`
- Create: `backend/tests/test_studio_snapshot_performance.py`

**Interfaces:**
- Consumes: `Novel.extra_data["series_plan"]` and the current workflow chapter ID.
- Produces: the existing `snapshot["series_plan"]` payload with `current_episode`, without calling `get_series_plan()`.

- [x] Add a failing test that patches `studio_snapshot.get_series_plan` to raise and proves a saved four-episode plan must still render in the snapshot.
- [x] Run `cd backend && pytest -q tests/test_studio_snapshot_performance.py` and confirm it fails at the patched full-plan rebuild.
- [x] Add a small saved-plan projection helper and replace the full `get_series_plan()` call in the Studio snapshot.
- [x] Re-run the targeted test and the production-graph snapshot tests.

### Task 2: Single Studio bootstrap request

**Files:**
- Modify: `frontend/src/components/studio/studio-shell.tsx`
- Modify: `frontend/e2e/studio-workspace.spec.ts`

**Interfaces:**
- Consumes: the existing `getStudioWorkflows()` request.
- Produces: one bootstrap request per mounted Studio page, including React Strict Mode development runs.

- [x] Add request counter assertions for bootstrap, direct-query refresh, and workflow switching.
- [x] Run the focused Playwright test and confirm the counters fail before the fix.
- [x] Guard bootstrap and snapshot effects while preserving explicit snapshot reload and workflow switching.
- [x] Re-run the focused Playwright test and TypeScript typecheck.

### Task 3: Real frontend performance acceptance

**Files:**
- No committed artifacts; screenshots go under `/tmp/studio-performance/`.

**Interfaces:**
- Verifies: `/studio` → automatic workflow selection → visible “制作看板”.

- [x] Reload the authenticated sunqy Studio page and measure time until “制作看板” is visible.
- [x] Confirm no loading stall, framework overlay, or relevant console error.
- [x] Capture the final viewport and report before/after timing with backend profiling evidence.
