# 小说 → 平台 Publication 一键流水线设计

**日期：** 2026-11-03（Asia/Shanghai）  
**仓库：** `hackersun/ai-video-platform`（本地路径 `/Users/sunqinyue/Documents/work/BJDEV/claude/ai-video-platform`）  
**分支：** `feat/series-run-redis-queue-and-tail-fsm`（本文仅文档，不实现业务代码）  
**状态：** 已按批准决策落盘  
**上游基线：** `docs/superpowers/specs/2026-11-03-series-run-redis-queue-and-tail-fsm-design.md` 已落地 Redis 持久队列 / `series-run-worker` / `close_media_tail`

---

## 1. Goal（目标）

交付一条**整书粒度、单请求驱动**的小说 → 平台成片发布流水线：用户对一本已具备章节与整书计划的小说发起一次请求后，系统在后台自动推进到：

1. **平台最终 mp4**（`render_backend=ffmpeg_local` 或等价最终渲染，`render_status=rendered`，`output_url` 为 `.mp4/.mov/.webm`）；
2. **平台 Publication 记录与可访问 URL**（`POST /api/v1/synthesis/publish` 语义产物：`publications.id` + `video_url` / `export_url`，以及前端发布详情路径）。

成功判定以**平台内 Publication**为准，**不**对接抖音、Bilibili 或其他外部分发平台。

本设计必须同时满足：

1. **整书一次请求**：一个 pipeline 请求覆盖全书所有计划集，而不是「每集点一次」或「仅关键镜头冒烟」作为终态。
2. **复用已完成耐久执行面**：继续使用 `REDIS_URL` 队列、`series-run-worker`、`SeriesRunOrchestrator`、`close_media_tail`；禁止回退到进程内 `asyncio.Task` 字典执行整书。
3. **诚实闭合**：`SeriesAnchorGenerationSubmission.status == completed` 不得伪造 `SeriesProductionRun.status == completed`；预览包 / HTML 审阅包不得伪造可发布 Publication。
4. **可商用分阶段**：按缺口地图四阶段交付，每阶段有可证伪的商用成功标准，而不是「页面能点完」即宣称完成。

---

## 2. Non-goals（非目标）

| 明确不做 | 说明 |
|---|---|
| 外部分发平台 | 不实现抖音 / Bilibili / 微信视频号上传、账号 OAuth、外链同步 |
| 改变既有 `ACTIVE_STATES` 顺序名 | `created → … → completed` 仍由 `series_run_orchestrator.py` 权威持有；发布阶段用**并列 Publication Pipeline FSM**，不把 `published` 硬塞进 Run 的 +1 前进规则 |
| 替换 Celery 全局任务平台 | 不引入 Celery / 通用 Job 框架；扩展现有 `avp:series_run:*` 模式为 pipeline 队列或同 Worker 内阶段调度 |
| Seedance 六证据矩阵扩容 | 不在本设计内重写供应商证据体系；质量自动化只消费现有 `anchor_quality_reports` / `QualityEvaluation` / `publication_readiness` |
| 完整 G6 计费账本重做 | 商用门禁阶段可**读取**现有成本/预算字段并 fail-closed；不新建预扣退款账本实现 |
| 巨型 endpoint 拆分大重构 | `series_runs.py` / `workflow.py` / `synthesis.py` 仅允许为接线增加最小路由与编排服务，不做目录级搬迁 |
| 单集草片产品替代整书终态 | `frontend/src/lib/episode-preview-production.ts` 的 `local_artifact_package` 草片链路可复用技术件，但**不是**本流水线商用终态 |
| 前端完整发布中心重做 | 本设计以后端编排与契约为主；前端只需能创建 pipeline、轮询状态、打开 Publication URL |

---

## 3. 现状基线与缺口地图（对照真实路径）

### 3.1 已具备（可直接复用）

