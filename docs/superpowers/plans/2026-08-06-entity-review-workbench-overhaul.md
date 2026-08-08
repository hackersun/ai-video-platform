# Entity Review Workbench Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a paginated, editable and batch-capable novel entity review workbench whose AI actions expose real model execution and whose candidate rebuild preserves approved facts and archives old candidates safely.

**Architecture:** Add a focused `app.features.entity_review` backend feature instead of growing the legacy `story_bible.py` endpoint hotspot. Keep the old story-entity list contract intact, reuse lifecycle approval gates, and split the 682-line route page into a small orchestrator plus controlled feature components and a state hook.

**Tech Stack:** FastAPI, async SQLAlchemy, Pydantic, pytest, Next.js 14, React 18, TypeScript, Tailwind CSS, Playwright.

## Global Constraints

- Preserve approved and legacy-active production entities; never hard-delete the existing candidate set.
- A failed or fallback model run must cause zero candidate-rebuild data changes.
- Existing `GET /story-bibles/entities` and production lifecycle contracts remain compatible.
- `backend/app/api/v1/endpoints/story_bible.py` and other legacy hotspots must not grow.
- The route page must shrink below 300 lines; new React components must stay below 200 lines and new production files below 500 lines.
- Every behavior change begins with a failing test and ends with fresh targeted verification.
- Do not automatically spend on model calls; only the user-triggered analyze, reanalyze and rebuild actions may call a configured model.

---

## File Map

- Create `backend/app/features/entity_review/schemas.py`: paged list, batch-review, reanalysis and rebuild DTOs.
- Create `backend/app/features/entity_review/repository.py`: scoped SQL pagination, filtering, search and ordering.
- Create `backend/app/features/entity_review/service.py`: batch review, preview/apply reanalysis and transactional candidate rebuild.
- Create `backend/app/features/entity_review/api.py`: `/entity-review` HTTP routes only.
- Modify `backend/app/api/v1/router.py`: include the focused router.
- Modify `backend/app/services/entity_quality_service.py`: strict source-aware quality gates and known-noise rules.
- Modify `backend/app/services/entity_review_service.py`: expose validated candidate items and execution evidence needed by preview/rebuild without changing existing response fields.
- Create `backend/tests/test_entity_review_workbench_api.py`: new API contracts and transaction safety.
- Modify `backend/tests/test_entity_extraction_quality.py`: regression corpus for known false positives.
- Create `frontend/src/features/entity-review/types.ts`: shared UI/API types.
- Create `frontend/src/features/entity-review/api.ts`: typed calls composed over `apiClient` methods.
- Create `frontend/src/features/entity-review/use-entity-review-workbench.ts`: URL state, loading, selection and local mutation handling.
- Create `frontend/src/features/entity-review/entity-review-toolbar.tsx`: filters, search and batch actions.
- Create `frontend/src/features/entity-review/entity-review-table.tsx`: selectable table, independent scroll and pagination.
- Create `frontend/src/features/entity-review/entity-review-inspector.tsx`: detail, edit and reanalysis controls.
- Create `frontend/src/features/entity-review/entity-edit-form.tsx`: candidate editor and validation.
- Modify `frontend/src/lib/api-client.ts`: add typed entity-review endpoints only.
- Modify `frontend/src/app/novels/[id]/asset-analysis/page.tsx`: reduce to data-context assembly and feature composition.
- Create `frontend/e2e/entity-review-workbench.spec.ts`: paging, batch, edit, reanalysis and scroll-state browser contract.

---

### Task 1: Strict Candidate Quality Gate

**Files:**
- Modify: `backend/app/services/entity_quality_service.py`
- Test: `backend/tests/test_entity_extraction_quality.py`

**Interfaces:**
- Consumes: `CanonicalEntityCandidate` with `entity_type`, `name`, `evidence`, `source`, confidence and event structure.
- Produces: `score_entity_candidate(candidate) -> EntityQualityResult`; no signature change.

- [ ] **Step 1: Add failing regression cases**

Add parametrized assertions that `赵家`, `林辰深`, `林辰正`, `孙三可`, `朱颜果`, `这日中午`, `气血翻涌` and `眼中闪过一丝厉色` return `reject_noise`, while explicit labels such as `角色：林辰` and structurally complete AI events remain reviewable.

