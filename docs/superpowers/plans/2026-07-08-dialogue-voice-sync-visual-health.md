# Dialogue Voice Sync Visual Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让工作流从小说对白生成、角色声线分配、音频/字幕/视频时长体检、每镜头角色一致性缺口可视化到 2 章前端验收形成闭环。

**Architecture:** 后端保持现有工作流接口，最小扩展分镜模板、TTS 声线解析和渲染响应字段；前端复用工作流页现有卡片区显示红黄绿体检和每镜头一致性缺口。真实云端生成仍从前端触发，后端只提供可观测契约与诊断。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Next.js 14, React, Playwright CLI, FFmpeg/ffprobe.

---

## Execution Contract

**Intent Lock:** 修复“角色对白被旁白化、用户主角声线被误用于旁白/配角、同步体检不可见、一致性缺口不在镜头卡片显示”的生产闭环问题。

**Scope Boundaries:** 不重构模型供应商架构；不手工修改后台数据完成验收；不承诺云端模型成功，除非浏览器前端发起并得到实际结果。

**Constraint Checklist:**
- API compatibility: 只新增可选字段，不破坏现有响应。
- Data: 不做 schema migration；把诊断放入 `extra_data` / response。
- UX: 工作流页直接展示红黄绿指标和每镜头缺口，避免只放在文本健康检查里。
- Security: 不输出 API key 或带签名 token 的完整 URL。
- Style: 保持现有大文件模式，做外科式补丁。

**Acceptance Criteria:**
- 角色模板镜头在没有直接引号对白时仍生成 `角色名：...`，不降级为 `（旁白）...`。
- 主角可使用用户默认克隆声线；旁白和配角不自动继承主角克隆声线。
- 渲染预检/渲染响应包含 `media_sync_health`，前端显示“音频/字幕/视频时长一致性体检”红黄绿指标。
- 工作流镜头卡片显示角色参考图、视觉 DNA、多视图、服装/道具锁定缺口。
- 浏览器前端发起一部新 2 章小说流程，保留关键截图和结果证据。

**Verification Commands:**
- `cd backend && pytest tests/test_storyboard_dialogue_metadata.py -q`
- `cd backend && pytest test_workflow_routes.py::<new voice/render tests> -q`
- `cd frontend && npm run typecheck`
- `cd frontend && npx playwright test e2e/workflow-production-guidance.spec.ts --grep "sync health|consistency gaps"`
- `command -v npx >/dev/null 2>&1` then Playwright CLI browser screenshots for the 2 章 flow.

**Decision Points:**
- 若真实 MiniMax/Seedance/TTS 云端失败，只修复可归因的平台问题；余额、模型队列、供应商异常需作为验收风险报告，不绕过前端改 DB。

## Tasks

- [ ] Add failing backend tests for template dialogue role fallback and narrator preservation.
- [ ] Patch `backend/app/services/storyboard_template_service.py` to synthesize character dialogue for `dialogue_role == "角色"`.
- [ ] Add failing backend tests for main-character-only user voice clone and narrator/side-character provider defaults.
- [ ] Patch `backend/app/api/v1/endpoints/workflow.py` voice resolution and render `media_sync_health` aggregation.
- [ ] Add frontend E2E assertions for sync health card and per-shot consistency gap chips.
- [ ] Patch `frontend/src/app/workflow/page.tsx` to consume/display the new diagnostics.
- [ ] Run targeted tests and typecheck.
- [ ] Restart backend/frontend.
- [ ] Use browser frontend to create a new 2-chapter novel, generate/validate a few shots per episode, trigger MiniMax image / TTS / video / FFmpeg render / publish where configured, and capture screenshots.