| 能力 | 真实路径 |
|---|---|
| 整书 Run 模型与幂等键 | `backend/app/models/series_production_run.py`（`user_id+novel_id+series_plan_version+idempotency_key`） |
| Run FSM + episode 构建 | `backend/app/services/series_run_orchestrator.py`（`ACTIVE_STATES`、`build_episodes`、`enter_media_running`、`close_media_tail`） |
| Redis 队列 / 单飞 / pause | `backend/app/core/redis_client.py`、`backend/app/services/series_run_execution_queue.py` |
| Worker 进程 | `backend/app/services/series_run_worker.py`；`compose.production.yml` 服务 `series-run-worker` |
| 媒体生成与尾部接线 | `backend/app/features/series_anchor_generation/generation.py` → `close_media_tail` |
| 整书计划 | `POST/GET /api/v1/novels/{novel_id}/series-plan`（`novels.py` + `series_production.py`） |
| 生产入口投影 | `backend/app/services/novel_production_entry.py` |
| 最终渲染 | `POST /api/v1/workflow/{workflow_id}/render`，`render_backend=ffmpeg_local`（`workflow.py` + `ffmpeg_local_renderer`） |
| 发布门禁 | `backend/app/services/publication_readiness.py`（只认最终视频扩展名 + `render_status=rendered`） |
| Publication CRUD/发布 | `backend/app/api/v1/endpoints/synthesis.py`（`POST /synthesis/publish`、`GET /synthesis/publications/{id}`、`…/download`） |
| Publication 模型 | `backend/app/models/publication.py` |
| 单集草片前端编排（参考） | `frontend/src/lib/episode-preview-production.ts` |
| 整书前端面板 | `frontend/src/components/novels/series-run-panel.tsx`、`frontend/src/features/series-runs/*` |

### 3.2 缺口地图（批准的四阶段）

当前从「小说」到「平台 Publication URL」**不是**一条自动管道，而是多段人工胶水：

```text
小说/章节 ──(人工)──► series-plan ──(人工)──► POST /series-runs
      ──(人工)──► execute-async ──(Worker)──► shots_ready
      ──(人工)──► 选关键镜头 / media/start / generate-selected
      ──(close_media_tail)──► completed
      ──(缺口)──► 每集 ffmpeg_local render
      ──(缺口)──► /synthesis/publish → Publication URL
```

| 阶段代号 | 名称 | 缺口本质 |
|---|---|---|
| **P1** | **post-tail publish glue** | Run `completed` 之后没有自动 render + Publication；成片与发布仍靠 workflow/synthesis 手工调用 |
| **P2** | **front-to-shots** | 从小说页到 `shots_ready` 仍需多次创建 Run / 绑模型 / execute-async；缺少「一请求建齐并跑到镜头就绪」 |
| **P3** | **quality automation** | 关键镜头选择、质量 accept/repair、可信评估仍偏人工；自动化不足会导致整书无法无人值守到发布 |
| **P4** | **commercial gates** | 发布前缺少统一商用门禁编排（权限、耐久、质量诚实性、最终 mp4、观测证据）；页面成功 ≠ 商用成功 |

本设计以 P1→P2→P3→P4 为交付顺序；**第一实现切片 = P1**。

---

## 4. Ideal E2E（理想端到端）

### 4.1 用户可见剧本

1. 用户已有小说 `novel_id`，章节齐全，且存在有效 `series_plan`（或 pipeline 请求允许 `ensure_series_plan=true` 时由服务端生成并锁定版本）。
2. 用户（或 Studio「一键发布到平台」）调用一次：
   - `POST /api/v1/novels/{novel_id}/publication-pipelines`
3. API **立即 202**，返回 `pipeline_id`、`series_run_id`（新建或复用）、`status=queued`。
4. 用户轮询 `GET /api/v1/publication-pipelines/{pipeline_id}`，看到阶段推进与每集证据。
5. 终态 `status=succeeded` 时响应包含：
   - `final_video_url`：平台最终 mp4（整书拼接成片或「主交付集」成片，见 §6.3 交付物规则）；
   - `publication_id` / `publication_url`：平台 Publication 详情与下载入口；
   - `episode_publications[]`：每集可选的成片与发布记录（整书主 Publication 仍唯一作为成功契约字段）。
