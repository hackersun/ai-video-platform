# Production OS Optimization And Frontend Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current Series Studio from a deterministic production workflow into a versioned, model-verified, quality-gated novel-to-multi-episode animation Production OS, with every acceptance path initiated from the frontend.

**Architecture:** Preserve the existing `StoryEntity -> StoryBible -> ProductionCard -> Asset -> EpisodeContract -> Workflow -> Publication` spine. Add model-contract verification, an event-sourced Production Graph, provider asset bindings, six-dimensional quality evaluations, and minimal repair planning around that spine; do not replace existing routes or migrate legacy JSON data destructively. Frontend Playwright is the release authority: backend unit tests prove contracts, but a phase is not accepted until a browser action triggers the relevant API and verifies persisted results.

**Tech Stack:** Next.js 14, React 18, TypeScript, Playwright, FastAPI, async SQLAlchemy, SQLite/PostgreSQL-compatible additive models, Pydantic, FFmpeg, current Volcano/DashScope/OpenAI-compatible adapters, pytest.

## Global Constraints

- Preserve all currently shipped novel, chapter, character, Story Bible, asset, script, storyboard, shot, video, TTS, synthesis, workflow, and publication behavior.
- Do not introduce Alembic; export additive models from `backend/app/models/__init__.py` and let the existing `backend/init_db.py` `create_all()` path create new tables.
- Treat the current uncommitted entity-extraction V2 files as in-progress user work; re-read the worktree before implementation and never overwrite unrelated edits.
- Candidate or rejected entities must never enter production prompts, production cards, asset generation, episode contracts, or final-quality jobs unless an explicit preview-only flag is used.
- A model registry entry stays `verified: false` until official documentation, deterministic payload tests, one successful live canary, and a recorded failure/retry test all exist.
- Every image, video, TTS, synthesis, and repair job must persist an immutable snapshot of approved facts, asset versions, Prompt Skill version, provider contract version, model ID, and effective parameters.
- Frontend acceptance must use an isolated database such as `sqlite+aiosqlite:////tmp/ai-video-platform-production-os.db`; never use `backend/ai_video.db` for standardized automation. The current `backend/app/core/database.py` hard-codes `./ai_video.db`, so no standardized E2E run is allowed until Task 1 makes `DATABASE_URL` effective and proves the resolved database path.
- Real cloud tests remain opt-in and require both an explicit enable flag and positive RMB budget. Default verification must incur no cloud cost.
- Do not claim commercial-series readiness until the same golden novel passes three live runs on three separate days without manual database repair.

---

## Execution Contract

### Intent Lock

Make high consistency a data and verification property of the production system rather than a best-effort prompt instruction.

### Scope Boundaries

In scope:

- Seedance 2.x contract verification and provider capability promotion.
- Safe completion of the entity extraction V2 lifecycle.
- Versioned Production Graph and impact-aware episode snapshots.
- Canonical assets with provider-specific bindings.
- Six-dimensional automated quality evaluation and minimal repair.
- Series Studio UX consolidation and frontend-originated acceptance.
- Quality, cost, latency, and human-repair observability.

Out of scope:

- Training or fine-tuning a custom video foundation model.
- Replacing every existing JSON field in one migration.
- Building a public template marketplace or billing system.
- Making Neo4j, Milvus, or Redis mandatory for the first production release.
- Automatically publishing generated media without a publishability gate.

### Release Gates

| Gate | Required evidence | Blocks |
| --- | --- | --- |
| G-1 Isolation | Effective database URL assertion, temporary DB path, pre/post row-count audit, no `e2e-user-*` rows in the development DB | Any standardized backend or browser acceptance |
| G0 Contract | Official URL, access date, model ID, request schema, deterministic payload test | Enabling a provider/model as verified |
| G1 Facts | Evidence-backed approved entities and state transitions | Episode contract lock |
| G2 Assets | Required canonical assets and provider bindings resolve to public media | Final-quality generation |
| G3 Quality | All hard dimensions pass or have an approved exception | Final render |
| G4 Delivery | MP4/media audit, subtitles, manifest, lineage and publishability pass | Publication |
| G5 Series | Three episodes pass repeatability, cost and repair thresholds | Commercial-series readiness |

### Standard Verification Environment

These commands become authoritative only after Task 1's database configuration test passes. Until then, run the backend from a repository-external copy so its relative `./ai_video.db` cannot touch the development database.

```bash
export TEST_DATABASE_URL='sqlite+aiosqlite:////tmp/ai-video-platform-production-os.db'
rm -f /tmp/ai-video-platform-production-os.db
cd backend
DATABASE_URL="$TEST_DATABASE_URL" DEV_MODE=true PYTHONPATH=. python3 init_db.py
DATABASE_URL="$TEST_DATABASE_URL" DEV_MODE=true PYTHONPATH=. uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run dev -- -p 3100
```

The primary acceptance URL is `http://127.0.0.1:3100/studio`. Playwright output must stay under `/tmp/ai-video-platform-production-os-e2e`.

### Observed Baseline Before Implementation

