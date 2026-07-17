# Asset Workbench Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add clear, accessible client-side pagination to the asset management workbench without changing the existing asset API or batch-selection behavior.

**Architecture:** Keep filtering and collection ownership in `AssetWorkbench`, derive a safe current page from the filtered result, and pass only the active slice to `AssetTable`. Put the visual controls in a focused `AssetPagination` feature component so the 2,245-line route page does not grow.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Playwright.

## Global Constraints

- Preserve the existing `/api/v1/assets` response contract and loading behavior.
- Reset to page 1 after search, collection, or page-size changes.
- Preserve selected asset IDs across page changes.
- Keep the asset route page line count unchanged.
- Verify desktop interaction and mobile horizontal overflow.

---

### Task 1: Pagination browser contract

**Files:**
- Modify: `frontend/e2e/assets-workbench-redesign.spec.ts`

**Interfaces:**
- Consumes: the current `/assets` route and mocked `GET /api/v1/assets` response.
- Produces: a regression test for 12-item pages, next-page navigation, search reset, and selectable page size.

- [x] **Step 1: Write the failing test**

Add 26 deterministic assets and assert that the first page shows assets 01-12, the next page shows 13-24, a search from page 2 resets the range to 1-1, and changing the page size to 24 shows 24 rows.

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/assets-workbench-redesign.spec.ts --project=chromium --workers=1`

Expected: FAIL because `asset-pagination`, `下一页`, and `每页资产数量` do not exist.

### Task 2: Focused pagination component and workbench state

**Files:**
- Create: `frontend/src/features/assets/components/asset-pagination.tsx`
- Modify: `frontend/src/features/assets/components/asset-workbench.tsx`

**Interfaces:**
- Consumes: `currentPage`, `pageSize`, `totalItems`, `onPageChange`, and `onPageSizeChange`.
- Produces: `AssetPagination` plus a safe `pagedAssets` slice passed to `AssetTable`.

- [x] **Step 1: Implement the minimum pagination UI**

Render `显示 {start}-{end} / {total}` with a 12/24/48 selector and accessible previous/next buttons. Clamp navigation to the valid page range.

- [x] **Step 2: Wire filtered state to pagination**

Maintain `currentPage` and `pageSize` in `AssetWorkbench`; reset the page for collection/search/page-size changes, slice `filteredAssets`, and derive the inspected asset from that slice.

- [x] **Step 3: Run targeted verification**

Run: `cd frontend && npx playwright test e2e/assets-workbench-redesign.spec.ts --project=chromium --workers=1`

Expected: all asset workbench tests PASS.

### Task 3: Frontend and rendered regression checks

**Files:**
- Verify only; no additional production files expected.

**Interfaces:**
- Consumes: the completed pagination behavior.
- Produces: type/build/browser evidence and a screenshot outside the repository.

- [x] **Step 1: Run static verification**

Run: `cd frontend && npm run typecheck && NEXT_DIST_DIR=.next-verify npm run build`

Expected: both commands exit 0.

- [x] **Step 2: Run rendered checks**

Open `/assets`, exercise next page and search reset, verify no relevant console errors or framework overlay, and capture desktop plus mobile screenshots under `/tmp`.
