# 后端管线可靠性审计 — 小说→视频商用一键路径

| 项 | 值 |
|---|---|
| 日期 | 2026-11-10（Asia/Shanghai） |
| 分支 | `feat/series-run-redis-queue-and-tail-fsm` |
| HEAD | `c91fc5f9` |
| 范围 | 只读审计：FastAPI / SQLAlchemy / Redis 队列 / Worker / FFmpeg / Series Run 尾态 FSM / 多角色配音 / plan fingerprint / 恢复·取消·重试 / 假模型 vs 真模型 / 本地·S3·七牛 / 幂等 / 卡住态 / Worker 崩溃恢复 / 并发超时 / 大文件导入 |
| 不做 | 不改代码、不 commit、不 push、不开 PR、不 git stash |
| 已知已修（历史验证） | 多角色卡住、H.264 成片、排队 UI、下载 Content-Disposition、conftest 隔离、plan fingerprint 重建 |
| 已知未验 | 真模型、真对象存储、PostgreSQL 实跑、网关限流 |

---

## 1. 结论摘要

模拟模型 + 真 Redis + 真 FFmpeg 的本机一键路径（注册→模型→小说→一键生成→看片→下载→发布）在 2026-11-08 前端全流程验证中已可用；连续生成与 Worker kill -9 恢复在假模型下通过。

**距「可商用」仍差四道硬门禁，加上若干会在真模型下放大成双计费/卡住的可靠性缺口：**

1. **真模型端到端未验**（费用门禁、多角色真实配音、供应商不确定态恢复）。
2. **真对象存储未验**（生产默认拒绝 `STORAGE_PROVIDER=local`，S3/七牛仅单次上传、无断点续传）。
3. **PostgreSQL 生产编排放了，但本机/CI 仍大量走 SQLite**；并发写与部分唯一索引行为未在 Postgres 上做压测验收。
4. **网关无请求体大小与 QPS 限流**（Caddy 仅反代；上传上限依赖应用层，multipart 解析前仍可被打满磁盘）。

额外高优先级可靠性问题（代码层面已存在，假模型下不易暴露）：

- **租约心跳只在阶段边界刷新**（`LOCK_TTL=120s` / `HEARTBEAT_TTL=60s`）。单阶段真模型/FFmpeg 超过该时间后，另一 Worker 可 reclaim → **双跑、双计费风险**。
- **一键配音只自动选定「一个」主角声线**；媒体预检要求**每个说话角色**有 `voice_binding`。假模型靠 acceptance fixture 给全员绑同一演示音色；**真模型下多角色仍可能 `voice_binding_missing` 阻断**。
- **队列 dead-letter 多数只写 metadata / 丢弃 processing 项，不强制把 run/pipeline 标成 failed**，界面可能长期「进行中/排队」而无可操作 blocker。

---

## 2. 一键路径架构

### 2.1 用户可见入口

前端「一键生成视频」→ `POST /api/v1/novels/{novel_id}/publication-pipelines`（202 Accepted）。

配套：`pause` / `resume` / `cancel`、批量状态查询、发布页拉取成片。

### 2.2 两层 FSM + 两条 Redis 队列

```
[浏览器]
   │  POST publication-pipelines (idempotency_key, ensure_series_plan=true)
   ▼
[API]  admission：同一 (user, novel) 仅一条 active(queued|running|paused)
   │  DB 写入 NovelPublicationPipeline status=queued
   │  LPUSH avp:publication_pipeline:queue
   ▼
[publication-pipeline-worker]  BLMOVE → processing；NX 锁 + heartbeat
   │
   ├─① ensure_series_plan_for_pipeline
   │     chapter_fingerprint 变化 → 重建 plan（旧 run 钉住旧 version）
   ├─② ensure_series_run_for_pipeline（幂等键 pubpipe:{client_key}）
   ├─③ SeriesRunOrchestrator.execute → shots_ready
   │     （也可经 series-run-worker / execute-async；DB 为权威进度）
   ├─④ prepare_run_for_media
   │     假模型：deterministic fixture + 自动 live canary
   │     真模型：billing opt-in + auto_bind_models + 主角 voice_selection
   │     + full anchors + story locks + reference + media preflight
   ├─⑤ media 提交 → close_media_tail
   │     media_running → evaluating → completed | blocked | failed
   ├─⑥ FFmpeg 本地合成（libx264 + yuv420p + aac + +faststart）
   └─⑦ 发布 / 可选 persist_private_media（s3|qiniu）
```

