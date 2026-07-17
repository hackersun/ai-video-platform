# Seedance 1.5 原生配音临时开关实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在四章系列关键镜头生成中提供默认关闭的 Seedance 1.5 原生配音临时开关，并阻止输入参考图冒充生成视频封面。

**Architecture:** 请求层使用单次 `native_audio` 布尔值，不持久化为用户默认配置。工作流媒体适配器在开启时跳过独立 TTS，向 Seedance 1.5 发送 `generate_audio=true` 和对白同步提示词；视频任务继续记录参考图输入，但只有供应商返回的真实封面才能写入 `cover_url`。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、Next.js 14、React、pytest、Playwright。

## Global Constraints

- 默认关闭，不改变现有 separate video + TTS 行为。
- 仅 `doubao-seedance-1-5-pro-251215` 允许开启原生配音。
- 开启后不提交独立 TTS，不产生重复人声或重复 TTS 费用。
- 对白必须包含说话人、原文、语言、口型、情绪、起止节奏和禁止增删台词约束。
- 参考图仍作为模型输入，但不得写入视频结果的 `cover_url`。
- 四章实模仍保持 2 个关键镜头、失败不自动重试和服务端预算门禁。

---

### Task 1: 锁定后端原生配音契约

**Files:**
- Modify: `backend/app/features/workflow_media/schemas.py`
- Modify: `backend/app/features/workflow_media/application/prepare_separate_media.py`
- Modify: `backend/app/features/workflow_media/application/generate_separate_media.py`
- Modify: `backend/app/features/workflow_media/adapters/video_submission.py`
- Test: `backend/tests/test_seedance_native_audio_submission.py`
- Test: `backend/tests/test_separate_media_submission_order.py`

- [x] 先增加失败测试，证明原生配音请求必须生成 `generate_audio=true`、跳过 TTS、保留对白约束且不使用参考图作为封面。
- [x] 实现最小请求、提示词、提交与持久化变更。
- [x] 运行聚焦 pytest 并确认通过。

### Task 2: 接通系列工作台临时开关

**Files:**
- Modify: `backend/app/features/series_anchor_generation/schemas.py`
- Modify: `backend/app/features/series_anchor_generation/generation.py`
- Modify: `backend/app/api/v1/endpoints/series_runs.py`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/features/series-runs/use-anchor-generation.ts`
- Modify: `frontend/src/components/novels/series-run-panel.tsx`
- Modify: `frontend/src/features/series-runs/series-run-view.tsx`

- [x] 将 `native_audio` 纳入幂等键和工作流媒体请求。
- [x] 增加默认关闭且仅当前页面会话有效的前端开关与明确说明。
- [x] 运行前端类型检查和相关测试。

### Task 3: 修复参考图封面语义并完成验收门禁

**Files:**
- Modify: `backend/app/api/v1/endpoints/video.py`
- Modify: `backend/app/features/series_anchor_generation/media_reconciliation.py`
- Modify: `frontend/e2e/four-chapter-live-canary.spec.ts`

- [x] 确保新建视频任务不再把输入参考图写入 `cover_url`。
- [x] 原生有声视频聚合证据使用 `video + native_audio`，不伪造 TTS 调用。
- [x] 浏览器验收断言临时开关、请求参数、原生音频任务证据和真实封面语义。
- [x] 运行后端聚焦测试、前端类型检查与构建。
