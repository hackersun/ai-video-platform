# 模型就绪状态统一实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让全局概览与提示词使用地图使用同一份实际生产路由结论，并把模型认证状态用中文点名说明。

**Architecture:** 提示词就绪检查不再读取模型版本上的旧 `prompt_profile_key` 字段，而是复用生产环节的模板解析服务。认证检查继续独立执行，通过模型版本关联模型名称，并区分“连接测试成功”和“契约/实模认证成功”。前端统计同时展示使用模板环节、已就绪数量、问题数量和无需模板数量。

**Tech Stack:** FastAPI、SQLAlchemy、Next.js 14、React、TypeScript、pytest、Playwright。

## Global Constraints

- 不修改现有模型绑定、提示词模板、认证记录和历史生成结果。
- 提示词是否就绪以实际生产路由结果为唯一来源。
- 认证不足仍是生产阻塞项，不得用提示词就绪掩盖。
- 所有操作提示使用中文并点名具体模型或生产环节。
- 当前工作区包含用户未提交改动，只修改本计划列出的文件。

---

### Task 1: 统一提示词生产准入判定

**Files:**
- Modify: `backend/tests/test_model_center_api.py`
- Modify: `backend/app/features/model_config/readiness.py`

**Interfaces:**
- Consumes: `resolve_prompt_usage_stage(db, user_id, stage_id, profile_version_id)`。
- Produces: 与提示词使用地图一致的 `prompt_profile_missing` 阻塞项。

- [x] 增加回归测试：模型版本没有 `prompt_profile_key`，但生产路由能匹配已发布环节模板时，概览不得报模板缺失。
- [x] 运行该测试并确认旧实现因直接检查 `prompt_profile_key` 而失败。
- [x] 按激活绑定匹配生产环节，并复用 `resolve_prompt_usage_stage`；只对 `internal_fallback` 或 `invalid_binding` 产生提示词阻塞项。
- [x] 运行模型中心后端目标测试并确认通过。

### Task 2: 让认证阻塞项点名模型和认证差距

**Files:**
- Modify: `backend/tests/test_model_center_api.py`
- Modify: `backend/app/features/model_config/readiness.py`

**Interfaces:**
- Consumes: `ModelProfileVersion.model_id`、`ModelProfile.display_name`、`ModelCertificationRun.level/status`。
- Produces: 带模型名称的 `model_certification_missing` 中文消息。

- [x] 增加回归测试：只有连接认证成功时，消息明确显示模型名称以及尚缺契约或实模认证。
- [x] 运行测试并确认旧通用消息失败。
- [x] 查询模型名称和连接认证状态，生成两类直白消息。
- [x] 运行模型中心后端目标测试并确认通过。

### Task 3: 澄清提示词使用地图统计

**Files:**
- Modify: `frontend/e2e/model-center-prompt-usage-map.spec.ts`
- Modify: `frontend/src/features/model-center/components/prompt-usage-summary.tsx`

**Interfaces:**
- Consumes: `PromptUsageMap.summary.total/counts`。
- Produces: 使用模板环节、已就绪、提示词问题、无需模板四个可读数字。

- [x] 增加前端回归断言：12 个总环节中明确显示 10 个使用模板、8/10 已就绪、2 个提示词问题、2 个无需模板。
- [x] 运行 Playwright 测试并确认旧统计文案失败。
- [x] 最小调整汇总卡文案和分母，不改变问题筛选行为。
- [x] 运行提示词地图前端测试并确认通过。

### Task 4: 真实账号与服务验收

**Files:**
- Verify only.

- [x] 用 `sunqy` 当前账号请求概览和提示词使用地图，确认模板误报清零且认证阻塞点名模型。
- [x] 运行后端目标测试、前端目标测试和生产构建。
- [x] 重启前后端并验证 3000 页面与 8000 健康接口。
