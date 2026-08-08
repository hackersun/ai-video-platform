# 仓库目录规范

## 目标

本规范定义仓库中每类内容的唯一位置。目录治理采用增量迁移：先明确职责和禁止项，再在有测试保护的业务批次中移动代码，不做一次性全仓重排。

## 当前顶层目录

| 路径 | 当前职责 | 规则 |
|---|---|---|
| `.github/` | CI 与 GitHub 协作配置 | 只放 workflow、CODEOWNERS、依赖更新和 PR/Issue 模板 |
| `backend/` | FastAPI、领域服务、模型、迁移兼容脚本和后端测试 | 运行时媒体、数据库、缓存和覆盖率结果不得作为源码提交 |
| `frontend/` | Next.js 应用和浏览器验收 | `.next*`、Playwright 会话、截图和测试结果不得提交 |
| `docs/` | 架构、产品、安全、运维、发布和历史设计 | 当前有效文档与历史记录必须分区，禁止把临时日志放在根目录 |
| `e2e/` | 旧版独立 Playwright 工程 | 仅维护现有兼容验收；新增前端流程优先放 `frontend/e2e` |
| `scripts/` | 跨前后端的开发、CI 和验收脚本 | 新脚本按 `dev/`、`ci/`、`maintenance/` 分类 |
| `tools/` | 不依赖业务运行时的仓库治理工具 | 工具不得初始化数据库、调用供应商或修改生产源码 |
| `test-results/` | 本地测试输出 | 非源码，必须忽略；历史跟踪内容需在备份后单独取消跟踪 |
| `tmp/` | 临时文件 | 非源码，任何内容都不得成为长期接口 |

## 目标结构

```text
backend/
├── app/
│   ├── api/                  # HTTP 入口与兼容路由
│   ├── core/                 # 配置、鉴权、数据库、时间等平台能力
│   ├── features/             # 按业务能力组织的实现
│   ├── models/               # 持久化模型
│   └── adapters/             # 真正跨业务域的外部适配器
├── migrations/               # Alembic 迁移
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── fixtures/
└── scripts/

frontend/
├── src/
│   ├── app/                  # 路由组装
│   ├── features/             # 领域 API、hooks、actions、components
│   ├── components/           # 无业务所有权的共享组件
│   └── lib/                  # transport 与真正通用工具
└── e2e/
    ├── smoke/
    ├── flows/
    └── fixtures/

docs/
├── architecture/
├── product/
├── security/
├── operations/
├── release/
└── archive/

infra/
├── compose/
├── docker/
└── kong/

scripts/
├── dev/
├── ci/
└── maintenance/
```

## 生产代码边界

- 后端新业务优先进入 `backend/app/features/<feature>/`。
- 跨 feature 只能依赖对方 `public.py`，不得导入私有实现。
- 现有 `backend/app/api/v1/endpoints` 作为兼容入口逐步变薄，不批量改 URL。
- 前端 `page.tsx` 只负责路由、布局和 feature 组装。
- `frontend/src/lib/api-client.ts` 保留兼容门面，领域方法逐步迁入 `features/*/api.ts`。
- 结构迁移不得同时改变响应字段、持久化状态、供应商参数和用户流程。

## 非源码内容

以下内容必须处于 Git 忽略范围，已经被跟踪的内容必须先归档再取消跟踪：

- `backend/static/dev/`、`backend/static/generated/` 和生成音视频。
- SQLite 数据库、数据库 WAL/SHM、导出数据和临时凭据。
- `.next*`、`node_modules`、`__pycache__`、`.pytest_cache`。
- `test-results`、Playwright 报告、截图、trace 和浏览器会话。
- `tmp`、覆盖率报告、临时 PDF 和本地日志。

取消跟踪生成物是独立数据维护批次。合并删除提交前必须确认本地主工作区、对象存储或归档包仍持有需要保留的数据。

## 迁移规则

1. 为旧行为建立刻画测试。
2. 创建职责单一的新模块和公开接口。
3. 让旧入口调用新接口，保留原路径和响应。
4. 运行目标测试、代码健康、前端或后端相关验证。
5. 确认热点文件没有增长，新模块没有越界依赖。
6. 结构迁移单独提交；行为变化另开批次。
7. 所有调用方迁移并经过一个发布周期后，才删除兼容入口。

## 根目录文件

根目录只保留仓库级入口：`README.md`、`AGENTS.md`、`CLAUDE.md`、包管理文件、Compose 兼容入口和许可证文件。`task_plan.md`、`findings.md`、`progress.md`、`design-qa.md` 等历史工作记录在确认无人继续使用后迁入 `docs/archive/project-history/`，不得在未确认时直接删除。