### 2.3 Series Run 状态机（尾态）

`ACTIVE_STATES`：

`created → preflight → planning → facts_ready → assets_ready → episodes_building → shots_ready → anchor_ready → media_running → evaluating → completed`

- `paused`：保存 `resume_status`；Redis `pause` 键加速停止（TTL 300s，DB 仍权威）。
- `failed` / `blocked`：只能恢复到 `episodes_building`。
- `close_media_tail`：媒体全成功 + 质量门 `ready` 才 `completed`；媒体失败 → `failed`；质量不全 → `blocked`。
- 乐观锁：`version` 列（StaleDataError → 409）。

### 2.4 队列与崩溃恢复（Series Run / Publication 对称设计）

| 机制 | 实现 |
|---|---|
| 入队 | Redis List `LPUSH` |
| 领取 | `BLMOVE queue → processing`（至少一次） |
| 单飞 | `SET lock NX EX 120` + heartbeat `EX 60` |
| 心跳 | Worker `should_stop` 回调内刷新（阶段间隙） |
| 回收 | 每 15s `reclaim_stale_processing`：无 lock 且无 heartbeat → attempt+1 再入队 |
| 上限 | `MAX_ATTEMPTS=25`；超限记 `queue_dead_letter` 或仅日志丢弃 |
| ACK | `finally` 里 `LREM processing` + 释放锁 |

DB 为进度真相；Redis 只存队列成员、锁、心跳、暂停信号。

### 2.5 存储分层

- 工作副本：始终本地 `/static/exports|generated/...`
- `STORAGE_PROVIDER=local|s3|qiniu`；发布时 `persist_private_media` 上传并写 `.object-store` marker
- 响应侧 `signed_url_for` → 已上传对象用供应商签名 URL，否则本地 HMAC
- `?download=1` → `Content-Disposition: attachment`（跨域下载）
- 生产门禁：`assert_production_safe()` 拒绝 fake + 未允许的 local storage

### 2.6 计费门禁（真模型）

- 默认：每用户 ¥200、每流水线 ¥50（`billing_guard`）
- 未 `live_calls_opt_in` → 一键在 `prepare_run_for_media` 失败关闭
- 生产环境即使设了 `DETERMINISTIC_PROVIDER_FAKE` 也不把账本标 fake

### 2.7 Plan fingerprint

`chapter_fingerprint = sha256(id:chapter_number:content_hash…)`  
`ensure_series_plan_for_pipeline`：指纹变化且 `ensure=true` → 重建 plan；已有 run 钉住自己的 `series_plan_version`。  
Orchestrator 另有「completed run 章节未变才可复用」的 freshness 检查，避免脏成片。

---

## 3. 失败矩阵（商用视角）

