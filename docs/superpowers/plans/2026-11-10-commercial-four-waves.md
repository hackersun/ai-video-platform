# 商用四波实施计划（2026-11-10）

- **分支**：`feat/series-run-redis-queue-and-tail-fsm`
- **产品决策（已确认）**：正式环境默认「**生产必须自带 Key**」；欢迎页文案说清；**不做赠送额度**（除非另有指示）。测试/演示环境仍可保留 `simulation_available` 下的演示模式，但文案不得误导为生产免费试用。
- **约束**：只改现有页面；一功能一入口；不放宽测试；不 stash；不改写历史；不开 PR；每项相关测试通过后 commit+push。
- **对照**：`docs/audits/2026-11-10-frontend-commercial-ux.md`、`docs/audits/2026-11-10-commercial-readiness.md`、`docs/audits/2026-11-10-backend-pipeline-reliability.md`、`docs/ui-simplification-plan-2026-11-08.md`

---

## 总览

| 波次 | 目标 | 本轮 |
|---|---|---|
| **第 1 波** | 前端再简化：主路径心智、欢迎态、导入、术语、导航、任务可读名 | **立即实施** |
| **第 2 波** | 后端管线可靠：队列/取消/失败恢复、费用闸验收、生产 fail-closed 证据 | 本轮不做 |
| **第 3 波** | 账号与滥用面：会话加固、注册登录限流、密码/邮箱策略、网关限流 | 本轮不做 |
| **第 4 波** | 可观测与上线门禁：readiness/指标/告警、备份恢复演练、法务终稿、真实模型小额验收 | **并行推进中**（2026-11-10：readiness+PG 契约+备份演练已做；实模/真桶待凭证） |

---

## 第 1 波：前端再简化

验收总目标（走查）：

- [x] 顶栏默认可见入口 ≤ 3：小说 / 成片 / 模型设置；任务中心、资产在「高级工具」
- [x] 手机宽度可进「模型设置」（不得被 `slice(0,4)` 挤掉）
- [x] 「快速开始」不作为主导航心智：改名「专家向导」并进高级工具；首页/dashboard CTA 统一「开始创作」→ `/novels`
- [x] 导入：「识别章节 + 确认导入」合并为「导入并开始」；失败才展开预览
- [x] 分集计划 / 故事设定等主路径去英文行话；扩展 glossary；Production Bible / Series Studio / Readiness / 门禁等不对新手主路径可见（专业页可保留但顶栏提示日常用一键）
- [x] 生产无试用时欢迎态清晰大卡「填写 API Key 开始」，文案说清无免费试用、需自带 Key
- [x] 数据概览纯数据、快捷入口 ≤ 3；工作室/制片/工作流顶栏提示「日常请用小说页一键生成」
- [x] 任务中心尽量显示书名 + 步骤中文（API 不够则前端可读映射）
- [x] 假模式新账号：注册 → 看片点击数记录；截图 `docs/ui-simplification-2026-11-08/wave1-after/`
- [x] 相关 Playwright + tsc/lint + 相关 backend 测试绿

### 任务清单

| # | 任务 | 主要文件 | 相关测试 | 状态 |
|---|---|---|---|---|
| W1-1 | 主导航→小说/成片/模型设置；任务中心+资产进高级；手机栏必含模型设置 | `top-navigation.tsx` | `top-navigation.spec.ts` | ✅ |
| W1-2 | 「快速开始」→「专家向导」进高级；首页/dashboard CTA「开始创作」→`/novels`；去掉连续动漫向导双叙事 | `page.tsx`(home)、`dashboard/page.tsx`、`top-navigation.tsx`、`quick-start` 文案 | `home-cta.spec.ts`、`smoke.spec.ts`、`top-navigation.spec.ts` | ✅ |
| W1-3 | 导入合并「识别+确认」→「导入并开始」；失败才展开预览 | `novels/page.tsx` | `novel-paste-import.spec.ts`、`novel-import-story-bible.spec.ts`、onboarding 相关 | ✅ |
| W1-4 | 扩展 glossary；分集计划/故事设定去英文行话；主路径不可见 Production Bible 等 | `glossary.ts`、novel detail、stage/blocker labels | novel / story-bible / series-plan 相关 e2e | ✅ |
| W1-5 | 生产无试用欢迎态：清晰大卡「填写 API Key 开始」；说清无免费试用 | `simple-model-setup.tsx` | `onboarding-simplification.spec.ts` | ✅ |
| W1-6 | dashboard 纯数据、快捷入口≤3；studio/producer/workflow 顶栏「日常请用小说页一键生成」 | `dashboard/page.tsx`、studio/producer/workflow 壳 | 相关 e2e（有则跑） | ✅ |
| W1-7 | 任务中心：书名 + 步骤中文（API 不够前端映射） | `jobs/page.tsx` | jobs / full-flow 相关 | ✅ |

