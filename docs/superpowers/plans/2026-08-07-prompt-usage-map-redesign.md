# Prompt Usage Map Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Prompt Template default screen with a production-stage map that reports the template actually selected by the canonical prompt router, while retaining the existing version workbench as a secondary template library.

**Architecture:** A new backend prompt-usage application owns the stage registry, resolves each unique default model binding once, and delegates template selection to the existing canonical prompt router. A thin Model Center API exposes the complete map, per-stage model preview, published candidates, and a safe “create model-specific draft” operation. New frontend feature files own API validation, query state, stage navigation, detail presentation, and assignment dialog; existing model-center composition files only switch the default prompt surface.

**Tech Stack:** FastAPI, async SQLAlchemy, Pydantic, pytest, Next.js 14, React 18, TypeScript, Tailwind CSS, Playwright.

## Global Constraints

- Preserve existing Prompt Profile rows, immutable versions, publish semantics, audit history, model bindings, and historical task evidence.
- The canonical prompt router remains the only owner of routing precedence: exact model, model family, provider, capability, then task-generic.
- Do not expose credentials, raw provider errors, internal English routing codes, or unsanitized connection parameters.
- Do not implement novel-, project-, or series-run-scoped Prompt overrides in this feature.
- Subtitle and synthesis must display `not_applicable`; they must not receive fabricated Prompt bindings.
- Frontend must not duplicate the stage registry or infer routing precedence.
- New production files target 300 lines and must stay below 500 lines; new functions target 50 lines and must stay below 80 lines.
- Existing files over 500 lines must not grow; route pages remain composition-only.
- Every behavior change follows RED → GREEN with fresh targeted verification.
- Because the worktree already contains unrelated user changes, stage and commit only the exact files owned by each task; never clean, reset, or rewrite unrelated modifications.

---

## File Structure

### Backend

- `backend/app/features/model_config/prompt_usage_contract.py`: immutable stage registry, status values, Chinese labels, and grouping helpers.
- `backend/app/features/model_config/prompt_usage_repository.py`: secret-free provider/model identity and published candidate reads.
- `backend/app/features/model_config/prompt_usage.py`: application orchestration for map, model preview, candidates, and assignment draft creation.
- `backend/app/features/model_config/api/prompt_usage.py`: thin HTTP routes and request validation.
- `backend/app/features/model_config/api/__init__.py`: include the new prompt-usage router.
- `backend/tests/test_prompt_usage_contract.py`: pure registry and presentation-contract tests.
- `backend/tests/test_prompt_usage_map.py`: API/application tests with isolated database fixtures.

### Frontend

- `frontend/src/features/model-center/prompt-usage-types.ts`: runtime-safe Prompt Usage Map types and response parsers.
- `frontend/src/features/model-center/prompt-usage-api.ts`: map, preview, candidates, and assignment requests.
- `frontend/src/features/model-center/hooks/use-prompt-usage-map.ts`: loading, refresh, selection, problem filtering, and stale-request protection.
- `frontend/src/features/model-center/components/prompt-usage-summary.tsx`: compact counts and problem-only control.
- `frontend/src/features/model-center/components/prompt-usage-stage-list.tsx`: grouped production-stage navigation.
- `frontend/src/features/model-center/components/prompt-usage-detail.tsx`: effective template, model evidence, Chinese explanation, and advanced disclosure.
- `frontend/src/features/model-center/components/prompt-usage-assignment-dialog.tsx`: candidate selection and model-specific draft confirmation.
- `frontend/src/features/model-center/components/prompt-usage-map.tsx`: composition for the map surface and template-library transition.
- `frontend/src/features/model-center/components/prompt-profile-list.tsx`: accept an optional initial profile selection when opened from the map.
- `frontend/src/features/model-center/components/model-center-management-panel.tsx`: render `PromptUsageMap` for the prompts section.
- `frontend/src/features/model-center/components/model-center-shell.tsx`: update heading and hide irrelevant catalog capability filters on the prompts section.
- `frontend/src/features/model-center/components/model-center-rail.tsx`: rename description to “生产环节实际使用”.
- `frontend/e2e/model-center-prompt-usage-map.spec.ts`: dedicated browser acceptance coverage.

---

### Task 1: Lock the production-stage registry and Chinese status contract

**Files:**
- Create: `backend/app/features/model_config/prompt_usage_contract.py`
- Create: `backend/tests/test_prompt_usage_contract.py`

