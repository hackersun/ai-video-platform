# 模型中心易用性与安全移除实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让供应商账号、模型目录和组合预设在常见桌面宽度下排版稳定，并把生产策略、默认模型选择和账号移除改成普通用户能理解且不会破坏历史数据的操作。

**Architecture:** 供应商账号采用“安全移除”而不是物理删除：后端在账号仍被启用绑定引用时拒绝操作，否则停用账号、清除密钥、保留审计历史并从正常列表隐藏。前端复用已有 `production-strategy.ts` 中文文案，并直接使用绑定接口已返回的模型、供应商和账号名称，不再通过目录分页二次反查名称。

**Tech Stack:** FastAPI、SQLAlchemy、Next.js 14、React、TypeScript、Tailwind CSS、pytest、Playwright。

## Global Constraints

- 不物理删除模型连接、模型版本、能力绑定、组合预设、认证历史或执行快照。
- 已发布模型版本保持不可变；本批次不新增模型版本删除或全局停用能力。
- 不改变现有生产策略枚举和已保存方案的运行时含义。
- 不修改用户当前未提交的原生音频能力字段与绑定编辑器行为。
- 不向已达 500 行的 `frontend/src/app/globals.css` 或超过 500 行的 `backend/app/features/model_config/management.py` 增加代码。
- 新行为先写失败测试，再做最小实现。

## Intent Lock

模型中心只展示用户做决定所需的业务名称，把 UUID、英文枚举、作用域和驱动细节留在详情或服务端，同时为账号清理提供可审计、可阻断的安全入口。

## Scope Boundaries

- 包含：供应商账号安全移除、账号/目录表格不换行与横向滚动、策略中文名称与说明、生产步骤模型下拉的人类可读标签。
- 不包含：模型物理删除、多租户模型所有权重构、组合预设物理删除、全站设计系统重做、数据库迁移。

## Acceptance Criteria

1. 未被启用默认模型引用的账号可以从界面移除；密钥被清空、账号从正常列表消失、审计事件保留。
2. 被启用默认模型引用的账号不能移除，界面明确说明需要先更换对应默认模型。
3. 供应商账号和模型目录在 1440px 桌面视口中，状态与操作按钮不逐字换行、不越出卡片；更窄视口可以横向滚动。
4. 组合预设列表与编辑器不再显示 `final_quality`、`direct_av_first` 等裸枚举，而显示既有中文名称和一句用途说明。
5. 新建方案只把“快速预览 / 高质量成片 / 低成本试错”作为生产目标；声音方式单独用中文单选项表达，避免同一概念出现两次。
6. 生产步骤下拉显示“模型名称（供应商 · 账号名称）”，不显示 profile UUID 或 `user 作用域`。
7. 现有 recipe spec 字段、策略值、binding id 和 API 返回保持兼容。

## Verification Commands

```bash
python3 -m pytest backend/tests/test_model_center_api.py -q

cd frontend
npx playwright test e2e/model-center-recovery.spec.ts e2e/model-center-recipes.spec.ts --project=chromium
npm run build

cd ..
git diff --check
```

---

### Task 1: 锁定账号安全移除契约

**Files:**
- Modify: `backend/tests/test_model_center_api.py`
- Modify: `backend/app/features/model_config/connection_management_repository.py`
- Create: `backend/app/features/model_config/connection_lifecycle.py`
- Modify: `backend/app/features/model_config/api/service.py`
- Modify: `backend/app/features/model_config/api/connections.py`
- Modify: `backend/app/features/model_config/management_repository.py`

**Interfaces:**
- Consumes: `PublishRequest(expected_revision: int, reason: str)`
- Produces: `remove_connection(db, *, user_id, connection_id, expected_revision, reason) -> dict`
- Produces: `DELETE /api/v1/model-center/connections/{connection_id}`

- [x] **Step 1: Write failing lifecycle tests**

Create isolated tests proving:

```python
async def test_remove_unused_connection_clears_secrets_and_hides_row():
    response = await client.delete(
        f"/api/v1/model-center/connections/{connection_id}",
        json={"expected_revision": 1, "reason": "清理重复账号"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert await load_secret(connection_id) in {None, ""}
    assert connection_id not in await listed_connection_ids()
    assert await latest_audit_action(connection_id) == "remove"

async def test_remove_connection_rejects_active_binding():
    response = await client.delete(
        f"/api/v1/model-center/connections/{connection_id}",
        json={"expected_revision": 1, "reason": "清理重复账号"},
    )
    assert response.status_code == 409
    assert "默认模型" in response.json()["detail"]["message"]
```