6. 任意硬失败进入 `failed` 或 `blocked`，带稳定 `blocker_code`；可 `POST …/resume` 后从断点续跑，不重新扣出已成功产物。

### 4.2 系统内部主路径（理想）

```text
Client
  │ POST publication-pipelines
  ▼
API：校验归属 / 商用门禁预检(P4 启用后) / 确保 series_plan
  │ 创建或复用 SeriesProductionRun
  │ 创建 NovelPublicationPipeline 行
  │ 入队 avp:publication_pipeline:queue（或扩展现有 worker 消费）
  ▼
Worker
  ├─ Phase front-to-shots：必要时 create/execute Run → shots_ready
  ├─ Phase media+quality：选镜 → media/start → generate（全书镜头策略见 §6）
    │                 → close_media_tail → Run completed
  ├─ Phase post-tail publish glue：
  │     每集 workflow render(ffmpeg_local)
  │     → 整书 assemble（多集成片拼接，若配置 book_assemble=true）
  │     → evaluate_publication_readiness
  │     → 创建 Publication（等价 /synthesis/publish）
  └─ 写 pipeline.status=succeeded + 证据摘要
```

### 4.3 成功与失败的产品语义

| 结果 | 用户看到 | 系统约束 |
|---|---|---|
| 成功 | 可播放最终 mp4 + Publication 页面/下载 URL | `publication_readiness.is_publishable==true` 且 Publication `status∈{succeeded,published}` |
| 阻塞 | 明确下一步（补章节、修质量、补模型绑定） | `blocked` + `blocker_code`，不生成假 Publication |
| 失败 | 可恢复错误与 run/pipeline 关联 ID | `failed`；已生成的中间 artifact 保留供 resume |

---

## 5. Target API shape（目标 API 形态）

路由挂在现有 `api_router` 下，前缀建议新增薄 endpoint 文件  
`backend/app/api/v1/endpoints/publication_pipelines.py`，并在 `backend/app/api/v1/router.py` `include_router`。  
**不**把整书编排继续堆进已经庞大的 `workflow.py`。

### 5.1 创建（一键入口）

`POST /api/v1/novels/{novel_id}/publication-pipelines` → **202**

请求体：

```json
{
  "idempotency_key": "user-visible-or-client-uuid",
  "series_plan_version": "可选；缺省取小说当前 series_plan.version",
  "ensure_series_plan": true,
  "model_bindings": {},
  "budget_policy": {},
  "delivery": {
    "mode": "whole_book_single_mp4",
    "render_backend": "ffmpeg_local",
    "visibility": "private",
    "title": "可选；缺省用小说标题",
    "publish_status": "published"
  },
  "media_policy": {
    "shot_scope": "all_episode_shots",
    "allow_anchor_smoke_only": false
  },
  "quality_policy": {
    "auto_accept_ready_reports": true,
    "block_on_untrusted_evaluation": true
  },
  "gates": {
    "require_commercial_gates": false
  }
}
```

响应体（202）：

```json
{
  "pipeline_id": "…",
  "novel_id": "…",
  "series_run_id": "…",
  "status": "queued",
  "stage": "accepted",
  "execution_status": "queued",
  "links": {
    "self": "/api/v1/publication-pipelines/{pipeline_id}",
    "series_run": "/api/v1/series-runs/{series_run_id}"
  }
}
```

`execution_status` 复用既有三值语义习惯：`queued` / `already_running` / `not_required`（当同幂等键已成功则 `not_required` 并返回既有 `publication_id`）。

### 5.2 查询

`GET /api/v1/publication-pipelines/{pipeline_id}` → 200

```json
{
  "pipeline_id": "…",
  "novel_id": "…",
  "series_run_id": "…",
  "status": "running",
  "stage": "episode_rendering",
  "series_run_status": "completed",
  "episodes": [
    {
      "episode_number": 1,
      "workflow_id": "…",
      "shots_ready": true,
      "media_completed": true,
      "render_status": "rendered",
      "synthesis_job_id": "…",
      "output_url": "https://…/ep1.mp4",
      "blocker_code": null
    }
  ],
  "final_video_url": null,
  "publication_id": null,
  "publication_url": null,
  "gate_summary": {},
  "blocker_code": null,
  "updated_at": "2026-11-03T22:50:00+08:00"
}
```

