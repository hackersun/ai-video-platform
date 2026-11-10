# Series Run Redis 持久队列与尾部 FSM 闭合设计

**日期：** 2026-11-03（Asia/Shanghai）  
**仓库：** `hackersun/ai-video-platform`  
**范围切片：** G4 任务/媒体持久化 + Run 尾部 FSM 闭合（可商用最小切片）  
**状态：** 已批准决策落盘；本文仅设计，不含实现代码

---

## 1. Goal（目标）

把整书 Series Production Run 的后台执行从**进程内 `asyncio.Task` 字典**升级为基于 **`REDIS_URL` 的持久队列 + 独立 Worker**，并在真实媒体成功且质量门通过后，**自动闭合** Run 状态机尾部：

`media_running → evaluating → completed`

失败时进入 `failed` 或 `blocked`，且 **`SeriesAnchorGenerationSubmission.status == completed` 绝不能伪造 `SeriesProductionRun.status == completed`**。

本切片交付后，必须同时满足：

1. **重启安全**：API / Worker / Redis AOF 任一短暂中断后，同一 `run_id` 可再次入队并由 Worker 从数据库真相恢复执行，不丢任务、不并行双飞。
2. **单飞（single-flight）**：任意时刻每个 `run_id` 至多一个活跃执行租约。
3. **与 pause 协作**：`POST /series-runs/{id}/pause` 写入 `paused` 后，Worker 在下一安全边界停手；恢复后可再次 `execute-async` 续跑。
4. **API 兼容**：保留 `POST /series-runs/{run_id}/execute-async` 的 202 语义与 `execution_status` 三值（`queued` / `already_running` / `not_required`）。
5. **G4 对齐证据**：创建、排队、执行、失败、重试、取消/暂停、重启恢复均有持久状态可观测（队列键 + DB `status` / `episodes` / `run_metadata`）。

---

## 2. Non-goals（非目标 / 本切片明确不做）

以下项登记为后续切片，**本设计与实现不得夹带**：

| 后续项 | 说明 |
|---|---|
| Seedance 六证据闭环 | 不在本切片扩展供应商证据矩阵或 Seedance 专用门禁 |
| 计费账本 / G6 流水 | 不新增预扣、扣减、退款账本；沿用现有 live canary 预算字段只读协作 |
| 巨型 endpoint 拆分 | `series_runs.py` 不在本切片做大规模路由拆分；仅允许为队列/尾部 FSM 增加最小接线 |
| Celery 迁移 | `docker-compose.yml` 中遗留的 `celery -A app.tasks` 不作为本切片路径；生产拓扑以 `compose.production.yml` 为准扩展 Worker |
| 通用任务平台 | 不抽象跨域 Job 框架；队列仅服务 Series Run 执行与尾部闭合 |
| 对象存储 / 签名 URL 改造 | G4 媒体私有存储条目不在本切片展开 |
| 改变 `ACTIVE_STATES` 顺序 | 状态名与合法前进顺序保持 `series_run_orchestrator.py` 现有定义 |

---

## 3. Architecture（架构）

### 3.1 现状（必须改掉的问题）

`backend/app/services/series_run_execution_queue.py` 现状：

- 模块级 `_tasks: dict[str, asyncio.Task[None]]` 进程内单飞。
- `start_series_run_execution` 用 `asyncio.create_task` 启动 `_execute`。
- `_execute` 打开 `AsyncSessionLocal`，跳过 `shots_ready` / `completed` / `paused`，否则调用 `SeriesRunOrchestrator().execute`。
- **进程重启即丢任务**；多 API worker（`compose.production.yml` 中 `API_WORKERS` 默认 2）下各进程自有 `_tasks`，**跨进程无法单飞**。

`compose.production.yml` **已具备** Redis 7（`appendonly yes`）与 API 环境变量 `REDIS_URL: redis://redis:6379/0`，但后端 `requirements.txt` **尚未声明 redis 客户端**，也没有 Series Run Worker 服务。