- Frontend typecheck and production build pass; Next.js builds all 45 current routes.
- The selected deterministic Studio browser suite passes 6 of 10 cases. Four failures are stale navigation/copy assumptions: tests do not open `设定` or `复审`, and one card test still expects the retired `就绪` label.
- The real-backend frontend suite passes 3 of 10 cases. Six failures are stale or ambiguous assertions: duplicate job-title locators, old quick-start heading, old preflight copy, and publication success without a final MP4.
- One real frontend defect is confirmed: the script generation-context API includes the manually created current-chapter event, but the UI's shared eight-item slice hides it behind scene and prop noise.
- Both inspected workflow preflight APIs return `ready=true`, zero blocking issues, and green media-sync evidence; the failing tests assert retired success text.
- Backend full regression passes in a repository-external sandbox: 849 passed, 1 skipped, 17 deprecation warnings.
- `backend/app/core/database.py` ignores `DATABASE_URL`; the first attempted isolated browser run therefore reached the existing development database. All exact test-user rows and 30 generated media artifacts from that run were removed, and `PRAGMA integrity_check` returned `ok`.
- The development database already had foreign-key audit findings before cleanup (one orphan script-to-novel reference and historical DEV/E2E image jobs without matching users). Preserve this as a baseline debt item; the isolated acceptance database must add zero findings.

---

## File Structure Map

### Existing files to preserve and extend

- `backend/app/core/model_registry.py`: runtime model capability authority.
- `backend/app/services/seedance_contract.py`: Seedance contract status and provider semantics.
- `backend/app/services/video_reference_adapter.py`: provider payload conversion.
- `backend/app/services/reference_package_builder.py`: canonical reference selection.
- `backend/app/services/story_entity_lifecycle.py`: entity visibility and transition authority.
- `backend/app/services/entity_review_service.py`: candidate review, approval, rejection, merge and feedback.
- `backend/app/services/production_bible.py`: approved-fact production projection.
- `backend/app/services/episode_contract_service.py`: episode-level immutable lock.
- `backend/app/services/consistency_ledger_service.py`: cross-shot and cross-episode findings.
- `backend/app/services/visual_consistency_service.py`: current shot visual evidence.
- `backend/app/api/v1/endpoints/workflow.py`: workflow generation, review, repair, render and contracts.
- `backend/app/api/v1/endpoints/studio.py`: Series Studio snapshot and actions.
- `frontend/src/app/studio/page.tsx`: primary production console.
- `frontend/src/app/studio/cards/page.tsx`: canonical asset approval.
- `frontend/src/app/studio/shot-review/page.tsx`: shot quality and repair.
- `frontend/src/lib/api-client.ts`: frontend API contract.
- `frontend/src/lib/studio-types.ts`: frontend Studio types.
- `frontend/src/lib/episode-preview-production.ts`: frontend-originated episode production orchestration.

### New focused units

- `backend/app/models/production_state_event.py`: append-only story-world and production-version events.
- `backend/app/models/provider_asset_binding.py`: canonical asset to provider asset/reference binding.
- `backend/app/models/quality_evaluation.py`: immutable quality evaluation result per artifact and dimension.
- `backend/app/services/production_graph_service.py`: approved state projection and impact calculation.
- `backend/app/services/provider_asset_binding_service.py`: create, resolve, verify and invalidate provider bindings.
- `backend/app/services/quality_evaluation_service.py`: six-dimensional evaluator orchestration.
- `backend/app/services/repair_planner.py`: smallest safe regeneration/edit plan.
- `frontend/src/components/studio/production-graph-panel.tsx`: state and version changes.
- `frontend/src/components/studio/model-contract-status.tsx`: verified/experimental provider state.
- `frontend/src/components/studio/quality-gate-panel.tsx`: dimension-level quality gates and repair actions.
- `frontend/e2e/production-os-frontend-acceptance.spec.ts`: deterministic browser-to-real-backend release suite.
- `frontend/e2e/production-os-live-canary.spec.ts`: budget-gated real provider suite.

---

### Task 1: Standardize Frontend-Originated Acceptance Before Behavior Changes

**Files:**
- Modify: `backend/app/core/database.py`
- Create: `backend/tests/test_database_config.py`
- Modify: `package.json`
- Modify: `frontend/package.json`
- Modify: `frontend/src/app/scripts/page.tsx`
- Modify: `frontend/e2e/full-flow.spec.ts`
- Modify: `frontend/e2e/series-studio-consistency-ledger.spec.ts`
- Modify: `frontend/e2e/series-studio-multi-episode.spec.ts`
- Modify: `frontend/e2e/series-studio-production-bible.spec.ts`
- Modify: `frontend/e2e/studio-production-cards.spec.ts`
- Create: `frontend/e2e/production-os-frontend-acceptance.spec.ts`
- Create: `frontend/e2e/helpers/production-os-fixture.ts`
- Test: `backend/tests/test_database_config.py`
- Test: `frontend/e2e/production-os-frontend-acceptance.spec.ts`

**Interfaces:**
- Consumes: existing REST endpoints and DEV_MODE deterministic media generation.
- Produces: `npm run verify:production-os`, the release-authority command for all later tasks.

- [ ] **Step 1: Write a failing database isolation test**

Import database configuration in a subprocess with a unique temporary URL, then assert that both async and sync engines resolve to that path instead of `backend/ai_video.db`.

```python
def test_database_url_environment_controls_async_and_sync_engines(tmp_path):
    db_path = tmp_path / "production-os.db"
    result = run_database_probe(
        env={"DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"},
    )
    assert result["async_database"] == str(db_path)
    assert result["sync_database"] == str(db_path)
```

