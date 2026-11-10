# Wave 3 · 商用最小门禁（2026-11-10）

## 范围

聚焦：auth/session、限流、CI 门禁、生产欢迎「必须自带 Key」文案确认。  
未改：publication pipeline / worker 心跳 / voice binding（第2波）、主导航三项与导入合并（第1波）、MinIO/PG restore（第4波）。

## 已落地

### 1) 分档限流（FastAPI middleware）

- 模块：`backend/app/core/rate_limit.py`、`backend/app/middleware/commercial_rate_limit.py`
- 挂载：`backend/main.py` → `CommercialRateLimitMiddleware`
- 分档：
  - auth：login 10/min、register 5/min、forgot 5/min、reset 10/min、refresh 30/min（可用 `AUTH_RATE_LIMIT_*` 覆盖）
  - generate：30/min（`API_RATE_LIMIT_GENERATE`）
  - upload / novel import：20/min（`API_RATE_LIMIT_UPLOAD`）
- 后端：默认 `RATE_LIMIT_BACKEND=auto`（有 `REDIS_URL` 用 Redis，否则内存）；测试强制 `memory`
- 超限：HTTP 429 + `Retry-After: 60`
- 网关：生产 Caddy 仍可由第2波维护 `/ready`；限流以 API 中间件为准。可选示例见 `ops/deploy/Caddyfile.rate-limit.example`

### 2) 会话加固（渐进）

- Access 默认 **15 分钟**（`ACCESS_TOKEN_EXPIRE_MINUTES`）
- Refresh 带 `jti`，`/auth/refresh` **轮换**并作废旧票；`/auth/logout` 撤销
- 同步下发 **HttpOnly** cookie：`avp_refresh_token`（path=`/api/v1/auth`，生产 `Secure`）
- 前端：`refresh` 存 **sessionStorage**；logout 调撤销；access 仍在 localStorage（剩余风险见下）
- 无 DB migration（避免与并行波冲突）

### 3) 注册防护 / 密码策略

- `backend/app/services/password_policy.py`：≥8 位、字母+数字、拒绝常见口令、拒绝包含用户名/邮箱名
- 注册 / 改密 / 重置均校验；Pydantic `min_length=8`
- 前端占位文案改为「至少8位，含字母和数字」；相关 e2e placeholder 已同步
- 登录/注册限流见上

### 4) CI

- `.github/workflows/ci.yml`：
  - push 触发扩展到 `feat/**` `fix/**` `codex/**`
  - PR 任意分支触发
  - frontend job 增加 `npm run lint`
  - 新增 `commercial-gates`（pytest 商用门禁）
  - 新增 `commercial-novice-e2e`（smoke + onboarding + auth-account）
- 前端脚本：`npm run e2e:commercial-novice`
- **未放宽**既有断言

### 5) 生产欢迎态

- 第1波 `W1-5` 已落地：无 simulation 时展示「填写 API Key 开始 / 正式环境没有免费试用」
- 本波确认文案仍在 `simple-model-setup.tsx`，**未重写布局**（避让第1波）

## 测试

```text
RATE_LIMIT_BACKEND=memory REFRESH_TOKEN_STORE=memory \
  pytest tests/test_commercial_rate_limit.py test_auth_account.py
→ 14 passed
```

## 剩余风险（需知情）

1. **Access token 仍在 localStorage**：XSS 可读；已缩短 TTL + refresh 轮换降低窗口，完整 HttpOnly access 需前端 credentials 全面改造（后续波）。
2. **无 jti 的旧 refresh**：升级前已签发的 refresh 无法进撤销表，只能等过期。
3. **限流键主要按 IP**：NAT 下可能误伤；生产建议接 Redis 并按需加用户维。
4. **commercial-novice e2e** 仍含 mock 型 onboarding，不能替代真假模式全链路；全量 fake pipeline 成本高，留第4波/本地。
5. **Caddy 层尚未强制 rate_limit 插件**：API 中间件已覆盖；边缘限流见 example 文件。
6. **并行波**：`main.py` 的 `/ready` 属第2波未提交改动；本波仅挂载限流中间件，rebase 时保留双方增量。

## 提交计划

- W3-1 限流
- W3-2 会话/密码/前端 auth 渐进
- W3-3 CI
- W3-4 本文档与 Caddy example