**Interfaces:**
- Produces: `PromptUsageStage`, `PromptUsageGroup`, `PROMPT_USAGE_GROUPS`, `prompt_usage_stages()`, `prompt_usage_stage(stage_id)`.
- Each routed stage exposes `id`, `name`, `group_id`, `prompt_task`, `model_task`, `capability`, `prompt_stage`, `output_contract`, and `uses_prompt`.
- Non-routed stages expose `uses_prompt=False` and no model contract.

- [ ] **Step 1: Write the failing registry tests**

```python
def test_prompt_usage_registry_covers_the_ordered_production_chain():
    assert [stage.id for stage in prompt_usage_stages()] == [
        "chapter_writing", "character_extraction", "scene_prop_extraction",
        "script_generation", "storyboard_generation", "character_image",
        "scene_reference_image", "prop_image", "shot_video", "tts_dialogue",
        "subtitle", "synthesis",
    ]


def test_non_prompt_stages_are_explicitly_not_applicable():
    assert prompt_usage_stage("subtitle").uses_prompt is False
    assert prompt_usage_stage("synthesis").uses_prompt is False
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd backend && python3 -m pytest -q tests/test_prompt_usage_contract.py`

Expected: collection fails because `prompt_usage_contract` does not exist.

- [ ] **Step 3: Implement the immutable registry**

```python
@dataclass(frozen=True)
class PromptUsageStage:
    id: str
    name: str
    group_id: str
    prompt_task: str | None
    model_task: str | None
    capability: ModelCapability | None
    prompt_stage: str | None = None
    output_contract: str | None = None
    uses_prompt: bool = True


PROMPT_USAGE_GROUPS = (
    PromptUsageGroup(
        "story_development", "故事开发",
        ("chapter_writing", "character_extraction", "scene_prop_extraction"),
    ),
    PromptUsageGroup(
        "content_production", "内容制作",
        ("script_generation", "storyboard_generation"),
    ),
    PromptUsageGroup(
        "visual_production", "视觉生产",
        ("character_image", "scene_reference_image", "prop_image", "shot_video"),
    ),
    PromptUsageGroup(
        "audio_delivery", "声音与交付",
        ("tts_dialogue", "subtitle", "synthesis"),
    ),
)
```

Use shared model binding tasks rather than inventing new defaults:

- Text generation stages use `model_task="script_generation"`, except entity extraction uses `model_task="entity_extraction"`.
- Reference-image stages use `model_task="shot_image"`.
- Video uses `model_task="shot_video"`.
- TTS uses `model_task="shot_speech"`.
- Entity extraction stages use `output_contract="json_array"`; stages without a production output-contract constraint use `None`.

- [ ] **Step 4: Run the registry tests and verify GREEN**

Run: `cd backend && python3 -m pytest -q tests/test_prompt_usage_contract.py`

Expected: all tests pass and the exact 12-stage order is stable.

- [ ] **Step 5: Commit the registry slice**

```bash
git add backend/app/features/model_config/prompt_usage_contract.py backend/tests/test_prompt_usage_contract.py
git commit -m "feat: define prompt usage stages"
```

---

### Task 2: Resolve the real default model and canonical Prompt selection

**Files:**
- Create: `backend/app/features/model_config/prompt_usage_repository.py`
- Create: `backend/app/features/model_config/prompt_usage.py`
- Create: `backend/app/features/model_config/api/prompt_usage.py`
- Modify: `backend/app/features/model_config/api/__init__.py`
- Create: `backend/tests/test_prompt_usage_map.py`

**Interfaces:**
- Consumes: registry functions from Task 1, `resolve_model_binding`, and `select_prompt_skill_for_model`.
- Produces: `get_prompt_usage_map(db, *, user_id) -> dict` and `resolve_prompt_usage_stage(db, *, user_id, stage_id, profile_version_id=None) -> dict`.
- HTTP: `GET /api/v1/model-center/prompt-usage-map` and `GET /api/v1/model-center/prompt-usage-map/stages/{stage_id}/resolve?profile_version_id=...`.

- [ ] **Step 1: Write failing application and API tests**