尾部 FSM 缺口：`series_anchor_generation/generation.py` 的 `generate_selected` 在媒体与质量评估后将 **Submission** 标为 `completed` 并 `commit`，**不会**调用 `transition_run` 走 `media_running → evaluating → completed`。未评估路径返回 `overall_readiness: trusted_multimodal_evaluation_required` 且 `ready: False`，若误把 Submission 完成当成 Run 完成，会直接违反商用诚实性。

### 3.2 目标拓扑

```text
Browser / Client
    │
    ▼
API (uvicorn)  ──POST execute-async──►  enqueue(run_id, user_id)
    │                                       │
    │                                       ▼
    │                              Redis 持久队列 + 锁
    │                                       │
    │                                       ▼
    │                         series-run-worker 进程
    │                                       │
    │                                       ▼
    │                    SeriesRunOrchestrator.execute(db, run)
    │                    （DB = 进度真相；Redis = 调度真相）
    │
    └──POST generate-selected / media/start──► 媒体与质量路径
                         │
                         ▼
              close_media_tail（新编排方法）
              media_running → evaluating → completed
              或 failed / blocked
```

原则：

- **数据库**仍是 Run / Episode / Submission / MediaJob 的权威状态。
- **Redis**只负责：待执行队列、处理中备份、单飞锁、活跃心跳；不存业务进度副本。
- **Worker**与 API 同镜像、同环境变量；命令入口独立，避免占用 HTTP worker。

---

## 4. Components / Files to touch（组件与改动面）

| 路径 | 动作 | 职责 |
|---|---|---|
| `backend/app/services/series_run_execution_queue.py` | **重写** | 去掉 `_tasks`；实现 `enqueue` / `is_active` / Redis 客户端；保持导出名 `start_series_run_execution`、`series_run_execution_active` |
| `backend/app/services/series_run_worker.py`（新建） | **新增** | 消费循环：取任务 → 抢锁 → 调 Orchestrator → 释放；处理暂停与崩溃回收 |
| `backend/app/services/series_run_orchestrator.py` | **扩展** | 增加 `close_media_tail`（或等价公开方法）；`build_episodes` 循环内增加 pause 协作检查点；可选 `claim` 辅助不改状态顺序 |
| `backend/app/features/series_anchor_generation/generation.py` | **接线** | 真实媒体成功且质量门通过后调用尾部闭合；Submission `completed` 与 Run 闭合分离提交语义 |
| `backend/app/api/v1/endpoints/series_runs.py` | **最小改动** | `execute-async` / `pause` / `resume` 继续调用同名队列 API；pause 后尽力通知 Worker 协作（见 §7） |
| `backend/app/core/redis_client.py`（新建） | **新增** | 从 `REDIS_URL` 创建异步 Redis 连接；统一前缀与超时 |
| `backend/requirements.txt` | **追加** | `redis[hiredis]>=5.0.0`（或锁定与运行时兼容的 5.x） |
| `compose.production.yml` | **扩展** | 新增 `series-run-worker` 服务；共享 API 同等 `DATABASE_URL` / `REDIS_URL` / 密钥与媒体卷 |
| `backend/tests/test_series_run_execution_queue.py`（新建） | **新增** | 队列、单飞、重启回收、pause 协作 |
| `backend/tests/test_series_run_media_tail_fsm.py`（新建） | **新增** | 尾部闭合、Submission≠Run completed、失败进 failed/blocked |
| `backend/tests/test_series_run_orchestrator.py` | **增补** | 保持现有 `execute-async` 契约；补充 pause 检查点与 tail 合法转移 |
| `backend/tests/test_production_deployment_contract.py` | **更新** | 服务集合纳入 `series-run-worker`；断言其 `REDIS_URL` 与 depends_on |

**刻意不改：** `ACTIVE_STATES` / `RECOVERY_STATES` 常量内容；`transition_run` 的合法前进规则（尾部仍逐步前进两步）；Submission 幂等键模型。