Run:

```bash
cd backend
python3 -m pytest -q tests/test_database_config.py
```

Expected now: FAIL because `backend/app/core/database.py` hard-codes `sqlite+aiosqlite:///./ai_video.db` and `sqlite:///./ai_video.db`.

- [ ] **Step 2: Make database configuration environment-driven and fail closed in standardized E2E**

Read `DATABASE_URL`, derive a compatible sync URL for `init_db.py`, and expose a startup/test diagnostic with the resolved database path. Add an `E2E_REQUIRE_ISOLATED_DB=true` guard that rejects `ai_video.db`, an empty path, or a non-`/tmp` SQLite path before the app starts.

Re-run `backend/tests/test_database_config.py`; expected: PASS. Start the backend with the Standard Verification Environment and assert that `/tmp/ai-video-platform-production-os.db` is non-empty while `backend/ai_video.db` has unchanged size and row counts.

- [ ] **Step 3: Repair the existing E2E contract without weakening assertions**

Update tests to perform the interactions the current UI requires:

- Open `设定` before asserting Production Bible and multi-episode plan content.
- Open `复审` before asserting the consistency ledger.
- Assert `终稿就绪` instead of the retired `就绪` metric label.
- Scope job-title assertions to the intended card or detail heading to avoid strict-mode duplicate matches.
- Assert current render-preflight success copy (`预检通过，可以执行渲染` or the FFmpeg-specific variant) and also assert `ready=true`; do not merely replace the old text.
- Make the publication test create a final rendered MP4 before expecting publish success; keep `publication_not_ready` as a separate negative test.
- Assert the current `连续动漫向导` heading.

- [ ] **Step 4: Fix generation-context preview priority at the UI boundary**

The API currently returns the manually created event `暗巷遭遇`, but `frontend/src/app/scripts/page.tsx` concatenates scenes, props and events and slices the shared list to eight items. Render category-aware previews, with at least the first three items from each non-empty category, so a current-chapter event cannot be displaced by extracted scene/prop noise. Keep full arrays in the API response and add a frontend assertion for the manual event.

- [ ] **Step 5: Write a failing real-backend browser acceptance**

Create a Playwright test that performs setup through the authenticated frontend browser context, opens `/novels/{id}`, generates the series plan from a visible control, opens `/studio`, locks an episode contract, starts preview production from the page, opens shot review, renders a local package, and verifies persisted workflow state through `page.evaluate(fetch(...))`.

```ts
test('frontend drives a novel through Series Studio and persists lineage', async ({ page }) => {
  const fixture = await createProductionOsFixtureFromBrowser(page, { episodes: 3, shotsPerEpisode: 2 });
  await page.goto(`/novels/${fixture.novelId}?tab=series-plan`);
  await page.getByRole('button', { name: /生成整书计划|重新生成计划/ }).click();
  await page.goto(`/studio?workflow_id=${fixture.workflowId}&novel_id=${fixture.novelId}&chapter_id=${fixture.chapterId}`);
  await page.getByRole('button', { name: /锁定本集生产合约/ }).click();
  await page.getByRole('button', { name: /生成本集草片/ }).click();
  await expect(page.getByText(/任务已提交|渲染包已生成/)).toBeVisible();
  const snapshot = await apiGetFromPage(page, `/studio/workflows/${fixture.workflowId}/snapshot`);
  expect(snapshot.episode_contract.contract_id).toBeTruthy();
  expect(snapshot.workflow.metadata.latest_production_strategy).toBeTruthy();
});
```

- [ ] **Step 6: Run the test against an isolated database and verify the expected baseline result**

Run:

```bash
PLAYWRIGHT_PORT=3100 PLAYWRIGHT_OUTPUT_DIR=/tmp/ai-video-platform-production-os-e2e \
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 \
npm --prefix frontend run e2e -- production-os-frontend-acceptance.spec.ts --project=chromium --workers=1
```

Expected before later tasks: the existing-flow case passes; assertions for model verification, Production Graph, provider bindings and six-dimensional gates fail with explicit missing fields.

After the run, query both databases. The temporary database must contain the test user's rows, and `backend/ai_video.db` must contain zero rows for that run's exact `e2e-user-*` IDs.

- [ ] **Step 7: Add stable package commands**

```json
{
  "scripts": {
    "verify:production-os:frontend": "npm --prefix frontend run typecheck && npm --prefix frontend run build",
    "verify:production-os:e2e": "npm --prefix frontend run e2e -- production-os-frontend-acceptance.spec.ts --project=chromium --workers=1",
    "verify:production-os": "npm run verify:production-os:frontend && npm run verify:production-os:e2e"
  }
}
```

- [ ] **Step 8: Verify the command uses the frontend as the action origin**

Add request assertions for these browser-triggered calls:

