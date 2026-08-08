# 商用持久任务与恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让整书执行和镜头参考图轮询在 API/worker 重启、多实例竞争和供应商超时下不丢失、不重复执行，并向用户提供中文、可操作的恢复状态。

**Architecture:** PostgreSQL `task_executions` 是调度真相源，业务任务表继续保存业务真相。Web 进程只幂等入队；独立 worker 使用版本号比较交换领取租约、周期心跳和终态事件。安全轮询可自动退避，未知付费提交状态进入人工确认，不自动重提。

**Tech Stack:** FastAPI、async SQLAlchemy、Alembic、PostgreSQL/SQLite 合同测试、独立 asyncio worker、Next.js 现有任务页面兼容接口。

## Global Constraints

- 保留所有现有 HTTP 路径、业务任务表、供应商安全门禁和错误隐藏语义。
- 新代码进入 `backend/app/features/task_execution/`；不扩张 legacy endpoint 的业务责任。
- 不以 Redis 或进程内内存作为任务唯一真相，不引入 Celery。
- 已接受或状态不确定的供应商请求不得自动再次提交；错误对用户使用中文直白说明。
- 每个行为变化必须先看到目标测试失败，再做最小实现。
- 生产 worker 缺失数据库、密钥或生产配置时必须 fail-closed。

---

## Execution Contract

**Intent Lock:** 服务重启、扩容或供应商超时不会丢任务，也不会因自动恢复重复发起可能收费的供应商请求。

**Out of Scope:** 本批不建立客户钱包、不迁移所有历史后台任务、不改变视频/图像/TTS 业务表、不做前端视觉重构。

**Acceptance Criteria:**

1. 相同用户、任务类型和幂等键只创建一个执行记录。
2. worker 通过租约和版本 CAS 保证同一时刻只有一个有效执行者；租约过期可恢复。
3. pending/retry_wait 可取消；运行中可请求取消并在安全点结束。
4. 安全轮询失败按退避重试，超过上限进入死信；不确定付费状态进入人工确认。
5. 整书执行和镜头图片轮询均不再由 Web 进程裸 `asyncio.create_task` 承担。
6. 状态、尝试、错误和事件可由当前用户查询；跨用户返回 404。
7. Alembic、SQLite、PostgreSQL、生产 Compose、全量后端、前端构建和代码健康门禁通过。