---

## 5. Data flow（数据流）

### 5.1 execute-async 入队

1. `POST /api/v1/series-runs/{run_id}/execute-async` 校验归属。
2. 若 `status ∈ {shots_ready, anchor_ready, completed, paused}` → 不入队，`execution_status=not_required`（与现逻辑一致；`anchor_ready` 已在 endpoint 中视为不需要 episode 执行）。
3. 否则调用 `start_series_run_execution(run_id, user_id)`：
   - 若已有有效单飞锁或已在 `processing` 中且心跳未过期 → 返回 `False` → API 映射 `already_running`。
   - 否则将任务 JSON 推入 Redis 主队列并返回 `True` → `queued`。
4. API 立即 202，**不**在请求内调用 `Orchestrator.execute`。

### 5.2 Worker 执行 episode 构建

1. Worker 用可靠队列语义从主队列弹出到处理中列表（见 §6）。
2. 对 `run_id` 尝试 `SET lock NX EX`；失败则丢弃本条（或延迟重入），避免双飞。
3. 打开 DB 会话加载 Run；若缺失或 `status ∈ {shots_ready, completed, paused}` → 确认性 ack（从 processing 移除）并释放锁。
4. 调用 `SeriesRunOrchestrator().execute(db, run)`；`failed`/`blocked` 仍按现有逻辑先恢复到 `episodes_building` 再构建。
5. 每个 episode stage 成功提交后刷新心跳；若读到 `paused` → 停止后续 stage，ack 任务，释放锁（进度已在 DB）。
6. 正常结束或失败落库后：从 processing 移除并释放锁。未捕获崩溃由回收器把 processing 中过期项重新入队。

### 5.3 媒体尾部闭合

1. 客户端（或现有流程）`media/start` → `enter_media_running`（已有）。
2. `generate-selected` 走现有 Submission / MediaJob / 质量路径。
3. **仅当**同时满足「真实媒体成功」与「质量门通过」（§8）时，调用 `close_media_tail`：
   - `transition_run(run, "evaluating")` 并 commit；
   - `transition_run(run, "completed")` 并 commit；
   - 写入 `gate_summary.media_tail` 证据摘要（通过时间、submission_id、selected_shot_ids、质量报告指纹）。
4. 若媒体批次失败或质量门判定硬失败 → `transition_run(run, "failed")`（可附 `run_metadata.tail_error`）。
5. 若质量尚未可信评估（例如仅有 `trusted_multimodal_evaluation_required`）→ **不得**前进到 `evaluating`/`completed`；可将 Run 置于 `blocked`（附 blocker code），或保持 `media_running` 等待后续 accept/repair——本切片约定：**缺可信质量证据时进入 `blocked`，并在 `gate_summary.media_tail` 写明原因**，避免无限停在「看起来成功」的 Submission 完成态被误读为 Run 完成。
6. Submission 行的 `status/response_payload` 更新与 Run 状态转移**分字段记录**；允许同一次请求内先写 Submission，再尝试闭合，但测试必须证明：仅 Submission `completed` 时 Run 仍可为 `media_running`/`blocked`。

---

## 6. Redis key design（键设计）

统一前缀：`avp:series_run:`（避免与其他产品键冲突）。所有键落在 `REDIS_URL` 指定 DB（生产 `.../0`）。

| 键 | 类型 | TTL | 用途 |
|---|---|---|---|
| `avp:series_run:queue` | LIST | 无 | 待执行主队列；元素为 JSON：`{"run_id","user_id","enqueued_at","attempt"}` |
| `avp:series_run:processing` | LIST | 无 | 可靠队列处理中备份；Worker 用 `BLMOVE`（Redis≥6.2）从 queue 左弹右推到 processing |
| `avp:series_run:lock:{run_id}` | STRING | 初始 120s，执行中续期 | 单飞锁；值=`{worker_id}:{lease_token}`；`SET NX EX` |
| `avp:series_run:heartbeat:{run_id}` | STRING | 60s | ISO8601 心跳；`series_run_execution_active` 与回收器读取 |
| `avp:series_run:pause:{run_id}` | STRING | 300s | pause 协作信号（可选加速停手）；值=`1`；DB `status=paused` 仍是权威 |

