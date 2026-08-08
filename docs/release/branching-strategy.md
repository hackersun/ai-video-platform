# 分支与版本发布规范

## 长期分支

| 分支 | 用途 | 允许来源 | 部署目标 |
|---|---|---|---|
| `main` | 已通过正式验收的生产真相 | `releases`、`hotfix/*` | production |
| `releases` | 下一版本候选 | `dev` | staging / pre-production |
| `dev` | 日常集成 | `feature/*`、`fix/*` | development |

`main`、`releases`、`dev` 都禁止直接开发。功能分支从 `dev` 创建；线上紧急修复从 `main` 创建。

## 短期分支

- `feature/<scope>-<intent>`：单一功能。
- `fix/<scope>-<intent>`：非紧急缺陷。
- `hotfix/<scope>-<intent>`：线上阻塞问题。
- `chore/<scope>-<intent>`：无业务行为的工具、依赖或文档。
- `archive/<name>-<date>`：只读历史归档，不接受开发提交。

Codex 创建的工作分支使用 `codex/` 前缀，例如 `codex/commercial-readiness-foundation`。

## 合并方向

```text
feature/* 或 fix/*
        ↓
       dev
        ↓
    releases
        ↓
       main
        ↓
   v<major>.<minor>.<patch>
```

`hotfix/*` 合入 `main` 后，必须以 PR 回灌 `releases` 和 `dev`，不得只修生产线。

## 分支保护

### main

- 只允许 PR 合并。
- 至少一名审批人。
- 必须解决所有 review conversation。
- 必需检查：前端、后端、代码健康、安全扫描、发布候选验收。
- 禁止强推和删除。
- 只允许从通过 staging 验收的 `releases` 或明确 hotfix 合入。

### releases

- 只允许 PR 合并。
- 必须通过与 `main` 相同的自动检查。
- 需要 staging environment 人工审批。
- 需要数据库迁移、备份恢复和回滚演练记录。
- 禁止强推和删除。

### dev

- 只允许 PR 合并。
- 必须通过前端、后端和代码健康检查。
- 禁止强推和删除。
- 允许 squash merge，PR 标题作为变更意图。

## 旧远端 dev 的处理

实际归档证据见[旧 dev 分支归档记录](legacy-dev-archive.md)。

旧 `dev` 与当前 `main` 属于不同历史。处理顺序固定为：

1. 读取旧 `dev` 的远端 SHA。
2. 创建 `archive/dev-legacy-20260808` 指向同一 SHA。
3. 从 GitHub 再次读取并证明两个 SHA 一致。
4. 检查旧 `dev` 独有提交并记录在归档说明中。
5. 当前治理版本进入 `main` 后，从该 `main` 重建 `dev`。
6. 替换 `dev` 只能使用 `--force-with-lease`，不能使用无租约强推。
7. `main` 永不重写。

## 版本号

采用语义化版本：

- major：不兼容 API、数据或操作流程变化。
- minor：向后兼容的新功能。
- patch：向后兼容的缺陷和安全修复。
- 候选版本：`v1.0.0-rc.1`，只指向 `releases` 已验收提交。

每个正式标签必须关联发布说明、制品摘要、数据库迁移、已知风险、回滚提交或镜像版本。

## 提交规则

- 一个提交只表达一个意图。
- 行为修复与结构整理分开。
- 不提交数据库、媒体、日志、测试结果和密钥。
- 提交前运行任务级测试和 `git diff --check`。
- 合并前运行受影响的完整前后端验证。
