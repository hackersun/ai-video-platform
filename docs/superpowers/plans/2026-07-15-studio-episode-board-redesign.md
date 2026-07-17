# Studio Episode Board Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/studio` around the selected episode-first production-board concept so producers can see the active episode, stage state, blockers, operational summary, and next action without scanning the full expert workspace.

**Architecture:** Keep `StudioShell` as the existing data/action compatibility owner and extract the new visual composition into focused Studio components. All status, counts, actions, routing, model readiness, and failures must be derived from the current `StudioSnapshot`, workflow list, and existing APIs; expert panels remain available below the primary board.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Radix UI, Lucide React, Playwright.

## Global Constraints

- Preserve backend APIs, billing behavior, production/test safety gates, stored workflow state, and provider/model contracts.
- Do not grow the 800+ line `studio-shell.tsx`; extract the primary board and remove redundant shell markup/imports.
- Keep each new feature component below 200 lines and each function below 80 lines.
- Reuse the current dark product theme, Radix primitives, Lucide icons, and existing Studio action handlers.
- Do not display invented cost values or model readiness; show only observable snapshot/API evidence.
- No new routes, dependencies, backend calls, or static fictional media assets.

## Execution Contract

**Intent Lock:** Make the Studio home screen episode-first and action-first while keeping all existing production capabilities reachable.

**Out of Scope:** Backend changes, provider changes, pricing calculations, new orchestration behavior, authentication, persistence migrations, and redesign of expert sub-pages.

**Acceptance Criteria:**

- The active series and episode are immediately visible.
- Episode/workflow switching remains functional and updates the route.
- Four production lanes render: `设定与资产`, `分镜与配音`, `镜头生成`, `复审与成片`.
- A right-side rail exposes episode summary, model contract readiness, and failed/blocking tasks.
- The primary CTA is visually isolated as `下一步：{action}` and retains confirmation/safe-retry behavior.
- Existing stage flow, action progress, advanced workspace tabs, and expert entry points remain available.
- Desktop and mobile rendered checks show no clipping, overlay, or relevant console error.

**Verification Commands:**

```bash
npm --prefix frontend run typecheck
cd frontend && PLAYWRIGHT_PORT=3116 PLAYWRIGHT_DIST_DIR=.next-studio-episode-board npx playwright test e2e/studio-smart-console.spec.ts e2e/series-studio-multi-episode.spec.ts --project=chromium --workers=1
NEXT_DIST_DIR=.next-studio-episode-board-build npm --prefix frontend run build
```

---

### Task 1: Lock the selected board contract with a failing E2E test

**Files:**
- Modify: `frontend/e2e/studio-smart-console.spec.ts`

**Interfaces:**
- Consumes: existing `smartSnapshot` and `/studio?workflow_id=wf-smart-console` route stubs.
- Produces: stable `data-testid` and accessible-text expectations for the selected layout.

- [x] **Step 1: Add assertions for the episode board**

Assert `studio-episode-workspace`, the four lane headings, `本集概览`, `模型就绪度`, `失败任务`, and `下一步：生产锁定`.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd frontend && PLAYWRIGHT_PORT=3116 PLAYWRIGHT_DIST_DIR=.next-studio-episode-board npx playwright test e2e/studio-smart-console.spec.ts --project=chromium --workers=1
```

Expected: FAIL because `studio-episode-workspace` and the new layout labels do not exist.

### Task 2: Extract and implement the episode-first primary workspace

**Files:**
- Create: `frontend/src/components/studio/studio-workspace-header.tsx`
- Create: `frontend/src/components/studio/studio-episode-stage-board.tsx`
- Create: `frontend/src/components/studio/studio-episode-sidebar.tsx`
- Create: `frontend/src/components/studio/studio-episode-workspace.tsx`
- Modify: `frontend/src/components/studio/studio-model-contracts.tsx`
- Modify: `frontend/src/components/studio/studio-command-bar.tsx`
- Modify: `frontend/src/components/studio/studio-shell.tsx`

**Interfaces:**
- Consumes: `StudioSnapshot`, `StudioWorkflowOption[]`, `StudioRunMode`, existing `onWorkflowChange`, and existing guided-action handler.
- Produces: `StudioEpisodeWorkspace` with `data-testid="studio-episode-workspace"`; no new API contract.

- [x] **Step 1: Build the header and episode switcher**

Render truthful series/episode metadata, overall progress, a compact workflow select, and episode buttons derived from workflows/series plan. Active episode selection calls the existing workflow-change handler.

- [x] **Step 2: Build four derived production lanes**

Group current guidance and snapshot evidence into the four selected lanes. Each lane shows status, evidence counts, and a direct existing destination where available.

- [x] **Step 3: Build the evidence sidebar**

Show task counts, strategy, readiness, model contracts, and blocking/failed evidence. Do not synthesize currency values.

- [x] **Step 4: Recompose `StudioShell` without growing the hotspot**

Replace the current command/stage/model/overview stack with `StudioEpisodeWorkspace`; retain loading, errors, mode safety, action progress, confirmation dialog, and all `StudioExpertSections` content.

- [x] **Step 5: Run the focused test and verify GREEN**

Run the Task 1 command. Expected: PASS.

### Task 3: Verify regressions, responsiveness, and design fidelity

**Files:**
- Modify: `design-qa.md`

**Interfaces:**
- Consumes: selected reference image `exec-243b7cc9-5996-47fd-bea0-4fd2c2c03313.png` and the browser-rendered `/studio` implementation.
- Produces: fresh test/build evidence and `design-qa.md` with `final result: passed` or `blocked`.

- [x] **Step 1: Run typecheck and focused multi-episode regressions**

Run the verification commands above and fix only failures caused by this batch.

- [x] **Step 2: Validate from the real frontend**

Open `/studio?workflow_id=wf-smart-console` in the in-app Browser with a controlled stubbed session, verify page identity, meaningful DOM, console health, the primary CTA confirmation, episode switcher, desktop viewport, and one mobile viewport.

- [x] **Step 3: Run blocking design QA**

Compare the selected 1440x1024 design and a same-state implementation screenshot in one combined visual input. Fix all P0/P1/P2 findings and record comparison history in `design-qa.md`.

- [x] **Step 4: Run the production build**

Run the build verification command. Expected: exit 0.
