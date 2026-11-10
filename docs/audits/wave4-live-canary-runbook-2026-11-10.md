# Wave4 实模小额验收剧本（2026-11-10）

- **分支**：`feat/series-run-redis-queue-and-tail-fsm`
- **时区**：Asia/Shanghai
- **性质**：操作手册。本文件不包含任何 API Key。真实扣费步骤 **必须** 在用户通过保密通道注入 `VOLC_API_KEY` / `VOLCENGINE_API_KEY` 之后执行。
- **预算硬顶**：约 **¥5**；只跑 **1 章**；超过即停，禁止自动重试付费请求。
- **对照**：`docs/operations/four-chapter-live-canary.md`（历史四章手册，预算更高，本波不沿用其金额）、`ops/wave4/env-credentials.checklist.md`

---

## 0. 本波已自动完成 vs 仍待凭证

| 项 | 状态 |
|---|---|
| 本 runbook + 截图清单 | ✅ 本文 |
| Docker PG + Redis 契约编排 | ✅ `ops/wave4/docker-compose.contracts.yml` |
| PG 上 publication one-click / runtime 契约脚本 | ✅ `ops/wave4/run_pg_publication_contracts.sh` |
| `pg_dump`/`pg_restore` 演练脚本 + RPO/RTO 记录位 | ✅ `ops/wave4/pg_backup_restore_drill.sh` → `docs/audits/wave4-evidence/` |
| `/ready` DB(+Redis) readiness 最小实现 + 测试 | ✅ `backend/app/core/health.py`、`/ready`、`tests/test_health_readiness.py` |
| MinIO 私有桶上传/签名/`download=1` 自动化脚本 | ✅ 脚本就绪；**本机镜像拉取 401/denied → 待镜像或待云凭证** |
| 真实火山 1 章小额跑通 | ⏸ **待用户保密提供 Key**（禁止聊天明文） |
| 真实七牛/S3 生产桶 | ⏸ **待凭证**（见 checklist） |

---

## 1. 前置门禁（全部通过才允许点「一键生成」）

1. 假模式全量回归近期已绿（后端 pytest / Playwright 相关套件）。
2. `GET /health` → 200 liveness；`GET /ready` → 200 且 `checks.database.ok=true`（若配置了 `REDIS_URL` 则 redis 也必须 ok）。
3. 正式欢迎态文案为「必须自带 Key」，无「免费试用」误导。
4. 费用闸：单次 ≤ ¥50、账号 ≤ ¥200；本 canary 另设 **服务端/人工硬顶 ¥5**。
5. 对象存储：生产拒绝 `STORAGE_PROVIDER=local`（除非显式允许）；本 canary 若仅验证模型链路，可用本地 HMAC 播放，但 **不得** 宣称私有桶已验收。
6. Key 仅通过保密表单/环境注入；聊天、截图、日志、证据包均不得出现明文。

---

## 2. 环境准备（不扣费）

```bash
cd /Users/sunqinyue/Documents/work/BJDEV/claude/ai-video-platform
git checkout feat/series-run-redis-queue-and-tail-fsm
git pull --rebase origin feat/series-run-redis-queue-and-tail-fsm

# 契约依赖（无 Key）
docker compose -f ops/wave4/docker-compose.contracts.yml up -d postgres redis
export REDIS_URL=redis://127.0.0.1:56379/0

# 应用按既有 e2e/开发方式启动；生产态禁止 DETERMINISTIC_PROVIDER_FAKE=1
# Key：export VOLCENGINE_API_KEY=***  （仅保密注入，不写进文档）
```

假模式预演（可选，0 费用）：用演示模式走同一截图清单，确认 UI 步骤后再切真 Key。

---

## 3. 前端逐步操作 + 截图清单（1 章 · ¥5）

截图目录建议：`docs/audits/wave4-evidence/live-canary-shots/`（文件名固定如下，便于门禁勾选）。

| # | 步骤 | 操作要点 | 截图文件名 | 通过标准 |
|---|---|---|---|---|
| 01 | 注册/登录 | 新账号或干净账号 | `01-login.png` | 进入系统 |
| 02 | 欢迎/模型设置 | 生产：选「我有 API Key」 | `02-welcome-byok.png` | 无免费试用误导 |
| 03 | 保存并检测 | 填入保密注入的 Key；语音缺 App ID 才出现 | `03-save-detect.png` | 检测通过或失败原因可读；**失败即停** |
| 04 | 费用闸确认 | 确认单次/账号上限展示 | `04-budget-gate.png` | 可见上限；本轮口头确认 ≤¥5 |
| 05 | 粘贴小说 | **仅 1 章**短文（建议 ≤800 字） | `05-novel-paste.png` | 自动标题可接受 |
| 06 | 小说详情 | 只点「一键生成」 | `06-novel-detail.png` | 单一入口 |
| 07 | 确认框（真实模式） | 确认花费上限文案 | `07-confirm.png` | 显示上限；确认后开始 |
| 08 | 进度 | 4 步进度可懂 | `08-progress.png` | 准备/剧本/画面配音/合成 |
| 09 | 成功成片 | 可播放非黑屏 | `09-playback.png` | 有画面+声音 |
| 10 | 下载 | `?download=1` 直接下载 | `10-download.png` | 文件可播 |
| 11 | 发布 | 发布页无大片空白 | `11-publish.png` | 发布成功或明确 blocker |
| 12 | 账本/费用 | 设置或任务中费用 | `12-cost.png` | **实际 ≤ ¥5**；超支则记失败并停 |

失败即停（任一）：

- Key 无效 / 额度不足 / 网络错误提示
- 供应商已受理但状态不明（避免重复提交）
- 费用预留失败或预估将超 ¥5
- 多角色缺配音导致 `required_entity_state_invalid`（应先修可靠性波次）
- `/ready` 变 503

---

## 4. 证据与脱敏

允许保留：截图、run_id、非敏感配置 ID、阶段状态、脱敏费用合计、`/ready` JSON、本波 `docs/audits/wave4-evidence/*` 报告。

禁止保留：API Key、Authorization 头、提示词全文、原始 base64 媒体、未脱敏签名 URL 永久副本。

结束后：停止本机 API/Worker/前端；契约 compose 可按需 `docker compose -f ops/wave4/docker-compose.contracts.yml down`（**勿误停其他并行波次容器**）。

---

## 5. 关联命令速查（无 Key 可跑）

```bash
# readiness + 存储单测 + 部署契约
cd backend && ./venv/bin/python -m pytest -q \
  tests/test_health_readiness.py \
  tests/test_object_storage_g4.py \
  tests/test_private_media_access.py \
  tests/test_production_deployment_contract.py

# PG 契约（需 compose postgres up）
../ops/wave4/run_pg_publication_contracts.sh

# 备份恢复演练
../ops/wave4/pg_backup_restore_drill.sh

# MinIO/S3（需 endpoint 可达）
../ops/wave4/run_minio_private_bucket_check.sh
```

---

## 6. 变更记录

| 时间（Asia/Shanghai） | 说明 |
|---|---|
| 2026-11-10 | 初稿；并行第4波；无真实扣费 |
