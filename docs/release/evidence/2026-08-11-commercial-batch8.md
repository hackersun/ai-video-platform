# 商业发布候选 Batch 8 验收证据

分支：`codex/commercial-batch8-release`

基线：`origin/dev@850753d0d4a1797e5fec7cb9a5e19685bfc58343`

## 本批次结果

- 增加存活、就绪和 Prometheus 指标端点；数据库或持久任务队列异常时就绪探针返回 503。
- 正常与异常 HTTP 响应都携带 `X-Request-ID`，服务端错误不再向客户端暴露异常堆栈。
- `staging` 和 `production` 的指标端点要求运营令牌，运营令牌成为正式环境必填项。
- JWT 实现迁移到维护中的 PyJWT；FastAPI、Starlette、Pillow 和测试依赖升级到无已知漏洞版本。
- CI 新增前后端依赖审计、已跟踪敏感文件扫描、真实代码健康棘轮以及 PostgreSQL 契约。
- 前端生产镜像改为 Next.js standalone 产物，并验证 npm 安装产物，避免 npm 假成功生成残缺镜像。
- 模型就绪卡显示具体模型、中文状态和中文验证缺口；剧集列表不再因空章节响应生成重复键。

## 自动化与运行态证据

```text
完整后端测试：2348 passed, 6 skipped（Python 3.11）
本批次聚焦后端测试：48 passed
PostgreSQL 15.13 空库迁移：升级至 20260809_0006，8 passed
前端类型检查与生产构建：通过，46 个路由
浏览器基础流程：2 passed
Production OS 确定性浏览器契约：4 passed, 1 skipped（真实后端外部验收项）
代码健康棘轮：734 个文件，150472 有效代码行，0 阻塞项
前端依赖审计：0 vulnerabilities
后端依赖审计：No known vulnerabilities found
已跟踪敏感文件扫描：通过
生产 Compose 配置：通过
git diff --check：通过
```

## 镜像与运行状态

```text
后端镜像：sha256:6967f84a5bfe8fc53929a672d2711dfa83ebd92f107d1765b03bb2629bda8eac
后端镜像大小：329740842 bytes
前端镜像：sha256:0d1eb719982b56c11acdc4b89581d578e0a8a5d87690f72a0471658b4992d03b
前端镜像大小：75596336 bytes
/health/live：HTTP 200
/health/ready：HTTP 200，database=ok，task_queue=ok
前端首页：HTTP 200
后端 100 请求 / 20 并发：100/100，P50 17.97ms，P95 32.95ms，最大 38.46ms
前端 50 请求 / 10 并发：50/50，P50 12.77ms，P95 14.29ms，最大 15.41ms
```

这些延迟来自本机容器冒烟，只用于发现明显回归，不替代预发布环境容量测试。

## 发布判断

自动门禁允许本批次进入 `releases` 候选线；不直接提升到 `main`，也不等同于允许正式切流。

正式切流前仍必须由对应责任人补齐：

1. 在预发布环境完成数据库备份、恢复演练和回滚计时，并保存审计记录。
2. 接入真实告警通道，验证就绪失败、5xx、任务积压和死信告警可送达值班人员。
3. 使用付费实模完成三章全流程验收，核对账单、字幕、角色连续性、参考资产传递和输出媒体。
4. 完成登录、移动端、工作室主流程的人工 UAT 与无障碍抽检。
5. 由法务确认许可证、隐私政策、数据保留、用户内容授权和第三方模型条款。

上述任一项未通过时，保持 `releases` 候选状态并禁止合入 `main`。
