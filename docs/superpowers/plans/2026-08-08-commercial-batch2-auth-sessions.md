# Commercial Batch 2: Account and Session Security Implementation Plan

> **Execution note:** The user delegated autonomous execution through verification and merge. Follow this plan task by task with strict red-green-refactor evidence.

## Intent Lock

生产环境中，没有有效且可撤销的会话就不能读取客户资源；新账号只有完成邮箱验证后才能进入生产系统。

## Scope Boundaries

- 保留现有 `/api/v1/auth/*` 路径和 Bearer Access Token 一个迁移周期。
- 不在本批次引入组织/工作区 RBAC、MFA、SSO 或客户计费。
- 不重写现有业务资源 API；统一认证依赖继续作为兼容入口。
- 不删除现有用户或强制现有激活用户重新验证邮箱。
- 邮件交付只建立可持久、可替换的通知出口；本地/测试环境可显式返回验证令牌。

## Constraint Checklist

- API：旧 Bearer Access Token 仍可用；访问令牌响应字段保留。
- 数据：新增表和字段只通过 Alembic；现有激活用户迁移为已验证。
- 安全：生产配置 fail-closed；Access 15 分钟；Refresh 仅存哈希且每次轮换；Cookie 状态写请求校验 CSRF。
- UX：错误使用中文直白描述，不向浏览器暴露堆栈、数据库或英文内部错误。
- 性能：认证查询有唯一索引；限流在生产使用 Redis，本地测试使用进程内后备。
- 代码健康：`auth.py` 不增长并抽出职责；`api-client.ts` 不增长；新增文件不超过项目阈值。
- 兼容：local/test 保留开发用户；staging/production 禁止开发用户和未签名令牌。

## Acceptance Criteria

1. `APP_ENV=production` 缺少 JWT、数据库、Redis、加密或对象存储关键配置时启动失败。
2. Access Token 默认 15 分钟；生产前端通过 HttpOnly Cookie 使用，Bearer 继续兼容。
3. Refresh Token 只以 SHA-256 哈希落库，刷新后旧令牌失效；复用旧令牌会撤销该用户会话。
4. 登出、修改密码和重置密码会撤销相关会话。
5. 密码最少 12 位并拒绝常见弱密码；新注册账号必须验证邮箱后登录。
6. 登录、注册、找回、重置具备可测试的限流；账号不存在与存在使用一致找回文案。
7. Cookie 认证的写请求缺少正确 CSRF 令牌时返回中文 403；Bearer 请求不受 Cookie CSRF 约束。
8. 匿名 `/users` 不再泄露用户列表。
9. 前端不再把新访问令牌写入 localStorage，支持 Cookie 会话和旧 Bearer 平滑迁移。
10. 后端全量、前端测试/构建、PostgreSQL 迁移、生产容器安全冒烟和 CI 均通过。

## Verification Commands

```bash
cd backend && pytest -q tests/security test_auth_account.py
cd backend && python -m pytest -q
cd frontend && npm test -- --runInBand
cd frontend && npm run build
docker compose -f infra/compose/production.yml config
./scripts/verify_postgres_contract.sh
npm run verify:code-health
```

## Tasks

### Task 1: Runtime environment and access-token contract

**Files**
- Create: `backend/app/core/runtime_environment.py`
- Create: `backend/app/core/auth_tokens.py`
- Modify: `backend/app/core/security.py`
- Modify: `backend/main.py`
- Test: `backend/tests/security/test_runtime_environment.py`
- Test: `backend/tests/security/test_access_tokens.py`

**Red**
- [ ] Add behavior tests for production missing secrets, production dev fallback rejection, signed cookie/Bearer acceptance and 15-minute expiry.
- [ ] Run the tests and record the expected failures.

**Green**
- [ ] Implement explicit environment parsing and production configuration validation.
- [ ] Centralize signed access-token creation/verification and update the compatibility dependency.
- [ ] Add stable Chinese 500 responses and baseline security headers without wildcard credential CORS.
- [ ] Re-run targeted tests.

