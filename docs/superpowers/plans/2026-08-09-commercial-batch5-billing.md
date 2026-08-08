# 商用客户账务与供应商对账 Implementation Plan

**Goal:** 建立客户余额、额度、预扣、结算、释放、退款、不可变流水和供应商成本对账闭环，并把真实供应商提交接入该闭环。

**Architecture:** 客户账务以整数微元（1 元 = 1,000,000 微元）和追加式流水为事实源；实模验收预算继续留在 `SeriesProductionRun`，二者独立校验。供应商提交前用账户版本 CAS 原子预扣，成功按实际客户费用结算，明确失败释放，不确定状态保持预扣并等待人工确认。正式环境强制 `CUSTOMER_BILLING_MODE=enforced`，local/test 默认关闭以保持历史测试兼容。

**Tech Stack:** FastAPI、async SQLAlchemy、Alembic、PostgreSQL/SQLite、现有持久 task worker、pytest。

## Execution Contract

**Intent Lock:** 任何收费、扣减、释放和退款都有不可覆盖、可按供应商任务追溯的人民币证据。

**Out of Scope:** 本批不接第三方支付网关、不设计套餐销售页、不替换实模验收预算、不重写现有生成端点。

**Constraints:**

- 金额只用整数微元计算和落库；HTTP 展示由服务端转换为固定 6 位人民币字符串。
- 客户余额、月度额度、项目预算、并发限制和实模预算必须分别校验。
- 失败或取消只释放预扣；供应商状态不确定时不得退款或重复提交。
- 财务流水、用量事件和对账记录只追加；更正使用冲正记录。
- 现有 HTTP 路径和供应商安全门禁保持兼容；新增接口只读且按当前用户隔离。

**Acceptance Criteria:**

1. 并发预扣只有满足余额、额度、项目预算和并发限制的请求成功。
2. 相同幂等键、供应商回调和释放请求不会重复扣费或重复写用量。
3. 成功结算记录客户费用、供应商成本、毛利和差异；失败释放，退款写冲正流水。
4. 流水、用量和对账记录在 ORM 与数据库层均不可修改或删除。
5. 正式环境未启用客户计费时拒绝启动；生产 Compose 显式传入计费模式。
6. 现有实模预算继续生效，不能替代或绕过客户余额控制。
7. SQLite、PostgreSQL、全量后端、前端、代码健康和生产镜像门禁通过。

## Task 1: 财务模型、金额契约与迁移

**Files:** `backend/app/models/billing.py`、`backend/alembic/versions/20260809_0005_customer_billing.py`、`backend/app/features/billing/domain.py`、目标测试。

- [x] 先写金额精度、表结构、唯一约束和数据库级不可变测试并确认失败。
- [x] 新增账户、项目预算、预扣、流水、用量和供应商对账表；只增不删。
- [x] 验证 SQLite 迁移和迁移 head。

## Task 2: 原子预扣、结算、释放与退款

**Files:** `backend/app/features/billing/service.py`、`repository.py`、目标测试。

- [x] 先写余额不足、月额度、项目预算、并发 CAS、重复幂等、部分结算、失败释放和退款测试。
- [x] 实现账户版本 CAS 和追加式流水；冲突返回中文可重试提示。
- [x] 对供应商状态不确定的预扣保持锁定，不自动退款。

## Task 3: 用量和供应商对账

**Files:** `backend/app/features/billing/reconciliation.py`、目标测试。

- [x] 先写供应商成本匹配、差异阈值、重复账单和缺失账单测试。
- [x] 结算时写用量、供应商成本、客户费用和毛利快照。
- [x] 导入账单只追加对账结果；差异超阈值冻结账户后续收费任务。

## Task 4: 接入真实供应商操作与正式环境门禁

**Files:** `backend/app/services/live_canary_budget.py`、`backend/app/features/billing/integration.py`、runtime/Compose 配置和目标测试。

- [x] 供应商提交前同时通过实模预算和客户账户预扣。
- [x] 成功捕获、明确失败释放、不确定状态保持预扣并转人工确认。
- [x] production/staging 未配置 enforced 时 fail closed；local/test 保持兼容。

## Task 5: 客户只读 API、运营调账脚本与最终门禁

**Files:** `backend/app/features/billing/api.py`、`schemas.py`、`backend/scripts/adjust_billing_balance.py`、`backend/main.py` 和目标测试。

- [x] 当前用户只能查看自己的余额、流水、用量和对账，跨用户不泄漏。
- [x] 运营调账必须提供操作者、中文原因和幂等键；不提供客户自助加钱接口。
- [x] 跑 PostgreSQL 并发合同、全量后端、前端、代码健康、Compose 和 Docker CI。
- [x] 内联审查后单一意图提交，走 `dev` PR 门禁。
