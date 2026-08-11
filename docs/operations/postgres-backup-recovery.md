# PostgreSQL 备份与恢复操作手册

## 适用范围

本手册用于发布前备份、预发布恢复演练和经审批的故障恢复。脚本只支持 PostgreSQL，不支持 SQLite；它不会备份对象存储，媒体必须按对象存储平台的独立策略复制和校验。

## 发布前备份

生产数据库当前使用 PostgreSQL 15。备份脚本会同时检查 `pg_dump` 和 `pg_restore`，任一工具不是 15 大版本都会用中文提示并停止，避免生成无法恢复的归档。

推荐先从当前发布提交构建固定版本的恢复镜像，再执行备份：

```bash
docker build \
  -f infra/docker/postgres-recovery.Dockerfile \
  -t ai-video-postgres-recovery:<发布提交> .
```

如果受控运维机已经安装 PostgreSQL 15 客户端，也可直接执行：

```bash
cd backend
export DATABASE_URL='postgresql://...'
export RELEASE_SHA='<准备发布的 Git 提交>'
python scripts/backup_postgres.py \
  --output-dir /secure-backups/ai-video \
  --label pre-release
```

不要使用操作系统默认安装的“最新 PostgreSQL 客户端”；客户端大版本必须与当前生产 PostgreSQL 15 一致。GitHub 恢复门禁使用上述固定镜像，不依赖 Runner 的系统包版本。

成功后会得到 `.dump` 和 `.dump.json` 两个文件：

- `.dump` 是 PostgreSQL custom archive，权限为 `0600`。
- `.dump.json` 记录文件名、生成时间、发布提交、字节数和 SHA-256，不记录数据库地址或密码。
- 目录权限为 `0700`。仍需由备份平台完成静态加密、异地复制和访问审计。

将两个文件一起保存。只有归档没有清单，或清单校验不一致，都不得恢复。

## 恢复演练

必须恢复到单独创建的演练数据库，不要直接覆盖生产库：

```bash
createdb ai_video_restore_drill
python scripts/restore_postgres.py \
  --database-url 'postgresql://.../ai_video_restore_drill' \
  --archive /secure-backups/ai-video/<备份文件>.dump \
  --manifest /secure-backups/ai-video/<备份文件>.dump.json \
  --confirm-target ai_video_restore_drill
```

`--confirm-target` 必须与 URL 中的数据库名称完全一致。脚本先校验文件名、大小、SHA-256 和归档目录，再执行带 `--clean --if-exists --no-owner --no-acl --exit-on-error` 的恢复。

备份和恢复必须使用同一大版本工具链。升级生产 PostgreSQL 前，要先调整固定恢复镜像版本、完成新旧归档兼容性演练并更新本手册，不能只升级数据库服务。

恢复后至少核对：

1. `alembic_version` 与当前发布镜像一致。
2. 用户、项目、任务、账务流水和媒体对象登记数量合理。
3. 抽取一条只读校验记录，与备份前值一致。
4. API 使用恢复库启动后 `/health/ready` 返回成功。
5. 持久任务没有被重复提交；供应商已接受的任务只允许继续轮询。

## RPO 与 RTO 证据

每次演练记录以下字段：

- 备份开始和结束时间、文件大小、SHA-256、发布提交。
- 故障假设时间、最近可用备份时间，两者差值作为实际 RPO。
- 恢复开始、数据校验完成、API readiness 恢复时间，整体作为实际 RTO。
- 操作者、审批单、目标数据库、失败步骤、回滚动作和最终结论。

没有现场计时和校验记录时，只能说明“工具可用”，不能宣称已经满足生产 RPO/RTO。

## 正式故障恢复

1. 先停止新流量和 worker，保留当前数据库快照。
2. 由两人确认备份时间、SHA-256、目标库名称和故障范围。
3. 优先恢复到新数据库并完成只读校验，再切换连接；不要在未知状态下直接清理原库。
4. 切换后先启动迁移检查，再启动 API、通知 worker、任务 worker 和前端。
5. 核对账务预扣、供应商任务和死信任务后逐步恢复流量。

恢复脚本不会删除备份文件，也不会自动切换生产连接。生产切换、原库清理和对象存储恢复必须走单独审批。