**队列元素字段（固定）：**

```json
{
  "run_id": "…",
  "user_id": "…",
  "enqueued_at": "2026-11-03T14:26:00+08:00",
  "attempt": 1
}
```

**入队去重：** `start_series_run_execution` 在推入前检查 `lock` 或未过期 `heartbeat`；若已活跃返回 `False`。允许主队列短暂出现同 `run_id` 重复元素，但 Worker 抢锁失败即 ack 丢弃，保证执行单飞。

**回收：** 独立协程每 15s 扫描 `processing`：解析元素；若无锁且 heartbeat 缺失或过期，则 `attempt+=1` 并 `LPUSH` 回 `queue`，同时从 `processing` 移除该元素（用 `LREM`）。`attempt` 超过 25 时不再入队，写日志并依赖人工/`execute-async` 再投；**不**自动改 DB 为 failed（避免与业务失败语义混淆），但在 `run_metadata.queue_dead_letter` 记录最后一次回收信息供运维。

**禁止：** 用 Redis Hash 复制整份 `episodes` 进度；进度只在 PostgreSQL/SQLite。

---

## 7. Worker lifecycle（Worker 生命周期）

### 7.1 进程入口

- 模块：`python -m app.services.series_run_worker`（或 `backend/scripts/run_series_run_worker.py` 薄封装调用同一 main）。
- 启动：加载环境 → 连通 DB 与 Redis → 注册 SIGTERM/SIGINT → 进入 `while not stopping: BLMOVE ...` 循环。
- 并发：本切片默认 **每进程单消费者协程**（`SERIES_RUN_WORKER_CONCURRENCY=1`）；水平扩展靠复制 Worker 容器，靠锁保证单飞。

### 7.2 compose.production.yml

新增服务示意（实现时按现有缩进风格写入）：

- `build: ./backend`
- `command: ["python", "-m", "app.services.series_run_worker"]`
- `environment`：与 `api` 相同的 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET_KEY`、`FERNET_KEY`、模型密钥、`DEV_MODE=false`、`MODEL_CENTER_READ_MODE`
- `volumes`：与 `api` 相同的 media 与 tmp 挂载（媒体生成尾部若在同 Worker 扩展时可复用；本切片 episode 构建也需要静态路径一致性）
- `depends_on`：`postgres` healthy、`redis` healthy
- `restart: unless-stopped`
- healthcheck：Python 探测 Redis `PING` + DB `SELECT 1`（或独立 `/worker-health` 若后续需要；本切片用命令行健康即可）

API 服务**不再**在进程内 `create_task` 执行 Run。

### 7.3 与 pause / resume 协作

1. `pause` endpoint：`transition_run(..., "paused")` 提交后，`SET avp:series_run:pause:{run_id}=1 EX 300`。
2. Worker 在每个 episode stage 的 `commit` 前后：
   - 若 Redis pause 信号存在，或 DB `status == paused` → 停止后续 stage，ack，释放锁。
3. 现有 `execute()` 开头已跳过 paused；本切片把检查下沉到 **stage 边界**，避免长任务无视 pause。
4. `resume`：按现有逻辑恢复到 `resume_status` 或从 `failed`/`blocked` 回到 `episodes_building`；**不自动入队**。客户端需再次 `execute-async`（与当前「显式执行」模型一致）。

### 7.4 优雅退出

收到 SIGTERM：设 `stopping=True`；当前任务跑到下一 stage 边界再退出；不强制 `KILL` 持锁任务。锁 TTL + 回收器覆盖崩溃场景。

---

## 8. FSM transitions（状态机与尾部闭合）

### 8.1 既有合法状态（保持）

来自 `series_run_orchestrator.py`：

```text
ACTIVE_STATES =
  created → preflight → planning → facts_ready → assets_ready
  → episodes_building → shots_ready → anchor_ready → media_running
  → evaluating → completed

