# 运行健康与故障定位手册

## 目的

本手册用于值班、发布和客服定位“页面打不开、任务卡住、接口报错”三类问题。所有检查都不得输出数据库地址、密钥、客户正文或供应商原始响应。

## 运营凭证

- local/test 环境允许直接读取指标，便于开发排障。
- staging/production 必须设置 `OPERATIONS_TOKEN`，缺失时后端拒绝启动。
- 指标请求使用 `Authorization: Bearer <OPERATIONS_TOKEN>`。
- 令牌只放入 Secret Manager 或部署平台密钥配置，不写入仓库、聊天记录、截图或监控 URL。

## 三个检查入口

| 入口 | 用途 | 成功判定 | 失败动作 |
|---|---|---|---|
| `GET /health/live` | 只证明 API 进程能响应 | HTTP 200，`status=alive` | 重启或回滚 API 实例 |
| `GET /health/ready` | 检查数据库连接并统计持久任务队列 | HTTP 200，`status=ready` | 停止接收新流量，检查数据库和 worker |
| `GET /metrics` | 读取低基数请求计数与累计耗时 | HTTP 200，Prometheus 文本 | 检查运营令牌和监控采集配置 |

负载均衡器只能用 `/health/live` 判断进程是否存活，用 `/health/ready` 判断是否接收新流量。不要用旧 `/health` 代替 readiness；旧入口只为兼容历史调用保留。

## 请求编号

- 每个 HTTP 响应都返回 `X-Request-ID`。
- 上游传入由字母、数字、点、下划线或短横线组成且不超过 128 个字符的编号时，服务沿用该编号；非法值会替换为新 UUID。
- 未处理异常向用户显示中文通用说明和 `request_id`，不回传堆栈。
- 客服先收集页面时间、账号、操作步骤和请求编号，再由值班人员按 `request_id` 查询受控日志。

## 当前指标

- `ai_video_http_requests_total{method,path,status}`：按 HTTP 方法、路由模板和状态码分组统计请求数。
- `ai_video_http_request_duration_seconds_sum{method,path}`：按 HTTP 方法和路由模板统计累计耗时。
- readiness 的 `task_queue` 返回 `pending`、`running`、`retry_wait`、`dead_letter`、`needs_attention` 数量，不包含任务载荷。

指标使用路由模板，不使用小说 ID、任务 ID、用户 ID 或原始 URL，避免标签数量无限增长。多 worker 部署时由 Prometheus 分实例抓取并聚合，不能把单个进程内数字当成全局总量。

## 建议告警

| 等级 | 条件 | 责任角色 | 首个动作 |
|---|---|---|---|
| P0 | readiness 连续 2 分钟失败，或 5xx 比例连续 5 分钟超过 10% | 当班运维 + 后端负责人 | 停止扩流，保留请求编号，判断回滚还是修复依赖 |
| P1 | `dead_letter` 或 `needs_attention` 持续增加，或任务 15 分钟无进展 | 当班运营 + 生产流程负责人 | 暂停同类批量任务，按任务 ID 核对供应商状态和账务 |
| P1 | 5xx 比例连续 10 分钟超过 3% | 当班运维 | 按路由模板聚类错误，检查最近发布和依赖状态 |
| P2 | p95 延迟高于基线两倍且持续 15 分钟 | 后端负责人 | 检查慢路由、数据库连接和队列积压 |

这里的“负责人”是值班角色，不是伪造的个人姓名。正式上线前，运营必须在告警平台绑定具体排班、电话和升级人。

## 标准处置顺序

1. 查看 `/health/live`，确认进程是否存在。
2. 查看 `/health/ready`，确认数据库和持久任务队列。
3. 用请求编号查询日志，按路由模板和状态码聚类，不搜索客户正文。
4. 对任务故障核对本地任务状态、供应商任务 ID、账务预扣与结算；供应商已接受时禁止盲目重提。
5. 如果故障来自新版本，按发布记录回滚应用镜像；涉及迁移时先执行对应的数据库回滚或恢复步骤。
6. 恢复后重新检查 readiness、错误率和任务推进，再逐步恢复流量。

## 发布前现场验证

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS -H "Authorization: Bearer ${OPERATIONS_TOKEN}" http://127.0.0.1:8000/metrics
```

正式环境还必须完成监控采集、告警路由、备份恢复演练和 staging 流量验证。仅在本机看到三个入口成功，不等于已满足公开收费运营门禁。