```python
@pytest.mark.asyncio
async def test_usage_map_returns_effective_internal_fallback_and_not_applicable(client):
    response = await client.get("/api/v1/model-center/prompt-usage-map")
    assert response.status_code == 200
    body = response.json()
    stages = {item["id"]: item for group in body["groups"] for item in group["stages"]}
    assert stages["storyboard_generation"]["template"]["name"] == "标准分镜创建"
    assert stages["storyboard_generation"]["routing"]["source_label"] == "模型专用覆盖"
    assert stages["subtitle"]["status"] == "not_applicable"
    assert stages["synthesis"]["message"] == "此环节不使用提示词模板。"
    assert "api_key" not in json.dumps(body)


@pytest.mark.asyncio
async def test_stage_preview_uses_requested_published_model_without_changing_binding(client):
    response = await client.get(
        "/api/v1/model-center/prompt-usage-map/stages/shot_video/resolve",
        params={"profile_version_id": "profile-video-v2"},
    )
    assert response.status_code == 200
    assert response.json()["model"]["profile_version_id"] == "profile-video-v2"
```

Also monkeypatch `resolve_model_binding` and assert the 12 stages resolve only the five unique `(model_task, capability)` pairs.

- [ ] **Step 2: Run the new backend suite and verify RED**

Run: `cd backend && python3 -m pytest -q tests/test_prompt_usage_contract.py tests/test_prompt_usage_map.py`

Expected: route registration and application imports fail.

- [ ] **Step 3: Implement secret-free model identity reads**

```python
@dataclass(frozen=True)
class PromptUsageModelIdentity:
    profile_version_id: str
    provider_code: str
    provider_name: str
    api_model_id: str
    capabilities: tuple[str, ...]
    prompt_profile_key: str | None


async def load_prompt_usage_model_identity(
    db: AsyncSession, binding: ResolvedModelBinding,
) -> PromptUsageModelIdentity:
    # Join only provider/model metadata. Never decrypt ModelConnection secrets.
```

- [ ] **Step 4: Implement cached stage resolution through canonical owners**

```python
async def get_prompt_usage_map(db: AsyncSession, *, user_id: str) -> dict:
    model_cache: dict[tuple[str, str], ResolvedModelBinding | ModelBindingError] = {}
    stages = []
    for stage in prompt_usage_stages():
        if not stage.uses_prompt:
            stages.append(not_applicable_stage(stage))
            continue
        key = (stage.model_task, stage.capability)
        if key not in model_cache:
            model_cache[key] = await resolve_default_binding(db, user_id=user_id, stage=stage)
        stages.append(await resolve_stage_prompt(db, user_id=user_id, stage=stage, binding=model_cache[key]))
    return group_prompt_usage(stages)
```

`resolve_stage_prompt` must call `select_prompt_skill_for_model` with the resolved provider code, API model ID, capabilities, output contract, and prompt stage. Convert internal routing codes to Chinese `source_label` and `message` in the backend response.

- [ ] **Step 5: Add thin authenticated API routes**

```python
@router.get("/prompt-usage-map")
async def prompt_usage_map(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await get_prompt_usage_map(db, user_id=user_id)
```

Include `prompt_usage.router` from `api/__init__.py`. Reject unknown stages with a Chinese 404 response and reject unpublished or incompatible preview profiles with a Chinese 422 response.

- [ ] **Step 6: Run backend tests and verify GREEN**

Run: `cd backend && python3 -m pytest -q tests/test_prompt_usage_contract.py tests/test_prompt_usage_map.py tests/test_prompt_profile_versioning.py`

Expected: all targeted tests pass; the response contains no credential fields.

- [ ] **Step 7: Commit the read-only backend slice**

```bash
git add backend/app/features/model_config/prompt_usage_contract.py backend/app/features/model_config/prompt_usage_repository.py backend/app/features/model_config/prompt_usage.py backend/app/features/model_config/api/prompt_usage.py backend/app/features/model_config/api/__init__.py backend/tests/test_prompt_usage_contract.py backend/tests/test_prompt_usage_map.py
git commit -m "feat: expose effective prompt usage map"
```

---

### Task 3: Create a safe model-specific Prompt draft from the selected published template

**Files:**
- Modify: `backend/app/features/model_config/prompt_usage_repository.py`
- Modify: `backend/app/features/model_config/prompt_usage.py`
- Modify: `backend/app/features/model_config/api/prompt_usage.py`
- Modify: `backend/tests/test_prompt_usage_map.py`