成功时 `status=succeeded`，`final_video_url` 与 `publication_url` 必填。

### 5.3 控制面

| 方法 | 路径 | 语义 |
|---|---|---|
| `POST` | `/publication-pipelines/{id}/pause` | 置 `paused`；同时对关联 `series_run_id` 调用既有 pause 信号 |
| `POST` | `/publication-pipelines/{id}/resume` | 恢复 pipeline 阶段；若 Run 仍需推进则再 `execute-async` |
| `POST` | `/publication-pipelines/{id}/cancel` | 协作式取消；不删除已有 Publication；状态 `cancelled` |
| `GET` | `/novels/{novel_id}/publication-pipelines` | 按小说列出最近流水线（默认 20） |

### 5.4 与既有 API 的关系

- **保留** `POST /series-runs`、`execute-async`、`generate-selected`、`/workflow/{id}/render`、`/synthesis/publish` 作为底层能力与人工逃生舱。
- Publication Pipeline **编排调用**这些能力（服务内函数优先，HTTP 自调用为次），对外只暴露 pipeline 合同。
- 前端一键入口只依赖 pipeline API；Series Run 面板继续服务调试与恢复。

---

## 6. Stage machine（阶段机）

### 6.1 两层状态机

**层 A — SeriesProductionRun（已有，不改顺序）**

```text
created → preflight → planning → facts_ready → assets_ready
→ episodes_building → shots_ready → anchor_ready → media_running
→ evaluating → completed
(+ failed | blocked | paused)
```

权威：`transition_run` / `close_media_tail`。

**层 B — NovelPublicationPipeline（新增并列 FSM）**

```text
accepted
→ ensuring_plan
→ ensuring_run
→ run_front_to_shots      # 直到 shots_ready（P2 自动化；P1 可要求 Run 已存在或同步创建后 execute）
→ run_media_quality       # media/start + 全书镜头生成 + close_media_tail
→ episode_rendering       # 每集 ffmpeg_local
→ book_assembling         # 可选整书拼接
→ publication_gating      # publication_readiness +（P4）commercial gates
→ publishing              # 创建 Publication
→ succeeded

旁路：paused | blocked | failed | cancelled
```

层 B 状态存在新表或 `publication_pipelines` 模型字段 `status`/`stage`；进度真相在 PostgreSQL/SQLite，Redis 只调度。

### 6.2 阶段转移规则

1. 只允许文档声明的前进边；禁止 `run_front_to_shots → publishing` 跳跃。
2. `run_media_quality` 完成条件：关联 Run `status==completed` 且 `gate_summary.media_tail.result==passed`。
3. `episode_rendering` 完成条件：计划内每一集都有 `render_status==rendered` 且最终视频 URL 通过 `is_final_video_url`。
4. `publication_gating` 失败（不可发布）→ `blocked`（`blocker_code=publication_not_ready` 或更细门禁码），**不得**写 Publication。
5. `publishing` 成功后才进入 `succeeded`；Publication 行与 pipeline 在同一逻辑事务边界提交（DB commit 顺序：先 Publication 与证据，再 pipeline succeeded）。
6. Run 已 `completed` 但 pipeline 在 render 失败：pipeline `failed/blocked`，**不**回写伪造 Run 非 completed；修复后从 `episode_rendering` resume。

### 6.3 整书交付物规则（`delivery.mode`）

| mode | 行为 |
|---|---|
| `whole_book_single_mp4`（默认） | 每集先 `ffmpeg_local` 出集 mp4，再按集序拼接为单文件最终 mp4，再发一条主 Publication |
| `per_episode_publications` | 每集独立 Publication；pipeline 成功要求全部集成功；`publication_url` 指向汇总页或第一集，同时 `episode_publications` 全量返回 |
| `primary_episode_only` | 仅发布 `series_plan` 标记的主集；仍属整书 pipeline 的受控降级，必须在创建时显式选择，默认禁止静默降级 |

