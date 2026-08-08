# 商用就绪与仓库治理设计

## 意图锁

在不破坏现有功能、数据、API、生成任务和供应商调用的前提下，把当前项目逐步收敛为可审计、可发布、可回滚的商业软件仓库，并建立 `main`、`releases`、`dev` 三条稳定分支。

## 已确认现状

- 当前稳定基线提交为 `379efa6132b1ac6b41814b38623fcb3d27d9f5ec`。
- 主工作区存在 170 项已跟踪改动和 130 项未跟踪内容，不能直接承担治理改造。
- 本地存在 25 个分支和 22 个 worktree；旧远端 `dev` 与当前 `main` 是历史分叉，不可直接合并。
- GitHub 仓库当前公开，`main` 没有分支保护和规则集。
- 当前受 Git 跟踪的数据约 209 MiB，其中 `backend/static` 约 165 MiB；`.git` 目录约 2.3 GiB。
- 前端基线 typecheck 和 production build 通过；后端基线最初为 2212 通过、2 失败、1 跳过，失败集中在实体审批安全门禁冲突。
- GitHub Actions 的 PostgreSQL 后端任务失败，已发现 SQLite 专用 SQL、无效 Docker 发布拓扑和缺少生产 Dockerfile。
- 现有架构治理文档已定义增量棘轮，但 `tools/code_health` 尚未实现。

## 设计原则

1. 先保护、再治理、后迁移；任何清理动作都必须有可恢复归档。
2. 不以“目录整齐”为理由批量移动业务代码。
3. 行为修复、结构迁移、基础设施和文档分别提交。
4. 新目录先成为真实职责所有者，旧入口以兼容门面逐步收缩。
5. `main` 永不强推；旧 `dev` 先归档，再以受保护的 `main` 重建。
6. 生成媒体、测试结果和缓存不再作为源代码管理，但从 Git 移除前必须确认本地和对象存储备份。
7. “可商用”必须由运行、权限、数据、成本、结算、恢复和发布证据共同证明，不能由页面可见或单次实模成功代替。

## 目标仓库结构

```text
ai-video-platform/
├── .github/
│   ├── workflows/
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   └── pull_request_template.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── features/
│   │   ├── models/
│   │   └── adapters/
│   ├── migrations/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── contract/
│   │   └── fixtures/
│   └── scripts/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── features/
│   │   ├── components/
│   │   └── lib/
│   └── e2e/
│       ├── smoke/
│       ├── flows/
│       └── fixtures/
├── docs/
│   ├── architecture/
│   ├── product/
│   ├── security/
│   ├── operations/
│   ├── release/
│   └── archive/
├── infra/
│   ├── compose/
│   ├── docker/
│   └── kong/
├── scripts/
│   ├── dev/
│   ├── ci/
│   └── maintenance/
└── tools/
    └── code_health/
```

该结构是迁移目标，不是一次提交中的移动清单。现有 `backend/app/api/v1/endpoints`、`frontend/src/lib/api-client.ts` 和大页面继续保持兼容，只有在对应刻画测试存在时才迁入 feature。

## 目录收敛策略

### 第一阶段：建立真相源

- `docs/architecture/repository-layout.md` 说明每个顶层目录的职责、允许内容和禁止内容。
- `tools/code_health` 扫描新文件、热点增长和非法依赖。
- `.github/CODEOWNERS` 为鉴权、计费、迁移、供应商协议和发布配置指定审查范围。
- `docs/release` 保存发布流程、分支策略和验收清单。

### 第二阶段：清理生成物

- 先输出被 Git 跟踪的媒体、截图、缓存和测试结果清单。
- 将仍需保留的媒体复制到对象存储或归档目录，并校验数量和摘要。
- 使用单独提交取消 Git 跟踪；不得把该提交与业务代码合并。
- Git 历史瘦身仅在远端备份、所有协作者通知和回滚演练后执行。

### 第三阶段：按业务域迁移

- 后端使用 `features/<feature>/public.py` 作为跨域门面。
- 前端使用 `features/<feature>/index.ts` 暴露稳定接口。
- 每次只迁移一个用例，原路由、响应字段和 API client 方法保持兼容。
- 超过 800 行的热点接收行为变化时，必须净缩小并抽取一个真实职责。

## 分支与发布模型

| 分支 | 职责 | 合入来源 | 门禁 |
|---|---|---|---|
| `main` | 线上生产真相 | `releases`、紧急 `hotfix/*` | PR、必需检查、审批、禁止强推和删除 |
| `releases` | 预发布候选 | `dev` | staging 部署、人工验收、迁移与回滚演练 |
| `dev` | 日常集成 | `feature/*`、`fix/*` | PR、前后端验证、代码健康检查 |
| `feature/*` | 单一功能 | 从 `dev` 创建 | 短生命周期、一个意图一个提交组 |
| `fix/*` | 普通修复 | 从 `dev` 创建 | 回归测试和影响说明 |
| `hotfix/*` | 线上紧急修复 | 从 `main` 创建 | 生产验证后回灌 `releases` 和 `dev` |

发布链路固定为：

```text
feature/* 或 fix/* -> dev -> releases -> main -> vX.Y.Z
```

## 旧分支迁移

