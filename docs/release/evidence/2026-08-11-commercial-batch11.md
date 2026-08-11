# Batch 11：CI Actions Node 24 运行时证据

## 结论

GitHub 远端 CI 已明确提示六类 Action 仍面向已弃用的 Node 20 Actions 运行时。根因不是应用使用的 Node.js 版本，而是工作流引用的 Action 主版本过旧。

本批次把四个 `actions/*` 官方 Action 和 Codecov 升级到 v7，把 Docker Buildx 升级到 v4，并增加合同测试阻止旧主版本回流。没有修改任务名称、触发条件、权限、依赖关系、测试命令、产物名称、分支保护上下文或应用代码。

## 官方依据

- `actions/checkout` 最新发布：v7.0.1，`action.yml` 声明 `runs.using: node24`。
  - https://github.com/actions/checkout/releases/tag/v7.0.1
- `actions/setup-python` 最新发布：v7.0.0，`action.yml` 声明 `runs.using: node24`。
  - https://github.com/actions/setup-python/releases/tag/v7.0.0
- `actions/setup-node` 最新发布：v7.0.0，`action.yml` 声明 `runs.using: node24`。
  - https://github.com/actions/setup-node/releases/tag/v7.0.0
- `actions/upload-artifact` 最新发布：v7.0.1，`action.yml` 声明 `runs.using: node24`。
  - https://github.com/actions/upload-artifact/releases/tag/v7.0.1
- `codecov/codecov-action` 最新发布：v7.0.0，采用复合 Action，不再声明 Node 20 运行时。
  - https://github.com/codecov/codecov-action/releases/tag/v7.0.0
- `docker/setup-buildx-action` 最新发布：v4.2.0，`action.yml` 声明 `runs.using: node24`。
  - https://github.com/docker/setup-buildx-action/releases/tag/v4.2.0

查询日期：2026-08-11。查询来源为上述 GitHub 官方仓库的 release API 和 v7 标签下的 `action.yml`。

## TDD 证据

### RED

命令：

```bash
.venv/bin/python -m pytest -q backend/tests/test_ci_action_runtime.py
```

结果：第一轮 `1 failed`，测试准确识别到 checkout 同时存在 v4/v5，setup-python 为 v5，setup-node 和 upload-artifact 为 v4。首次远端运行后又从最终注释发现 Codecov v3 和 Docker Buildx v3，扩展合同后再次得到预期的 `1 failed`，并准确显示两者的 v3 与目标主版本不符。

### GREEN

命令：

```bash
.venv/bin/python -m pytest -q \
  backend/tests/test_ci_action_runtime.py \
  backend/tests/test_commercial_release_attestation.py
```

结果：`9 passed`。

## 验证清单

- [x] 六类 Action 的所有引用均使用已核验的 Node 24 兼容主版本。
- [x] CI Action 运行时合同与商业发布证明合同通过。
- [x] CI YAML 可解析。
- [x] 代码健康门禁通过：736 个文件、150708 行有效代码、0 个阻塞项。
- [x] 全量后端测试通过：2368 passed、7 skipped、83 warnings。
- [x] 前端类型检查和生产构建通过：46 个路由。
- [x] npm 审计 0 漏洞；Python 锁定依赖未发现已知漏洞。
- [ ] 最终远端八项 CI 通过，且没有 Action 运行时或输入兼容性提示。
- [ ] `dev` 晋级 `releases`，`main` 保持不变。

本地全量验证日期：2026-08-11。现有 83 条 Python 弃用告警与本批次 Action 版本变更无关，远端 CI 将继续作为最终兼容性证据。

首次远端运行 `31470328843` 的八项检查全部通过，但最终注释仍指出 `codecov/codecov-action@v3` 和 `docker/setup-buildx-action@v3` 使用 Node 20。因此该运行没有被当作完成证据，也没有执行合并；修订后的远端运行才是最终验收来源。

第二次远端运行 `31472400038` 的八项检查全部通过，Node 20 注释清零，但 Codecov v7 指出旧输入 `file` 无效，支持的输入名是 `files`。该运行同样没有被当作完成证据；合同测试已增加 Codecov v7 输入名约束。

## 回滚

若 GitHub 托管运行器对 v7 出现兼容问题，只回滚本批次提交即可恢复原 Action 版本。回滚会重新出现 Node 20 弃用风险，因此不得绕过 CI 直接晋级；应保留失败日志并重新评估官方支持版本。