**走查与收尾**

- [x] 假模式新账号全路径点击统计
- [x] 截图 `docs/ui-simplification-2026-11-08/wave1-after/`
- [x] 本计划勾选第 1 波；打包 `~/Documents/avp-wave1.tgz` → `/workspace/wave1/`
- [x] 停止服务

---

### 第1波实施记录（2026-11-10）

- 假模式新账号旅程：`docs/ui-simplification-2026-11-08/wave1-after/wave1.json`
- 点击序列：勾选条款 → 注册 → 演示模式 → 导入并开始 → 一键生成视频 → 播放 → 下载视频 → 查看发布（共 8 次主路径点击；native dialog=0）
- 生成约 8s 完成；下载 `video/mp4` ~6.2MB；dashboard 快捷入口=3；欢迎页 chooser=2（演示/自带 Key）
- 截图：`wave1-after/01-welcome.png` … `12-dashboard-shortcuts.png`
- 附：进度卡优先展示后端 `blocker_detail` 中文修复提示（`blocker-messages.ts`）
- 验证：frontend typecheck/lint 绿；Playwright 22/22（top-navigation/home-cta/dashboard-shortcuts/jobs-readable-names/novel-paste-import/onboarding-simplification/smoke）；backend `test_simple_setup_hides_test_artifacts` 2 passed

## 第 2 波：后端管线可靠（本轮不做）

目标：生产态下队列、取消、失败恢复、费用闸有证据可验。

| # | 任务 | 验收要点 | 状态 |
|---|---|---|---|
| W2-1 | series-run / publication-pipeline 取消与失败恢复契约 | 取消后不再继续扣费；失败可「继续」且幂等 | ☐ |
| W2-2 | 费用闸：opt-in + ¥50/次 + ¥200/账号；假模式不计费 | 单测 + 假模式走查账本 | ☐ |
| W2-3 | `assert_production_safe` 与 Compose 生产默认值对齐文档 | 启动拒绝假模式/DEV；手册与 env 示例一致 | ☐ |
| W2-4 | 任务/流水线 API 补齐可读字段（novel_title、stage 中文）供任务中心 | 契约测试 | ☐ |
| W2-5 | 1 章短片策略或自动拆章（若产品确认） | 与前端 FE-11 联动；单独立项也可 | ☐ |

---

## 第 3 波：账号与滥用面（本轮不做）

目标：公开注册前的最小安全面。

| # | 任务 | 验收要点 | 状态 |
|---|---|---|---|
| W3-1 | Access 短时 + Refresh HttpOnly/Secure/轮换可撤销 | 不再长期依赖 localStorage 长期令牌 | ☐ |
| W3-2 | 密码策略 + 邮箱验证或邀请码 | 注册激活链路可测 | ☐ |
| W3-3 | 登录/注册/重置限流 | 网关或中间件分档 | ☐ |
| W3-4 | 生成/上传接口限流 | 与计费闸配合 | ☐ |
| W3-5 | 关闭生产 DEV 旁路证据 | 越权合同测试 | ☐ |

---

## 第 4 波：可观测与上线门禁（本轮不做）

目标：可宣称「邀请制小流量实模」或冲公开收费的运行证据。

| # | 任务 | 验收要点 | 状态 |
|---|---|---|---|
| W4-1 | liveness/readiness（依赖 DB/Redis/存储） | `/health` liveness + `/ready` DB/Redis | ✅ 2026-11-10 |
| W4-2 | 结构化日志 + request id + 关键告警挂钩 | 手册可操作 | ☐ |
| W4-3 | DB + 对象存储备份与至少一次恢复演练记录 | RPO/RTO 写明 | ✅ DB 演练；⏸ 对象存储待凭证/镜像 |
| W4-4 | ToS/隐私法务终稿替换草案 | 注册同意版本号更新 | ☐ |
| W4-5 | 真实模型小额验收 + 私有桶真实上传/播放 | 门禁清单勾选 | ⏸ runbook 已写；待 Key/桶凭证 |

---

## 风险与边界

1. 演示模式仅非生产；欢迎文案必须区分「演示（测试环境）」与「生产需自带 Key」。
2. 导入合并不得放宽「≥2 章」等现有业务断言；失败路径必须可测。
3. 专业页术语可附注英文，但不得出现在小说主路径默认 UI。
4. 第 2–4 波涉及安全与运维，不在本轮改代码。

## 变更记录

| 日期 | 说明 |
|---|---|
| 2026-11-10 | 初稿；产品确认必须自带 Key、无赠送额度；开做第 1 波 |

| 2026-11-10 | Wave4 并行：readiness、PG 契约、备份演练、canary runbook；MinIO/实模待凭证 |
