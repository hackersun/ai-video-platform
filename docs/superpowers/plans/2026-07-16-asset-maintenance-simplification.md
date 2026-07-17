# Asset Maintenance Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the asset workbench, AI production wizard, and asset editor share production-visible entities while separating single-asset archival from explicit production-object deactivation.

**Architecture:** Add a focused asset-maintenance backend feature that reuses the existing StoryEntity lifecycle service and owns the transactional deactivate use case. Add a frontend asset-maintenance API/types layer plus focused wizard and editor components; keep the legacy route page as compatibility orchestration and reduce its line count.

**Tech Stack:** FastAPI, async SQLAlchemy, Pydantic, Next.js 14, React 18, TypeScript, Tailwind CSS, Playwright, pytest.

## Global Constraints

- Preserve current asset archive, generic StoryEntity list/delete, stored data, route query parameters, and provider safety gates.
- Do not add logic to the 2017-line `assets.py`, 3495-line `story_bible.py`, or 2245-line `assets/page.tsx`; route-page integration must produce negative net line growth.
- `story_entity_lifecycle.py` remains the single owner of production visibility.
- No database schema change and no destructive mutation of sunqy production objects during acceptance.
- Every behavior change begins with a failing focused test and is verified from the frontend.

---

### Task 1: Production-object maintenance backend contract

**Files:**
- Create: `backend/app/features/assets/__init__.py`
- Create: `backend/app/features/assets/schemas.py`
- Create: `backend/app/features/assets/application.py`
- Create: `backend/app/features/assets/api.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_asset_entity_maintenance.py`

**Interfaces:**
- `list_asset_entity_options(db, user_id, novel_id, entity_type, limit)` returns only `query_story_entities_for_assets` results with active-asset counts.
- `deactivate_asset_entity(db, user_id, entity_id, reason)` sets lifecycle `archived`, soft-archives active `Asset` rows, and returns the affected count.
- HTTP routes are `GET /asset-maintenance/entity-options` and `POST /asset-maintenance/entities/{entity_id}/deactivate`.

- [ ] **Step 1: Write failing lifecycle integration tests**

Create legacy-active, approved, candidate, rejected and archived entities plus active assets. Assert option listing includes only legacy-active and approved entities, includes the correct `active_asset_count`, and excludes the other lifecycle states.

- [ ] **Step 2: Run RED**

Run: `cd backend && pytest -q tests/test_asset_entity_maintenance.py`

Expected: FAIL because `app.features.assets.application` and the API routes do not exist.

- [ ] **Step 3: Implement the minimum application and API**

Use `query_story_entities_for_assets`, `get_entity_review_status`, `set_entity_review_status(ARCHIVED)`, and one SQLAlchemy update over active assets. Return typed option and deactivation responses; make repeated deactivation idempotent.

- [ ] **Step 4: Run GREEN and lifecycle regression**

Run: `cd backend && pytest -q tests/test_asset_entity_maintenance.py tests/test_story_entity_lifecycle.py`

Expected: all tests PASS.

### Task 2: Shared frontend entity source and synchronization

**Files:**
- Create: `frontend/src/features/assets/types.ts`
- Create: `frontend/src/features/assets/api.ts`
- Modify: `frontend/src/app/assets/page.tsx`
- Test: `frontend/e2e/assets-maintenance-linkage.spec.ts`

**Interfaces:**
- `listAssetEntityOptions(params)` calls the new asset-maintenance endpoint.
- `deactivateAssetEntity(entityId, reason)` calls the deactivation endpoint.
- `AssetEntityOption` exposes id, name, entity_type, description, lifecycle_status and active_asset_count.

- [ ] **Step 1: Write the failing browser linkage test**

Mock entity options with one active and one archived character. Assert only the active character is selectable. Archive one asset and assert the character remains selectable. Deactivate the character and assert the UI refreshes both assets and entity options, clears the selection, and reports the number of archived assets.

- [ ] **Step 2: Run RED**

Run: `cd frontend && npx playwright test e2e/assets-maintenance-linkage.spec.ts --project=chromium --workers=1`

Expected: FAIL because the page still calls generic StoryEntity listing and has no deactivate action.

- [ ] **Step 3: Implement the shared asset entity API and state refresh**

Replace only the asset page's entity-loading call with `listAssetEntityOptions`. After deactivation, call the existing asset reload and the entity-options reload, then clear invalid wizard/form entity IDs. Keep single-asset archive behavior unchanged.