`media_policy.shot_scope`：

- 默认 `all_episode_shots`：每集全部镜头进媒体与成片（整书一键的产品语义）。
- `anchor_shots_only` 仅允许在验收/金丝雀配置下使用，且 `allow_anchor_smoke_only=true`；**商用 `require_commercial_gates=true` 时拒绝该降级**。

---

## 7. Reuse existing modules（复用清单）

| 步骤 | 复用模块 | 用法 |
|---|---|---|
| 确保整书计划 | `series_production.py`、`novels` series-plan endpoints | `ensure_series_plan` 时调用既有生成/读取，锁定 `series_plan_version` |
| 创建/复用 Run | `create_series_run_record`（series_runs 特征域） | 同一 `idempotency_key` 空间可派生 `pipeline:{key}` 避免与手工 Run 撞车的策略见 §9 |
| 跑到 shots | `start_series_run_execution` + Worker + `SeriesRunOrchestrator.execute` | 禁止新写进程内任务字典 |
| 媒体与尾部 | `enter_media_running`、`generate-selected` 服务函数、`close_media_tail` | Pipeline Worker 内直接调服务层 |
| 渲染 | `workflow` 的 ffmpeg_local 路径 / `ffmpeg_local_renderer.render_workflow_package` | 服务内调用，写 SynthesisJob `render_status=rendered` |
| 发布门禁 | `evaluate_publication_readiness` | gating 阶段唯一视频可发布判定 |
| 创建 Publication | `synthesis.publish_export` 核心逻辑抽成 service 函数供 pipeline 复用 | 保持 URL 与权限行为一致 |
| 前端轮询模式 | `frontend/src/features/series-runs/execute-and-poll.ts` | 可平行增加 `publication-pipelines` poll helper |
| 影响分析 | `series_production.resolve_production_graph_artifact_impact` | 计划变更后阻断发布（`production_graph_superseded`） |

新建（设计允许的最小面）：

| 路径 | 职责 |
|---|---|
| `backend/app/models/publication_pipeline.py` | pipeline 行：状态、阶段、关联 run/publication、gate_summary、幂等键 |
| `backend/app/services/publication_pipeline_orchestrator.py` | 层 B FSM 推进 |
| `backend/app/services/publication_pipeline_queue.py` | Redis 键 `avp:publication_pipeline:*`，模式复制 series_run 队列 |
| `backend/app/services/publication_pipeline_worker.py` **或** 扩展 `series_run_worker` 双队列消费 | 同镜像部署 |
| `backend/app/api/v1/endpoints/publication_pipelines.py` | §5 API |
| `backend/tests/test_publication_pipeline_*.py` | 合同与 fail-closed |

---

## 8. Fail-closed rules（失败即关闭规则）

1. **Redis 不可用**：创建/入队返回 HTTP 503；禁止静默改走内存队列或 API 进程内长任务。
2. **缺 `REDIS_URL` 且后端为 redis**：Worker/API 启动或首次入队失败，与现网 Series Run 一致。
3. **`publication_readiness` 未通过**：不得插入 `status=published/succeeded` 的可播放假发布；预览包 / `local_artifact_package` 不得作为商用终态。
4. **仅 Submission completed**：不得标记 pipeline `succeeded`，也不得标记 Run `completed`（已有尾部测试约束继续生效）。
5. **质量不可信**：`trusted_multimodal_evaluation_required` 或选中镜头缺少 `ready=true` 报告 → pipeline `blocked`（`quality_gate_incomplete`），除非显式非商用验收开关且不得在 `require_commercial_gates=true` 时打开。
6. **镜头范围偷降级**：商用门禁开启时，`anchor_shots_only` 直接 409/blocked。
7. **外部分发配置**：请求体若出现 `douyin`/`bilibili` 等外发目标字段 → 400，明确「仅平台 Publication」。
8. **权限**：pipeline 必须校验小说归属；带 `project_id` 时复用 `require_project_role`（与 synthesis 发布一致，editor 才能发布）。
9. **Production Graph 已 superseded**：沿用 `publication_readiness` 的 `production_graph_superseded`，阻断发布。
10. **部分集成功**：`whole_book_single_mp4` 模式下任一整集 render 失败 → 整 pipeline 不得 `succeeded`。