RECOVERY_STATES = failed | blocked
paused：从 ACTIVE_STATES[:-1] 进入；恢复必须回到 resume_status
```

`transition_run` 前进仍只允许 **当前下标 +1**；因此尾部闭合必须连续两次合法调用：先 `evaluating` 再 `completed`，不可跳跃。

### 8.2 尾部闭合判定（质量门）

定义函数级规则（实现放在 orchestrator 或 generation 旁的纯函数，便于单测）：

**真实媒体成功** 当且仅当：

- 选中的每个 `shot_id` 存在 `is_active` 且 `status ∈ {succeeded, completed}` 的 `MediaGenerationJob`；
- 作业带有可追溯 `artifact_id`（`extra_data.artifact_id` 或产出 URL 回退规则与 `quality_status.py` 一致）；
- Submission 自身可为 `completed`，但这只是必要条件之一，不是充分条件。

**质量门通过** 当且仅当：

- 对每个选中 shot 的权威 artifact，`run.run_metadata.anchor_quality_reports[artifact_id].ready is True`；
- 报告覆盖当前锁定的 `selected_anchor_shot_ids` 全集（允许 repair 后的新 artifact，以最新 accepted 为准）；
- **禁止**把 `unevaluated_quality_results`（`ready: False` / `trusted_multimodal_evaluation_required`）当成通过；
- 在 `deterministic_provider_fake_enabled()` 且 `deterministic_quality_identity` 为真时，允许走现有 `evaluate_deterministic_anchors` 写入 ready 报告后再闭合——这是验收假源路径，不是生产偷渡。

**失败映射：**

| 条件 | Run 目标状态 |
|---|---|
| 媒体批次抛错 / Submission `error_code=media_batch_submission_failed` 且无成功产物 | `failed` |
| 媒体成功但质量门不可信或未覆盖 | `blocked`（`gate_summary.media_tail.blocker_code` 例如 `quality_gate_incomplete`） |
| 质量门显式拒绝且不可自动修复 | `blocked` 或保持 `media_running` 等待 repair；本切片对「评估已完成但 ready 全假」用 `blocked` |
| 质量门通过 | `evaluating` → `completed` |

### 8.3 硬约束：Submission completed ≠ Run completed

- API 响应与 UI 必须能区分：`submission.status` vs `run.status`（现有 generate-selected 响应已返回 submission 载荷；Run 需客户端再 GET 或在响应中附 `run_status`——本切片要求 generate-selected **在闭合后刷新并返回当前 `run.status`**，若未闭合则显式返回仍为 `media_running`/`blocked`）。
- 契约测试：构造 Submission `completed` + 质量未 ready → 断言 `run.status != "completed"`。
- 禁止任何「Submission 完成后无条件 `transition_run(..., "completed")`」快捷路径。

---

## 9. Error / Idempotency（错误与幂等）

| 场景 | 行为 |
|---|---|
| 重复 `execute-async` | 第二次返回 `already_running` 或 `not_required`；不建第二锁 |
| Worker 抢锁失败 | ack 丢弃重复消息 |
| Orchestrator stage 异常 | 现有逻辑：episode 写 `blocker`，`transition_run(..., "failed")`，再抛出；Worker 捕获日志后 ack（进度在 DB，可 resume/execute-async） |
| Redis 短暂不可用 | `start_series_run_execution` 向 API 抛出 → 503 或 503 风格 HTTP（实现选 `HTTP 503` + 明确 detail）；**不**静默回退到进程内 Task |
| DB 提交成功但 ack 前 Worker 崩溃 | 回收器重新入队；Orchestrator 跳过已 `shots_ready` 的 episode，保持现有恢复语义 |
| 尾部闭合中第一次 `evaluating` 成功、第二次崩溃 | 重启后检测 `status==evaluating` 且质量门仍通过 → 只补 `completed`（`close_media_tail` 必须幂等） |
| 已 `completed` 再调尾部闭合 | no-op 成功 |
| `paused` 期间生成接口 | 保持现有 409/校验；本切片不放开 pause 下媒体提交 |

幂等键：

- Submission：继续使用现有 `generation_key` 唯一约束。
- 队列：逻辑幂等靠 `run_id` 锁，不引入第二套业务幂等表。

---

## 10. Testing（测试）

### 10.1 单元 / 组件

- `test_series_run_execution_queue.py`：fakeredis 或测试容器 Redis；入队、单飞、`execution_active`、回收过期 processing、pause 信号。
- `test_series_run_media_tail_fsm.py`：质量通过 → `evaluating`→`completed`；仅 Submission completed → Run 非 completed；质量不足 → `blocked`；媒体失败 → `failed`；`evaluating` 中断恢复。
- 扩展 `test_series_run_orchestrator.py`：stage 边界遇 `paused` 停止；非法跳跃 `media_running→completed` 仍失败。

### 10.2 API 契约

- 保持 `test_execute_async_returns_immediately_and_queues_owned_run`：mock 点仍为 `start_series_run_execution`。
- 新增：pause 后 Worker 模拟循环不再推进 episode。
- `test_production_deployment_contract.py`：服务集含 `series-run-worker`；`redis` AOF 命令保留；API 与 Worker 均有 `REDIS_URL`。

### 10.3 本地手工验收脚本（不入库强制 CI）

见 §11；验收清单写入 PR 描述。

---

## 11. Rollout / Local how-to（发布与本地操作）

### 11.1 本地（开发）

1. 确保 Redis：`docker compose -f compose.production.yml up -d redis`（或开发用 `docker-compose.yml` 的 redis）。
2. 导出 `REDIS_URL=redis://127.0.0.1:6379/0` 与现有 `DATABASE_URL`。
3. 安装依赖：`pip install -r requirements.txt`（含 redis 客户端）。
4. 终端 A：照常启动 API（`uvicorn`）。
5. 终端 B：`cd backend && python -m app.services.series_run_worker`。
6. 调用 `POST /api/v1/series-runs/{id}/execute-async`，观察 Worker 日志与 DB `status` 推进。
7. 执行中途 `POST .../pause`，确认停止；`resume` 后再 `execute-async` 续跑。
8. 走媒体与质量门后，确认 Run 进入 `completed`，且故意缺少质量报告时停留在 `blocked` 而非 `completed`。