**Interfaces:**
- Produces: `list_prompt_usage_candidates(db, *, user_id, stage_id) -> dict`.
- Produces: `create_prompt_usage_assignment_draft(db, *, user_id, stage_id, prompt_version_id, reason) -> dict`.
- HTTP: `GET /prompt-usage-map/stages/{stage_id}/candidates` and `POST /prompt-usage-map/stages/{stage_id}/assignment-drafts`.
- Assignment creates a draft only; existing preview and publish APIs remain the publication owner.

- [ ] **Step 1: Write failing candidate and assignment tests**

```python
@pytest.mark.asyncio
async def test_candidates_only_include_published_templates_for_the_same_prompt_task(client):
    response = await client.get(
        "/api/v1/model-center/prompt-usage-map/stages/shot_video/candidates"
    )
    assert response.status_code == 200
    assert {item["task"] for item in response.json()["items"]} == {"shot_video"}
    assert {item["status"] for item in response.json()["items"]} == {"published"}


@pytest.mark.asyncio
async def test_assignment_creates_draft_with_exact_current_model_route(client):
    response = await client.post(
        "/api/v1/model-center/prompt-usage-map/stages/shot_video/assignment-drafts",
        json={"prompt_version_id": "prompt-video-generic-v2", "reason": "用于默认视频模型"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["routing"]["model_filter"] == ["seedance-2-0"]
```

Add a negative test proving that a `script_generation` template cannot be assigned to `shot_video`.

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd backend && python3 -m pytest -q tests/test_prompt_usage_map.py -k 'candidate or assignment'`

Expected: endpoints are not registered.

- [ ] **Step 3: Implement candidate loading and immutable draft creation**

Load the selected published `PromptProfileVersion` together with its `PromptProfile`, verify `profile.task == stage.prompt_task`, copy its content/variables/evaluation, and merge exact current model routing on the server:

```python
routing = {
    **dict(source.routing or {}),
    "provider_filter": [model.provider_code],
    "model_filter": [model.api_model_id],
}
```

Create a new immutable draft through the existing Prompt Profile versioning owner. Store the Chinese reason in release notes or the existing audit path; do not publish automatically.

- [ ] **Step 4: Verify assignment tests and existing version guards**

Run: `cd backend && python3 -m pytest -q tests/test_prompt_usage_map.py tests/test_prompt_profile_versioning.py tests/test_model_center_version_guards.py`

Expected: all tests pass; published rows remain immutable.

- [ ] **Step 5: Commit the assignment slice**

```bash
git add backend/app/features/model_config/prompt_usage_repository.py backend/app/features/model_config/prompt_usage.py backend/app/features/model_config/api/prompt_usage.py backend/tests/test_prompt_usage_map.py
git commit -m "feat: create model-specific prompt drafts"
```

---

### Task 4: Add the frontend Prompt Usage data boundary

**Files:**
- Create: `frontend/src/features/model-center/prompt-usage-types.ts`
- Create: `frontend/src/features/model-center/prompt-usage-api.ts`
- Create: `frontend/src/features/model-center/hooks/use-prompt-usage-map.ts`
- Create: `frontend/e2e/model-center-prompt-usage-map.spec.ts`

**Interfaces:**
- Produces: `PromptUsageMap`, `PromptUsageStage`, `PromptUsageCandidate`, and strict parser functions.
- Produces: `promptUsageApi.getMap()`, `.previewStage(stageId, profileVersionId)`, `.listCandidates(stageId)`, `.createAssignmentDraft(stageId, input)`.
- Produces hook state `{data, loading, error, selectedStageId, problemsOnly, refresh, selectStage, toggleProblemsOnly}`.

- [ ] **Step 1: Write the failing map-loading browser test**

```typescript
test('opens the prompt usage map before the template library', async ({ page }) => {
  await mockPromptUsageMap(page);
  await page.goto('/llm-config?section=prompts');
  await expect(page.getByRole('heading', { name: '提示词使用地图' })).toBeVisible();
  await expect(page.getByText('分镜生成')).toBeVisible();
  await expect(page.getByText('标准分镜创建 · v3')).toBeVisible();
  await expect(page.getByText('模型专用覆盖')).toBeVisible();
  await expect(page.getByText('此环节不使用提示词模板。')).toBeVisible();
  await expect(page.getByLabel('输入映射 JSON')).toHaveCount(0);
});
```

- [ ] **Step 2: Run the E2E test and verify RED**

Run: `cd frontend && npx playwright test e2e/model-center-prompt-usage-map.spec.ts --project=chromium --workers=1`

Expected: the existing version workbench appears and the map heading is missing.

- [ ] **Step 3: Implement strict types and API parsing**

```typescript
export type PromptUsageStatus =
  | 'effective' | 'overridden' | 'internal_fallback'
  | 'invalid_binding' | 'not_applicable';

