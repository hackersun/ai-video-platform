# 豆包 Seed-TTS 2.0 四章实模切换实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 四章 Wave 1 从 sunqy 的旧 MiniMax TTS 固定绑定切换到默认配置“豆包语音 Seed-TTS 2.0”，并从前端完成新一轮无自动重试实模验证。

**Architecture:** 保留现有四章 runner、服务端预算、七牛参考资产和视频模型链路，只替换 TTS 配置白名单并补齐豆包 2.0 的模型执行契约与安全声线契约。浏览器仍负责显式启用实模、锁定声线、生成参考图和提交两个跨章关键镜头。

**Tech Stack:** Node.js test runner、Playwright、FastAPI、pytest、SQLite、Next.js 14。

## Global Constraints

- 服务端预算上限固定为 RMB 10，关键镜头固定为 2 个。
- provider 失败或受理状态不确定时禁止自动重试。
- 只使用 sunqy 的 `sunqy-volcano-seed-tts-2-0`，API 模型为 `seed-tts-2.0`。
- 开发库只读复制到 `/tmp` 隔离库；七牛签名公网映射和其他三个模型配置不变。
- 证据只保留脱敏模型/任务/成本/评分信息，不保存密钥、提示词正文和签名 URL。

---

### Task 1: 锁定 Wave 1 豆包 TTS 配置

**Files:**
- Modify: `scripts/run-four-chapter-acceptance.test.mjs`
- Modify: `scripts/run-four-chapter-acceptance.mjs`
- Modify: `frontend/e2e/four-chapter-live-canary.spec.ts`

**Interfaces:**
- Consumes: `parseLiveCanaryOptions(source)`。
- Produces: `configIds` 中 TTS 固定为 `sunqy-volcano-seed-tts-2-0`，实模清单断言同一配置。

- [x] 测试先断言新 ID 且排除旧 MiniMax TTS ID，运行 Node 测试看见失败。
- [x] 仅替换 runner 与浏览器清单中的 TTS ID，并把示例证据改成豆包 2.0 契约。
- [x] 运行 `node --test scripts/run-four-chapter-acceptance.test.mjs`，预期全部通过。

### Task 2: 补齐豆包 2.0 服务端契约

**Files:**
- Modify: `backend/tests/test_model_execution_contract.py`
- Create: `backend/tests/test_series_run_voice_contract.py`
- Modify: `backend/app/features/model_execution_contract/registry.py`
- Modify: `backend/app/features/series_run_story_locks/application/voice_contract.py`

**Interfaces:**
- Consumes: `resolve_model_execution_contract()` 与 `provider_voice_allowlist()`。
- Produces: `volcano/seed-tts-2.0/tts -> volcano.seed_tts.v3.v1`，安全声线为 `zh_female_vv_uranus_bigtts`。

- [x] 先增加模型与声线测试，运行 pytest 看见缺少契约导致失败。
- [x] 增加唯一的豆包 2.0 执行契约和 Volcano 安全声线分支。
- [x] 运行聚焦 pytest，预期全部通过。

### Task 3: 前端与实模闭环验收

**Files:**
- Modify: `docs/operations/four-chapter-live-canary.md`

**Interfaces:**
- Consumes: sunqy 已保存配置、四章 runner、现有七牛映射。
- Produces: 新运行 ID、两个关键镜头的任务/产物/费用/一致性证据，或明确失败阶段且零自动重试的证据。

- [x] 从前端 `/llm-config` 测试“豆包语音 Seed-TTS 2.0”，确认 `test_status=success` 且 `tested_at` 更新。
- [x] 运行 typecheck、构建和聚焦后端门禁。
- [x] 从开发库生成 0600 权限的 `/tmp` 源副本，用固定预算和镜头数启动 `verify:four-chapter:live`。
- [x] 等待异步任务终态；成功则核对 TTS/video/七牛/费用/一致性，失败则保留脱敏证据并停止，不自动重试。
- [x] 清理隔离数据库，确认开发库行数/大小和服务健康未漂移，并更新操作手册的当前模型矩阵与本轮结果。