---

## 9. Idempotency（幂等）

| 键/范围 | 规则 |
|---|---|
| Pipeline 创建 | 唯一约束建议：`(user_id, novel_id, series_plan_version, idempotency_key)`；重复 POST 返回同一 `pipeline_id`（200/202 均可，但 body 稳定） |
| Series Run | 继续使用 `SeriesProductionRun` 现有唯一约束；pipeline 使用 `idempotency_key = "pubpipe:" + client_key` 创建/复用 Run，避免与用户手工 Run 键冲突 |
| 队列 | 每 `pipeline_id` 单飞锁 `avp:publication_pipeline:lock:{id}`；重复入队返回 `already_running` |
| 每集 render | 以 `(workflow_id, render_backend, content_fingerprint)` 为逻辑幂等；已 `rendered` 且 URL 仍可读则跳过 |
| Publication | 同一 `(pipeline_id, delivery.mode)` 只创建一条主 Publication；重入发现已有则复用 ID |
| `close_media_tail` | 保持既有幂等（`completed` no-op；`evaluating` 可补完） |
| Resume | 从当前 `stage` 继续，不重置已 `passed` 的阶段证据 |

---

## 10. Observability（可观测性）

### 10.1 结构化字段（必须落库）

`publication_pipelines.gate_summary` / `run_metadata` 同类 JSON 固定键：

- `stage_timings[]`：`{stage, entered_at, exited_at, result}`
- `series_run_ref`：`{id, status, media_tail}`
- `episode_render_refs[]`：`{episode_number, workflow_id, synthesis_job_id, render_backend, render_status, output_url}`
- `publication_ref`：`{id, status, video_url, export_url}`
- `blocker_code` / `blocker_detail`
- `queue`：`{enqueued_at, attempt, worker_id, last_heartbeat}`

### 10.2 日志与指标

- 日志：`pipeline_id`、`novel_id`、`series_run_id`、`stage`、`blocker_code` 强制结构化字段。
- 指标（最小）：队列长度、processing 堆积、阶段耗时直方图、成功/阻塞/失败计数、单飞锁争用次数。
- 追溯：从 Publication `metadata` 写回 `pipeline_id` 与 `series_run_id`，保证发布页能反查流水线。

### 10.3 与 G 观测对齐

P4 启用后，pipeline 成功响应必须能导出「证据包」摘要（ID 列表 + 门禁通过时间），供商用验收粘贴；不要求本阶段新建完整 G8 告警手册，但日志与 DB 证据必须足够人工审计。

---

## 11. Local / prod runbook sketch（运行手册草图）

### 11.1 本地

1. 启动依赖：`docker compose -f compose.production.yml up -d redis postgres`（或开发等效栈）。
2. 导出 `REDIS_URL=redis://127.0.0.1:6379/0`、`DATABASE_URL=…`。
3. 终端 A：API（uvicorn）；终端 B：`python -m app.services.series_run_worker`；终端 C（P1 后）：`python -m app.services.publication_pipeline_worker`（若未合并进同一 Worker）。
4. 准备小说：导入/确认章节 → `POST /novels/{id}/series-plan`。
5. 一键：`POST /novels/{id}/publication-pipelines`（带 `idempotency_key`）。
6. 轮询至 `succeeded`；下载 `final_video_url`，确认本机可播；打开 `publication_url`。
7. 负面例：去掉质量报告或强制 preview package → 必须 `blocked`/`failed`，且无 Publication。
8. 重启例：render 中杀 Worker → 回收后续跑，不双发 Publication。

### 11.2 生产