```python
@pytest.mark.parametrize("entity_type,name,evidence", KNOWN_FALSE_POSITIVES)
def test_quality_rejects_live_false_positives(entity_type, name, evidence):
    result = score_entity_candidate(CanonicalEntityCandidate(
        entity_type=entity_type, name=name, evidence=evidence,
        confidence=100, source="deterministic",
    ))
    assert result.auto_decision == REJECT_NOISE
    assert result.score <= 35
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && python3 -m pytest -q tests/test_entity_extraction_quality.py -k 'live_false_positives or deterministic_source'`

Expected: current 88-100 score examples fail.

- [ ] **Step 3: Implement source and semantic gates**

Add focused helpers for character suffix/predicate contamination, character-type boundary terms, and incomplete event fragments. Make any `noise:*`, `low_production_usefulness`, or non-explicit deterministic source ineligible for `auto_approve`; explicit deterministic labels may remain `needs_review` or better when evidence is exact.

- [ ] **Step 4: Verify GREEN and existing quality tests**

Run: `cd backend && python3 -m pytest -q tests/test_entity_extraction_quality.py tests/test_entity_extraction_classification.py`

- [ ] **Step 5: Commit task files only**

```bash
git add backend/app/services/entity_quality_service.py backend/tests/test_entity_extraction_quality.py
git commit -m "fix: reject noisy entity extraction candidates"
```

### Task 2: Server-Side Review Pagination

**Files:**
- Create: `backend/app/features/entity_review/__init__.py`
- Create: `backend/app/features/entity_review/schemas.py`
- Create: `backend/app/features/entity_review/repository.py`
- Create: `backend/app/features/entity_review/api.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/test_entity_review_workbench_api.py`

**Interfaces:**
- Produces: `GET /api/v1/entity-review/novels/{novel_id}/entities` returning `{items,page,page_size,total,total_pages,summary}`.
- Query fields: `page`, `page_size`, `entity_type`, `review_status`, `query`, `sort`.

- [ ] **Step 1: Write failing API tests**

Seed 121 novel-scoped entities across types and lifecycle states. Assert page 1 and page 3 are disjoint, `page_size=50`, search checks name/description/evidence, lifecycle filtering is server-side, and another user's rows never appear.

- [ ] **Step 2: Verify RED**

Run: `cd backend && python3 -m pytest -q tests/test_entity_review_workbench_api.py -k pagination`

Expected: 404 because the router does not exist.

- [ ] **Step 3: Implement repository and schemas**

Use a shared scoped predicate `StoryEntity.user_id == user_id` and `StoryEntity.novel_id == novel_id`. Count before applying offset, order deterministically by `updated_at DESC, id DESC`, and build search with escaped `%`/`_` terms across scalar text columns plus serialized aliases where supported.

- [ ] **Step 4: Register the focused router**

Import `router as entity_review_router` in `app/api/v1/router.py` and include it with `prefix=""` and tag `实体审核`.

- [ ] **Step 5: Verify GREEN**

Run: `cd backend && python3 -m pytest -q tests/test_entity_review_workbench_api.py -k pagination`

- [ ] **Step 6: Commit task files only**

```bash
git add backend/app/features/entity_review backend/app/api/v1/router.py backend/tests/test_entity_review_workbench_api.py
git commit -m "feat: add paged entity review API"
```

### Task 3: Batch Review With Partial Success

**Files:**
- Modify: `backend/app/features/entity_review/schemas.py`
- Create: `backend/app/features/entity_review/service.py`
- Modify: `backend/app/features/entity_review/api.py`
- Test: `backend/tests/test_entity_review_workbench_api.py`

**Interfaces:**
- Produces: `POST /api/v1/entity-review/bulk-review` with `entity_ids: list[str]` (1-100) and `action: approve|reject`.
- Response: `{updated: StoryEntityResponse[], skipped: {id,reason,repair_action}[], summary}`.

- [ ] **Step 1: Write failing partial-success tests**

Assert an evidence-backed candidate is approved while a missing-evidence candidate is skipped; assert bulk reject updates both; assert cross-user and cross-novel IDs are skipped without leaking entity details.

- [ ] **Step 2: Verify RED**

Run: `cd backend && python3 -m pytest -q tests/test_entity_review_workbench_api.py -k bulk_review`

- [ ] **Step 3: Implement using lifecycle services**

Call `approve_review_entity` and `reject_review_entity`; do not copy evidence or duplicate-risk rules. Preserve successful rows when another ID is skipped and return fresh novel summary.

- [ ] **Step 4: Verify GREEN**