export interface PromptUsageStage {
  id: string;
  name: string;
  status: PromptUsageStatus;
  message: string;
  model: PromptUsageModel | null;
  template: PromptUsageTemplate | null;
  routing: PromptUsageRouting;
}
```

Reject malformed status values and missing group/stage arrays with the Chinese error `提示词使用地图响应无效`.

- [ ] **Step 4: Implement the query hook with stale-request protection**

Use a monotonically increasing request token. Only the newest `refresh()` or model preview response may update state. Select the first issue stage when problem-only mode is enabled and the previous selection is hidden.

- [ ] **Step 5: Run TypeScript verification**

Run: `cd frontend && npm run typecheck`

Expected: typecheck passes. The E2E still fails only because the map components are not connected yet.

- [ ] **Step 6: Commit the frontend data slice**

```bash
git add frontend/src/features/model-center/prompt-usage-types.ts frontend/src/features/model-center/prompt-usage-api.ts frontend/src/features/model-center/hooks/use-prompt-usage-map.ts frontend/e2e/model-center-prompt-usage-map.spec.ts
git commit -m "feat: add prompt usage map client"
```

---

### Task 5: Build the production-flow map and preserve the template library

**Files:**
- Create: `frontend/src/features/model-center/components/prompt-usage-summary.tsx`
- Create: `frontend/src/features/model-center/components/prompt-usage-stage-list.tsx`
- Create: `frontend/src/features/model-center/components/prompt-usage-detail.tsx`
- Create: `frontend/src/features/model-center/components/prompt-usage-map.tsx`
- Modify: `frontend/src/features/model-center/components/prompt-profile-list.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-management-panel.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-shell.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-rail.tsx`
- Modify: `frontend/e2e/model-center-prompt-usage-map.spec.ts`

**Interfaces:**
- Consumes the hook and API boundary from Task 4.
- `PromptUsageMap` owns only view mode (`map` or `library`) and selected profile handoff.
- `PromptProfileList` adds `initialSelectedId?: string | null` without changing existing default behavior.

- [ ] **Step 1: Extend the failing E2E with hierarchy and filtering assertions**

```typescript
await expect(page.getByTestId('prompt-usage-summary')).toContainText('12 个环节');
await expect(page.getByRole('button', { name: '只看问题环节' })).toBeVisible();
await page.getByRole('button', { name: '只看问题环节' }).click();
await expect(page.getByText('场景/道具提取')).toBeVisible();
await expect(page.getByText('剧本生成')).toHaveCount(0);
await page.getByRole('button', { name: '模板库' }).click();
await expect(page.getByText('提示词版本工作台')).toBeVisible();
```

- [ ] **Step 2: Implement compact summary and grouped stage list**

Status labels must be literal Chinese mappings owned by the backend response. Frontend color mapping is presentation-only:

- `effective`: green
- `overridden`: violet
- `internal_fallback`: amber
- `invalid_binding`: red
- `not_applicable`: neutral gray

- [ ] **Step 3: Implement the detail panel**

Show template name/version, model, and the backend-provided Chinese source label/message. Render `<details>` titled `高级设置` containing read-only effective version identifiers and a button `在模板库编辑`; template content remains owned by the template library because built-in routed templates do not necessarily have a legacy Prompt Profile detail resource.

- [ ] **Step 4: Switch the prompts section to the map**

```tsx
if (section === 'prompts') return <PromptUsageMap location={location} />;
```

Update the heading to `提示词使用地图` / `查看每个生产环节当前实际使用的模板、模型和覆盖来源。` Hide the catalog capability filter bar when `section === 'prompts'` and change the rail description to `生产环节实际使用`.

- [ ] **Step 5: Run the map E2E and typecheck**

Run: `cd frontend && npx playwright test e2e/model-center-prompt-usage-map.spec.ts --project=chromium --workers=1`

Run: `cd frontend && npm run typecheck`

Expected: map, filtering, detail, advanced disclosure, and template-library handoff pass.

- [ ] **Step 6: Commit the read-only UI slice**

```bash
git add frontend/src/features/model-center/components/prompt-usage-summary.tsx frontend/src/features/model-center/components/prompt-usage-stage-list.tsx frontend/src/features/model-center/components/prompt-usage-detail.tsx frontend/src/features/model-center/components/prompt-usage-map.tsx frontend/src/features/model-center/components/prompt-profile-list.tsx frontend/src/features/model-center/components/model-center-management-panel.tsx frontend/src/features/model-center/components/model-center-shell.tsx frontend/src/features/model-center/components/model-center-rail.tsx frontend/e2e/model-center-prompt-usage-map.spec.ts
git commit -m "feat: make prompt usage map the default view"
```

---

### Task 6: Connect model preview and safe template replacement

**Files:**
- Create: `frontend/src/features/model-center/components/prompt-usage-assignment-dialog.tsx`
- Modify: `frontend/src/features/model-center/components/prompt-usage-detail.tsx`
- Modify: `frontend/src/features/model-center/components/prompt-usage-map.tsx`
- Modify: `frontend/e2e/model-center-prompt-usage-map.spec.ts`

**Interfaces:**
- Assignment dialog consumes candidates from Task 3 and returns the created draft profile ID.
- The map switches to the template library with that profile selected; existing preview and publish controls remain authoritative.

- [ ] **Step 1: Write the failing assignment flow E2E**

```typescript
await page.getByText('镜头视频').click();
await page.getByRole('button', { name: '更换模板' }).click();
await page.getByLabel('选择已发布模板').selectOption('prompt-video-generic-v2');
await page.getByRole('button', { name: '创建模型专用草稿' }).click();
await expect.poll(() => assignmentRequests.length).toBe(1);
expect(assignmentRequests[0]).toEqual({
  prompt_version_id: 'prompt-video-generic-v2',
  reason: '用于当前默认镜头视频模型',
});
await expect(page.getByText('提示词版本工作台')).toBeVisible();
await expect(page.getByRole('button', { name: '发布此版本' })).toBeVisible();
```

- [ ] **Step 2: Run the assignment E2E and verify RED**

Run: `cd frontend && npx playwright test e2e/model-center-prompt-usage-map.spec.ts --project=chromium --workers=1 --grep '更换模板'`

Expected: the `更换模板` button or dialog is missing.

- [ ] **Step 3: Implement the assignment dialog and model preview**

The dialog must explain in Chinese:

> 将基于所选已发布模板创建当前模型专用草稿。生产任务不会改变，直到你预览并发布该草稿。

Do not expose `model_filter`, `provider_filter`, `routing_reason`, or other internal codes in the UI. On success, switch to the template library and select the returned profile.

- [ ] **Step 4: Refresh map state after existing publish completion**

Pass an `onPublished` callback through the library wrapper so successful publication returns to the map and calls `refresh()`. Assert that historical jobs are not mutated and only subsequent routing changes.

- [ ] **Step 5: Run assignment, legacy Prompt workbench, and type tests**

Run: `cd frontend && npx playwright test e2e/model-center-prompt-usage-map.spec.ts e2e/model-center-prompts.spec.ts --project=chromium --workers=1`

Run: `cd frontend && npm run typecheck`

Expected: both the new map and the preserved legacy workbench pass.

- [ ] **Step 6: Commit the interaction slice**

```bash
git add frontend/src/features/model-center/components/prompt-usage-assignment-dialog.tsx frontend/src/features/model-center/components/prompt-usage-detail.tsx frontend/src/features/model-center/components/prompt-usage-map.tsx frontend/src/features/model-center/components/prompt-profile-list.tsx frontend/e2e/model-center-prompt-usage-map.spec.ts
git commit -m "feat: simplify prompt template replacement"
```

---

### Task 7: Integrated verification, visual acceptance, and operator handoff

**Files:**
- Modify only if verification finds a task-related defect in files already listed above.
- Update: `docs/superpowers/plans/2026-08-07-prompt-usage-map-redesign.md` with actual verification results.

**Interfaces:**
- Consumes all prior tasks.
- Produces final verified implementation evidence and browser screenshots of the default map, problem-only mode, stage detail, and template assignment dialog.

- [x] **Step 1: Run fresh backend verification**

Run: `cd backend && python3 -m pytest -q tests/test_prompt_usage_contract.py tests/test_prompt_usage_map.py tests/test_prompt_profile_versioning.py tests/test_model_center_version_guards.py tests/test_model_center_api.py`

Expected: all selected backend tests pass.

- [x] **Step 2: Run fresh frontend verification**

Run: `cd frontend && npm run typecheck`

Run: `cd frontend && NEXT_DIST_DIR=.next-prompt-usage-map npm run build`

Run: `cd frontend && npx playwright test e2e/model-center-prompt-usage-map.spec.ts e2e/model-center-prompts.spec.ts e2e/model-center-config.spec.ts --project=chromium --workers=1`

Expected: typecheck, build, and selected browser suites pass.

- [x] **Step 3: Perform manual code-health ratchet checks**

Run: `git diff --check`

Run: `wc -l backend/app/features/model_config/prompt_usage_contract.py backend/app/features/model_config/prompt_usage_repository.py backend/app/features/model_config/prompt_usage.py backend/app/features/model_config/api/prompt_usage.py frontend/src/features/model-center/components/prompt-usage-*.tsx`

Expected: no whitespace errors; no new production file exceeds 500 lines; each new feature component remains below 200 lines; no existing >500-line hotspot grows.

The repository currently has no active `verify:code-health` npm script, so record the manual evidence rather than claiming an unavailable check passed.

- [x] **Step 4: Capture browser-visible acceptance evidence**

Use Playwright against the running frontend to capture:

- Default prompt usage map with all four production groups.
- Problem-only filtered state.
- Effective stage detail showing template, version, model, and Chinese source explanation.
- Template replacement dialog explaining that publication is required before production changes.

Save screenshots under `output/prompt-usage-map-acceptance/` and report their absolute paths.

- [x] **Step 5: Verify service health**

Run: `curl -fsS http://localhost:8000/docs -o /dev/null`