- [x] **Step 2: Run tests and verify RED**

Run: `cd backend && python3 -m pytest tests/test_model_center_connection_lifecycle.py -q`

Expected: FAIL because the DELETE route and lifecycle use case do not exist.

- [x] **Step 3: Implement repository-level conditional removal**

In `connection_management_repository.py`, count active `ModelBinding` rows for the user and connection. If the count is zero, update the matching revision to `status="disabled"`, clear `api_key` and `api_secret`, increment revision, and append a sanitized `ModelConfigAuditEvent(action="remove")`. Return an outcome containing the active-binding count and resulting revision; never return or log credentials.

- [x] **Step 4: Add the focused lifecycle use case and thin route**

`connection_lifecycle.py` owns the transaction and maps `not found`, revision conflict, and active binding usage to `ManagementOperationError`. The route only validates `PublishRequest`, invokes the use case, and maps the existing domain error through `raise_http`.

- [x] **Step 5: Hide disabled connections from normal lists**

Add `ModelConnection.status != "disabled"` to both `connection_page` and overview connection queries. Historical certification and execution rows remain unchanged.

- [x] **Step 6: Run lifecycle tests and verify GREEN**

Run: `cd backend && python3 -m pytest tests/test_model_center_connection_lifecycle.py -q`

Expected: all tests pass.

### Task 2: Add a clear account removal interaction

**Files:**
- Create: `frontend/src/features/model-center/components/remove-connection-dialog.tsx`
- Modify: `frontend/src/features/model-center/api.ts`
- Modify: `frontend/src/features/model-center/hooks/use-model-connections.ts`
- Modify: `frontend/src/features/model-center/components/model-center-connections-panel.tsx`
- Modify: `frontend/e2e/model-center-recovery.spec.ts`

**Interfaces:**
- Consumes: `DELETE /model-center/connections/{id}`
- Produces: `removeConnection(id, { expected_revision, reason })`

- [x] **Step 1: Write failing Playwright tests**

Cover the visible flow:

```ts
test('unused provider account can be safely removed', async ({ page }) => {
  await page.goto('/llm-config?section=connections');
  await page.getByRole('button', { name: '移除生产套餐' }).click();
  await page.getByLabel('移除原因').fill('清理重复账号');
  await page.getByRole('button', { name: '确认移除账号' }).click();
  await expect(page.getByText('账号已移除，密钥已清除')).toBeVisible();
});

test('active account removal explains how to recover', async ({ page }) => {
  // mock DELETE as 409 resource_in_use
  await expect(page.getByText('请先到“默认模型”更换相关模型')).toBeVisible();
});
```

- [x] **Step 2: Run the new spec and verify RED**

Run: `cd frontend && npx playwright test e2e/model-center-usability.spec.ts --project=chromium`

Expected: FAIL because there is no remove action or dialog.

- [x] **Step 3: Implement the accessible confirmation dialog**

The dialog shows account name, explains that credentials will be cleared but history retained, requires a two-character reason, and exposes Cancel/Confirm actions. It must use `role="dialog"`, `aria-modal="true"`, an explicit accessible name, and a disabled pending state.

- [x] **Step 4: Wire mutation and refresh**

Add the API/hook mutation, invalidate connection/catalog/binding/readiness queries through the existing mutation store, close the dialog on success, and render the server's conflict message without converting it to internal error codes.

- [x] **Step 5: Run removal UI tests and verify GREEN**

Run: `cd frontend && npx playwright test e2e/model-center-usability.spec.ts --project=chromium -g 'account'`

Expected: all account-removal tests pass.

### Task 3: Stabilize account and catalog table layout

**Files:**
- Modify: `frontend/src/features/model-center/components/model-center-connections-panel.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-catalog-panel.tsx`
- Test: `frontend/e2e/model-center-recovery.spec.ts`

**Interfaces:**
- Preserves all list and navigation APIs.

- [x] **Step 1: Add a failing 1440px layout test**