```ts
await page.waitForRequest(req => req.method() === 'POST' && req.url().includes('/series-plan'));
await page.waitForRequest(req => req.method() === 'POST' && req.url().includes('/episode-contract/lock'));
await page.waitForRequest(req => req.method() === 'POST' && req.url().includes('/generate-media-batch'));
await page.waitForRequest(req => req.method() === 'POST' && req.url().includes('/render'));
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/database.py backend/tests/test_database_config.py package.json frontend/package.json frontend/src/app/scripts/page.tsx frontend/e2e/full-flow.spec.ts frontend/e2e/series-studio-consistency-ledger.spec.ts frontend/e2e/series-studio-multi-episode.spec.ts frontend/e2e/series-studio-production-bible.spec.ts frontend/e2e/studio-production-cards.spec.ts frontend/e2e/production-os-frontend-acceptance.spec.ts frontend/e2e/helpers/production-os-fixture.ts
git commit -m "test: standardize frontend production os acceptance"
```

---

### Task 2: Verify And Promote Seedance Provider Contracts

**Files:**
- Modify: `docs/seedance-2-contract-checklist.md`
- Modify: `backend/app/services/seedance_contract.py`
- Modify: `backend/app/core/model_registry.py`
- Modify: `backend/app/services/video_reference_adapter.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py`
- Test: `backend/tests/test_seedance_contract.py`
- Test: `backend/tests/test_reference_package.py`
- Test: `frontend/e2e/production-os-frontend-acceptance.spec.ts`

**Interfaces:**
- Produces: `resolve_seedance_contract(model_id: str) -> SeedanceContract` and visible `contract_status` metadata.
- Consumers: model routing, reference payload adapter, Studio contract status panel, live canary.

- [ ] **Step 1: Write contract tests for exact provider payloads**

```python
def test_seedance_20_contract_emits_documented_reference_roles():
    payload = build_video_reference_payload(
        model_id="doubao-seedance-2-0-260128",
        prompt="参考角色与场景生成镜头",
        reference_package={"images": [{"url": "https://cdn.example/a.png", "at_index": 1}]},
    )
    assert payload.contract_status == "confirmed"
    assert payload.content[0]["type"] == "text"
    assert payload.content[1]["type"] == "reference_image"
```

- [ ] **Step 2: Keep models experimental until all promotion evidence is present**

Implement a promotion predicate with exact required keys:

```python
REQUIRED_CONFIRMATION_EVIDENCE = {
    "official_schema_url",
    "official_schema_accessed_at",
    "payload_contract_test",
    "live_canary_job_id",
    "pricing_url",
    "failure_retry_evidence",
}

def contract_is_confirmed(evidence: dict[str, object]) -> bool:
    return all(evidence.get(key) for key in REQUIRED_CONFIRMATION_EVIDENCE)
```

- [ ] **Step 3: Expose contract status through existing model APIs**

Add `contract_status`, `contract_version`, `verified_at`, `reference_limits`, and `verification_gaps` to model responses without removing existing fields.

- [ ] **Step 4: Show the status in Series Studio**

The frontend must display `已验证`, `实验`, or `不可用`. Selecting final quality with an experimental model must show a confirmation explaining that real provider evidence is incomplete.

- [ ] **Step 5: Verify deterministic and frontend behavior**

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_seedance_contract.py tests/test_reference_package.py
cd frontend && npx playwright test e2e/production-os-frontend-acceptance.spec.ts -g "model contract" --project=chromium --workers=1
```

- [ ] **Step 6: Commit**

```bash
git add docs/seedance-2-contract-checklist.md backend/app/services/seedance_contract.py backend/app/core/model_registry.py backend/app/services/video_reference_adapter.py backend/app/api/v1/endpoints/llm_config.py backend/tests/test_seedance_contract.py frontend/e2e/production-os-frontend-acceptance.spec.ts
git commit -m "feat: verify video provider contracts"
```

---

### Task 3: Finish The Evidence-Backed Entity V2 Safety Boundary

**Files:**
- Modify: `backend/app/services/story_entity_lifecycle.py`
- Modify: `backend/app/services/entity_review_service.py`
- Modify: `backend/app/services/entity_extraction_service.py`
- Modify: `backend/app/services/consistency_context.py`
- Modify: `backend/app/services/production_bible.py`
- Modify: `backend/app/services/production_card_service.py`
- Modify: `backend/app/api/v1/endpoints/story_bible.py`
- Modify: `frontend/src/app/novels/[id]/asset-analysis/page.tsx`
- Modify: `frontend/src/components/novels/story-workbench-panel.tsx`
- Test: `backend/tests/test_story_entity_lifecycle.py`
- Test: `backend/tests/test_entity_extraction_quality.py`
- Test: `backend/tests/test_entity_review_api.py`
- Test: `frontend/e2e/production-os-frontend-acceptance.spec.ts`

**Interfaces:**
- Produces: one authoritative entity visibility contract and evidence-backed approval flow.
- Consumers: Production Bible, Production Cards, assets, prompts, episode contracts and Production Graph.

- [ ] **Step 1: Add a failing safety regression**

```python
async def test_candidate_entity_never_enters_final_prompt(db_session):
    candidate = await seed_entity(db_session, review_status="candidate", name="错误主角")
    context = await build_consistency_prompt(db_session, candidate.user_id, novel_id=candidate.novel_id)
    assert "错误主角" not in context["prompt"]