1. 同镜像部署 API + `series-run-worker` + publication pipeline worker（或双队列同进程）。
2. 滚动顺序：先 API（可入队）→ Worker；回滚前排空 `avp:publication_pipeline:processing` 或接受回收重放。
3. 功能开关：
   - `PUBLICATION_PIPELINE_ENABLED=true`
   - `PUBLICATION_PIPELINE_REQUIRE_COMMERCIAL_GATES=false`（预发可关，生产商用开）
4. 监控队列与 `blocked` 比率；`publication_not_ready` 激增视为发布门禁回归。

---

## 12. Phased delivery（分阶段交付与商用成功标准）

### 12.1 P1 — post-tail publish glue（第一实现切片）

**范围：** Run 已能到 `completed` 的前提下，自动每集 `ffmpeg_local` →（可选拼接）→ `publication_readiness` → 平台 Publication。

**成功标准（全部满足才算 P1 商用候选增量）：**

1. 对已 `completed` 的整书 Run，创建 pipeline 可无人值守产出 `final_video_url` + `publication_id`。
2. 预览包路径被拒绝；契约测试覆盖 `publication_readiness` 失败不建发布。
3. 幂等：两次相同 `idempotency_key` 不创建第二条主 Publication。
4. Worker 重启不丢 render/publish 阶段；单飞有效。
5. 不宣称 front-to-shots / 质量全自动 / 外发平台完成。

### 12.2 P2 — front-to-shots

**范围：** 从小说 + series_plan 一请求创建/复用 Run 并执行到 `shots_ready`（含模型绑定校验与 preflight）。

**成功标准：**

1. 无手工 `execute-async` 点击也能到 `shots_ready`。
2. pause/resume 与既有 Series Run 协作。
3. 缺章节 / 缺计划 → `blocked` 稳定码，不空转烧模型。

### 12.3 P3 — quality automation

**范围：** 自动镜头范围（默认全书镜头）、自动消费 ready 质量报告、不可信评估 fail-closed；最小自动 repair 策略可只做「阻断 + 可恢复」，不做无限重试烧钱。

**成功标准：**

1. 无需人工点 `anchors/quality` 即可在可信报告齐全时通过 `run_media_quality`。
2. 缺可信评估必 `blocked`，测试锁定 Submission≠Run≠pipeline succeeded。
3. 商用模式拒绝 `anchor_shots_only` 静默成功。

### 12.4 P4 — commercial gates

**范围：** 在 `publication_gating` 串联商用门禁（与仓库治理/商用就绪文档同向）：

- 身份与对象归属；
- 队列耐久与单飞证据存在；
- 质量诚实性（媒体尾部 + publication_readiness）；
- 最终 mp4 存在且可追溯；
- 成本/预算策略字段完整（读现有，不新造账本）；
- 观测证据包可导出。

**成功标准：**

1. `gates.require_commercial_gates=true` 时任一门禁失败 → 不发布。
2. 成功响应含证据摘要，可支撑人工商用验收签字。
3. 仍不包含抖音/Bilibili；仍不宣称 G0–G8 平台级全部完工，只宣称「本流水线发布门禁」通过。

---

## 13. First implementation slice（第一实现切片 = P1）

### 13.1 切片目标

实现 **NovelPublicationPipeline P1**：假设关联 `SeriesProductionRun` 已 `completed`（或创建时传入 `series_run_id` 且状态为 `completed`），完成：

1. 读取 Run `episodes[]` 中各集 `workflow_id`；
2. 对每集调用 ffmpeg_local 最终渲染；
3. 按 `delivery.mode=whole_book_single_mp4` 拼接（若仅一集则跳过拼接）；
4. `evaluate_publication_readiness` 通过后创建平台 Publication；
5. pipeline → `succeeded`，返回 Publication URL。

P1 **可以**接受请求体带已完成的 `series_run_id`；也可以在同请求内若 Run 未完成则 `blocked` 并提示先跑 Run（把自动 front/media 留给 P2/P3）。为避免切片膨胀，P1 默认合同：

