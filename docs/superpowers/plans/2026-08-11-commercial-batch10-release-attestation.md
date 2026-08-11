# 商业发布证明门禁实施计划

## Intent Lock

把 G0-G8 从说明文档变成可执行门禁：候选分支允许保留明确阻塞项，只有证据齐全的 `releases -> main` PR 才能通过。

## Scope Boundaries

- 不修改业务 API、数据库、供应商调用、计费或媒体数据。
- 不伪造外部实模、法务、值班、UAT 或预发布恢复证据。
- 不自动合并 `main`，也不降低现有七项 CI 门禁。
- 不引入新的运行时依赖或远端证明服务。

## Constraints

- 证明清单使用仓库内 JSON，字段和状态由版本化校验器约束。
- 所有状态说明和修复动作必须是中文直白描述。
- `dev`、`releases` 及其 PR 只校验清单结构，允许状态为 `blocked`。
- 目标为 `main` 的 PR 必须来自 `releases`，G0-G8 必须全部为 `pass`，且通过项仍在有效期内。
- 本地证据路径必须存在；外部证据必须是 HTTPS 链接。

## Acceptance Criteria

1. 缺少门禁、重复门禁、未知字段状态、空责任人和不存在的证据路径均校验失败。
2. 阻塞项必须给出中文原因和中文修复动作。
3. 非 `main` 目标允许阻塞项并输出候选状态摘要。
4. `main` PR 来源不是 `releases`、存在阻塞项或证明过期时失败并逐项输出中文修复动作。
5. CI 新增 `commercial-release-gate`，不改变现有七项门禁。
6. 目标测试、完整后端、前端构建、代码健康和工作流语法验证通过。

## Verification Commands

```bash
cd backend && pytest -q tests/test_commercial_release_attestation.py
cd backend && pytest -q
cd frontend && npm run typecheck && npm run build
python3 tools/code_health/check.py --policy tools/code_health/policy.json --baseline tools/code_health/baseline.json
python3 scripts/verify_commercial_release.py --target-branch releases --source-branch dev --event-name pull_request
python3 scripts/verify_commercial_release.py --target-branch main --source-branch releases --event-name pull_request
```

## Tasks

- [x] 先写校验器合同测试并确认失败。
- [x] 实现清单解析、结构校验、证据校验和 `main` 严格模式。
- [x] 增加当前候选清单，真实标记未完成外部门禁。
- [x] 接入 CI 并更新发布门禁说明。
- [ ] 完成全量验证、差异审查、PR 和发布分支提升。

## Rollback

删除新增 CI job、校验器和清单即可回滚，不涉及数据库或运行态。若校验器误报，先保持 `main` No-Go，修正合同后重新跑门禁，不允许临时取消现有分支保护。