```

- [ ] **Step 2: Route all production consumers through lifecycle queries**

Direct `select(StoryEntity)` remains permitted only in admin/review endpoints and the lifecycle service. Add a test that scans the critical consumer file list and fails on new direct production queries.

- [ ] **Step 3: Require source evidence for new production approval**

An entity extracted by AI can become approved only when at least one `StoryEntityMention` has `source_id`, non-empty evidence, and a confidence value. Manual entities remain compatible but record `source="manual"` and approver identity.

- [ ] **Step 4: Make frontend approval explicit and impact-aware**

The Asset Analysis page must show original evidence, duplicate risk, quality components, downstream impact and the exact action: approve, reject, merge or enrich. Bulk approval excludes items with high duplicate risk or missing evidence.

- [ ] **Step 5: Verify from the frontend**

The browser creates an extraction run, confirms candidates do not appear in Production Cards, approves one entity from the page, refreshes Studio, and then verifies that only the approved entity appears.

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_story_entity_lifecycle.py tests/test_entity_extraction_quality.py tests/test_entity_review_api.py
cd frontend && npx playwright test e2e/production-os-frontend-acceptance.spec.ts -g "entity evidence" --project=chromium --workers=1
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/story_entity_lifecycle.py backend/app/services/entity_review_service.py backend/app/services/entity_extraction_service.py backend/app/services/consistency_context.py backend/app/services/production_bible.py backend/app/services/production_card_service.py backend/app/api/v1/endpoints/story_bible.py frontend/src/app/novels/[id]/asset-analysis/page.tsx frontend/src/components/novels/story-workbench-panel.tsx backend/tests/test_story_entity_lifecycle.py backend/tests/test_entity_extraction_quality.py backend/tests/test_entity_review_api.py frontend/e2e/production-os-frontend-acceptance.spec.ts
git commit -m "feat: enforce evidence backed production entities"
```

---

### Task 4: Add A Versioned Production Graph With Dual Timelines

**Files:**
- Create: `backend/app/models/production_state_event.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/init_db.py`
- Create: `backend/app/services/production_graph_service.py`
- Modify: `backend/app/services/production_bible.py`
- Modify: `backend/app/services/story_state_machine.py`
- Modify: `backend/app/services/episode_contract_service.py`
- Modify: `backend/app/services/series_production.py`
- Modify: `backend/app/api/v1/endpoints/story_bible.py`
- Create: `frontend/src/components/studio/production-graph-panel.tsx`
- Modify: `frontend/src/app/studio/page.tsx`
- Test: `backend/tests/test_production_graph_service.py`
- Test: `backend/tests/test_episode_contract_service.py`
- Test: `frontend/e2e/production-os-frontend-acceptance.spec.ts`

**Interfaces:**
- Produces: `append_state_event()`, `project_story_state()`, `build_episode_state_snapshot()`, and `analyze_state_change_impact()`.
- Consumers: series plan, episode contract, shot prompts, consistency ledger and Studio.

- [ ] **Step 1: Define the append-only event model**

```python
class ProductionStateEvent(Base):
    __tablename__ = "production_state_events"
    id: Mapped[str]
    user_id: Mapped[str]
    novel_id: Mapped[str]
    chapter_id: Mapped[str | None]
    episode_index: Mapped[int | None]
    entity_id: Mapped[str | None]
    event_type: Mapped[str]
    story_time: Mapped[dict]
    production_time: Mapped[dict]
    before_state: Mapped[dict]
    after_state: Mapped[dict]
    evidence: Mapped[dict]
    approved_by: Mapped[str | None]
    created_at: Mapped[datetime]
```

- [ ] **Step 2: Write projection and immutability tests**

Test costume change, injury persistence, prop owner changes, scene weather, relationship change, restoration to an earlier production version, and rejection of in-place mutation.

- [ ] **Step 3: Build episode snapshots from approved events**

Episode contracts store the graph version/hash, projected opening state, expected closing state and relevant event IDs. Locking fails when required facts have unresolved conflicts.

- [ ] **Step 4: Add impact analysis**

A change to an approved event returns affected episode contracts, shots, video/TTS jobs and publications. Published artifacts are never silently changed; they are marked `superseded_review_required`.

- [ ] **Step 5: Expose the dual timeline in Studio**

The panel shows story order and production revision order separately, with an impact badge and links to affected shots.

- [ ] **Step 6: Verify from the frontend**

