# Studio 快捷处理与集数覆盖修复计划

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 工作台每个“去处理”入口打开准确功能并携带当前制作上下文，目标页可一键返回工作台；集数导航展示小说全部章节，不再因缺少工作流而漏集。

**Architecture:** 用单一链接构造器统一追加 Studio 上下文、来源和返回地址；看板数据改为条目级动作路由。集数选项由“章节全集 + 已有工作流”合并生成，未建工作流章节明确标记为待创建，不修改任何持久化数据。

**Tech Stack:** Next.js 14、React、TypeScript、Playwright。

---

### Task 1: 用前端用例锁定回归

**Files:**
- Modify: `frontend/e2e/studio-smart-console.spec.ts`

- [x] 构造“两章、仅第一章有工作流”的 Studio API fixture。
- [x] 断言两集都展示，第二集显示未创建工程。
- [x] 断言每个快捷入口有独立地址，并重点验证字幕页参数与返回工作台链路。
- [x] 运行 `cd frontend && npx playwright test e2e/studio-smart-console.spec.ts --project=chromium`，确认修复前失败。

### Task 2: 统一快捷处理链接与返回入口

**Files:**
- Modify: `frontend/src/lib/studio-context-links.ts`
- Modify: `frontend/src/components/studio/studio-episode-board-data.ts`
- Modify: `frontend/src/components/studio/studio-episode-stage-board.tsx`
- Create: `frontend/src/components/studio/studio-return-dock.tsx`
- Modify: `frontend/src/components/layout/main-layout.tsx`
- Modify: `frontend/src/app/subtitles/page.tsx`

- [x] 修复显式查询参数被当前快照覆盖的问题，并生成可信的 `return_to`。
- [x] 为 12 个任务配置条目级目标路由与参数，逐项渲染“去处理”。
- [x] 所有 MainLayout 页面在 `source=studio` 时提供固定返回入口。
- [x] 字幕页按 workflow/novel/chapter/storyboard 过滤加载。
- [x] 运行专项 Playwright 用例，验证快捷入口和返回链路。

### Task 3: 合并章节与工作流生成集数导航

**Files:**
- Modify: `frontend/src/components/studio/studio-workspace-header.tsx`
- Test: `frontend/e2e/studio-quick-actions.spec.ts`

- [x] 以小说章节为全集，关联已有工作流并保留无章节的兼容工作流。
- [x] 未创建工作流的章节显示“未创建工程”，不伪造工作流或修改数据库。
- [x] 运行专项 Playwright 用例确认两章都可见。

### Task 4: 前端回归与真实数据验收

**Files:**
- Test: `frontend/e2e/studio-smart-console.spec.ts`
- Test: `frontend/e2e/series-studio-multi-episode.spec.ts`
- Test: `frontend/e2e/studio-real-data-acceptance.spec.ts`

- [x] 运行 Studio 专项 E2E、TypeScript 检查和生产构建。
- [x] 重启前后端并检查 OpenAPI 与 `/studio`。
- [x] 从前端以 sunqy 数据打开 `雨巷铜铃前端闭环-1783489301`，确认两章展示、字幕入口参数和返回入口可见。

### Task 5: 最终可操作闭环

**Files:**
- Modify: `frontend/src/components/studio/studio-workspace-header.tsx`
- Create: `frontend/src/lib/studio-quick-actions.ts`
- Modify: `frontend/src/components/studio/studio-return-dock.tsx`
- Test: `frontend/e2e/studio-smart-console.spec.ts`
- Test: `frontend/e2e/studio-real-data-acceptance.spec.ts`

- [x] 未建工作流章节支持点击创建空工作流，并在成功后自动切换到新集。
- [x] 创建失败时保留当前工作台并提供可读错误，可再次点击重试。
- [x] 快捷任务名称、目标地址和 focus 参数使用单一配置源。
- [x] 目标页显示当前快捷任务，并继续提供返回原工作台入口。
- [x] 模拟前端实际验证创建请求和自动切换；sunqy 真实数据只读验证按钮可用。
