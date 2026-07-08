# Real Cloud Frontdoor Acceptance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** unblock front-end scoped entity re-extraction, then run a low-cost real-cloud 4-chapter acceptance flow from the browser as user `sunqy`.

**Architecture:** Keep the code change narrow: `/entities` reads URL scope filters and passes them to existing API client methods. Real-cloud validation must be initiated from browser UI and documented with screenshots and artifact paths.

**Tech Stack:** Next.js 14, Playwright, FastAPI, MiniMax TTS, Volcano Seedance/SD1.5.

---

### Task 1: Entity Review Scope Filter

**Files:**
- Modify: `frontend/src/app/entities/page.tsx`
- Test: `frontend/e2e/entities-scope-filter.spec.ts`

- [ ] **Step 1: Write failing E2E test**

Create `frontend/e2e/entities-scope-filter.spec.ts` to open `/entities?novel_id=novel-001`, intercept `/api/v1/story-bibles/entities` and `/api/v1/story-bibles/entities/stats`, and assert both requests include `novel_id=novel-001`.

- [ ] **Step 2: Verify test fails**

Run: `cd frontend && npx playwright test e2e/entities-scope-filter.spec.ts --project=chromium`
Expected before implementation: FAIL because current page omits `novel_id` from API requests.

- [ ] **Step 3: Implement minimal page fix**

Read `novel_id`, `chapter_id`, and `script_id` via `useSearchParams()`, pass them into `apiClient.getStoryEntities()` and `apiClient.getStoryEntityStats()`, and display a small active-filter badge.

- [ ] **Step 4: Verify fix**

Run: `cd frontend && npm run typecheck`
Run: `cd frontend && npx playwright test e2e/entities-scope-filter.spec.ts --project=chromium`
Expected: both commands exit 0.

### Task 2: Front-End Entity Re-Extraction Evidence

**Files:**
- No production file expected.
- Artifacts: `output/real-cloud-acceptance-20260707/*.png`

- [ ] **Step 1: Open scoped entity page from browser**

Open `/entities?novel_id=d9657527-da8a-43c9-9fe5-43cf02812f21` as `sunqy` with localStorage token.

- [ ] **Step 2: Trigger scoped re-extraction from UI**

Select current-novel entities, click `重抽模式`, enter `delete_then_extract`, confirm cleanup, decline asset creation for this cleanup step.

- [ ] **Step 3: Screenshot and verify entity quality**

Capture before/after screenshots and verify core entities include `林岚`, `阿绒`, `黎夏`, `云灯集市`, `雨巷`, `旧伞铺`, `星桥`, `黎明邮局`, `铜铃星灯`, `星形纽扣`, `信封`; verify obvious action-noise names are absent.

### Task 3: Browser-Initiated Real Cloud Shot Acceptance

**Files:**
- No production file expected unless a blocking bug is reproduced and fixed with tests first.
- Artifacts: `output/real-cloud-acceptance-20260707/*.png` and generated media under backend static paths returned by the UI/API.

- [ ] **Step 1: From browser, open producer for each chapter**

Use `/producer?novel_id=<novel>&chapter_id=<chapter>` and keep screenshots of strategy/workflow/shot states.

- [ ] **Step 2: Select one key shot per chapter**

Prefer one 4-second shot when available; otherwise document existing duration and do not manually alter backend records.

- [ ] **Step 3: Trigger real image, TTS, video, synthesis from UI**

Use configured `sunqy` models and `sunqinyue-default`/MiniMax voice where UI exposes it. Do not fake media outputs.

- [ ] **Step 4: Inspect outputs**

Check role/scene/prop consistency, subtitle timing, voice alignment, and video availability. Record pass/fail/blocked with paths.
