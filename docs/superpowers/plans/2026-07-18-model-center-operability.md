# Model Center Operability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Model Center catalog, validation, connection testing, and settings navigation genuinely operable from the authenticated frontend.

**Architecture:** Keep the existing versioned Model Center API and catalog projection. Add only the missing certification execution state transition and selection filters, then wire catalog and connection actions to those stable contracts. Provider-paid connection checks remain explicit user actions; contract validation remains local and free.

**Tech Stack:** FastAPI, async SQLAlchemy, Next.js 14, React 18, TypeScript, Playwright.

## Global Constraints

- Preserve existing catalog data, credentials, published versions, bindings, and legacy compatibility projections.
- Never return raw credentials or provider request/response bodies.
- Do not claim unsupported update, disable, or rollback routes are available.
- A contract certification performs local driver-contract validation only.
- A connection certification may call a provider and must be visibly identified as a real connection request.
- Every behavior change starts with a failing isolated API or browser test.

---

### Task 1: Certification selection and completion

**Files:**
- Modify: `backend/app/features/model_config/api/certifications.py`
- Modify: `backend/app/features/model_config/api/service.py`
- Modify: `backend/app/features/model_config/management.py`
- Modify: `backend/app/features/model_config/certification_repository.py`
- Create: `backend/app/features/model_config/certification_execution.py`
- Test: `backend/tests/test_model_center_api.py`

**Interfaces:**
- Consumes: published `ModelProfileVersion`, user-owned `ModelConnection`, installed model driver.
- Produces: filtered certification candidates and completed `success` or `failed` runs with sanitized evidence.

- [x] Add failing API tests proving draft connections are selectable only for `level=connection`, exact profile/connection filters work, local contract certification completes, and connection failures are sanitized.
- [x] Run the focused tests and confirm the expected failures.
- [x] Implement exact candidate filters and a focused certification executor.
- [x] Persist completion status, timestamps, costs, and sanitized evidence without exposing secrets.
- [x] Run the focused and full Model Center backend tests.

### Task 2: Catalog details and actionable navigation

**Files:**
- Create: `frontend/src/features/model-center/components/model-catalog-detail.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-catalog-panel.tsx`
- Modify: `frontend/src/features/model-center/navigation.ts`
- Modify: `frontend/src/features/model-center/components/test-lab.tsx`
- Modify: `frontend/src/features/model-center/api.ts`
- Modify: `frontend/src/features/model-center/hooks/use-certification-history.ts`
- Test: `frontend/e2e/model-center-config.spec.ts`

**Interfaces:**
- Consumes: `ModelCatalogView`, filtered certification candidates, existing contract-validation endpoint.
- Produces: a real “查看与操作” dialog, local validation feedback, and preselected test/settings routes.

- [x] Add a failing Playwright test that clicks a catalog row action and validates the model, enters a preselected test flow, and reaches connection/binding settings.
- [x] Run the test and confirm it fails because “查看” is not interactive.
- [x] Implement the detail dialog and preserve return/capability/model selection query parameters.
- [x] Show explicit compatibility guidance for rows that cannot be version-validated.
- [x] Run the focused Playwright test and TypeScript typecheck.

### Task 3: Connection test deadlock removal

**Files:**
- Modify: `frontend/src/features/model-center/components/model-center-connections-panel.tsx`
- Test: `frontend/e2e/model-center-config.spec.ts`

**Interfaces:**
- Consumes: `has_secret`, provider ID, exact certification candidate filters.
- Produces: an enabled test entry for secret-bearing draft connections and a preselected connection-certification screen.

- [x] Add a failing browser test for a draft secret-bearing connection.
- [x] Confirm the current button is disabled.
- [x] Gate testing on `has_secret`, not verified status, and route with exact connection selection.
- [x] Display a clear message when credentials are missing.
- [x] Re-run focused browser tests.

### Task 4: Integrated verification

**Files:**
- Verify only; no production changes unless a failing acceptance check exposes a root cause.

- [x] Run isolated Model Center backend API tests.
- [x] Run Model Center Playwright tests.
- [x] Run frontend typecheck and production build.
- [x] Restart backend/frontend if required by runtime changes.
- [x] From the signed-in frontend, click catalog “查看与操作”, run free contract validation, verify preselected test/settings links, and confirm connection-test availability without submitting a paid provider request.
- [x] Inspect browser console and network errors, then report exact evidence and any intentionally unavailable operations.