| # | 故障场景 | 当前行为 | 用户感知 | 风险 | 严重度 |
|---|---|---|---|---|---|
| F1 | Worker `kill -9` 后重启 | 锁/心跳过期 → reclaim → 续跑（假模型已验约 2 分钟内完成） | 短暂卡住后继续 | 真模型：若卡在供应商已受理阶段，可能重复提交 | **P0**（真模型） |
| F2 | 单阶段耗时 > 60–120s（真视频/长 FFmpeg） | 心跳不刷新 → 被另一 Worker reclaim → 并行执行 | 进度抖动 / 双份费用 | **双计费、双产物** | **P0** |
| F3 | Redis 宕机 | 入队/异步执行 503；已在跑的 DB 进度仍在 | 无法新开一键 | 需运维恢复 Redis + 人工 resume/重入队 | P1 |
| F4 | 多角色说话人无音色（真模型） | media preflight `voice_binding_missing` → pipeline blocked | 「媒体前置检查未通过」 | 假模型被 fixture 掩盖；真模型一键失败 | **P0** |
| F5 | 角色曾被错误归档 | `reactivate_reused_archived_characters` 在 story lock 前拉回 candidate | 修复后可续跑 | 已有回归测试；需保留 | 已缓解 |
| F6 | 章节改动后仍用旧 plan/run | fingerprint 重建 plan；stale completed run 不复用 | 重新生成 | 正确 | 已缓解 |
| F7 | 重复点击一键 | admission 唯一索引 + idempotency；返回 already_running/queued | 不产生第二份任务 | 前端连点 UX 已改善 | 已缓解 |
| F8 | 取消后 Worker 仍持锁 | status=`cancelled`，Worker SKIP；resume 可重入队 | 「已取消」 | 基本正确 | OK |
| F9 | 供应商结果不确定（accepted/reserved/unknown） | recovery API：禁止盲目重试，要求刷新/人工对账 | 专业文案，新手难懂 | 真模型必现路径 | P1 |
| F10 | 队列 attempt 耗尽 | metadata `queue_dead_letter`；reclaim 路径可能只丢弃 | 可能一直像「排队/进行中」 | **无明确 failed + blocker** | **P0** |
| F11 | SQLite 多 Worker 并发写 | 本机默认可跑；生产 compose 用 Postgres | 锁等待 / database is locked | 商用必须 Postgres 并验收 | **P0**（上线） |
| F12 | `STORAGE_PROVIDER=local` 上生产 | `assert_production_safe` 拒绝启动（除非显式允许） | 服务起不来 | 正确 fail-closed；需配真桶 | 门禁 OK / 未验上传 |
| F13 | 大文件小说 >10MiB | 应用层拒收，中文提示拆分 | 明确 | Gateway 未限流时仍可打满解析/磁盘 | P1 |
| F14 | S3/七牛大成片上传失败 | 单次 PUT/form；失败记 warning，不抛穿 | 成片本地可播、外链失败 | 无断点续传、无自动重试编排 | P1 |
| F15 | FFmpeg 缺失 / 无 libx264 | 回退或失败（视路径） | 合成失败 | 镜像需带 ffmpeg+libx264 | P1 |
| F16 | 假模型误开在生产 | 启动直接 RuntimeError | 起不来 | 正确 | OK |
| F17 | Pause 信号 Redis TTL 过期 | DB 仍 paused；Worker 以 DB 为准 | 仍暂停 | Redis 仅加速 | OK |
| F18 | 质量门未齐 | `blocked` + `quality_gate_incomplete` | 需修复后 resume | 真模型质量波动时常见 | P1 |
| F19 | 计费未 opt-in / 超 cap | `live_calls_not_opted_in` / SpendCapExceeded | 中文引导去模型设置 | 符合商用 | OK（待真模型验） |
| F20 | 导入空/错类型/超大 | 校验 + 清理半文件 | 明确中文错误 | Gateway 仍缺 | 应用层 OK |

---

## 4. 商用阻塞缺口（必须上线前关闭）

### B1. 真模型小额端到端（阻塞发布）

- 环境：`DETERMINISTIC_PROVIDER_FAKE` 关闭；用户 opt-in；cap 每次 ¥50 / 账号 ¥200。
- 覆盖：1 章、**≥2 说话角色**、看片/下载/发布、取消重跑、Worker 重启各 1 次。
- 证明：ledger 无意外双计费；成片 H.264 可播；失败有中文 blocker。

### B2. 真对象存储（阻塞多实例/持久化）

- 配 `STORAGE_PROVIDER=s3` 或 `qiniu`，跑通 `persist_private_media` + 签名下载 + 过期刷新。
- 验证跨 API 副本仍能播（不能只靠本机磁盘）。