### 11.2 生产（compose.production.yml）

1. 合并本切片后构建后端镜像。
2. `docker compose -f compose.production.yml up -d redis postgres` → `api` → **`series-run-worker`**。
3. 滚动：先部署含新队列代码的 API（入队到 Redis），再拉起 Worker；回滚时先扩旧 API 前确认队列已排空或可接受回收重放。
4. 监控：Redis list 长度、`processing` 堆积、锁数量、Worker 重启次数；对接现有健康检查体系（G8 完整告警手册仍属后续，本切片至少暴露 Worker 日志与 compose health）。

### 11.3 功能开关

环境变量 `SERIES_RUN_QUEUE_BACKEND=redis|memory`：

- 生产与 CI 集成默认 `redis`（缺 `REDIS_URL` 则启动失败，fail-closed）。
- 单测可强制 `memory` 仅用于纯单元替身；**禁止**生产回落 memory。

---

## 12. Risks（风险）

| 风险 | 影响 | 缓解 |
|---|---|---|
| 多 API worker 旧代码残留进程内 Task | 双执行 | 删除 `_tasks` 路径；部署契约测试禁止回归 |
| `BLMOVE` 与 Redis 版本 | 语法不可用 | 镜像固定 `redis:7-alpine`；本地文档写明 ≥6.2 |
| 锁 TTL 短于单 stage 模型超时 | 误并行 | 心跳续期；TTL≥`SERIES_STAGE_MODEL_TIMEOUT_SECONDS`（已有默认 90）的 2 倍以上，本切片锁续期间隔 30s、TTL 120s |
| 将 Submission completed 误当 Run completed | 商用假阳性 | 契约测试 + `gate_summary` 审计字段 |
| pause 仅改 DB、Worker 不查 | 暂停无效 | stage 边界双读 DB+Redis 信号 |
| processing 回收导致重复 stage | 重复副作用 | 依赖现有 `create_or_resolve_*` 幂等；测试恢复路径 |
| Worker 与 API 代码版本漂移 | 行为不一致 | 同镜像同 tag 部署 |
| Redis AOF 磁盘满 | 队列停写 | 沿用数据盘监控；失败 fail-closed 返回 503 |

