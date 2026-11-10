# 第2波·真模型可靠性落地 — 2026-11-10

| 项 | 值 |
|---|---|
| 日期 | 2026-11-10（Asia/Shanghai） |
| 分支 | `feat/series-run-redis-queue-and-tail-fsm` |
| HEAD | `ca305360` |
| 范围 | Worker/租约心跳、多角色默认配音、dead-letter 终态、生成失败中文映射 |
| 约束 | 主要只改 `backend/`；不 stash、不改写历史、不开 PR、不放宽断言；与第1/3/4波并行时保留本波队列/配音文件 |

---

## 1. 结论

四项必做均已落地并推送。假模式相关单元/回归测试本波覆盖集 **42 passed**。长阶段不再只靠阶段边界刷新租约；多角色一键路径会自动补齐 `voice_binding`；队列超限会把 run/pipeline 标成 `failed` + 可懂 blocker；生成路径错误带中文可执行修复文案（区别于连接测试文案）。

---

## 2. 提交

| Commit | 内容 |
|---|---|
| `9860f291` | **W2-1/W2-3** mid-stage heartbeat refresh + dead-letter failed terminal |
| `631ccbcf` | **W2-2** one-click auto-bind default voice for every speaking character |
| `ca305360` | **W2-4** map generation failures to Chinese actionable repair hints |

远端已推送：`f691025c..ca305360`。

---

## 3. 改动要点

### W2-1 Worker / 租约心跳

- `HEARTBEAT_REFRESH_INTERVAL_SECONDS = 20`（`HEARTBEAT_TTL=60` / `LOCK_TTL=120`）
- `series_run_worker` 与 `publication_pipeline_worker` 在 `_execute_*` 内启动 `_heartbeat_loop`，**长阶段定时刷新**，不再只依赖 orchestrator 阶段边界的 `should_stop`
- 测试：`test_execute_run_refreshes_heartbeat_on_timer`、`test_refresh_execution_heartbeat_extends_lock_and_heartbeat`

### W2-3 Dead-letter 终态

- `record_queue_dead_letter`：写入 metadata + **强制 `status=failed`** + `blocker_code=queue_dead_letter` + 中文「请重试」说明（series run 走 `gate_summary`；pipeline 走 `blocker_code/detail`）
- `reclaim_stale_processing`：超限时**再入队一次**带 `dead_letter=true`，让 worker 有机会落库（原先 reclaim 直接丢弃导致 UI 长期「进行中」）
- 测试：`test_reclaim_requeues_dead_letter_for_worker`、`test_record_queue_dead_letter_marks_run_failed`、`test_publication_*`、`test_process_one_dead_letters_marks_failed`

### W2-2 真模型多角色配音

- `ensure_speaking_voice_bindings`：一键路径在 preflight 前给每个 `speaking` 角色补默认 `voice_binding`（可轮换 allowlist）
- preflight 若仍报 `voice_binding_missing`，按返回的 `entity_ids` **强制绑定**（覆盖对白推导出的说话人）
- 缓存 `voice_options_cache` 供轮换
- 回归：`test_ensure_binds_each_speaking_character_missing_voice`（去掉该调用会继续暴露 missing）、`test_ensure_force_entity_ids_marks_dialogue_speakers`

### W2-4 生成失败中文映射

- `_classify_provider_failure` + `generation_failure_message`（与 `connection_failure_message` 分文案）
- Driver executor evidence 增加 `repair_hint`（仍脱敏）
- publication worker fail-closed / media blocker 走 `actionable_blocker_detail`
- `BLOCKER_REPAIR_HINTS` 覆盖 models / voice / dead-letter 等

---

## 4. 测试数字（本波）

```
tests/test_ensure_speaking_voice_bindings.py
tests/test_generation_failure_message.py
tests/test_connection_failure_message.py
tests/test_series_run_worker.py
tests/test_series_run_execution_queue.py
tests/test_publication_pipeline_dead_letter.py
tests/test_publication_pipeline_one_click.py
tests/test_model_execution_snapshot.py::test_driver_evidence_never_keeps_raw_provider_exception_text
→ 42 passed
```

未在本波重跑全量 backend（与其他波并行抢机器）；假模式关键队列/一键/驱动映射子集已绿。

---

## 5. 主要改动文件

- `backend/app/services/series_run_execution_queue.py`
- `backend/app/services/series_run_worker.py`
- `backend/app/services/publication_pipeline_queue.py`
- `backend/app/services/publication_pipeline_worker.py`
- `backend/app/services/publication_pipeline_prepare.py`
- `backend/app/services/publication_pipeline_media.py`
- `backend/app/features/model_drivers/adapters/_shared.py`
- `backend/app/features/model_drivers/executor.py`
- 对应 `backend/tests/test_*`

---

## 6. 未决 / 交给其他波或后续真实验收

1. **真模型小额实跑**（第4波）：需火山 Key；验证多角色配音 + 心跳防双计费 + ledger 无双扣。
2. **前端展示 dead-letter blocker**：后端已标 `failed` + 中文 detail；若 UI 仍只读 status 文案，需第1波确认任务列表/小说详情是否展示 `blocker_detail`。
3. **`repair_hint` 前端透出**：API/任务详情是否已把 evidence.repair_hint 展示给用户（本波只保证后端携带）。
4. **同世代防双跑令牌**：本波用定时刷新租约降低 reclaim 窗口；更强的「世代 token 拒绝陈旧 worker 提交」未做。
5. 未改 auth/限流/CI（第3波）、未改 compose/MinIO/PG 演练（第4波）。

---

## 7. 服务

本波未长期拉起本机 API/Worker；无需要停止的自启服务。