### Task 2: Persistent refresh sessions and migration

**Files**
- Create: `backend/app/models/user_session.py`
- Create: `backend/app/services/auth_sessions.py`
- Create: `backend/alembic/versions/20260808_0002_auth_sessions.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/api/v1/endpoints/auth.py`
- Test: `backend/tests/security/test_auth_sessions.py`
- Test: `backend/tests/migrations/test_auth_session_migration.py`

**Red**
- [ ] Add tests for hashed storage, rotation, stale-token reuse, logout, concurrent refresh and password revocation.
- [ ] Add migration tests for existing-user verification backfill and PostgreSQL/SQLite upgrade.
- [ ] Run and record failures.

**Green**
- [ ] Implement opaque refresh tokens, family rotation and revocation.
- [ ] Set/clear Secure HttpOnly SameSite cookies while retaining local/test JSON compatibility.
- [ ] Wire refresh/logout/password flows to persisted sessions.
- [ ] Re-run targeted tests and migration contract.

### Task 3: Registration verification, password policy and rate limiting

**Files**
- Create: `backend/app/services/password_policy.py`
- Create: `backend/app/services/auth_rate_limit.py`
- Modify: `backend/app/api/v1/endpoints/auth.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements.lock`
- Test: `backend/tests/security/test_registration_security.py`
- Test: `backend/tests/security/test_auth_rate_limit.py`

**Red**
- [ ] Add tests for weak password rejection, pending registration, verification activation, generic duplicate/forgot responses and endpoint-specific throttling.
- [ ] Run and record failures.

**Green**
- [ ] Implement password policy and email verification token lifecycle.
- [ ] Implement Redis-backed production limiter with deterministic local/test fallback.
- [ ] Protect the user directory from anonymous access.
- [ ] Re-run targeted tests.

### Task 4: Browser cookie and CSRF migration

**Files**
- Create: `backend/app/core/csrf.py`
- Create: `frontend/src/lib/auth-session.ts`
- Modify: `backend/main.py`
- Modify: `frontend/src/lib/fetch-with-auth.ts`
- Modify: `frontend/src/contexts/AuthContext.tsx`
- Modify: `frontend/src/lib/api-client.ts` without net line growth
- Modify: `frontend/src/app/register/page.tsx`
- Test: `backend/tests/security/test_csrf.py`
- Test: `frontend/src/lib/__tests__/auth-session.test.ts`
- Test: existing auth context/request tests

**Red**
- [ ] Add cookie CSRF positive/negative tests and browser request credential/header tests.
- [ ] Run and record failures.

**Green**
- [ ] Require double-submit CSRF for cookie-authenticated state changes.
- [ ] Make frontend requests credential-aware and remove new localStorage token persistence.
- [ ] Keep legacy localStorage Bearer read-only migration support.
- [ ] Update registration copy and state for email verification.
- [ ] Re-run targeted backend/frontend tests.

### Task 5: Integration, production evidence and merge

- [ ] Run the complete backend suite and frontend tests/build.
- [ ] Run code-health ratchet and dependency/security checks.
- [ ] Upgrade fresh SQLite and PostgreSQL databases through Alembic.
- [ ] Start isolated production containers; verify missing-secret failure, valid-secret startup, cookie login/refresh/logout and health endpoints.
- [ ] Review the diff for compatibility, secrets, English error leakage and unrelated edits.
- [ ] Commit task-scoped changes, push branch, open PR, wait for CI, merge to `dev`, and verify the remote merge commit.

## Rollback

- Roll back application image first; schema additions remain backward compatible for one release.
- Do not downgrade or delete `user_sessions` during an incident; revoke all sessions and return to Bearer access compatibility if needed.
- Keep old refresh-JWT acceptance disabled by default and time-boxed behind an explicit migration flag only if deployment evidence requires it.