- [ ] **Step 4: Run GREEN**

Run the focused Playwright spec and confirm all linkage assertions pass.

### Task 3: Compact AI asset production wizard

**Files:**
- Create: `frontend/src/features/assets/components/asset-production-wizard.tsx`
- Create: `frontend/src/features/assets/components/asset-required-view-grid.tsx`
- Modify: `frontend/src/app/assets/page.tsx`
- Test: `frontend/e2e/assets-maintenance-linkage.spec.ts`

**Interfaces:**
- `AssetProductionWizard` receives the active preset, production entity options, selected values, asset view state, and existing generation/retry/edit callbacks.
- The default surface exposes one primary `生成 N 个缺失视图` action and a collapsed `生成设置` control.

- [ ] **Step 1: Add failing UX assertions**

Assert the wizard is visible as `补齐资产`, the selected object shows its active asset count, the primary button includes the missing count, and style controls are hidden until `生成设置` is expanded.

- [ ] **Step 2: Run RED**

Run the focused Playwright spec and verify failure against the current large wizard.

- [ ] **Step 3: Extract and simplify the wizard**

Move rendering into the two focused feature components, preserve deep-link selection and current generate/retry/edit callbacks, and remove the default style-example gallery from the primary flow.

- [ ] **Step 4: Run GREEN and existing asset E2E**

Run: `cd frontend && npx playwright test e2e/assets-maintenance-linkage.spec.ts e2e/assets-low-barrier-management.spec.ts e2e/assets-workbench-redesign.spec.ts --project=chromium --workers=1`

Expected: all tests PASS.

### Task 4: Workbench-consistent asset editor drawer

**Files:**
- Create: `frontend/src/features/assets/components/asset-editor-drawer.tsx`
- Create: `frontend/src/features/assets/components/asset-entity-deactivate-dialog.tsx`
- Modify: `frontend/src/features/assets/components/asset-inspector.tsx`
- Modify: `frontend/src/features/assets/components/asset-workbench.tsx`
- Modify: `frontend/src/app/assets/page.tsx`
- Test: `frontend/e2e/assets-maintenance-linkage.spec.ts`

**Interfaces:**
- `AssetEditorDrawer` is a controlled `role=dialog` side sheet; it receives form values/options and existing upload/save/regenerate handlers.
- `AssetEntityDeactivateDialog` displays entity name and active asset count before calling the deactivate callback.
- Inspector labels remain explicit: `归档当前资产` and `停用制片对象`.

- [ ] **Step 1: Add failing editor and destructive-action assertions**

Assert edit opens a right-side dialog, technical fields are collapsed initially, Escape/Cancel returns to the unchanged workbench, and the two destructive actions have distinct labels and confirmations.

- [ ] **Step 2: Run RED**

Run the focused Playwright spec and verify it fails because the editor is currently an in-page card.

- [ ] **Step 3: Implement drawer and deactivation confirmation**

Extract the existing form into a controlled fixed drawer, show scope-dependent selectors progressively, keep technical JSON fields collapsed by default, and wire the explicit object deactivation dialog through the workbench inspector.

- [ ] **Step 4: Run GREEN and hotspot ratchet**

Run the asset E2E set, then `wc -l frontend/src/app/assets/page.tsx`.

Expected: tests PASS and the route page contains fewer than 2245 lines.

### Task 5: Static, API, and real frontend verification

**Files:**
- Verify only; screenshots go under `/tmp/asset-maintenance-final/`.

**Interfaces:**
- Produces fresh backend, type/build, browser, accessibility, and design-fidelity evidence.

- [ ] **Step 1: Run backend verification**

Run: `cd backend && pytest -q tests/test_asset_entity_maintenance.py tests/test_story_entity_lifecycle.py`

- [ ] **Step 2: Run frontend verification**

Run: `cd frontend && npm run typecheck && NEXT_DIST_DIR=.next-asset-maintenance npm run build`

- [ ] **Step 3: Run the frontend workflow**

Open the sunqy `/assets` workbench, verify production options are lifecycle-filtered, edit opens/closes without losing context, and confirm dialogs explain both operations. Use isolated mocked data for the destructive deactivation assertion; do not mutate real sunqy entities.

- [ ] **Step 4: Perform desktop and mobile visual QA**

Capture desktop and 390px mobile states for workbench, compact wizard, editor drawer, and deactivate confirmation. Inspect them with `view_image` against the approved existing workbench system, record at least five fidelity comparisons, and fix all material issues before completion.