**Verification Commands:**

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_task_execution_*.py tests/test_series_run_orchestrator.py -q
PATH="$PWD/.venv/bin:$PATH" npm run verify:backend
npm run verify:frontend
npm run verify:code-health
docker compose -f infra/compose/production.yml config
```

### Task 1: 持久任务、事件和迁移

**Files:**
- Create: `backend/app/models/task_execution.py`
- Create: `backend/alembic/versions/20260809_0004_durable_tasks.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_task_execution_migration.py`
- Test: `backend/tests/test_task_execution_domain.py`

**Interfaces:**
- Produces: `TaskExecution`, `TaskExecutionEvent`；状态 `pending/running/retry_wait/succeeded/failed/dead_letter/needs_attention/cancelled`。

- [x] 写迁移与模型失败测试：表、唯一幂等约束、领取索引、审计事件不可修改。
- [x] 运行测试，确认因模型/迁移不存在而失败。
- [x] 实现最小模型和增量 Alembic 迁移，不删除或回写业务表。
- [x] 运行测试，确认通过。

### Task 2: 幂等入队、租约领取和状态机

**Files:**
- Create: `backend/app/features/task_execution/domain.py`
- Create: `backend/app/features/task_execution/repository.py`
- Create: `backend/app/features/task_execution/dispatcher.py`
- Create: `backend/app/features/task_execution/public.py`
- Test: `backend/tests/test_task_execution_dispatcher.py`

**Interfaces:**
- Produces: `DatabaseTaskDispatcher.submit(...) -> (TaskExecution, bool)`、`claim_one(...)`、`heartbeat(...)`、`complete(...)`、`request_cancel(...)`、`retry(...)`。

- [x] 写失败测试：重复入队、并发领取、过期租约恢复、取消、人工确认后重试。
- [x] 运行测试，确认缺少接口而失败。
- [x] 用版本 CAS 和 `lease_owner` 实现最小状态机，每次状态变化写 `TaskExecutionEvent`。
- [x] 运行测试，确认通过，并检查错误文案为中文。

### Task 3: worker 与安全处理器

**Files:**
- Create: `backend/app/features/task_execution/handlers.py`
- Create: `backend/app/features/task_execution/worker.py`
- Create: `backend/scripts/run_task_worker.py`
- Modify: `infra/compose/production.yml`
- Test: `backend/tests/test_task_execution_worker.py`
- Test: `backend/tests/test_deployment_compose_contract.py`

**Interfaces:**
- Consumes: Task 2 的领取、心跳和完成接口。
- Produces: `TaskOutcome`、处理器注册表、独立 `task-worker` 服务。

- [x] 写失败测试：成功、可安全重试、超过上限死信、未知异常转人工确认、取消请求。
- [x] 运行测试，确认 worker/处理器不存在而失败。
- [x] 实现单任务执行、心跳和中文错误投影；生产 Compose 增加独立 worker。
- [x] 运行测试，确认通过。

### Task 4: 替换整书执行的进程内队列

**Files:**
- Create: `backend/app/features/task_execution/series_run_handler.py`
- Modify: `backend/app/services/series_run_execution_queue.py`
- Modify: `backend/app/api/v1/endpoints/series_runs.py`
- Test: `backend/tests/test_series_run_orchestrator.py`
- Test: `backend/tests/test_task_execution_series_run.py`

**Interfaces:**
- Produces: `enqueue_series_run_execution(db, run) -> TaskExecution`；任务键包含 run id 和当前版本。

- [x] 改写测试，要求 `execute-async` 返回持久 `execution_id` 且重复请求不创建重复任务。
- [x] 运行测试，确认仍使用进程内 launcher 而失败。
- [x] 接入数据库 dispatcher；handler 重新加载 run 并调用现有 `SeriesRunOrchestrator`，异常进入人工确认。
- [x] 运行测试，确认通过。

### Task 5: 替换镜头参考图的进程内轮询

**Files:**
- Create: `backend/app/features/task_execution/shot_image_handler.py`
- Modify: `backend/app/services/image_poll_service.py`
- Modify: `backend/app/api/v1/endpoints/shots.py`
- Test: `backend/tests/test_task_execution_shot_image.py`

**Interfaces:**
- Produces: `enqueue_shot_image_poll(db, shot_id, provider_task_id, user_id)`；单次安全状态查询返回 success/retry_wait/dead_letter。

- [x] 写失败测试：API 只入队；未知状态退避；成功只落一个资产；超限为中文死信。
- [x] 运行测试，确认裸 `asyncio.create_task` 和长循环仍存在而失败。
- [x] 将轮询拆为单次幂等步骤并接入 dispatcher，保留现有结算与媒体持久化规则。
- [x] 运行测试，确认通过。

### Task 6: 查询、取消、恢复 API 与最终门禁

**Files:**
- Create: `backend/app/features/task_execution/api.py`
- Create: `backend/app/features/task_execution/schemas.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_task_execution_api.py`

**Interfaces:**
- Produces: `GET /api/v1/task-executions`、`GET /api/v1/task-executions/{id}`、`POST .../cancel`、`POST .../retry`。

- [x] 写失败测试：用户隔离 404、中文状态/动作、取消、`needs_attention` 必须显式确认才能重试。
- [x] 运行测试，确认接口未注册而失败。
- [x] 实现只读列表/详情及受控动作，不暴露内部异常和 payload 密钥。
- [x] 运行目标测试、全量后端、前端构建、代码健康、PostgreSQL 与生产 Compose 冒烟。
- [x] 内联审查 diff 并修复阻断项；随后以单一意图提交并走 `dev` PR 门禁。