Use the browser to approve a prop-owner change in episode 2, verify episode 1 is unchanged, verify episode 3 inherits the new owner, and verify affected shots become review tasks.

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_production_graph_service.py tests/test_episode_contract_service.py
cd frontend && npx playwright test e2e/production-os-frontend-acceptance.spec.ts -g "production graph" --project=chromium --workers=1
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/production_state_event.py backend/app/models/__init__.py backend/init_db.py backend/app/services/production_graph_service.py backend/app/services/production_bible.py backend/app/services/story_state_machine.py backend/app/services/episode_contract_service.py backend/app/services/series_production.py backend/app/api/v1/endpoints/story_bible.py frontend/src/components/studio/production-graph-panel.tsx frontend/src/app/studio/page.tsx backend/tests/test_production_graph_service.py backend/tests/test_episode_contract_service.py frontend/e2e/production-os-frontend-acceptance.spec.ts
git commit -m "feat: add versioned production graph"
```

---

### Task 5: Bind Canonical Assets To Provider-Specific References

**Files:**
- Create: `backend/app/models/provider_asset_binding.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/init_db.py`
- Create: `backend/app/services/provider_asset_binding_service.py`
- Modify: `backend/app/services/reference_package_builder.py`
- Modify: `backend/app/services/video_reference_adapter.py`
- Modify: `backend/app/api/v1/endpoints/assets.py`
- Modify: `frontend/src/app/studio/cards/page.tsx`
- Modify: `frontend/src/lib/api-client.ts`
- Test: `backend/tests/test_provider_asset_binding.py`
- Test: `backend/tests/test_reference_package.py`
- Test: `frontend/e2e/production-os-frontend-acceptance.spec.ts`

**Interfaces:**
- Produces: `resolve_provider_binding(asset_id, provider_id, model_id) -> ProviderAssetBinding`.
- Consumers: final-quality reference packages and model-specific prompt references.

- [ ] **Step 1: Add the binding model and uniqueness rule**

The unique active binding key is `(asset_id, asset_version, provider_id, model_id, binding_kind)`. Store provider asset ID, public URL, checksum, dimensions/duration, upload status, verified time and invalidation reason.

- [ ] **Step 2: Write resolver tests**

Cover cached reuse, expired public URL refresh, checksum mismatch, model-specific incompatibility, provider upload failure and fallback to a direct public URL.

- [ ] **Step 3: Make reference packages binding-aware**

Reference selection remains canonical and provider-neutral; conversion to provider payload happens after a verified binding resolves. Save both canonical asset IDs and provider binding IDs in job metadata.

- [ ] **Step 4: Add a frontend binding health view**

Each Production Card shows canonical readiness and per-provider readiness. A final-quality action is disabled only for missing bindings required by the selected model.

- [ ] **Step 5: Verify from the frontend**

Choose a model in Studio, generate missing bindings from the card page, return to Studio, and verify the final-quality gate changes from blocked to ready without changing the canonical asset version.

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_provider_asset_binding.py tests/test_reference_package.py
cd frontend && npx playwright test e2e/production-os-frontend-acceptance.spec.ts -g "provider binding" --project=chromium --workers=1
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/provider_asset_binding.py backend/app/models/__init__.py backend/init_db.py backend/app/services/provider_asset_binding_service.py backend/app/services/reference_package_builder.py backend/app/services/video_reference_adapter.py backend/app/api/v1/endpoints/assets.py frontend/src/app/studio/cards/page.tsx frontend/src/lib/api-client.ts backend/tests/test_provider_asset_binding.py backend/tests/test_reference_package.py frontend/e2e/production-os-frontend-acceptance.spec.ts
git commit -m "feat: bind canonical assets to providers"
```

---

### Task 6: Implement Six-Dimensional Quality Gates And Minimal Repair

**Files:**
- Create: `backend/app/models/quality_evaluation.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/init_db.py`
- Create: `backend/app/services/quality_evaluation_service.py`
- Create: `backend/app/services/repair_planner.py`
- Modify: `backend/app/services/visual_consistency_service.py`
- Modify: `backend/app/services/consistency_ledger_service.py`
- Modify: `backend/app/services/shot_quality_service.py`
- Modify: `backend/app/api/v1/endpoints/workflow.py`
- Create: `frontend/src/components/studio/quality-gate-panel.tsx`
- Modify: `frontend/src/app/studio/shot-review/page.tsx`
- Modify: `frontend/src/lib/studio-types.ts`
- Test: `backend/tests/test_quality_evaluation_service.py`
- Test: `backend/tests/test_repair_planner.py`
- Test: `frontend/e2e/production-os-frontend-acceptance.spec.ts`

**Interfaces:**
- Produces: `evaluate_artifact() -> QualityEvaluationSet` and `plan_minimal_repair() -> RepairPlan`.
- Consumers: shot review, final render preflight, publication readiness and feedback metrics.

- [ ] **Step 1: Define independent dimensions**

```python
QUALITY_DIMENSIONS = {
    "narrative_truth",
    "character_visual",
    "scene_prop_state",
    "motion_camera",
    "voice_lipsync",
    "delivery_integrity",
}
```

Every record stores expected state, observed state, evidence, score, confidence, severity, threshold version, evaluator version and repair action.

- [ ] **Step 2: Write hard-gate tests**

Main-character identity mismatch, future-episode leakage, wrong prop owner, wrong speaker, missing subtitle and corrupt MP4 are blocking. Minor background variation and noncritical ambient-audio differences are warnings.

- [ ] **Step 3: Combine deterministic and model-based evaluators**

Deterministic checks own lineage, duration, files, subtitles and state equality. Multimodal models provide semantic observations. Embedding/face/speaker similarity provides repeatable numeric signals. No single LLM score can override a deterministic blocker.

- [ ] **Step 4: Generate the smallest repair plan**

Examples:

```python
assert plan_minimal_repair(issue="wrong_voice").actions == ["regenerate_tts", "rerun_lipsync", "rerender_audio"]
assert plan_minimal_repair(issue="wrong_prop_state").actions == ["regenerate_shot_video", "rerun_visual_review"]
assert plan_minimal_repair(issue="subtitle_timing").actions == ["retime_subtitles", "rerender_subtitles"]
```

- [ ] **Step 5: Add frontend quality and repair controls**

Shot Review displays six dimension rows, expected versus observed evidence, blocker severity, cost/risk estimate and exact repair scope. The primary button says what will be regenerated; it never uses an ambiguous “retry all”.

- [ ] **Step 6: Verify from the frontend**