### B3. PostgreSQL 实跑与迁移（阻塞横向扩展）

- `compose.production.yml` 已声明 Postgres 15 + 两 Worker；需用生产 compose 或等价环境跑通一键 + 并发两小说。
- 确认部分唯一索引 `uq_publication_pipeline_active_novel` 在 Postgres 生效；对比 SQLite 行为。

### B4. 网关限流与请求体上限（阻塞公网暴露）

- 当前 `ops/deploy/Caddyfile` **无** `request_body` / rate limit。
- 至少：全站/API QPS 限流、`/api/*` 与 multipart 上传的 body 上限（≥ 应用层 10MiB 小说、与素材上限对齐并留余量）、慢连超时。

### B5. 长阶段租约（阻塞真模型稳跑）

- 在供应商 poll / FFmpeg 执行循环内定期 `refresh_execution_heartbeat`，或按阶段提高 TTL，并加「同 run 世代令牌」防止双跑。
- 否则 F1/F2 在真模型下不可接受。

### B6. 真模型多角色自动配音（阻塞多角色小说）

- `prepare_run_for_media` 今日只 `persist_voice_selection` 主角；preflight 却要求所有 speaking 实体有 binding。
- 需：为每个说话角色自动分配默认/区分声线（或明确降级为旁白策略），并写回归测试（非仅 deterministic fixture）。

### B7. Dead-letter → 可操作终态

- attempt 耗尽或 reclaim 丢弃时：pipeline/run → `failed`，`blocker_code=queue_dead_letter`，前端可「重试/联系支持」。

---

## 5. 加固优先级

### P0（本周，上线前门禁）

1. 长阶段心跳 / 防双跑令牌（B5）
2. 真模型多角色 voice 自动绑定（B6）
3. Dead-letter 落失败态（B7）
4. 生产 compose：Postgres + Redis AOF + 两 Worker + ffmpeg 镜像自检
5. Caddy（或前置网关）body 限制 + 基础 rate limit（B4）
6. 真存储配置与冒烟（B2）
7. 真模型 ¥5–50 预算冒烟（B1）

### P1（稳商用）

1. 供应商不确定态：前端简化「刷新状态 / 不要重复点」向导
2. S3/七牛大文件重试与可观测（成功/失败指标）
3. 队列深度、processing 年龄、dead-letter 计数告警
4. 同用户并发多小说压测（admission 仅限同 novel）
5. `SERIES_STAGE_MODEL_TIMEOUT_SECONDS`（compose 默认 90）与租约 TTL 对齐文档化
6. 假/真路径矩阵测试：CI 默认 fake；nightly 可选 live canary

### P2（体验与运维）

1. 卡住任务运维 API（force-fail / requeue）
2. 成片上传异步化与进度
3. Worker 水平扩容手册与单飞正确性证明
4. 备份：Postgres + Redis AOF + media volume

---

## 6. 验收测试建议

### 6.1 假模型回归（每次合并，已有基础）

- `backend/tests/test_series_run_*`、`test_publication_pipeline_*`、`test_multi_character_archived_reactivation.py`、`test_object_storage_*`、`test_ffmpeg_local_render.py`、`test_billing_*`
- 前端 Playwright 一键三连 + cancel/resume
- 明确：`DETERMINISTIC_PROVIDER_FAKE=1` + 隔离 DB（conftest）

### 6.2 可靠性专项（上线前手工/脚本）

| ID | 步骤 | 期望 |
|---|---|---|
| R1 | 一键中途 `kill -9` publication worker，60s 内拉起 | 无双 publication；最终 succeeded 或明确 failed |
| R2 | 注入「单阶段 sleep 180s」 | 不应出现第二 Worker 同时执行同一 pipeline（修 B5 后） |
| R3 | Redis 停 30s 再启 | 新一键 503 或可重试；恢复后 resume 成功 |
| R4 | 同 novel 连点 10 次一键 | 仅 1 条 active；其余 already_running |
| R5 | 两用户两小说并行 | 互不阻塞（不同 admission 槽） |
| R6 | 取消 → 立即再一键 | 新 pipeline succeeded |
| R7 | 改章节后再一键 | plan 重建；不复用旧 completed 脏片 |
| R8 | 导入 11MB / 空 / 错扩展名 | 中文错误；无半文件残留 |
| R9 | 无 ffmpeg 镜像 | 健康检查或首跑失败信息明确 |

