# Studio 人工处理上下文修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让工作室的每个阻断项都进入与当前小说、章节、工作流一致的可操作页面，并让 Story Bible 页面只展示和处理当前小说的数据。

**Architecture:** 在 Studio 前端用一个纯函数把阻断代码转换为中文处理说明、按钮和目标入口，侧栏逐项呈现而不再合并成一个泛化按钮。Story Bible 页面消费现有 URL 上下文，调用已有 `novel_id` 过滤接口，并把列表展示抽到独立组件以遵守大型页面只减不增的约束。

**Tech Stack:** Next.js 14、React 18、TypeScript、Playwright。

## Global Constraints

- 不修改现有后端数据、历史 Story Bible 或工作流状态。
- 所有跳转保留 `workflow_id`、`novel_id`、`chapter_id`、`source=studio` 和安全的 `return_to`。
- 页面只显示中文直白说明，不暴露内部错误代码作为主要文案。
- `frontend/src/app/story-bibles/page.tsx` 当前超过 800 行，本次修改后不得增长。

---

### Task 1: 逐项人工处理入口

**Files:**
- Create: `frontend/src/lib/studio-repair-options.ts`
- Modify: `frontend/src/components/studio/studio-episode-sidebar.tsx`
- Modify: `frontend/src/lib/studio-quick-actions.ts`
- Test: `frontend/e2e/studio-manual-repair.spec.ts`

**Interfaces:**
- Consumes: `StudioIssue`, `StudioSnapshot`, `withStudioQuickAction()`。
- Produces: `buildStudioRepairOption(issue, snapshot)`，返回中文标题、处理说明、按钮名称和带上下文链接。

- [x] **Step 1: Write the failing test**

创建含“缺分镜、缺 Story Bible、缺镜头”三个阻断项的工作室快照，断言侧栏逐项显示三个中文动作，并断言 Story Bible 动作链接包含当前工作流、小说、章节、来源问题和返回地址。

- [x] **Step 2: Run test to verify it fails**

Run: `npx playwright test e2e/studio-manual-repair.spec.ts --project=chromium --workers=1`

Expected: FAIL，因为当前侧栏只有一个“人工处理”按钮。

- [x] **Step 3: Write minimal implementation**

实现阻断项到处理入口的纯函数；侧栏标题改为“待处理事项”，每项展示原因、下一步和独立按钮。

- [x] **Step 4: Run test to verify it passes**

Run: `npx playwright test e2e/studio-manual-repair.spec.ts --project=chromium --workers=1`

Expected: PASS。

### Task 2: 当前小说 Story Bible 处理页

**Files:**
- Create: `frontend/src/features/story-bibles/story-bible-list-panel.tsx`
- Modify: `frontend/src/app/story-bibles/page.tsx`
- Test: `frontend/e2e/studio-manual-repair.spec.ts`

**Interfaces:**
- Consumes: URL 参数 `novel_id`、`action=create`、`source_issue_code`、`return_to`。
- Produces: 仅当前小说的 Story Bible 列表、小说名称、内容完整度、自动选择或生成入口。

- [x] **Step 1: Extend the failing test**

点击“为当前小说生成设定”，断言请求为 `/story-bibles?novel_id=novel-repair`，页面显示当前小说名称，且无可用版本时自动打开已预选小说的生成窗口。

- [x] **Step 2: Run test to verify it fails**

Run: `npx playwright test e2e/studio-manual-repair.spec.ts --project=chromium --workers=1`

Expected: FAIL，因为当前页面请求未带 `novel_id`，也不会消费处理上下文。

- [x] **Step 3: Write minimal implementation**

读取 URL 上下文并过滤 API 请求；抽出列表组件，明确显示关联小说、角色/场景/道具/事件数量和“内容为空/可使用”状态；没有版本时自动打开当前小说的生成窗口。

- [x] **Step 4: Run test to verify it passes**

Run: `npx playwright test e2e/studio-manual-repair.spec.ts --project=chromium --workers=1`

Expected: PASS。

### Task 3: 集成验证与平滑部署

**Files:**
- Verify only: affected frontend files and running frontend container.

- [x] **Step 1: Run targeted verification**

Run: `npm run typecheck && npx playwright test e2e/studio-manual-repair.spec.ts e2e/studio-smart-console.spec.ts --project=chromium --workers=1`

- [x] **Step 2: Build production frontend**

Run: `NEXT_PUBLIC_API_URL=/api/v1 API_PROXY_TARGET=http://host.docker.internal:8000 NEXT_DIST_DIR=.next-studio-repair npm run build`

- [x] **Step 3: Canary and deploy**

先在独立端口验证 `/studio`、带小说上下文的 `/story-bibles` 和 API 代理，再切换正式前端容器；保留当前镜像和容器用于回滚。