Run: `curl -fsS http://localhost:3000/llm-config?section=prompts -o /dev/null`

Expected: both commands exit 0.

- [x] **Step 6: Commit verification evidence only if the plan file is updated**

```bash
git add docs/superpowers/plans/2026-08-07-prompt-usage-map-redesign.md
git commit -m "docs: record prompt usage map verification"
```

Do not commit generated screenshots, `.next-*` build directories, media outputs, or unrelated dirty-worktree files.

---

## Acceptance Checklist

- [x] The Prompt section opens on the production-flow map, not raw JSON fields.
- [x] All 12 stages appear in stable production order.
- [x] Each routed stage shows the actual default model and canonical Prompt selection.
- [x] Subtitle and synthesis explicitly say they do not use Prompt templates.
- [x] Exact-model, model-family, provider, capability, generic, and internal-fallback outcomes have Chinese explanations.
- [x] Problem-only filtering works without losing the current valid selection.
- [x] Advanced fields remain collapsed by default.
- [x] The existing template library, AI optimization, preview, publish, history, diff, rollback, and legacy actions remain reachable.
- [x] Template replacement creates a draft and never silently changes production.
- [x] Publishing refreshes the map and affects only subsequent tasks.
- [x] No credentials or raw provider error bodies appear in map responses or UI.
- [x] Targeted backend tests, frontend typecheck/build, and Playwright suites pass.
- [x] New files and modified hotspots satisfy the manual code-health ratchet.

## Verification Results (2026-08-08)

- Backend targeted suite: `95 passed in 13.39s`.
- Frontend: `npm run typecheck` passed; the production build compiled and generated all 46 pages.
- Browser regression: 14 Chromium tests passed across the Prompt Usage Map, legacy Prompt workbench, and Model Center configuration flows.
- Live browser acceptance: 12 stages render in four groups; problem filtering, detail selection, Chinese explanations, template-library handoff, and the draft-only replacement dialog work against the running services.
- Historical recovery duplicates are collapsed by normalized profile key; candidate choices identify `当前账号` and `系统内置` in Chinese.
- Code health: new backend files are at most 254 lines; new Prompt Usage components are at most 60 lines; `git diff --check` passed.
- Service health: backend port 8000 and frontend port 3000 both returned successful responses.
- Evidence screenshots: `output/playwright/prompt-usage-map/01-default-map-light.png`, `02-problems-only-light.png`, and `03-assignment-dialog-light.png` (generated artifacts, intentionally not committed).
