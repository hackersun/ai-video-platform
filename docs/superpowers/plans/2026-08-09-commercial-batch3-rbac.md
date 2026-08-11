# Commercial Batch 3 RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan.

**Goal:** 在不改变现有项目 API 和历史数据可见性的前提下，增加组织、工作区、项目四级角色授权、机器可读权限矩阵和不可变成员审计。

**Architecture:** 保留 `Project.user_id` 与现有 `ProjectMember` 作为兼容真相，在其上新增个人组织和个人工作区；统一权限服务先解析项目所有者/项目成员，再校验工作区与组织成员状态。现有项目通过幂等迁移归入所有者的个人工作区，未迁移的本地数据库仍按旧权限安全工作。项目无权访问继续返回 404，前端不参与授权判断。

**Tech Stack:** FastAPI, async SQLAlchemy, Alembic, SQLite/PostgreSQL, pytest.

## Execution Contract

- **Intent lock:** 每一次项目资源访问都由服务端的同一角色规则判定，停用成员与跨组织用户不得旁路。
- **Out of scope:** 本批不改任务调度、计费、媒体存储，不重写已有资源表，不删除 `user_id`，不开放平台管理员读取客户正文。
- **Compatibility:** 现有 owner/editor/viewer 含义不变；新增 reviewer 只允许查看与审核，不能编辑普通内容；旧数据库在迁移前仍可运行。
- **Data safety:** 迁移仅新增表、列、索引并幂等回填；downgrade 明确要求备份恢复，不做破坏性反向迁移。
- **UX/error contract:** 无权资源统一返回 404 中文“项目不存在”；非法角色返回 422 中文可行动说明。
- **Acceptance:** owner/editor/reviewer/viewer、停用成员、非成员、跨组织均有正反向测试；成员变更产生不可修改审计事件；权限矩阵覆盖项目 API；SQLite 与 PostgreSQL migration upgrade 可重复执行。
- **Verification:** 定向 pytest → PostgreSQL migration contract → `npm run verify:backend` → `npm run verify:code-health` → Docker Compose 健康与 API 冒烟。
- **Decision points:** 用户已授权后续自主执行；仅在发现会丢数据、改变公开 API 或需要真实付费外部调用时暂停。

## Task 1: Freeze the permission contract with failing tests

**Files:**
- Create: `backend/tests/security/test_commercial_rbac.py`
- Create: `backend/tests/security/test_api_permission_matrix.py`
- Modify: `backend/tests/security/test_auth_session_migration.py`

1. 写角色归一化和能力矩阵测试：owner/editor/reviewer/viewer 的 view/edit/review/manage_members 权限必须明确。
2. 写项目访问测试：停用成员、非成员和跨组织成员均得到 404；reviewer 可查看和审核但不能编辑。
3. 写机器可读 API 权限矩阵合同测试，要求项目读写和成员管理路由都有声明。
4. 写迁移合同测试，要求新增租户表、`projects.workspace_id`、reviewer 兼容与个人空间回填。
5. 运行定向测试并确认因缺少新能力失败，而非夹具或导入错误。

## Task 2: Add tenant models and an additive migration

**Files:**
- Create: `backend/app/models/tenant.py`
- Create: `backend/alembic/versions/20260809_0003_commercial_rbac.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/__init__.py`

1. 新增 Organization、OrganizationMember、Workspace、WorkspaceMember 与 immutable AuditEvent。
2. 为 Project 增加 nullable `workspace_id`，ProjectMember 接受 reviewer；增加必要唯一约束和索引。
3. 编写幂等迁移：为每个现有项目所有者创建个人组织/工作区、回填 workspace_id、补齐 owner 成员。
4. 运行迁移测试直至通过，并在 PostgreSQL 容器执行首次与重复 upgrade。

## Task 3: Centralize authorization without growing legacy hotspots

**Files:**
- Create: `backend/app/features/access_control/__init__.py`
- Create: `backend/app/features/access_control/roles.py`
- Create: `backend/app/features/access_control/service.py`
- Create: `backend/app/features/access_control/audit.py`
- Modify: `backend/app/core/permissions.py`

1. 实现稳定的项目能力枚举与角色映射，`core.permissions` 仅保留兼容门面。
2. 项目授权先验证项目角色，再验证关联工作区/组织成员仍有效；所有失败统一隐藏为 404。
3. 旧项目没有 workspace_id 时保持现有 owner/member 规则，防止迁移窗口中断。
4. 成员与角色变更写入追加式审计事件，普通业务 API 不提供更新/删除审计记录的入口。
5. 运行角色和越权测试直至通过。

## Task 4: Expose tenant administration and classify APIs

**Files:**
- Create: `backend/app/features/access_control/schemas.py`
- Create: `backend/app/features/access_control/api.py`
- Create: `backend/app/features/access_control/permission_matrix.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/api/v1/endpoints/projects.py`

1. 提供当前用户组织/工作区列表和成员管理最小 API；首次访问时幂等创建个人组织与工作区。
2. 项目创建自动绑定个人工作区；项目成员新增、改角色、停用调用统一服务并写审计。
3. 将 reviewer 加入请求说明和项目列表查询；项目更新仍要求 editor，成员管理仍要求 owner。
4. 发布只读权限矩阵端点，矩阵内容来自代码常量，不手工复制路由逻辑。
5. 运行 API 合同测试及现有项目/合成相关回归测试。

## Task 5: Full verification and protected integration

1. 运行 `npm run verify:backend`、`npm run verify:frontend`、`npm run verify:code-health`。
2. 用生产 Compose + PostgreSQL 启动，检查 Alembic、API、前端与 worker 健康；用真实 HTTP 完成注册/验证/建项目/添加成员/越权 404/审计查询冒烟，不调用付费模型。
3. 检查 diff 只包含本批范围，执行内联代码审查并修复阻断项。
4. 提交单一意图 commit，推送 `codex/commercial-batch3-rbac-tasks`，创建 PR 到 `dev`，等待全部 CI 通过后合并。
