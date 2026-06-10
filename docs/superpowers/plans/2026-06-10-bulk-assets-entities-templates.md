# 资产实体模板批量维护 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为资产、实体、创作模板、提示词/技能模板补齐批量维护能力，并支持资产/实体按小说或剧本重新抽取。

**Status:** 已落地并通过后端回归、前端构建、组合 E2E 验证。

**Architecture:** 后端新增轻量批量动作接口，复用现有 ORM、实体抽取、资产生成和提示词模板服务。前端复用现有列表页选择态和 toast/message 反馈，避免新增独立批量任务系统。

**Tech Stack:** FastAPI、SQLAlchemy AsyncSession、Pydantic、Next.js 14、React、TypeScript、Playwright。

---

### Task 1: 后端批量维护接口测试

**Files:**
- Create: `backend/tests/test_bulk_maintenance_actions.py`
- Modify: none

- [ ] **Step 1: 写失败测试**

测试覆盖资产批量归档跳过锁定资产、实体覆盖重抽保留 ID、创作模板批量复制预置模板、提示词技能批量删除阻断激活模板。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/test_bulk_maintenance_actions.py -q`

Expected: FAIL，原因是 bulk-action 和 reextract 接口/服务函数尚不存在。

### Task 2: 后端资产批量动作

**Files:**
- Modify: `backend/app/api/v1/endpoints/assets.py`
- Test: `backend/tests/test_bulk_maintenance_actions.py`

- [ ] **Step 1: 实现 `AssetBulkActionRequest` 和 `AssetBulkActionResponse`**

字段包括 `asset_ids`、`action`、`scope`、`tags`、`allow_test_override`、各类 scope id。

- [ ] **Step 2: 实现 `POST /assets/bulk-action`**

支持 `archive`、`lock`、`unlock`、`set_scope`、`set_tags`。生产模式跳过锁定资产归档，测试模式允许跳过但返回 warnings。

- [ ] **Step 3: 跑资产相关测试**

Run: `cd backend && pytest tests/test_bulk_maintenance_actions.py -q`

Expected: 资产批量测试 PASS，其它未实现测试仍 FAIL。

### Task 3: 后端实体批量动作与重抽

**Files:**
- Modify: `backend/app/api/v1/endpoints/story_bible.py`
- Test: `backend/tests/test_bulk_maintenance_actions.py`

- [ ] **Step 1: 实现 `EntityBulkActionRequest` 和响应**

支持 `delete`、`approve`、`set_scope`、`set_tags`。

- [ ] **Step 2: 实现 `POST /story-bibles/entities/bulk-action`**

删除时同步软归档该实体的非锁定资产；锁定资产默认跳过并返回修复提示。

- [ ] **Step 3: 实现 `POST /story-bibles/entities/reextract`**

支持 `append`、`overwrite`、`delete_then_extract` 三种模式。`overwrite` 按 `entity_type + canonical_name/name` 更新，不替换实体 ID。

- [ ] **Step 4: 跑实体相关测试**

Run: `cd backend && pytest tests/test_bulk_maintenance_actions.py -q`

Expected: 实体批量和重抽测试 PASS。

### Task 4: 后端模板批量动作

**Files:**
- Modify: `backend/app/api/v1/endpoints/templates.py`
- Modify: `backend/app/api/v1/endpoints/prompt_skills.py`
- Modify: `backend/app/services/prompt_skill_service.py`
- Test: `backend/tests/test_bulk_maintenance_actions.py`

- [ ] **Step 1: 实现创作模板 `POST /templates/bulk-action`**

支持 `delete`、`clone`、`set_category`、`set_tags`、`set_public`。预置模板删除必须跳过并返回阻断原因。

- [ ] **Step 2: 实现提示词技能 `POST /prompt-skills/bulk-action`**

支持 `delete`、`clone`、`set_tags`。内置模板删除跳过，激活模板删除跳过，克隆允许批量执行。

- [ ] **Step 3: 跑模板相关测试**

Run: `cd backend && pytest tests/test_bulk_maintenance_actions.py -q`

Expected: 全部后端批量测试 PASS。

### Task 5: 前端 API Client

**Files:**
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/prompt-skills-api.ts`

- [ ] **Step 1: 增加批量 API 方法**

添加 `bulkActionAssets`、`bulkActionStoryEntities`、`reextractStoryEntities`、`bulkActionTemplates`、`bulkActionPromptSkills`。

- [ ] **Step 2: 类型保持宽松**

返回值用现有页面可消费的对象结构，避免引入大规模类型迁移。

### Task 6: 前端资产与实体批量工具条

**Files:**
- Modify: `frontend/src/app/assets/page.tsx`
- Modify: `frontend/src/app/entities/page.tsx`
- Test: `frontend/e2e/assets.spec.ts`
- Test: `frontend/e2e/entities-multiview.spec.ts`

- [ ] **Step 1: 写 E2E 失败测试**

断言选择资产后出现“批量归档/批量解锁”，选择实体后出现“批量删除/重新抽取”。

- [ ] **Step 2: 接入工具条按钮**

复用已有 `selectedAssets`、`selectedEntities`，调用新增 API 后刷新列表。

- [ ] **Step 3: 跑 E2E**

Run: `cd frontend && npx playwright test e2e/assets.spec.ts e2e/entities-multiview.spec.ts --project=chromium --workers=1`

Expected: PASS。

### Task 7: 前端模板与提示词技能批量工具条

**Files:**
- Modify: `frontend/src/app/templates/page.tsx`
- Modify: `frontend/src/app/prompt-skills/page.tsx`
- Test: `frontend/e2e/templates.spec.ts`
- Test: `frontend/e2e/prompt-skills.spec.ts`

- [ ] **Step 1: 写 E2E 失败测试**

断言模板和提示词技能选中后出现批量操作工具条，并显示内置/预置不可删除提示。

- [ ] **Step 2: 接入批量操作**

创作模板和提示词模板保持入口分离，但交互文案统一为“已选择 N 项”和“不可处理项原因”。

- [ ] **Step 3: 跑 E2E**

Run: `cd frontend && npx playwright test e2e/templates.spec.ts e2e/prompt-skills.spec.ts --project=chromium --workers=1`

Expected: PASS。

### Task 8: 回归与稳定点

**Files:**
- All changed files

- [ ] **Step 1: 后端测试**

Run: `cd backend && pytest tests/test_bulk_maintenance_actions.py tests/test_entity_extraction_classification.py -q`

Expected: PASS。

- [ ] **Step 2: 前端构建**

Run: `cd frontend && npm run build`

Expected: PASS。

- [ ] **Step 3: 前端组合回归**

Run: `cd frontend && npx playwright test e2e/assets.spec.ts e2e/entities-multiview.spec.ts e2e/templates.spec.ts e2e/prompt-skills.spec.ts --project=chromium --workers=1`

Expected: PASS。

- [ ] **Step 4: 提交稳定点**

只 stage 本轮改动文件，提交信息：`feat: add bulk maintenance and reextract controls`。