Run: `cd backend && python3 -m pytest -q tests/test_entity_review_workbench_api.py -k bulk_review`

- [ ] **Step 5: Commit task files only**

```bash
git add backend/app/features/entity_review backend/tests/test_entity_review_workbench_api.py
git commit -m "feat: support partial entity batch review"
```

### Task 4: Real Reanalysis Preview And Safe Candidate Rebuild

**Files:**
- Modify: `backend/app/services/entity_review_service.py`
- Modify: `backend/app/features/entity_review/schemas.py`
- Modify: `backend/app/features/entity_review/service.py`
- Modify: `backend/app/features/entity_review/api.py`
- Test: `backend/tests/test_entity_review_workbench_api.py`

**Interfaces:**
- Produces: `POST /api/v1/entity-review/entities/{entity_id}/reanalyze` with `mode=preview|apply` and optional `preview_run_id`.
- Produces: `POST /api/v1/entity-review/novels/{novel_id}/rebuild-candidates`.
- `run_candidate_entity_extraction` adds backward-compatible `candidate_items` and existing `prompt_routing` evidence to its returned dictionary.

- [ ] **Step 1: Write failing model-success, timeout and rollback tests**

Monkeypatch the model-stage resolver. Assert preview stores a run-scoped proposed candidate without changing the entity; apply requires the matching preview run; rebuild archives only candidate/rejected rows after provider-model success; deterministic fallback raises a safe conflict and leaves all lifecycle states unchanged.

- [ ] **Step 2: Verify RED**

Run: `cd backend && python3 -m pytest -q tests/test_entity_review_workbench_api.py -k 'reanalyze or rebuild'`

- [ ] **Step 3: Implement preview/apply**

Use the selected entity's evidence plus scoped chapter/novel source as model input. Persist the validated proposed candidate and hash in an `EntityExtractionRun` preview record. Apply only when `preview_run_id`, user, entity, text hash and proposed payload match; update candidate fields and keep lifecycle `candidate`.

- [ ] **Step 4: Implement transactional rebuild**

Run model preview first. Require `model_execution.execution_mode == "provider_model"`. In one transaction mark candidate/rejected rows archived with `rebuild_run_id`, then persist validated new candidates; rollback on every exception. Preserve approved and legacy-active rows exactly.

- [ ] **Step 5: Verify GREEN and lifecycle regressions**

Run: `cd backend && python3 -m pytest -q tests/test_entity_review_workbench_api.py tests/test_entity_review_api.py tests/test_entity_review_service.py tests/test_story_entity_lifecycle.py`

- [ ] **Step 6: Commit task files only**

```bash
git add backend/app/features/entity_review backend/app/services/entity_review_service.py backend/tests/test_entity_review_workbench_api.py
git commit -m "feat: add safe entity reanalysis and rebuild"
```

### Task 5: Typed Frontend State And API Layer

**Files:**
- Create: `frontend/src/features/entity-review/types.ts`
- Create: `frontend/src/features/entity-review/api.ts`
- Create: `frontend/src/features/entity-review/use-entity-review-workbench.ts`
- Modify: `frontend/src/lib/api-client.ts`
- Create: `frontend/e2e/entity-review-workbench.spec.ts`

**Interfaces:**
- Produces: `useEntityReviewWorkbench(novelId)` with `query`, `page`, `items`, `summary`, `selectedIds`, `activeEntity`, `initialLoading`, `refreshing`, and mutation commands.
- Local mutation command contract: patch/remove the affected row first, retain selected IDs and URL state, then refresh summary without returning to the initial-loading skeleton.

- [ ] **Step 1: Add the failing URL-state browser contract**

