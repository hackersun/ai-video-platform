# Standard Prompt Skills and Menu IA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐覆盖小说到出片全流程的标准 Prompt 技能库，并按 B 方案重组顶部菜单。

**Architecture:** 后端用独立 `default_prompt_skills.py` 存放内置技能定义，服务层在列表、预览、生成提示词前幂等补齐。前端只调整导航配置和 Prompt 技能任务选项，不重写业务页面。

**Tech Stack:** FastAPI、SQLAlchemy AsyncSession、pytest、Next.js 14、React、Playwright。

---

### Task 1: 标准 Prompt 技能库

**Files:**
- Create: `backend/app/services/default_prompt_skills.py`
- Modify: `backend/app/services/prompt_skill_service.py`
- Test: `backend/test_prompt_skills.py`

- [x] 写失败测试：`test_builtin_prompt_skills_cover_core_ai_flow`，验证 14 个内置任务、内容非空、可预览。
- [x] 写失败测试：`test_user_active_prompt_skill_overrides_builtin_prompt_skill`，验证用户激活同任务技能时覆盖内置默认。
- [x] 实现 `STANDARD_PROMPT_SKILLS` 和 `ensure_standard_prompt_skills()`。
- [x] 在列表、预览、生成提示词入口幂等补齐标准技能。
- [x] 运行：`cd backend && python3 -m pytest test_prompt_skills.py::test_builtin_prompt_skills_cover_core_ai_flow test_prompt_skills.py::test_user_active_prompt_skill_overrides_builtin_prompt_skill -q`

### Task 2: 流程型菜单与任务选项

**Files:**
- Modify: `frontend/src/components/layout/top-navigation.tsx`
- Modify: `frontend/src/app/prompt-skills/page.tsx`
- Test: `frontend/e2e/prompt-skills.spec.ts`

- [x] 写失败 E2E：验证顶部出现 `工作台`、`内容创作`、`资产设定`、`生产出片`、`配置`。
- [x] 写失败 E2E：验证 Prompt 技能任务下拉包含小说、章节、剧本、分镜、镜头、视频、头像、封面等任务。
- [x] 实现 B 方案导航分组。
- [x] 扩展 Prompt 技能任务选项到 14 个标准任务。
- [x] 运行：`cd frontend && npx playwright test e2e/prompt-skills.spec.ts`

### Task 3: 回归与稳定提交

**Files:**
- All files touched above.

- [x] 运行后端 Prompt 技能回归：`cd backend && python3 -m pytest test_prompt_skills.py test_prompt_skill_prompt_composer.py -q`
- [x] 运行前端构建：`cd frontend && npm run build`
- [x] 运行前端聚焦 E2E：`cd frontend && npx playwright test e2e/prompt-skills.spec.ts e2e/studio-full-flow.spec.ts`
- [x] 精确暂存本任务文件。
- [x] 提交：`feat: add standard prompt skills and flow navigation`
