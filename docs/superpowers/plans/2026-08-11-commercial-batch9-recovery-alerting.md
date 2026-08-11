# 商用恢复与告警 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前商业候选版本补齐可重复的 PostgreSQL 备份恢复演练、可执行告警规则和受保护分支安全门禁，使数据库故障、队列积压和接口异常能够被验证、发现并安全恢复。

**Architecture:** 备份与恢复逻辑放入新的 operations feature，命令行脚本只负责参数和退出码；备份采用 PostgreSQL custom archive、SHA-256 清单和精确目标库确认，避免误恢复。运行指标在现有低基数指标端点上追加数据库与持久队列状态，Prometheus/Alertmanager 通过独立 Compose overlay 接入，不改变现有 API 路径或生产业务拓扑。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、PostgreSQL 15、pytest、Prometheus、Alertmanager、Docker Compose、GitHub Actions。

## Global Constraints

- 保留所有现有 API 路径、响应字段、数据库表、用户数据、任务状态和供应商安全门禁。
- 数据库工具只读备份；恢复必须校验 SHA-256，并要求操作者输入与目标数据库完全一致的确认值。
- 指标不得包含用户 ID、小说正文、任务载荷、密钥、数据库 URL 或供应商原始响应。
- 告警名称稳定，中文说明必须包含首个处理动作；仓库只提供示例路由，真实值班通道由部署密钥文件提供。
- 不把本地恢复演练或告警规则校验表述成真实预发布环境、真实值班送达或正式生产切流。
- 新生产文件不超过 500 行，新函数不超过 80 行；不增长现有 legacy hotspot。

---

### Task 1: PostgreSQL backup and restore contract

**Files:**
- Create: `backend/app/features/operations/__init__.py`
- Create: `backend/app/features/operations/postgres_recovery.py`
- Create: `backend/scripts/backup_postgres.py`
- Create: `backend/scripts/restore_postgres.py`
- Test: `backend/tests/test_postgres_recovery.py`

**Interfaces:**
- Produces: `create_postgres_backup(database_url, output_dir, runner, clock) -> BackupManifest`.
- Produces: `restore_postgres_backup(database_url, archive_path, manifest_path, confirmation, runner) -> None`.
- `BackupManifest` contains archive name, byte size, SHA-256, UTC creation time and release SHA; it never contains credentials or a database URL.

- [x] Write tests that require PostgreSQL-only URLs, atomic archive creation, `0600` archive/manifest permissions, credential-free manifests, checksum rejection and exact target database confirmation.
- [x] Run `cd backend && pytest -q tests/test_postgres_recovery.py` and confirm failure because the operations module does not exist.
- [x] Implement the minimal recovery module and thin CLI entry points using `pg_dump --format=custom` and `pg_restore --clean --if-exists --no-owner --no-acl`.
- [x] Re-run the target test and confirm it passes.

### Task 2: Operational queue metrics and alert rules

**Files:**
- Modify: `backend/app/core/operational_health.py`
- Modify: `backend/app/core/request_observability.py`
- Modify: `backend/main.py`
- Modify: `backend/tests/test_operational_observability.py`
- Create: `infra/monitoring/prometheus.yml`
- Create: `infra/monitoring/prometheus-alerts.yml`
- Create: `infra/monitoring/alertmanager.yml.example`
- Create: `infra/compose/monitoring.yml`
- Test: `backend/tests/test_monitoring_contract.py`

**Interfaces:**
- Produces: `render_operational_metrics(snapshot: Mapping[str, object]) -> str` with `ai_video_database_ready`, `ai_video_task_queue_depth{status}` and `ai_video_task_oldest_active_age_seconds`.
- `/metrics` keeps the same authenticated endpoint and Prometheus media type, appending operational gauges without exposing task payloads.

- [x] Extend observability tests to require low-cardinality queue gauges, oldest active task age and safe metrics behavior when the database is unavailable.
- [x] Add monitoring contract tests that require P0 readiness/5xx rules and P1 dead-letter/stalled-task rules with Chinese remediation annotations.
- [x] Run both test files and confirm the new assertions fail for missing gauges and files.
- [x] Implement the minimal gauges, authenticated scrape config, pinned monitoring images, alert rules and external alert-routing mount.
- [x] Re-run both test files and validate alert syntax with `promtool check rules`.

### Task 3: Real PostgreSQL recovery drill and CI gate

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `backend/tests/test_postgres_recovery_runtime.py`
- Create: `docs/operations/postgres-backup-recovery.md`
- Modify: `docs/operations/observability-runbook.md`
- Modify: `infra/compose/production.env.example`

**Interfaces:**
- CI job `operations-recovery` upgrades the source database, writes a canary row, creates a custom archive, restores it to a separate `*_restore_drill` database, verifies the canary and Alembic head, and validates Prometheus rules plus production monitoring Compose.

- [x] Write a PostgreSQL runtime test that proves the restored database contains the canary and current migration head.
- [x] Run the runtime test without the drill environment and confirm it skips locally rather than touching a developer database.
- [x] Add the isolated CI service/job and exact operator commands; no production credentials or media are used.
- [x] Document backup retention, encrypted storage expectations, recovery confirmation, RPO/RTO measurement and rollback limits in direct Chinese.
- [x] Run workflow/Compose contract checks and the local PostgreSQL drill with an ephemeral PostgreSQL 15 container.

### Task 4: Verification, protected integration and evidence

**Files:**
- Create: `docs/release/evidence/2026-08-11-commercial-batch9.md`
- Modify: `docs/superpowers/plans/2026-08-11-commercial-batch9-recovery-alerting.md`

**Interfaces:**
- Produces a release evidence record separating automated proof from external No-Go gates.

- [ ] Run targeted recovery/monitoring tests, full backend suite, PostgreSQL contract, frontend typecheck/build, security audit, code-health ratchet, Docker builds and Compose validation.
- [x] Perform an inline diff review for destructive restore defaults, secret leakage, alert cardinality and unrelated changes.
- [x] Record commit, image, recovery duration and remaining staging/alert-delivery gates in Chinese release evidence.
- [ ] Commit one intent, push the feature branch, require `security-scan` and `operations-recovery` on `dev`/`releases`/`main`, then merge through protected PRs after all checks pass.

## Rollback

- Code rollback removes only the new operations feature, scripts, monitoring overlay, CI job and documentation; no existing schema or API is changed.
- Monitoring overlay can be stopped independently without stopping API, worker, PostgreSQL or Redis.
- Backup archives are immutable evidence; rollback never deletes archives or manifests automatically.
- A failed restore drill destroys only the explicitly named drill database. Production restore remains a manual, exact-name-confirmed operation.
