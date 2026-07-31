# Shot Reference Review Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Studio → 镜头参考检查 show the real reference image and bound character/scene/prop references, explain the six quality dimensions in plain Chinese, and provide an obvious repair-and-return path.

**Architecture:** Keep the existing workflow and repair APIs stable. Add a focused backend projection module for review-safe reference fields, extract the oversized page's shot card into a focused component, and keep raw diagnostic evidence collapsed behind an optional details control.

**Tech Stack:** FastAPI, SQLAlchemy, Next.js 14, React 18, TypeScript, Tailwind, Playwright, pytest.

## Global Constraints

- Preserve stored data, provider calls, workflow state, and existing regeneration/quality-repair contracts.
- Do not grow `backend/app/api/v1/endpoints/workflow.py` or the existing 500+ line route page.
- Use the stable local `Shot.image_url` for browser preview before any short-lived provider URL.
- Keep technical evidence available but hidden by default; primary copy must be understandable Chinese.
- Every behavior change starts with a failing targeted test.

---

### Task 1: Reference review API contract

**Files:**
- Create: `backend/app/services/shot_review_projection.py`
- Modify: `backend/app/api/v1/endpoints/workflow.py`
- Test: `backend/tests/test_shot_regeneration.py`

**Interfaces:**
- Produces: `shot_reference_review_fields(shot, latest_video, video_extra, fallback_character_names) -> dict[str, Any]`
- Response fields: `reference_image_url`, `reference_image_status`, `reference_asset_id`, `reference_entities`

- [x] Add a failing API assertion that a shot with an image and bound references returns the four review fields.
- [x] Run `cd backend && pytest -q tests/test_shot_regeneration.py::test_shot_review_aggregates_latest_evidence` and confirm the new assertion fails.
- [x] Implement the projection helper and merge its result into `_shot_review_item` without growing the legacy endpoint file.
- [x] Re-run the targeted backend test and confirm it passes.

### Task 2: Understandable shot review UI

**Files:**
- Create: `frontend/src/components/studio/shot-review-card.tsx`
- Modify: `frontend/src/app/studio/shot-review/page.tsx`
- Modify: `frontend/src/components/studio/quality-gate-panel.tsx`
- Test: `frontend/e2e/studio-shot-review.spec.ts`
- Test: `frontend/e2e/task6-quality-gate.spec.ts`

**Interfaces:**
- Consumes: the Task 1 review fields.
- Produces: a full-width review card with reference/finished media comparison, entity bindings, empty-state actions, and plain-language quality gate summaries.

- [x] Add failing Playwright assertions for a visible reference image, character/scene/prop labels, clear reference-repair action, blocker explanation, and collapsed technical evidence.
- [x] Run the two focused Playwright specs and confirm failures are for missing UI behavior.
- [x] Extract `ShotReviewCard`, replace the three-column result grid with a full-width list, and add the reference-focus guide.
- [x] Replace always-visible JSON with plain-language dimension cards and a collapsed `技术证据` disclosure.
- [x] Re-run both specs and confirm they pass.

### Task 3: Runtime acceptance

**Files:**
- No committed artifact; screenshots are saved under `/tmp/shot-reference-audit/`.

**Interfaces:**
- Verifies: Studio quick action → focused shot review → reference preview → quality repair guidance → return to Studio.

- [x] Run `npm --prefix frontend run typecheck`.
- [x] Run the relevant frontend build command without leaving generated config changes.
- [x] Reload the authenticated sunqy Chrome tab and capture the corrected desktop page.
- [x] Verify page identity, no blank/error overlay, no relevant console errors, a rendered reference image, actionable controls, and the preserved `返回工作台继续处理` link.