### 6.3 真模型门禁（用户授权 Key，预算封顶）

| ID | 步骤 | 期望 |
|---|---|---|
| L1 | 1 章单角色，opt-in，cap 内 | succeeded；ledger 一条约定费用 |
| L2 | 1 章 **3 说话角色** | 不因 `voice_binding_missing` 失败；三人可区分或有默认策略 |
| L3 | 无效 Key | 中文「Key 无效」；无 reserved 残留 |
| L4 | 人工制造供应商 timeout | recovery 提示勿重复提交；对账后可续 |
| L5 | 超 per-pipeline cap | 拒绝并写 `blocked_cap` |
| L6 | 真桶上传后换机播签名 URL | 可下载/可播 |

### 6.4 存储 / DB

| ID | 步骤 | 期望 |
|---|---|---|
| S1 | `STORAGE_PROVIDER=s3` 冒烟上传+签名 | marker 存在；本地路径仍可渲染 |
| S2 | `qiniu` 同上 | 私有桶；禁止 public-read |
| S3 | 生产 env + local storage 无 allow | 进程拒绝启动 |
| D1 | Postgres 上跑 publication admission 并发插入 | 仅一行 active |
| D2 | SQLite 路径不用于生产部署检查清单 | 文档/脚本 fail-closed |

---

## 7. 关键代码锚点（审计索引）

| 主题 | 路径 |
|---|---|
| 一键 API | `backend/app/api/v1/endpoints/publication_pipelines.py` |
| Pipeline FSM | `backend/app/services/publication_pipeline_orchestrator.py` |
| 媒体准备 | `backend/app/services/publication_pipeline_prepare.py` |
| Plan/fingerprint | `backend/app/services/publication_pipeline_front.py`, `series_production.py` |
| Series Run FSM | `backend/app/services/series_run_orchestrator.py` |
| Series 队列/Worker | `series_run_execution_queue.py`, `series_run_worker.py`, `core/redis_client.py` |
| Pipeline 队列/Worker | `publication_pipeline_queue.py`, `publication_pipeline_worker.py` |
| 媒体预检/配音 | `features/series_run_media_preflight/public.py` |
| 归档角色复活 | `features/series_run_story_locks/application/deterministic_acceptance.py` |
| 恢复策略 | `features/series_run_recovery/*` |
| FFmpeg | `services/ffmpeg_local_renderer.py`, `core/dev_generation.py` |
| 存储 | `core/object_storage.py`, `services/media_delivery.py` |
| 计费 | `services/billing_guard.py` |
| 生产门禁 | `core/runtime_env.py` |
| 上传 10MiB | `services/upload_persistence.py`, `docs/streaming-uploads.md` |
| 生产编排 | `compose.production.yml`, `ops/deploy/Caddyfile` |

---

## 8. 与前端/产品的交界（后端视角）

- 一键应继续只暴露 **publication-pipeline** 一条后端入口；Series Run 分步 API 保留给「更多 → 分步制作」。
- 排队/停机文案依赖 pipeline `execution_status` + status；dead-letter 若不上失败态，前端无法诚实提示。
- 真模型费用确认框依赖 billing settings；后端已有 cap，需保证 prepare 路径与前端数字一致。

---

## 9. 审计声明

- 本报告基于 `c91fc5f9` 源码与既有 `docs/frontend-full-flow-verification-2026-11-08.md` 结论交叉核对。
- **未**在本轮启动服务、未打真模型、未连真桶、未在 Postgres 上重跑套件。
- 修复实施需另开任务，经用户确认后再改代码。