Create `frontend/e2e/entity-review-workbench.spec.ts` with mocked novel, paged-review and summary responses. Assert search changes reset `page=1`, changing pages preserves selected IDs, and an approve response updates the row without rendering the initial full-page skeleton.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npx playwright test e2e/entity-review-workbench.spec.ts --project=chromium --workers=1`

Expected: the current route lacks server pagination and stable mutation behavior.

- [ ] **Step 3: Implement typed endpoint methods and URL state hook**

Add only the four new entity-review methods to `api-client.ts`. Use `URLSearchParams` for `page`, `page_size`, `type`, `status`, `q`, and `entity`; update with `router.replace` without navigation. Keep initial loading separate from background refresh.

- [ ] **Step 4: Verify typecheck**

Run: `cd frontend && npm run typecheck`

- [ ] **Step 5: Commit task files only**

```bash
git add frontend/src/features/entity-review frontend/src/lib/api-client.ts
git commit -m "feat: add entity review workbench state"
```

### Task 6: Paginated Table, Batch Toolbar And Sticky Inspector

**Files:**
- Create: `frontend/src/features/entity-review/entity-review-toolbar.tsx`
- Create: `frontend/src/features/entity-review/entity-review-table.tsx`
- Create: `frontend/src/features/entity-review/entity-review-inspector.tsx`
- Create: `frontend/src/features/entity-review/entity-edit-form.tsx`
- Modify: `frontend/src/app/novels/[id]/asset-analysis/page.tsx`
- Modify: `frontend/e2e/entity-review-workbench.spec.ts`

**Interfaces:**
- Consumes: the hook contract from Task 5.
- Produces: accessible row selection, current-page selection, batch approve/reject, server pagination, candidate editing and reanalysis preview/apply UI.

- [ ] **Step 1: Write failing Playwright contracts with mocked APIs**

Mock 121 entities and assert 50 visible rows on page 1, page 3 is reachable, selected IDs survive page changes, single approve keeps the scroll container position, edit saves a candidate, and preview/apply displays changed fields before mutation.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npx playwright test e2e/entity-review-workbench.spec.ts --project=chromium --workers=1`

- [ ] **Step 3: Implement focused components**

Keep each component below 200 lines. Give the table a fixed desktop height, sticky header and sticky pagination footer. Put edit and reanalysis in the inspector; do not place merge suggestions in a distant page section.

- [ ] **Step 4: Reduce the route page**

Move state and presentation out of `page.tsx`; keep novel header, overview cards and `<EntityReviewWorkbench novelId={novelId} />` composition only. Verify the route page is below 300 lines.

- [ ] **Step 5: Verify browser contract and responsive reflow**

Run: `cd frontend && npx playwright test e2e/entity-review-workbench.spec.ts --project=chromium --workers=1`

- [ ] **Step 6: Verify typecheck and build**

Run: `cd frontend && npm run typecheck && NEXT_DIST_DIR=.next-entity-review npm run build`

- [ ] **Step 7: Commit task files only**

```bash
git add 'frontend/src/app/novels/[id]/asset-analysis/page.tsx' frontend/src/features/entity-review frontend/e2e/entity-review-workbench.spec.ts frontend/src/lib/api-client.ts
git commit -m "feat: rebuild entity review workbench"
```

### Task 7: Integration And Real Novel Acceptance

**Files:**
- Modify only if a verified integration defect is found in task-scoped files.

**Interfaces:**
- Verifies all contracts from Tasks 1-6 against the running frontend, backend and the real `玄玉道途` novel.

- [ ] **Step 1: Run fresh targeted backend suites**

Run: `cd backend && python3 -m pytest -q tests/test_entity_review_workbench_api.py tests/test_entity_extraction_quality.py tests/test_entity_review_api.py tests/test_entity_review_service.py tests/test_story_entity_lifecycle.py`

- [ ] **Step 2: Run frontend gates**

Run: `cd frontend && npm run typecheck && NEXT_DIST_DIR=.next-entity-review-final npm run build && npx playwright test e2e/entity-review-workbench.spec.ts --project=chromium --workers=1`

- [ ] **Step 3: Run code-health checks**

Run `git diff --check`, ensure no new endpoint imports another endpoint, ensure each new production file is below 500 lines, each React component below 200 lines, and route page below 300 lines.

- [ ] **Step 4: Restart local services and verify paging before data mutation**

Confirm page totals match the live database, navigate first/middle/last pages, edit a disposable candidate, batch-reject a bounded disposable test set, and verify no scroll reset.

- [ ] **Step 5: Execute approved safe candidate rebuild**

For novel `73324b41-7015-498b-b92b-73b89ab2f140`, record approved and candidate IDs first. Call rebuild once. If the model does not return `provider_model`, stop with all 639 candidates unchanged. On success, verify the 2 approved IDs are unchanged, old candidates are archived with the rebuild run ID, and new candidates are paginated and reviewable.

- [ ] **Step 6: Capture browser evidence**

Capture the stable workbench, a later page, edit state, batch selection state and post-action scroll position. Inspect each screenshot before reporting it.

- [ ] **Step 7: Report full-suite baseline separately**

Run `npm run verify:backend` only after targeted suites pass. Report repository-wide failures separately from task-scoped verification and do not expand the repair scope without a task-related failure.
