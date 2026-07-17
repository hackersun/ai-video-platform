# Asset Workbench Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the asset page's first-screen maintenance experience with the selected three-column production workbench while preserving existing asset workflows.

**Architecture:** Keep data fetching and mutations in the compatibility page. Move the new presentation into focused `features/assets` components that consume the existing asset data and callbacks. Keep the AI view wizard and edit form below the workbench so deep links and existing workflows remain compatible.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Lucide React, Playwright.

## Global Constraints

- Preserve asset APIs, stored data, query parameters and safety confirmations.
- `frontend/src/app/assets/page.tsx` must have negative net line growth.
- New feature components must remain below 200 lines.
- No new provider calls, backend changes, packages or static placeholder images.
- Every behavior change begins with a failing Playwright assertion.

---

### Task 1: Workbench contract and RED browser test

**Files:**
- Create: `frontend/e2e/assets-workbench-redesign.spec.ts`

**Interfaces:**
- Produces the visible contracts `asset-workbench`, `asset-collection-*`, `asset-table-row`, `asset-inspector`, and `asset-bulk-bar`.

- [ ] **Step 1: Write a deterministic mocked test**

The fixture returns one locked character asset, one failed prop asset and one draft scene asset. Assertions require:

```ts
await expect(page.getByRole('heading', { name: '资产工作台' })).toBeVisible();
await page.getByTestId('asset-collection-failed').click();
await expect(page.getByTestId('asset-table-row')).toHaveCount(1);
await page.getByTestId('asset-table-row').click();
await expect(page.getByTestId('asset-inspector')).toContainText('青铜铃');
await page.getByLabel('选择青铜铃').check();
await expect(page.getByTestId('asset-bulk-bar')).toContainText('已选择 1 项');
```

- [ ] **Step 2: Run RED**

Run:

```bash
cd frontend
npx playwright test e2e/assets-workbench-redesign.spec.ts --project=chromium --workers=1
```

Expected: fail because `asset-workbench` and the new heading do not exist.

---

### Task 2: Shared workbench types and pure collection rules

**Files:**
- Create: `frontend/src/features/assets/types.ts`
- Create: `frontend/src/features/assets/asset-collections.ts`
- Test: `frontend/e2e/assets-workbench-redesign.spec.ts`

**Interfaces:**
- `AssetWorkbenchItem` contains the existing asset fields used by presentation.
- `filterAssetsByCollection(assets, collection)` returns the rows for `all/attention/failed/draft/locked/character/scene/prop`.

- [ ] **Step 1: Add failing collection assertions**

Clicking failed must leave only the failed prop; clicking locked must leave only the locked character.

- [ ] **Step 2: Implement minimal collection rules**

```ts
export function filterAssetsByCollection(items: AssetWorkbenchItem[], key: AssetCollectionKey) {
  if (key === 'failed') return items.filter((item) => Boolean(item.error_message) || item.status === 'failed');
  if (key === 'draft') return items.filter((item) => !item.is_locked || !item.is_final);
  if (key === 'locked') return items.filter((item) => item.is_locked);
  if (['character', 'scene', 'prop'].includes(key)) return items.filter((item) => item.category === key);
  if (key === 'attention') return items.filter((item) => item.status === 'failed' || !item.is_locked || !item.is_final);
  return items;
}
```

- [ ] **Step 3: Run GREEN**

Run the focused Playwright test and confirm the collection assertions pass after Task 3 renders the controls.

---

### Task 3: Three-column workbench presentation

**Files:**
- Create: `frontend/src/features/assets/components/asset-workbench-header.tsx`
- Create: `frontend/src/features/assets/components/asset-collection-sidebar.tsx`
- Create: `frontend/src/features/assets/components/asset-table.tsx`
- Create: `frontend/src/features/assets/components/asset-inspector.tsx`
- Create: `frontend/src/features/assets/components/asset-bulk-bar.tsx`
- Create: `frontend/src/features/assets/components/asset-workbench.tsx`

**Interfaces:**
- `AssetWorkbench` receives assets, novels, current filters, selected IDs and the existing mutation callbacks.
- Row checkboxes call `onToggleSelect(id)`; row clicks call `onInspect(asset)`.
- Inspector calls existing preview/edit/retry/lock/version/archive callbacks.

- [ ] **Step 1: Implement header and sidebar**

Render selected design hierarchy with `资产工作台`, `补齐缺失资产`, a context row and smart collections.

- [ ] **Step 2: Implement table**

Use a lightweight grouped surface with row separators, 64px thumbnail, status badge, reference count and one row action. Keep `data-testid="asset-card"` on rows for compatibility.

- [ ] **Step 3: Implement inspector and batch bar**

Inspector shows actual media URL, version, scope, entity, consistency/error evidence and three primary actions. Batch bar exposes existing lock, unlock, tag, scope, rebuild and archive callbacks.

- [ ] **Step 4: Keep responsive behavior**

At widths below `xl`, hide the left sidebar behind horizontally scrollable collection buttons and move the inspector below the table. The page itself must not overflow horizontally.

---

### Task 4: Integrate without growing the legacy hotspot

**Files:**
- Modify: `frontend/src/app/assets/page.tsx`

**Interfaces:**
- The page passes its existing state and handlers into `AssetWorkbench`.
- The existing AI wizard and create/edit form remain below the first-screen workbench.

- [ ] **Step 1: Replace stats/filter/card-list ownership**

Remove the six-stat strip and legacy asset card list from the page return. Render `AssetWorkbench` in their place.

- [ ] **Step 2: Preserve compatibility selectors**

Keep `aria-label="资产库"` on the visible workbench heading for legacy route tests only if required; prefer updating focused tests to visible copy when no external contract depends on it.

- [ ] **Step 3: Verify hotspot ratchet**

Run:

```bash
wc -l frontend/src/app/assets/page.tsx
```

Expected: fewer than 2645 lines.

- [ ] **Step 4: Run asset regression tests**

```bash
cd frontend
npx playwright test e2e/assets-workbench-redesign.spec.ts e2e/assets-low-barrier-management.spec.ts --project=chromium --workers=1
```

Expected: all pass; if old assertions require the previous card layout, update only selectors whose visible control moved.

---

### Task 5: Build, browser interactions and Design QA

**Files:**
- Create: `design-qa.md`

- [ ] **Step 1: Run static verification**

```bash
cd frontend
npm run typecheck
NEXT_DIST_DIR=.next-assets-workbench npm run build
```

- [ ] **Step 2: Verify from the frontend**

Open `http://localhost:3000/assets` in the connected browser and test:

1. page identity and no framework overlay;
2. failed collection changes row count;
3. row selection changes inspector;
4. checkbox displays bulk bar;
5. search changes the displayed set;
6. console contains no relevant errors.

- [ ] **Step 3: Capture desktop and mobile**

Capture 1440 × 1024 and 390 × 844 screenshots with realistic mocked or isolated data.

- [ ] **Step 4: Run Design QA**

Combine the selected source image and implementation screenshot in one comparison image. Record typography, spacing, colors, images and copy findings in `design-qa.md`. Fix every P0/P1/P2 issue and repeat until the file ends with:

```text
final result: passed
```
