# 商业发布候选 Batch 9 验收证据

分支：`codex/commercial-batch9-recovery-alerting`

基线：`origin/dev@87682424e3a2c9cf50e2e99e624e35dc23ae0ac9`

## 本批次结果

- 新增 PostgreSQL 15 专用备份恢复镜像，备份和恢复客户端大版本不一致时直接停止。
- 备份使用 custom archive、SHA-256 清单、私有文件权限和同名归档防覆盖；恢复要求目标数据库名称完全确认。
- CI 新增独立 `operations-recovery` 门禁：迁移源库、写入 canary、备份、恢复到隔离库，并验证 canary 与 Alembic head。
- `/metrics` 在原有低基数请求指标上增加数据库状态、固定任务状态队列深度和最老活跃任务年龄，不输出任务载荷和客户内容。
- 新增固定版本 Prometheus、Alertmanager overlay 及 6 条中文 P0/P1 告警；真实值班地址只从部署外部文件加载。
- 增加中文备份恢复手册和运行健康手册，明确正式切流前的 RPO/RTO、告警送达和双人确认要求。

## 自动化与本机运行证据

```text
恢复与监控聚焦测试：15 passed, 1 skipped（未设置隔离恢复环境时主动跳过）
最终备份防覆盖契约：6 passed
完整后端测试：2358 passed, 7 skipped（Python 3.11）
前端类型检查与生产构建：通过，46 个路由（Node 24）
代码健康棘轮：736 个文件，150699 有效代码行，0 阻塞项
前端依赖审计：0 vulnerabilities
后端依赖审计：No known vulnerabilities found
已跟踪敏感文件扫描：通过
Prometheus 配置：通过，6 条规则
Production + monitoring Compose 配置：通过
CI 工作流 YAML：通过
git diff --check：通过
```

## PostgreSQL 15 真实恢复演练

```text
源数据库：独立 PostgreSQL 15.13 临时容器
迁移版本：20260809_0006
canary：batch9-local-recovery
备份 SHA-256：be390b18ba7960dd9541e9bb42d81a5cec5b74c41943b781ec1bce8ed3d9ae9f
恢复目标：ai_video_restore_drill
恢复命令耗时：2 秒
恢复验证：1 passed；canary 与 Alembic head 均一致
```

演练完成后，临时 PostgreSQL 容器、网络和两批临时备份均已清理；未停止或修改现有开发前后端服务。2 秒是本机小数据集恢复命令耗时，不代表生产 RTO。

## 镜像证据

```text
后端镜像：sha256:2b4eed840b9be6524c77fb8823a307d88dcfe77a220a25a7b8aea35a8fd22d3a
后端镜像大小：329773635 bytes
PostgreSQL 恢复镜像：sha256:521d90b65951395ae6257fbc2bfbc81bcabf9fd75fde386e442e7466c1cfc490
PostgreSQL 恢复镜像大小：118385574 bytes
```

本机前端 Docker 构建在 `npm ci` 阶段连续两次遇到 npm 10.8.2 的 `Exit handler never called`，同时 Docker 容器访问 npm registry 无响应；相同锁文件的宿主机安装、审计、类型检查和生产构建均通过。该项不按代码成功处理，以远端 GitHub `docker-build` 门禁为最终证据。

## 差异审查

- 破坏性恢复：恢复只允许显式目标库，校验文件名、大小和 SHA-256，使用 `--exit-on-error`，不自动切换生产连接。
- 备份不可变：同秒同标签已有归档或正在生成时直接拒绝，不覆盖旧证据。
- 密钥：数据库密码仅经 `PGPASSWORD` 子进程环境传递；清单、日志和指标不记录数据库 URL、密码、任务载荷或用户内容。
- 指标基数：任务状态标签固定为 5 个值，请求路径沿用路由模板，不增加用户、小说或任务 ID 标签。
- 范围：未修改 API 路径、响应契约、数据库表、供应商调用、计费状态或现有媒体数据。

## 发布判断

本批次自动门禁全部通过且远端 `operations-recovery`、`docker-build` 通过后，可合入 `dev` 并提升到 `releases` 候选线；不直接提升到 `main`，也不等同于允许正式切流。

正式切流前仍必须由对应责任人补齐：

1. 在预发布环境使用真实数据规模完成加密备份、异地副本恢复、API readiness 和 RPO/RTO 计时。
2. 配置真实值班 Webhook，验证 P0/P1 告警的触发、送达、确认和恢复通知。
3. 使用付费实模完成三章全流程验收，核对账单、字幕、人物连续性、参考资产传递和输出媒体。
4. 完成登录、移动端、工作室主流程的人工 UAT 与无障碍抽检。
5. 由法务确认许可证、隐私政策、数据保留、用户内容授权和第三方模型条款。

上述任一项未通过时，保持 `releases` 候选状态并禁止合入 `main`。