At `1440x1000`, assert the credentials/status text and every action button have one visual line, and the right edge of the operation group remains within the table scroll container. At `1024x800`, assert the table container reports horizontal overflow instead of shrinking labels character by character.

- [x] **Step 2: Run the layout test and verify RED**

Run: `cd frontend && npx playwright test e2e/model-center-usability.spec.ts --project=chromium -g 'layout'`

Expected: FAIL because action text currently wraps and catalog columns have no minimum width.

- [x] **Step 3: Apply component-scoped layout constraints**

Use explicit table minimum widths, `whitespace-nowrap` on status/action cells and buttons, `shrink-0` on icons, and `flex-nowrap` for action groups. Keep descriptive cells wrappable and retain `overflow-x-auto`; do not grow `globals.css`.

- [x] **Step 4: Re-run the layout test and capture screenshots**

Run the Playwright layout cases and save accepted `connections-1440.png` and `catalog-1440.png` screenshots for visual comparison with the user-provided evidence.

### Task 4: Replace internal strategy and binding vocabulary

**Files:**
- Modify: `frontend/src/features/model-center/components/recipe-list.tsx`
- Modify: `frontend/src/features/model-center/components/recipe-editor.tsx`
- Modify: `frontend/src/features/model-center/components/recipe-pipeline.tsx`
- Test: `frontend/e2e/model-center-recovery.spec.ts`
- Test: `frontend/e2e/model-center-recipes.spec.ts`

**Interfaces:**
- Consumes: `PRODUCTION_STRATEGY_COPY`, `DEFAULT_PRODUCTION_STRATEGY` from `frontend/src/lib/production-strategy.ts`
- Preserves: `ProductionRecipeInput.spec.strategy` and all binding IDs in submitted JSON.

- [x] **Step 1: Write failing copy and option-label tests**

Assert that the list renders `高质量成片` instead of `final_quality`; the editor renders the three production goals with the selected description; the audio choice and subtitle explanation are Chinese; and an option built from a UUID-valued binding displays `Seedance 2.0（火山引擎 · 主视频账号）` without UUID or `user 作用域`.

- [x] **Step 2: Run tests and verify RED**

Run: `cd frontend && npx playwright test e2e/model-center-usability.spec.ts e2e/model-center-recipes.spec.ts --project=chromium -g 'strategy|binding|native-audio'`

Expected: FAIL on raw enums, raw timeline values, and UUID fallback text.

- [x] **Step 3: Reuse the existing strategy copy owner**

Render recipe rows through `getProductionStrategyCopy`. In the new-recipe form expose `draft_fast`, `final_quality`, and `low_cost` as “生产目标”; show the selected `description` and `modelHint`. Existing `direct_av_first` and `separate_video_tts` rows remain readable through their existing Chinese copy.

- [x] **Step 4: Separate the audio decision from production target**

Replace the checkbox pair with one radio group: “视频自带声音” and “视频静音后单独配音”. Continue deriving the same `audio.mode` and `subtitle.source` values, but display only Chinese explanations to users.

- [x] **Step 5: Use resolved binding fields directly**

Remove the recipe pipeline's catalog query. Build option labels from `binding.profile_name`, `binding.provider_name`, and `connectionDisplayName(binding.connection_name, binding.provider_name)`. Keep `binding.id` only as the option value submitted to the backend.

- [x] **Step 6: Verify payload compatibility**

Re-run the existing recipe test that asserts `binding_id`, `audio.mode`, and `subtitle.source`. The submitted JSON must remain unchanged apart from the user-selected production strategy.

### Task 5: Final integration and visual acceptance

**Files:**
- Verify only; no new production files.

- [x] **Step 1: Run focused backend and frontend tests**

Run the commands in `Verification Commands` and read the complete output.

- [x] **Step 2: Run code-health checks**

Run the repository's available code-health/verification scripts. Confirm no touched production file exceeds its limit and `management.py`/`globals.css` have no net growth.

- [x] **Step 3: Browser acceptance**

From the running app, verify: supplier account removal success and blocked states; catalog operation columns at 1440px; recipe strategy descriptions; and friendly model options. Capture the four corresponding screenshots and inspect each saved image.

- [x] **Step 4: Final diff review**

Confirm that unrelated dirty-worktree files are untouched, no existing user edits were overwritten, no secrets or generated media entered the diff, and `git diff --check` passes.
