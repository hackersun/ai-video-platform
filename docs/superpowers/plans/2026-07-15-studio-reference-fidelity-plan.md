# Studio Reference Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `/studio` into high-fidelity alignment with the approved detailed production-board reference without inventing product data.

**Architecture:** Keep `StudioShell` as the compatibility owner and refine the extracted episode-workspace components. Use existing workflow metadata, snapshot evidence, `apiClient.getNovel`, and model-contract API; no backend or persistence changes.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Radix UI, Lucide React, Playwright.

## Global Constraints

- Preserve production/test safety gates, confirmation behavior, APIs, billing behavior, and stored workflow state.
- `studio-shell.tsx` must not grow; new or modified feature components remain under 200 lines and functions under 80 lines.
- Missing cover, cost, owner, model, or duration data must be labelled as unavailable, never fabricated.
- No new backend route, dependency, model call, or generated production asset.

---

### Task 1: Lock the detailed visual contract

**Files:**
- Modify: `frontend/e2e/studio-smart-console.spec.ts`

**Interfaces:**
- Consumes: the current smart-console snapshot and workflow API stubs.
- Produces: assertions for `studio-series-summary`, `studio-episode-board-header`, `studio-shot-generation-summary`, `studio-cost-summary`, and dual command actions.

- [ ] Add a novel-detail stub with `cover_url: null`, chapter totals, and updated time.
- [ ] Add workflow progress/job fields and shot quality evidence to the snapshot stub.
- [ ] Assert the detailed summary, episode progress, board header metrics, cost unavailable state, and compact mode control.
- [ ] Run the single test and confirm RED because the detailed regions do not exist.

### Task 2: Implement the high-fidelity series and episode frame

**Files:**
- Modify: `frontend/src/lib/studio-types.ts`
- Modify: `frontend/src/components/studio/studio-workspace-header.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`

**Interfaces:**
- Consumes: `StudioWorkflowOption` progress/job metadata, `StudioSnapshot`, and `apiClient.getNovel`.
- Produces: truthful series summary and episode cards with stable test ids and existing workflow-switch callbacks.

- [ ] Extend only the optional workflow fields already returned by `/workflow/`.
- [ ] Fetch novel detail inside the header and render cover/missing-cover state, chapter totals, update time, and readiness.
- [ ] Replace the generic episode buttons with progress/status cards plus new-episode and series-management actions.
- [ ] Remove the large top mode banner from `StudioShell` without growing the legacy hotspot.
- [ ] Run the focused test and confirm the header portion is GREEN.

### Task 3: Implement the dense episode board and evidence rail

**Files:**
- Modify: `frontend/src/components/studio/studio-episode-stage-board.tsx`
- Modify: `frontend/src/components/studio/studio-episode-sidebar.tsx`
- Modify: `frontend/src/components/studio/studio-model-contracts.tsx`
- Modify: `frontend/src/components/studio/studio-command-bar.tsx`
- Modify: `frontend/src/components/studio/studio-episode-workspace.tsx`

**Interfaces:**
- Consumes: snapshot shots, jobs, production, assets, consistency, guidance, metadata, mode, and guided-action callbacks.
- Produces: detailed four-column board, cost/model/failure rail, compact mode switch, secondary action, and primary action.

- [ ] Render the episode board header and truthful shot totals, completed/pending evidence, and duration.
- [ ] Render three compact evidence cards per lane, including video progress and real shot-warning rows.
- [ ] Render a right-rail cost unavailable state, aggregate model readiness, and repairable blockers/failed jobs.
- [ ] Move mode switching and secondary recovery/navigation into the bottom command bar.
- [ ] Run the focused and multi-episode tests and confirm GREEN.

### Task 4: Browser and design QA

**Files:**
- Modify: `design-qa.md`

**Interfaces:**
- Consumes: the supplied screenshot and live `/studio` route for the real four-chapter workflow.
- Produces: desktop/mobile evidence, comparison history, and final `passed` or `blocked` result.

- [ ] Validate exactly four same-novel episode cards, the series menu, compact mode switch, secondary action, and primary action from the frontend.
- [ ] Capture desktop 1440 x 1024 and mobile 390 x 844; confirm no visible fetch error or horizontal overflow.
- [ ] Normalize source and implementation into one side-by-side image; fix all P0/P1/P2 findings and repeat.
- [ ] Run `npm run typecheck`, the two focused Playwright tests, and `NEXT_DIST_DIR=.next-verify npm run build`.
- [ ] Record final evidence in `design-qa.md`.