---

## 13. Success criteria for commercial（可商用成功标准）

对本切片「可商用」按 G4 任务/媒体耐久与 FSM 诚实性裁剪，必须全部满足：

1. **持久排队：** kill -9 API 进程后，已 `queued` 的任务仍在 Redis；Worker 拉起后继续执行直至 DB 达 `shots_ready` 或 `failed`。
2. **跨进程单飞：** 两个 Worker 副本 + 两次 `execute-async`，同一 `run_id` 不会并行推进两个 stage（用锁争用计数或 stage `attempt_count` 断言）。
3. **重启恢复：** Worker 在 episode 中途被杀死，回收后重入，已完成 stage 不重复建 canonical 行（沿用现有 recovery 测试语义）。
4. **pause 有效：** 暂停后 30s 内无新的 episode stage 提交。
5. **尾部诚实闭合：** 质量门通过 ⇒ `media_running→evaluating→completed` 有序发生；仅 Submission `completed` ⇒ Run **不是** `completed`。
6. **失败可见：** 媒体失败 ⇒ `failed`；缺质量证据 ⇒ `blocked`，且 `gate_summary.media_tail` 含稳定 `blocker_code`。
7. **部署契约：** `compose.production.yml` 含健康 Redis（AOF）与 `series-run-worker`；`test_production_deployment_contract` 通过。
8. **无范围污染：** 变更集不含 Seedance 六证据、计费账本、巨型 endpoint 拆分。

全部 8 条通过后，本切片可标记为 **G4 任务耐久 + FSM 尾部闭合的商用候选增量**；整平台商用仍需 G0–G8 其余门禁，不在本文宣称完成。

---

## 14. 实施顺序建议（供后续 plan/coding 会话）

1. 落地 `redis_client` + 重写 `series_run_execution_queue` + 队列单测。  
2. 实现 `series_run_worker` + compose 服务 + 部署契约测试。  
3. Orchestrator pause 检查点。  
4. `close_media_tail` + generation 接线 + 尾部 FSM 测试。  
5. 本地按 §11 跑通重启/暂停/尾部三条手工剧本，再开 PR。

---

## 15. 已确认决策摘要

- Redis 持久队列经 `REDIS_URL`，替换进程内 `_tasks`。  
- 保留 `execute-async`；Worker 消费并调用 `SeriesRunOrchestrator.execute`。  
- 每 `run_id` 单飞；重启安全；与 pause 协作。  
- 真实媒体成功 + 质量门通过后自动 `media_running → evaluating → completed`；失败走 `failed`/`blocked`。  
- Submission completed 不得伪造 Run completed。  
- 目标：G4 任务/媒体耐久 + FSM 闭合的可商用切片。  
- 范围外：Seedance 六证据、计费账本、巨型 endpoint 拆分。  
- API 与键设计优先复用现有文件模式，已对照：`series_run_execution_queue.py`、`series_run_orchestrator.py`、`series_anchor_generation/generation.py`、`compose.production.yml`。
