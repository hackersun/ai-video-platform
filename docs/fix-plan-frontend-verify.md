# 前端复验问题修复计划（2026-11-05）

来源：上一轮前端验证（`/tmp/avp-e2e/ppw.log`，截图 `~/Documents/avp-shots/verify/`，`report.json`）。

| # | 级别 | 问题 | 修法 | 测试 |
|---|------|------|------|------|
| 1 | 严重 | 模拟模型验收夹具 `FACTS` 写死第 3、4 章，2 章小说 `_fixture_entities` IndexError | `FACTS` 改为相对位置（首章/第二章/倒数第二/末章），按实际章节数映射并钳制到 `[1, N]`；末集事件/对白锚点改为“最后一集”而非写死第 4 集 | `backend/tests/test_acceptance_fixture_chapter_count.py`：1/2/4 章 |
| 2 | 严重 | 章节增加后 `ensure_series_plan_for_pipeline` 复用旧分集计划 | 计划写入章节指纹（id + 序号 + 内容 sha256，按序）；ensure 时比对，不一致（增/删/改）且 `ensure=True` 时重建并产生新 plan 版本；已绑定 Series Run 的流水线在编排器里直接跳过计划阶段，运行中任务用的是自身 episodes 快照，不受影响 | `backend/tests/test_series_plan_fingerprint_rebuild.py` |
| 3 | 较高 | `/llm-config` 无模拟模式入口 | simple-setup 返回 `simulation_available`（非生产且服务端开启模拟）与 `simulation_enabled`；保存接口支持 `simulation: true`，一键把 4 张卡片绑定到确定性模型并测试通过；前端在 4 张卡片上方显示一个「模拟模式（不调用付费接口）」开关，仅非生产显示；保存后停留本页并提示“下一步：创建小说” | 后端 `backend/tests/test_simple_setup_simulation.py`；前端 Playwright `e2e/fix-verify-simulation.spec.ts` |
| 4 | 一般 | 新建小说表单丢内容；一键生成确认框强调付费；新建章节入口多 | 先查根因（见下）再改为函数式更新；确认框在模拟模式下提示「模拟模式、不扣费」；章节表单只保留一个「创建章节」按钮 + 创建方式选择 | Playwright 同上 |

## 4. 表单丢内容根因调查
- 所有字段 `onChange={() => setNovel({ ...novel, x })}` 读取的是渲染闭包里的 `novel`；
- AI 简介 / AI 封面是异步请求，完成时 `setNovel({ ...novel, intro })` 用的是点击时的旧快照，会把等待期间新填的标题/描述/标签覆盖回去；同一事件循环中的连续更新也会互相覆盖。
- 修法：全部改为 `setNovel((prev) => ({ ...prev, x }))`；保存草稿后跳到新小说详情（主路径不中断）。

## 收尾验证
后端相关测试、前端 typecheck + lint、Playwright 全量；临时脚本按新用户走：注册→模拟模式→2 章小说→一键生成→看片→下载→发布→加到 3 章再跑，确认计划重建。