Create one wrong-voice fixture and one wrong-prop fixture. Trigger evaluation from the page, run each suggested repair, and verify unrelated video/TTS job IDs remain unchanged.

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_quality_evaluation_service.py tests/test_repair_planner.py
cd frontend && npx playwright test e2e/production-os-frontend-acceptance.spec.ts -g "quality gate|minimal repair" --project=chromium --workers=1
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/quality_evaluation.py backend/app/models/__init__.py backend/init_db.py backend/app/services/quality_evaluation_service.py backend/app/services/repair_planner.py backend/app/services/visual_consistency_service.py backend/app/services/consistency_ledger_service.py backend/app/services/shot_quality_service.py backend/app/api/v1/endpoints/workflow.py frontend/src/components/studio/quality-gate-panel.tsx frontend/src/app/studio/shot-review/page.tsx frontend/src/lib/studio-types.ts backend/tests/test_quality_evaluation_service.py backend/tests/test_repair_planner.py frontend/e2e/production-os-frontend-acceptance.spec.ts
git commit -m "feat: add quality gates and minimal repair"
```

---

### Task 7: Consolidate Series Studio Into A Stage-Gated Production Console

**Files:**
- Modify: `frontend/src/app/studio/page.tsx`
- Modify: `frontend/src/lib/studio-api.ts`
- Modify: `frontend/src/lib/studio-types.ts`
- Modify: `frontend/src/lib/episode-preview-production.ts`
- Modify: `backend/app/services/studio_snapshot.py`
- Modify: `backend/app/services/studio_guidance.py`
- Modify: `backend/app/api/v1/endpoints/studio.py`
- Test: `frontend/e2e/production-os-frontend-acceptance.spec.ts`
- Test: `frontend/e2e/series-studio-multi-episode.spec.ts`

**Interfaces:**
- Consumes: verified model contracts, approved Production Graph, provider bindings and quality evaluations.
- Produces: a single stage state machine and one next action at a time.

- [ ] **Step 1: Add a backend stage contract**

```ts
type ProductionStage =
  | 'facts'
  | 'assets'
  | 'episode_contract'
  | 'draft'
  | 'review'
  | 'final'
  | 'render'
  | 'publish';
```

The snapshot returns the current stage, blockers, confirmable warnings, completed evidence and one recommended next action.

- [ ] **Step 2: Remove competing primary actions**

The page presents one primary action derived from the snapshot. Expert panels remain available as drill-downs and do not duplicate the primary action.

- [ ] **Step 3: Preserve multi-episode context**

Changing episodes refreshes the Production Graph projection, contract, assets, quality and jobs for that episode without losing the series-level context.

- [ ] **Step 4: Make progress and failures resumable**

Every failed frontend orchestration step displays the persisted backend task ID, safe retry action and completed prior stages. Reloading the browser resumes from the persisted stage.

- [ ] **Step 5: Verify desktop and mobile frontend flows**

Use Desktop Chrome and a 390×844 viewport. Verify command bar, stage flow, primary action, blocker links, episode switch, refresh recovery and no horizontal overflow.

```bash
cd frontend && npm run typecheck && npm run build
cd frontend && npx playwright test e2e/production-os-frontend-acceptance.spec.ts e2e/series-studio-multi-episode.spec.ts --project=chromium --workers=1
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/studio/page.tsx frontend/src/lib/studio-api.ts frontend/src/lib/studio-types.ts frontend/src/lib/episode-preview-production.ts backend/app/services/studio_snapshot.py backend/app/services/studio_guidance.py backend/app/api/v1/endpoints/studio.py frontend/e2e/production-os-frontend-acceptance.spec.ts frontend/e2e/series-studio-multi-episode.spec.ts
git commit -m "feat: stage gate series studio production"
```

---

### Task 8: Add Production Metrics, Golden-Series Evaluation And Budget-Gated Live Canary

**Files:**
- Modify: `backend/app/models/quality_evaluation.py`
- Modify: `backend/app/models/llm_config.py`
- Create: `backend/app/services/production_metrics.py`
- Modify: `backend/app/api/v1/endpoints/dashboard.py`
- Modify: `frontend/src/app/analytics/page.tsx`
- Create: `frontend/e2e/production-os-live-canary.spec.ts`
- Modify: `package.json`
- Test: `backend/tests/test_production_metrics.py`
- Test: `frontend/e2e/production-os-live-canary.spec.ts`

**Interfaces:**
- Produces: series/episode/shot quality, cost, latency, retry and human-repair metrics.
- Consumers: release decision, routing policy and Prompt Skill quality feedback.

- [ ] **Step 1: Define decision metrics**

Required metrics:

- first-pass shot acceptance rate;
- main-character hard-failure rate;
- state-continuity conflict rate;
- voice/lip-sync hard-failure rate;
- regenerated shots per accepted shot;
- RMB per accepted final minute;
- wall-clock minutes per accepted final minute;
- human review and repair minutes per accepted final minute;
- provider/model/prompt/contract version attribution.

- [ ] **Step 2: Write metric aggregation tests**

Use accepted final shots as the denominator for cost and repair efficiency. Keep failed and abandoned jobs visible; never calculate only over successful jobs.

- [ ] **Step 3: Add a golden-series dataset contract**

The fixture contains 8–12 chapters, three episodes, approved assets, expected state events, required dialogue and quality annotations. Store only sanitized test fiction and generated assets.

- [ ] **Step 4: Implement the budget gate**

```ts
test.skip(process.env.PRODUCTION_OS_LIVE !== '1', 'Set PRODUCTION_OS_LIVE=1 to enable real provider calls.');
test.skip(Number(process.env.PRODUCTION_OS_LIVE_MAX_RMB || '0') <= 0, 'A positive RMB budget is required.');
```

The test starts generation from `/studio`, never directly from a test-side provider API call.

- [ ] **Step 5: Establish readiness rules**

- `deterministic_ready`: backend contract tests, frontend build and deterministic browser suite pass.
- `internal_trial_ready`: one real-context frontend run passes against persisted local data.
- `series_production_candidate`: a budget-gated three-episode live run passes once.
- `commercial_series_ready`: three runs on separate days pass thresholds without manual database repair.

- [ ] **Step 6: Verify deterministic metrics and default live skip**

```bash
cd backend && DEV_MODE=true PYTHONPATH=. pytest -q tests/test_production_metrics.py
npm --prefix frontend run e2e -- production-os-live-canary.spec.ts --project=chromium --workers=1
```

Expected: deterministic metrics pass; live test is skipped with the budget-gate message.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/quality_evaluation.py backend/app/models/llm_config.py backend/app/services/production_metrics.py backend/app/api/v1/endpoints/dashboard.py frontend/src/app/analytics/page.tsx frontend/e2e/production-os-live-canary.spec.ts package.json backend/tests/test_production_metrics.py
git commit -m "feat: add series production readiness metrics"
```