1. 读取远端 SHA 并建立 `archive/dev-legacy-20260808`。
2. 验证归档 SHA 与旧 `dev` 完全相同。
3. 对仍有独立提交的旧 feature 建立 `archive/<name>-20260808`。
4. 不删除任何含未合并提交的本地 worktree。
5. 当前治理分支通过验证并进入 `main` 后，从新 `main` 建立 `dev` 和 `releases`。
6. 如需替换旧远端 `dev`，仅允许对 `dev` 使用 `--force-with-lease`，且归档验证必须先通过。
7. `main` 在任何情况下都不允许强推。

## GitHub 治理

- `main`：PR 必需、至少一人审批、必需检查、解决会话后方可合并、禁止强推和删除。
- `releases`：继承 `main` 检查，并增加 staging environment 人工审批。
- `dev`：要求前端、后端、代码健康和安全扫描通过。
- 敏感目录使用 CODEOWNERS：鉴权、数据库迁移、模型凭据、供应商适配、计费和 workflow。
- Dependabot 每周分别检查 root npm、frontend npm、backend pip 和 GitHub Actions。
- 仓库可见性在敏感信息和许可证审计完成前保持现状；若选择闭源商业模式，再独立切换为 private。

## 商用改造分批

### P0-A：仓库与发布基础

- 代码健康棘轮、目录地图、分支策略、PR 模板和 CODEOWNERS。
- 修复 PostgreSQL CI、生产 Dockerfile、依赖锁定和高危漏洞。
- 建立可重复的构建、制品签名、版本标签和回滚记录。

### P0-B：认证、权限和安全

- 生产环境启动时拒绝默认 JWT 密钥和开发模式。
- Access Token 迁移为 Secure、HttpOnly、SameSite Cookie；Refresh Token 可轮换和撤销。
- 建立组织、工作区、项目三级 RBAC 与 API 权限矩阵。
- 增加邮箱验证、密码强度、登录限流、审计日志、安全响应头和异常脱敏。

### P0-C：数据、任务和媒体可靠性

- 使用 Alembic 管理 SQLite/PostgreSQL 兼容迁移。
- 生成任务引入持久队列、幂等键、租约、重试、死信和重启恢复。
- 媒体使用私有对象存储、签名 URL、生命周期和删除策略。
- 数据库与对象存储执行备份恢复演练，并记录 RPO/RTO。

### P1-A：登录与获客体验

- 抽取统一 `AuthShell`，登录、注册、找回和重置密码共享同一视觉语言。
- 注册补充隐私、服务条款、邮箱验证和企业登录扩展位。
- 首页补充真实案例、支持模型、服务边界、价格说明、安全与支持渠道。

### P1-B：生产流程与数据可信度

- 仪表盘统一统计真相源，隔离 E2E 与验收数据。
- 快速开始拆分“体验演示”和“商业制作”，商业制作必须提供真实章节正文。
- 提交前展示模型、参考资产、预计时间、预计成本和积分影响。
- 草稿、运行状态和恢复点保存到服务端。

### P1-C：商业运营闭环

- 套餐、额度、预算、不可变用量流水、失败退款和供应商账单对账。
- 管理员、运营、财务、客服和审核角色分离。
- 内容安全、版权来源、数据导出、删除和留存策略。
- 监控、告警、值班、事故处理、SLA 和客户支持流程。

## 平滑迁移约束

- 数据库只允许先加后删，删除字段必须跨至少一个发布周期。
- 新实现通过 feature flag、暗发布或双读对比进入生产。
- 旧 API 和导入路径保留兼容门面，迁移完成后再弃用。
- 回填脚本必须幂等、可试运行、可审计并提供反向操作。
- 真实模型验收设置明确预算和任务上限，不以取消生产客户额度控制换取测试便利。
- 每个批次都包含回滚说明、目标测试和运行态验证。

## 商用发布门禁

只有以下证据全部成立，才能标记为商业候选版本：

1. 前端 typecheck/build、后端 SQLite/PostgreSQL 测试和代码健康检查全部通过。
2. 生产镜像可构建、可启动，并通过 liveness、readiness 和依赖检查。
3. 不存在未豁免的严重或高危依赖漏洞。
4. 分支保护、审批、发布环境和回滚标签已启用。
5. 权限矩阵、审计日志和安全回归通过。
6. 备份恢复、数据库迁移回滚和任务重启恢复通过演练。
7. 实模请求从模型绑定、参考资产、供应商请求、任务轮询、媒体存储到播放完整闭环。
8. 费用预估、额度扣减、供应商账单和失败补偿可以对账。
9. 登录、创建项目、生成、恢复、导出和删除数据通过正式 UAT。
10. 正式环境没有测试小说、测试角色、验收模型和临时媒体。

## 本阶段范围

本阶段只实施：

- 修复阻塞稳定基线的实体审批契约冲突。
- 固化目录、分支、发布和商用治理文档。
- 实现只读代码健康棘轮和 CI 报告。
- 增加 GitHub PR 模板、CODEOWNERS 和 Dependabot 配置。
- 保护性归档旧远端分支，并准备新的 `dev`、`releases`。

本阶段不实施：

- 批量移动业务代码。
- 删除本地或远端 worktree。
- 删除媒体和业务数据。
- 重写 `main` 历史。
- 认证、数据库和计费架构迁移。
- 未经许可证审计改变仓库可见性。

## 回滚

- 所有本地改动位于 `codex/commercial-readiness-foundation` 独立 worktree。
- 远端旧分支在替换前建立等 SHA 的 archive 分支。
- GitHub 规则集可以独立停用，不需要回退代码。
- 代码健康 CI 首先以 report-only 上线；确认基线后才设为阻断。
- 每个提交只表达一个意图，可按提交逐项回滚。