- 若提供 `series_run_id` 且 `status==completed` → 进入 render/publish；
- 若未提供但小说存在唯一已完成 Run 与匹配 `series_plan_version` → 自动绑定；
- 否则 `blocked` / `blocker_code=series_run_not_completed`（P2 再解除）。

### 13.2 P1 文件级任务顺序

1. 模型 + migration/建表 `publication_pipelines`。
2. `publication_pipeline_orchestrator`：阶段 `accepted→episode_rendering→book_assembling→publication_gating→publishing→succeeded`。
3. Redis 队列与 worker（复制 series_run 模式，前缀 `avp:publication_pipeline:`）。
4. API：创建/查询/pause/resume。
5. 从 `synthesis.py` 抽「创建 Publication」纯服务函数供编排调用，endpoint 改走同一函数。
6. 测试：`test_publication_pipeline_post_tail_glue.py`（成功、门禁拒绝、幂等、重启单飞）。
7. 本地按 §11.1 跑通一本书一集与两集拼接各一条。

### 13.3 P1 明确不包含

- 自动 `execute-async` 到 shots（P2）
- 自动 generate-selected / 质量自动 accept（P3）
- `require_commercial_gates` 全套（P4）
- 任何外发平台
- 修改 `ACTIVE_STATES` 列表

---

## 14. Risks（风险）

| 风险 | 影响 | 缓解 |
|---|---|---|
| 把单集草片 `local_artifact_package` 误当终态 | 假商用发布 | P1 测试强制 `ffmpeg_local` + readiness |
| 只跑关键镜头却标记整书成功 | 产品欺诈 | 默认 `all_episode_shots`；商用拒绝 anchor-only |
| 扩展 ACTIVE_STATES 破坏既有尾部测试 | 回归 | 并列 pipeline FSM，不改 Run +1 规则 |
| 双 Worker 双队列锁设计不一致 | 双发 Publication | 统一锁 TTL/心跳/回收参数；Publication 层幂等 |
| `workflow.py` 继续膨胀 | 不可维护 | 编排放独立 service，endpoint 只接线 |
| 整书拼接音画同步问题 | 成片不可用 | P1 先要求每集已是最终 mp4 再 concat；失败 blocked 而非静默 |
| 前端仍引导去外发 | 范围漂移 | API 400 外发字段；文档与 UI 文案只提平台 Publication |

---

## 15. 已确认决策摘要

- **终态**：平台最终 mp4 + 平台 Publication URL；**不做**抖音/Bilibili。
- **粒度**：整书单一 pipeline；一次请求跑全书（P1 先接 completed Run 的发布胶水，P2/P3 补齐前端到媒体自动段）。
- **执行面**：建立在已完成的 Redis 队列 / `series-run-worker` / `close_media_tail` 之上。
- **阶段顺序（缺口地图）**：post-tail publish glue → front-to-shots → quality automation → commercial gates。
- **状态机**：Run FSM 保持；新增 Publication Pipeline 并列 FSM。
- **第一切片**：P1 post-tail publish glue，产出真实可发布 Publication。

---

## 16. 对照路径索引（实现前只读清单）

- `docs/superpowers/specs/2026-11-03-series-run-redis-queue-and-tail-fsm-design.md`
- `docs/superpowers/plans/2026-11-03-series-run-redis-queue-and-tail-fsm.md`
- `backend/app/services/series_run_orchestrator.py`
- `backend/app/services/series_run_execution_queue.py`
- `backend/app/services/series_run_worker.py`
- `backend/app/core/redis_client.py`
- `backend/app/features/series_anchor_generation/generation.py`
- `backend/app/services/publication_readiness.py`
- `backend/app/api/v1/endpoints/synthesis.py`
- `backend/app/api/v1/endpoints/workflow.py`（`/{workflow_id}/render`）
- `backend/app/api/v1/endpoints/series_runs.py`
- `backend/app/api/v1/endpoints/novels.py`
- `backend/app/models/publication.py`
- `backend/app/models/series_production_run.py`
- `compose.production.yml`
- `frontend/src/lib/episode-preview-production.ts`
- `frontend/src/features/series-runs/*`