---

## Final Standardized Verification

### A. Static frontend gate

```bash
npm run verify:frontend
```

Required: TypeScript and Next.js production build exit 0.

### B. Frontend isolated UI gate

```bash
npm --prefix frontend run e2e -- \
  smoke.spec.ts \
  series-studio-full-flow.spec.ts \
  series-studio-multi-episode.spec.ts \
  series-studio-production-bible.spec.ts \
  series-studio-consistency-ledger.spec.ts \
  studio-production-cards.spec.ts \
  studio-shot-review.spec.ts \
  --project=chromium --workers=1
```

Required: zero failures; all network mocks assert frontend request shape and rendered state.

### C. Frontend-to-real-local-backend gate

Start the isolated backend and run:

```bash
PLAYWRIGHT_PORT=3100 \
PLAYWRIGHT_OUTPUT_DIR=/tmp/ai-video-platform-production-os-e2e \
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 \
npm --prefix frontend run e2e -- \
  full-flow.spec.ts \
  production-os-frontend-acceptance.spec.ts \
  --project=chromium --workers=1
```

Required: browser actions create or advance real database records, persisted lineage matches visible context, final media is generated only in DEV_MODE, and the test database is removed after the run.

### D. Backend supporting contract gate

```bash
cd backend
DATABASE_URL='sqlite+aiosqlite:////tmp/ai-video-platform-production-os-contract.db' \
DEV_MODE=true PYTHONPATH=. pytest -q
```

Required: zero failures. This gate supports but does not replace C.

### E. Browser health gate

For `/studio`, `/studio/cards`, `/studio/shot-review`, `/novels/{id}`, `/workflow` and `/synthesis`:

- URL and page title match the intended route.
- Meaningful content renders; no blank shell or framework error overlay.
- No relevant console errors or unhandled promise rejections.
- Primary controls change real persisted UI state.
- Desktop and 390×844 views have no clipping, overlap or horizontal overflow.
- Screenshots are stored under `/tmp/ai-video-platform-production-os-e2e/screenshots`.

### F. Live provider gate

```bash
PRODUCTION_OS_LIVE=1 \
PRODUCTION_OS_LIVE_MAX_RMB=100 \
PRODUCTION_OS_LIVE_EPISODES=3 \
PRODUCTION_OS_LIVE_SHOTS_PER_EPISODE=2 \
npm --prefix frontend run e2e -- production-os-live-canary.spec.ts --project=chromium --workers=1
```

Run only with explicit approved credentials and budget. Record job IDs, model and contract versions, quality dimensions, actual cost, retries, failures and sanitized artifact manifests.

---

## Self-Review

- Spec coverage: contract verification, entity safety, state/version consistency, provider assets, quality gates, minimal repair, frontend UX, metrics and live validation each have a dedicated task.
- Type consistency: Production Graph, provider binding and quality evaluation interfaces are defined before their frontend consumers.
- Safety: all standardized tests use temporary databases; live tests are opt-in and budget-gated.
- Acceptance authority: every behavior-changing task has an explicit frontend Playwright verification in addition to backend tests.
- Compatibility: existing routes and JSON fields remain; new tables and response fields are additive.
- Scope: marketplace, billing, custom model training and broad infrastructure replacement remain excluded.

## Execution Order And Stop Points

1. Execute Task 1 and obtain a stable frontend-originated baseline.
2. Execute Tasks 2 and 3; stop for review because they control external model trust and production fact visibility.
3. Execute Tasks 4 and 5; stop for review because they introduce additive persistent models.
4. Execute Tasks 6 and 7; run full deterministic browser and backend gates.
5. Execute Task 8 deterministic metrics; request explicit approval before the first live provider run.
6. Do not mark commercial readiness until G0–G5 evidence is recorded.
