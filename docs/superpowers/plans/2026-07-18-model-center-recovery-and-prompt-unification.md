# 模型中心修复与提示词统一实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不丢失 `sunqy` 现有模型配置、提示词正文、默认绑定和生产任务的前提下，消除 PromptSkill/PromptProfile 双轨，补齐模型中心真实可维护能力，并从前端完成确定性全流程验收。

**Architecture:** 继续使用已经落地的 `features/model_config`、`features/prompt_profiles` 和 `features/model-center`，不创建第三套配置体系。`PromptProfileVersion` 成为提示词唯一版本真相，旧 `/prompt-skills` API 作为兼容投影；模型中心所有列表使用服务端分页和可读关联字段，所有写操作使用草稿、校验、发布、影响确认和审计事件。

**Tech Stack:** FastAPI、Pydantic、async SQLAlchemy、SQLite/PostgreSQL、Next.js 14、React 18、TypeScript、Tailwind CSS、pytest、Playwright。

## Global Constraints

- 保留现有 `/api/v1/llm/*`、`/api/v1/external/*`、`/api/v1/prompt-skills/*` 和 `/api/v1/model-center/*` 路由兼容；已有字段不得删除或改变语义。
- 不删除 `prompt_skills`、`prompt_profiles`、`prompt_profile_versions`、模型连接、绑定、组合预设或认证历史。
- `backend/ai_video.db` 在迁移执行前只允许只读预检；迁移必须先备份、输出脱敏计划、显式 `--apply`，并通过幂等测试。
- 已发布 Prompt、模型档案和组合预设保持不可变；修改、停用和回滚均创建新版本。
- Prompt 正文可以返回给所属用户，但不得进入日志、错误、审计摘要或模型中心概览响应。
- API Key/API Secret 继续只写、加密保存、脱敏响应；本计划不得输出任何真实密钥。
- 未实现的操作不得显示成可用主按钮；前端能力必须与后端真实路由一致。
- 目录可见不等于生产就绪；概览必须检查连接、模型版本、绑定、Prompt、组合预设和认证。
- 普通模式不得要求用户填写 UUID 或原始 JSON；UUID 只允许在高级详情中复制，复杂 JSON 由结构化表单生成。
- 所有目录筛选、搜索和分页在服务端执行；测试实验室不得只读取第一页候选项。
- 不自动发起付费图像、语音或视频调用；实模验收必须获得独立费用授权。
- 新生产文件目标不超过 300 行、上限 500 行；React feature 组件不超过 200 行；FastAPI 路由方法不超过 60 行。
- `management.py`、`repository.py`、`backfill.py` 当前接近 500 行，不增加新职责；新行为放入聚焦模块。
- 每个行为变化先写失败测试，批次结束运行目标测试、前端 typecheck/build 和浏览器验收。

---

## Execution Contract

### Intent Lock

把当前“数据仍在但页面看不到、旧能力仍在但入口丢失、按钮存在但后端不支持”的模型中心，修复为数据单一、能力真实、可从前端维护并能回到生产工作台的闭环。

### Current Verified Baseline

- `sunqy` 旧 `prompt_skills` 共 14 条，14 条正文非空，8 条启用。
- 模型中心 `prompt_profiles` 共 8 条，8 条版本正文非空，但 14 条旧技能的 `prompt_profile_version_id` 全部为空。
- 模型目录总计 220 条，当前前端只展示第一页 20 条；能力筛选只过滤这 20 条。
- 规范模型版本共 254 条；`sunqy` 模型中心认证运行记录为 0。
- `sunqy` 模型连接 14 条，其中 6 条 `verified`、8 条 `draft`。
- 提供方、模型档案、模型版本、能力绑定的多项写路由当前明确返回 `501 operation_not_implemented`。

### Scope Boundaries

- 不重写小说、Story Bible、资产、剧本、分镜、视频、配音、字幕和合成业务。
- 不移除旧页面地址；`/prompt-skills` 继续保留兼容入口和返回上下文。
- 不在本批次增加任意脚本驱动、动态执行代码或跨供应商自动付费降级。
- 不清理与模型中心无关的工作树文件、媒体产物和缓存。
- 不把“全部模型都能使用”作为默认假设；未安装驱动的模型只能保存为草稿并显示明确原因。

### Acceptance Criteria

1. `sunqy` 的 14 条旧提示词全部可从模型中心查看，正文非空，启用/停用状态正确，迁移前后内容哈希一致。
2. 每个旧 PromptSkill 都链接到一个有效 PromptProfileVersion；重复执行迁移创建数和更新数均为 0。
3. 小说、章节、剧本、分镜、实体抽取、图像、视频和一致性流程都通过同一 Prompt 选择公开接口解析版本。
4. 旧 `/prompt-skills` 的列表、创建、编辑、AI优化、预览、克隆、激活、删除和批量能力继续可用，并与模型中心看到同一版本。
5. 模型中心提示词页可查看正文、历史、差异、路由范围、验证样例、发布影响，并提供 AI 优化和预览。
6. 模型目录能分页、搜索、按能力/提供方/状态筛选；220 条数据均可访问，筛选结果不受第一页限制。
7. 连接页面显示提供方名称并使用下拉选择；“新增模型”和“新增连接”语义分开。
8. 已安装驱动的提供方与模型版本可从前端创建、校验、发布、停用和回滚；未安装驱动只能保存草稿。
9. 能力绑定可创建、修改、停用和查看影响；页面显示路由策略、优先级、有效模型、连接和认证等级。
10. 组合预设显示真实策略，支持查看、编辑草稿、校验、发布和回滚；新草稿可从前端进入 published 状态。
11. 概览不会再仅凭“有连接、有组合”显示无阻塞；所有阻塞项都有准确处理链接和返回工作台链接。
12. 测试实验室可搜索全部模型和连接，只允许兼容组合，并能查看认证运行历史和脱敏证据。
13. 确定性四章前端回归通过后，才允许单独申请付费实模授权。

### Verification Commands

```bash
cd backend
python -m pytest -q \
  tests/test_model_center_prompt_recovery.py \
  tests/test_prompt_profile_versioning.py \
  tests/test_prompt_skill_routing.py \
  test_prompt_skills.py \
  test_prompt_skill_ai_entrypoints.py \
  tests/test_model_center_api.py \
  tests/test_model_center_repository.py \
  tests/test_model_binding_resolution.py \
  tests/test_production_recipe_contract.py \
  tests/test_model_center_backfill.py \
  tests/test_model_center_shadow_compare.py

cd ../frontend
npm run typecheck
NEXT_DIST_DIR=.next-model-center-recovery npm run build
npx playwright test \
  e2e/prompt-skills.spec.ts \
  e2e/model-center-api-contract.spec.ts \
  e2e/model-center-navigation.spec.ts \
  e2e/model-center-prompts.spec.ts \
  e2e/model-center-recipes.spec.ts \
  e2e/model-center-test-lab.spec.ts \
  e2e/model-center-recovery.spec.ts \
  e2e/four-chapter-series-run.spec.ts \
  --project=chromium --workers=1
```

### Decision Points

- Task 1 只建立刻画测试和只读审计，不修改真实数据。
- Task 2 完成迁移预检后，必须检查备份、14 条提示词映射、内容哈希和冲突报告；未通过不得执行 `--apply`。
- Task 5 完成提示词前端恢复后，先由真实 `sunqy` 页面验收，再进入模型档案写能力。
- Task 11 的确定性浏览器验收全部通过后，再单独申请四章、预算和关键镜头实模授权。
- 删除旧表、旧路由或兼容投影属于后续独立计划。

---

## Target File Structure

```text
backend/app/features/model_config/
├── prompt_recovery.py                 # PromptSkill 到 PromptProfile 的预检和幂等修复
├── prompt_assistance.py               # AI优化、预览和样例验证应用服务
├── catalog_management.py              # 提供方/模型档案版本写用例
├── binding_management.py              # 绑定写用例与影响查询
├── readiness.py                       # 完整发布前检查
└── api/
    ├── catalog.py
    ├── profiles.py
    ├── bindings.py
    ├── prompts.py
    └── recipes.py

frontend/src/features/model-center/
├── components/
│   ├── model-center-pagination.tsx
│   ├── provider-model-label.tsx
│   ├── model-version-picker.tsx
│   ├── provider-profile-editor.tsx
│   ├── binding-editor.tsx
│   ├── recipe-detail.tsx
│   ├── prompt-profile-workbench.tsx
│   ├── prompt-profile-history.tsx
│   ├── prompt-assistant-panel.tsx
│   └── readiness-checklist.tsx
└── hooks/
    ├── use-paged-model-catalog.ts
    ├── use-prompt-profile-detail.ts
    └── use-certification-history.ts
```

---

## Batch 0 — 锁定现状和数据安全

### Task 1: 建立提示词恢复刻画测试和只读审计

**Files:**
- Create: `backend/tests/test_model_center_prompt_recovery.py`
- Create: `backend/scripts/audit_model_center_prompt_links.py`
- Modify: `backend/tests/model_center_helpers.py`

**Interfaces:**
- Consumes: `PromptSkill`, `PromptProfile`, `PromptProfileVersion` 当前表结构。
- Produces: `PromptLinkAudit`, `audit_prompt_links(db, user_id) -> PromptLinkAudit`。

- [ ] **Step 1: 写失败的孤立数据库刻画测试**

```python
@pytest.mark.asyncio
async def test_prompt_link_audit_reports_active_inactive_and_unlinked_rows(db_session):
    user_id = "user-1"
    await seed_prompt_skill(db_session, id="active", user_id=user_id, version=3, active=True, content="ACTIVE")
    await seed_prompt_skill(db_session, id="inactive", user_id=user_id, version=2, active=False, content="INACTIVE")

    audit = await audit_prompt_links(db_session, user_id)

    assert audit.legacy_total == 2
    assert audit.legacy_nonempty == 2
    assert audit.active_total == 1
    assert audit.inactive_total == 1
    assert audit.linked_total == 0
    assert audit.content_conflicts == ()
```

- [ ] **Step 2: 运行测试确认接口不存在**

Run: `cd backend && python -m pytest -q tests/test_model_center_prompt_recovery.py::test_prompt_link_audit_reports_active_inactive_and_unlinked_rows`

Expected: FAIL because `audit_prompt_links` and `PromptLinkAudit` do not exist.

- [ ] **Step 3: 实现只读审计值对象和脚本**

```python
@dataclass(frozen=True)
class PromptLinkAudit:
    legacy_total: int
    legacy_nonempty: int
    active_total: int
    inactive_total: int
    linked_total: int
    orphan_profile_ids: tuple[str, ...]
    content_conflicts: tuple[str, ...]


async def audit_prompt_links(db: AsyncSession, user_id: str) -> PromptLinkAudit:
    skills = list((await db.scalars(select(PromptSkill).where(PromptSkill.user_id == user_id))).all())
    versions = await load_linked_prompt_versions(db, skills)
    return PromptLinkAudit(
        legacy_total=len(skills),
        legacy_nonempty=sum(bool((row.content or "").strip()) for row in skills),
        active_total=sum(bool(row.is_active) for row in skills),
        inactive_total=sum(not bool(row.is_active) for row in skills),
        linked_total=sum(row.prompt_profile_version_id in versions for row in skills),
        orphan_profile_ids=tuple(sorted(find_orphan_profile_ids(skills, versions))),
        content_conflicts=tuple(sorted(find_content_conflicts(skills, versions))),
    )
```

CLI 只接受 `--user-id` 和 `--database-url`，输出数量、ID和哈希，不输出正文，不提供 `--apply`。

- [ ] **Step 4: 运行刻画测试和真实只读审计**

Run: `cd backend && python -m pytest -q tests/test_model_center_prompt_recovery.py`

Expected: PASS.

Run: `cd backend && python scripts/audit_model_center_prompt_links.py --user-id 56ae84de-951f-4e74-ac79-3550d6f6f3b2`

Expected: JSON reports `legacy_total=14`, `legacy_nonempty=14`, `active_total=8`, `inactive_total=6`, `linked_total=0`; no prompt body appears.

- [ ] **Step 5: 提交只读基线**

```bash
git add backend/tests/test_model_center_prompt_recovery.py backend/tests/model_center_helpers.py backend/scripts/audit_model_center_prompt_links.py
git commit -m "test: characterize model center prompt recovery"
```

---

## Batch 1 — P0 提示词数据恢复和单一运行时

### Task 2: 幂等修复全部 PromptSkill 到规范版本的关联

**Files:**
- Create: `backend/app/features/model_config/prompt_recovery.py`
- Modify: `backend/app/features/model_config/backfill.py:145-160,326-352`
- Modify: `backend/app/features/prompt_profiles/versioning.py:83-142`
- Modify: `backend/scripts/backfill_model_center.py`
- Test: `backend/tests/test_model_center_prompt_recovery.py`
- Test: `backend/tests/test_model_center_backfill.py`

**Interfaces:**
- Consumes: Task 1 `audit_prompt_links()`。
- Produces: `plan_prompt_recovery()`, `apply_prompt_recovery()`, `PromptRecoveryReport`。

- [ ] **Step 1: 写迁移完整性和幂等失败测试**

```python
@pytest.mark.asyncio
async def test_prompt_recovery_links_every_skill_and_preserves_content_hash(db_session):
    active = await seed_prompt_skill(db_session, id="active", version=3, active=True, content="ACTIVE")
    inactive = await seed_prompt_skill(db_session, id="inactive", version=2, active=False, content="INACTIVE")

    report = await apply_prompt_recovery(db_session, user_id=active.user_id)
    await db_session.flush()

    assert report.skills_linked == 2
    assert report.content_conflicts == ()
    assert await linked_content_hash(db_session, active.id) == stable_prompt_hash("ACTIVE")
    assert await linked_content_hash(db_session, inactive.id) == stable_prompt_hash("INACTIVE")
    assert await linked_status(db_session, active.id) == "published"
    assert await linked_status(db_session, inactive.id) == "disabled"

    second = await apply_prompt_recovery(db_session, user_id=active.user_id)
    assert second.created_total == 0
    assert second.updated_total == 0
```

- [ ] **Step 2: 运行测试确认现有回填只处理启用项且不写关联**

Run: `cd backend && python -m pytest -q tests/test_model_center_prompt_recovery.py::test_prompt_recovery_links_every_skill_and_preserves_content_hash`

Expected: FAIL with inactive row missing or `prompt_profile_version_id is None`.

- [ ] **Step 3: 实现 check-first 恢复计划**

```python
@dataclass(frozen=True)
class PromptRecoveryReport:
    profiles_created: int = 0
    versions_created: int = 0
    skills_linked: int = 0
    created_total: int = 0
    updated_total: int = 0
    content_conflicts: tuple[str, ...] = ()


async def plan_prompt_recovery(db: AsyncSession, *, user_id: str) -> PromptRecoveryPlan:
    skills = await load_all_prompt_skills(db, user_id=user_id)
    return PromptRecoveryPlan(tuple(await plan_skill_recovery(db, skill) for skill in skills))


async def apply_prompt_recovery(db: AsyncSession, *, user_id: str) -> PromptRecoveryReport:
    plan = await plan_prompt_recovery(db, user_id=user_id)
    if plan.content_conflicts:
        raise PromptRecoveryConflict(plan.content_conflicts)
    return await persist_prompt_recovery_plan(db, plan)
```

恢复规则：优先复用 `PromptSkill.prompt_profile_version_id`；其次复用 `key in {legacy.<skill_id>, legacy:<skill_id>}` 且正文哈希一致的档案；否则新增档案。启用技能链接到 `published`，停用技能链接到 `disabled`。若现有规范 `v1` 与旧技能版本号不一致，创建带迁移来源证据的新头版本，不改写已发布版本。

- [ ] **Step 4: 修改旧兼容版本服务先解析已链接档案**

```python
async def ensure_legacy_prompt_profile(db: AsyncSession, skill: PromptSkill) -> PromptProfileVersion:
    linked = await linked_prompt_version(db, skill)
    if linked is not None:
        return linked
    recovered = await recover_single_prompt_skill(db, skill)
    skill.prompt_profile_version_id = recovered.id
    return recovered
```

禁止继续假设 `PromptProfile.id == PromptSkill.id`；档案身份由已链接版本的 `profile_id` 决定。

- [ ] **Step 5: 扩展 CLI 为显式恢复模式**

```bash
python scripts/backfill_model_center.py --check-prompts --user-id USER_ID
python scripts/backfill_model_center.py --apply-prompts --user-id USER_ID --backup-ack BACKUP_PATH
```

`--apply-prompts` 在存在内容冲突、孤立已发布版本或备份路径不存在时退出非零。

- [ ] **Step 6: 运行迁移、版本和数据库方言测试**

Run: `cd backend && python -m pytest -q tests/test_model_center_prompt_recovery.py tests/test_model_center_backfill.py tests/test_prompt_profile_versioning.py tests/test_model_center_migrations.py`

Expected: PASS; second recovery run has zero writes.

- [ ] **Step 7: 提交安全恢复实现**

```bash
git add backend/app/features/model_config/prompt_recovery.py backend/app/features/model_config/backfill.py backend/app/features/prompt_profiles/versioning.py backend/scripts/backfill_model_center.py backend/tests/test_model_center_prompt_recovery.py backend/tests/test_model_center_backfill.py
git commit -m "fix: unify legacy prompt profile links"
```

### Task 3: 将所有生产 Prompt 解析收敛到一个公开接口

**Files:**
- Modify: `backend/app/features/prompt_profiles/public.py`
- Modify: `backend/app/features/prompt_profiles/routing.py`
- Modify: `backend/app/services/prompt_template_router.py:203-270`
- Modify: `backend/app/services/prompt_skill_service.py:394-479`
- Modify: `backend/app/services/consistency_context.py:630-680`
- Modify: `backend/app/features/video_generation/application/consistency_package.py:330-360`
- Test: `backend/tests/test_prompt_skill_routing.py`
- Test: `backend/test_prompt_skill_prompt_composer.py`
- Test: `backend/test_prompt_skills.py`

**Interfaces:**
- Consumes: Task 2 已链接 Prompt 版本。
- Produces: `resolve_prompt_entries(query: PromptRouteQuery) -> tuple[PromptSelection, ...]`。

- [ ] **Step 1: 写跨入口一致性失败测试**

```python
@pytest.mark.asyncio
async def test_video_and_template_router_resolve_same_prompt_version(db_session, linked_prompt):
    routed = await select_prompt_skill_for_model(
        db_session, user_id=linked_prompt.user_id, task="shot_video",
        provider_name="volcano", model_id="doubao-seedance-1-5-pro",
    )
    entries = await active_prompt_skill_entries(
        db_session, linked_prompt.user_id, task="shot_video", context={},
    )
    assert routed["prompt_profile_version_id"] == entries[0]["prompt_profile_version_id"]
    assert routed["prompt_skill_version"] == entries[0]["version"]
```

- [ ] **Step 2: 运行测试确认当前两个入口选择规则不同**

Run: `cd backend && python -m pytest -q tests/test_prompt_skill_routing.py::test_video_and_template_router_resolve_same_prompt_version`

Expected: FAIL because direct PromptSkill selection does not return the canonical linked version.

- [ ] **Step 3: 定义唯一公开解析接口**

```python
async def resolve_prompt_entries(db: AsyncSession, query: PromptRouteQuery) -> tuple[PromptSelection, ...]:
    selection = await select_prompt_profile(db, query=query)
    return (selection,) if selection is not None else ()
```

`active_prompt_skill_entries()` 保留旧函数名，但内部调用 `resolve_prompt_entries()` 并投影旧字段，不再直接查询 `PromptSkill.content`。

- [ ] **Step 4: 改造生产调用方只依赖公开门面**

```python
entries = await resolve_prompt_entries(
    db,
    PromptRouteQuery(user_id=user_id, task=task, context=context or {}),
)
skill_blocks = [entry.prompt for entry in entries]
```

`consistency_context.py` 和视频一致性包不得导入 `prompt_profiles` 私有模块，只从 `app.features.prompt_profiles.public` 导入。

- [ ] **Step 5: 运行 Prompt 和生产入口回归**

Run: `cd backend && python -m pytest -q tests/test_prompt_skill_routing.py test_prompt_skill_prompt_composer.py test_prompt_skills.py tests/test_model_execution_snapshot.py`

Expected: PASS;所有入口记录同一 `prompt_profile_version_id`。

- [ ] **Step 6: 提交运行时收敛**

```bash
git add backend/app/features/prompt_profiles/public.py backend/app/features/prompt_profiles/routing.py backend/app/services/prompt_template_router.py backend/app/services/prompt_skill_service.py backend/app/services/consistency_context.py backend/app/features/video_generation/application/consistency_package.py backend/tests/test_prompt_skill_routing.py backend/test_prompt_skill_prompt_composer.py backend/test_prompt_skills.py
git commit -m "fix: resolve prompts through one canonical path"
```

### Task 4: 补齐提示词详情、历史、AI优化和预览 API

**Files:**
- Create: `backend/app/features/model_config/prompt_assistance.py`
- Modify: `backend/app/features/model_config/management_repository.py:119-135`
- Modify: `backend/app/features/model_config/prompt_management_repository.py`
- Modify: `backend/app/features/model_config/api/prompts.py`
- Modify: `backend/app/features/model_config/api/schemas.py`
- Modify: `backend/app/api/v1/endpoints/prompt_skills.py`
- Test: `backend/tests/test_model_center_api.py`
- Test: `backend/test_prompt_skill_ai_entrypoints.py`

**Interfaces:**
- Produces: `GET /prompt-profiles/{id}`, `GET /prompt-profiles/{id}/versions`, `POST /prompt-profiles/{id}/optimize`, `POST /prompt-profiles/{id}/preview`。

- [ ] **Step 1: 写详情和辅助能力失败测试**

```python
async def test_prompt_profile_detail_returns_owned_body_and_history(client, prompt_profile):
    response = await client.get(f"/api/v1/model-center/prompt-profiles/{prompt_profile.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["head"]["task_template"] == "legacy body"
    assert payload["versions"][0]["checksum"]
    assert payload["versions"][0]["content"] == "legacy body"


async def test_prompt_profile_optimize_reuses_legacy_optimizer(client, prompt_profile):
    response = await client.post(
        f"/api/v1/model-center/prompt-profiles/{prompt_profile.id}/optimize",
        json={"version_id": prompt_profile.head_id, "mode": "productionize", "model_config_id": None},
    )
    assert response.status_code == 200
    assert response.json()["optimized_content"]
    assert response.json()["source"] in {"ai_model", "local_rules"}
```

- [ ] **Step 2: 运行测试确认只有目录元数据**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py -k 'prompt_profile_detail or prompt_profile_optimize'`

Expected: FAIL with 404.

- [ ] **Step 3: 定义详情响应和版本响应**

```python
class PromptVersionDetail(BaseModel):
    id: str
    version: int
    status: str
    stage: str | None
    content: str
    input_mapping: dict[str, Any]
    routing: dict[str, Any]
    output_schema: dict[str, Any]
    validation_fixtures: list[dict[str, Any]]
    release_notes: str
    checksum: str


class PromptProfileDetail(BaseModel):
    id: str
    key: str
    name: str
    task: str
    head: PromptVersionDetail
    versions: list[PromptVersionDetail]
```

详情查询必须按 `PromptProfile.user_id == current_user_id` 限定；列表仍不返回正文，避免概览负载膨胀。

- [ ] **Step 4: 复用现有优化和预览能力**

```python
async def optimize_prompt_profile(db, *, user_id, profile_id, version_id, mode, model_config_id):
    detail = await load_owned_prompt_version(db, user_id=user_id, profile_id=profile_id, version_id=version_id)
    return await optimize_prompt_skill_content(db, user_id, {
        "task": detail.task,
        "name": detail.name,
        "content": detail.content,
        "mode": mode,
        "model_config_id": model_config_id,
    })
```

旧 `/prompt-skills/optimize` 和新接口调用同一应用服务；不得复制优化规则。

- [ ] **Step 5: 运行 API、鉴权和脱敏测试**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py test_prompt_skill_ai_entrypoints.py test_prompt_skills.py`

Expected: PASS;其它用户不能读取正文，错误和审计不包含正文。

- [ ] **Step 6: 提交提示词管理 API**

```bash
git add backend/app/features/model_config/prompt_assistance.py backend/app/features/model_config/management_repository.py backend/app/features/model_config/prompt_management_repository.py backend/app/features/model_config/api/prompts.py backend/app/features/model_config/api/schemas.py backend/app/api/v1/endpoints/prompt_skills.py backend/tests/test_model_center_api.py backend/test_prompt_skill_ai_entrypoints.py
git commit -m "feat: restore prompt detail and assistance api"
```

### Task 5: 重建模型中心提示词工作台并保留旧入口能力

**Files:**
- Create: `frontend/src/features/model-center/hooks/use-prompt-profile-detail.ts`
- Create: `frontend/src/features/model-center/components/prompt-profile-workbench.tsx`
- Create: `frontend/src/features/model-center/components/prompt-profile-history.tsx`
- Create: `frontend/src/features/model-center/components/prompt-assistant-panel.tsx`
- Modify: `frontend/src/features/model-center/components/prompt-profile-list.tsx`
- Modify: `frontend/src/features/model-center/components/prompt-profile-editor.tsx`
- Modify: `frontend/src/features/model-center/components/prompt-profile-diff.tsx`
- Modify: `frontend/src/features/model-center/api.ts`
- Modify: `frontend/src/features/model-center/types.ts`
- Modify: `frontend/src/app/prompt-skills/page.tsx`
- Test: `frontend/e2e/model-center-prompts.spec.ts`
- Test: `frontend/e2e/prompt-skills.spec.ts`

**Interfaces:**
- Consumes: Task 4 detail/versions/optimize/preview APIs。
- Produces: 可读取、编辑、优化、预览、发布、回滚的提示词工作台。

- [ ] **Step 1: 写前端正文恢复和 AI 优化失败测试**

```typescript
test('loads saved prompt body and keeps legacy entry capabilities', async ({ page }) => {
  await page.goto('/prompt-skills?returnTo=%2Fstudio');
  await expect(page).toHaveURL(/section=prompts/);
  await expect(page.getByLabel('任务模板')).not.toHaveValue('');
  await expect(page.getByRole('button', { name: 'AI 优化' })).toBeVisible();
  await expect(page.getByRole('button', { name: '预览 Prompt' })).toBeVisible();
  await expect(page.getByRole('link', { name: '返回工作台' })).toHaveAttribute('href', '/studio');
});
```

- [ ] **Step 2: 运行确认当前字段为空且按钮缺失**

Run: `cd frontend && npx playwright test e2e/model-center-prompts.spec.ts e2e/prompt-skills.spec.ts --project=chromium --workers=1`

Expected: FAIL on empty task template or missing AI optimization button.

- [ ] **Step 3: 实现按选择项加载详情的 Hook**

```typescript
export function usePromptProfileDetail(profileId?: string) {
  const request = useCallback(
    () => profileId ? modelCenterApi.getPromptProfile(profileId) : Promise.resolve(null),
    [profileId],
  );
  return useModelCenterQuery(`prompt-profile:${profileId || 'none'}`, request);
}
```

- [ ] **Step 4: 编辑器从服务端头版本初始化且切换时重置**

```typescript
useEffect(() => {
  if (!detail?.head) return;
  setDraft(promptDraftFromVersion(detail.head));
}, [detail?.head.id]);
```

列表增加任务、状态、关键字筛选；停用档案可查看但不能直接作为生产头版本。历史面板显示版本、状态、发布时间、发布说明和差异。

- [ ] **Step 5: 恢复 AI 优化、预览和变量指导**

```tsx
<PromptAssistantPanel
  version={detail.head}
  modelConfigs={textModelConfigs}
  onOptimize={modelCenterApi.optimizePromptProfile}
  onPreview={modelCenterApi.previewPromptProfile}
  onApply={(content) => update('taskTemplate', content)}
/>
```

AI 返回结果先进入建议区，用户点击“应用优化结果”后才修改草稿；不得自动保存或发布。

- [ ] **Step 6: 保留 `/prompt-skills` 兼容入口和返回上下文**

`LegacyModelCenterRedirect` 继续跳转 `section=prompts`，但新工作台必须包含旧页面的创建、AI优化、预览、变量说明、克隆/新版本、发布/激活、停用和删除限制说明。

- [ ] **Step 7: 运行浏览器、类型和构建验证**

Run: `cd frontend && npm run typecheck && NEXT_DIST_DIR=.next-prompt-recovery npm run build && npx playwright test e2e/model-center-prompts.spec.ts e2e/prompt-skills.spec.ts --project=chromium --workers=1`

Expected: PASS;保存的正文可见，AI建议不会自动覆盖，旧入口可返回工作台。

- [ ] **Step 8: 提交提示词前端恢复**

```bash
git add frontend/src/features/model-center/hooks/use-prompt-profile-detail.ts frontend/src/features/model-center/components/prompt-profile-workbench.tsx frontend/src/features/model-center/components/prompt-profile-history.tsx frontend/src/features/model-center/components/prompt-assistant-panel.tsx frontend/src/features/model-center/components/prompt-profile-list.tsx frontend/src/features/model-center/components/prompt-profile-editor.tsx frontend/src/features/model-center/components/prompt-profile-diff.tsx frontend/src/features/model-center/api.ts frontend/src/features/model-center/types.ts frontend/src/app/prompt-skills/page.tsx frontend/e2e/model-center-prompts.spec.ts frontend/e2e/prompt-skills.spec.ts
git commit -m "fix: restore complete prompt management workbench"
```

---

## Batch 2 — P1 模型目录、连接、档案和绑定真实可维护

### Task 6: 修复模型目录和连接的可读合同、搜索与分页

**Files:**
- Modify: `backend/app/features/model_config/catalog.py`
- Modify: `backend/app/features/model_config/repository.py:316-426`
- Modify: `backend/app/features/model_config/management_repository.py:35-118`
- Modify: `backend/app/features/model_config/api/catalog.py`
- Modify: `backend/app/features/model_config/api/connections.py`
- Modify: `backend/app/features/model_config/api/schemas.py`
- Create: `frontend/src/features/model-center/components/model-center-pagination.tsx`
- Create: `frontend/src/features/model-center/components/provider-model-label.tsx`
- Create: `frontend/src/features/model-center/hooks/use-paged-model-catalog.ts`
- Modify: `frontend/src/features/model-center/components/model-center-catalog-panel.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-connections-panel.tsx`
- Modify: `frontend/src/features/model-center/api.ts`
- Test: `backend/tests/test_model_center_repository.py`
- Test: `backend/tests/test_model_center_api.py`
- Test: `frontend/e2e/model-center-api-contract.spec.ts`
- Test: `frontend/e2e/model-center-recovery.spec.ts`

- [ ] **Step 1: 写服务端分页和可读字段失败测试**

```python
async def test_catalog_filters_before_pagination_and_returns_display_names(client, catalog_rows):
    response = await client.get("/api/v1/model-center/catalog?capability=video_generation&page=2&page_size=10&q=seedance")
    payload = response.json()
    assert payload["meta"]["total"] == 23
    assert len(payload["items"]) == 10
    assert all("video_generation" in item["capabilities"] for item in payload["items"])
    assert all(item["provider_name"] and item["model_name"] for item in payload["items"])
```

- [ ] **Step 2: 运行确认筛选只发生在前端第一页**

Run: `cd backend && python -m pytest -q tests/test_model_center_repository.py -k catalog_filters_before_pagination`

Expected: FAIL because catalog endpoint does not accept capability/query filters or display names.

- [ ] **Step 3: 扩展目录和连接响应**

```python
class CatalogItem(BaseModel):
    provider_id: str
    provider_name: str
    provider_code: str
    model_name: str
    api_model_id: str
    profile_version_id: str | None
    profile_version: int | None
    driver_key: str | None
    certification_status: str
    capabilities: list[str]


class ConnectionItem(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    provider_code: str
    name: str
    status: str
    has_secret: bool
    enabled: bool
    revision: int
```

`list_product_catalog()` 接收 `capability`, `provider_id`, `status`, `q`, `page`, `page_size`，在数据库/规范目录层过滤后再分页。

- [ ] **Step 4: 前端增加真实分页和可读标签**

```tsx
<ModelCenterPagination
  page={data.meta.page}
  pageSize={data.meta.page_size}
  total={data.meta.total}
  onPageChange={setPage}
/>
```

连接创建表单把“提供方 ID”输入框改为已启用提供方下拉；顶部“新增模型”改为当前页面上下文动作，连接页显示“新增连接”。

- [ ] **Step 5: 运行目录 API 和浏览器分页验证**

Run: `cd backend && python -m pytest -q tests/test_model_center_repository.py tests/test_model_center_api.py`

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-api-contract.spec.ts e2e/model-center-recovery.spec.ts --project=chromium --workers=1`

Expected: PASS;第 2 页可见，图像/视频筛选总数来自服务端，页面不再展示提供方 UUID。

- [ ] **Step 6: 提交可读目录和分页**

```bash
git add backend/app/features/model_config/catalog.py backend/app/features/model_config/repository.py backend/app/features/model_config/management_repository.py backend/app/features/model_config/api/catalog.py backend/app/features/model_config/api/connections.py backend/app/features/model_config/api/schemas.py frontend/src/features/model-center/components/model-center-pagination.tsx frontend/src/features/model-center/components/provider-model-label.tsx frontend/src/features/model-center/hooks/use-paged-model-catalog.ts frontend/src/features/model-center/components/model-center-catalog-panel.tsx frontend/src/features/model-center/components/model-center-connections-panel.tsx frontend/src/features/model-center/api.ts backend/tests/test_model_center_repository.py backend/tests/test_model_center_api.py frontend/e2e/model-center-api-contract.spec.ts frontend/e2e/model-center-recovery.spec.ts
git commit -m "fix: add readable paged model catalog"
```

### Task 7: 实现提供方和模型档案版本管理

**Files:**
- Create: `backend/app/features/model_config/catalog_management.py`
- Modify: `backend/app/features/model_config/api/catalog.py`
- Modify: `backend/app/features/model_config/api/profiles.py`
- Modify: `backend/app/features/model_config/api/schemas.py`
- Create: `frontend/src/features/model-center/components/provider-profile-editor.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-catalog-panel.tsx`
- Modify: `frontend/src/features/model-center/api.ts`
- Test: `backend/tests/test_model_center_api.py`
- Test: `backend/tests/test_model_center_version_guards.py`
- Test: `frontend/e2e/model-center-recovery.spec.ts`

- [ ] **Step 1: 写草稿、驱动校验和发布失败测试**

```python
async def test_operator_can_create_and_publish_profile_for_installed_driver(client):
    provider = await create_provider(client, code="volcano", family="volcano")
    profile = await create_profile(client, provider_id=provider["id"], name="Seedream 5 Pro")
    version = await create_profile_version(
        client, profile["id"], driver_key="volcano_ark_image",
        api_model_id="doubao-seedream-5-0-pro", capabilities=["image_generation"],
    )
    assert version["status"] == "draft"
    published = await publish_profile_version(client, version["id"], reason="契约验证通过")
    assert published["published_version_id"] == version["id"]


async def test_uninstalled_driver_stays_draft_with_actionable_error(client):
    response = await create_profile_version_response(client, driver_key="unknown-driver")
    assert response.status_code == 422
    assert response.json()["detail"]["action_code"] == "install_or_select_driver"
```

- [ ] **Step 2: 运行确认当前路由返回 501**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py -k 'create_and_publish_profile or uninstalled_driver'`

Expected: FAIL with `operation_not_implemented`.

- [ ] **Step 3: 实现应用服务并保持路由薄**

```python
async def create_profile_versioned(db, *, user_id, command: CreateProfileCommand) -> ProfileVersionResult:
    driver = require_installed_driver(command.driver_key)
    validate_capability_subset(command.capabilities, driver.capabilities)
    async with db.begin():
        profile, version, audit = await persist_profile_draft(db, user_id=user_id, command=command)
    return ProfileVersionResult.from_rows(profile, version, audit)
```

发布前必须存在成功的 contract certification；停用和回滚创建新版本，禁止修改已发布行。

- [ ] **Step 4: 实现分步前端向导**

步骤固定为：选择/新建提供方 → 选择已安装驱动 → 填写模型标识和能力 → 参数/限制 → 保存草稿 → 契约测试 → 发布。普通模式不显示原始 JSON。

- [ ] **Step 5: 运行版本守卫、API和浏览器测试**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py tests/test_model_center_version_guards.py tests/test_model_driver_contract.py`

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-recovery.spec.ts --project=chromium --workers=1`

Expected: PASS;安装驱动可发布，未知驱动不可发布且错误可处理。

- [ ] **Step 6: 提交档案管理闭环**

```bash
git add backend/app/features/model_config/catalog_management.py backend/app/features/model_config/api/catalog.py backend/app/features/model_config/api/profiles.py backend/app/features/model_config/api/schemas.py frontend/src/features/model-center/components/provider-profile-editor.tsx frontend/src/features/model-center/components/model-center-catalog-panel.tsx frontend/src/features/model-center/api.ts backend/tests/test_model_center_api.py backend/tests/test_model_center_version_guards.py frontend/e2e/model-center-recovery.spec.ts
git commit -m "feat: complete model profile management"
```

### Task 8: 实现能力绑定维护和影响预览

**Files:**
- Create: `backend/app/features/model_config/binding_management.py`
- Modify: `backend/app/features/model_config/management_repository.py:100-118`
- Modify: `backend/app/features/model_config/api/bindings.py`
- Modify: `backend/app/features/model_config/api/schemas.py`
- Create: `frontend/src/features/model-center/components/binding-editor.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-management-panel.tsx`
- Modify: `frontend/src/features/model-center/hooks/use-model-bindings.ts`
- Test: `backend/tests/test_model_binding_resolution.py`
- Test: `backend/tests/test_model_center_api.py`
- Test: `frontend/e2e/model-center-recovery.spec.ts`

- [ ] **Step 1: 写绑定创建、兼容校验和返回字段失败测试**

```python
async def test_binding_api_returns_route_policy_and_rejects_provider_mismatch(client, binding_fixture):
    listed = await client.get("/api/v1/model-center/bindings")
    assert listed.json()["items"][0]["route_policy"] == "single"
    response = await client.post("/api/v1/model-center/bindings", json=binding_fixture.mismatched_payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "binding_connection_mismatch"
```

- [ ] **Step 2: 运行确认路由策略缺失且写路由 501**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py -k binding`

Expected: FAIL on missing `route_policy` or operation not implemented.

- [ ] **Step 3: 实现乐观锁和影响保护**

```python
async def update_binding_versioned(db, *, user_id, binding_id, expected_revision, changes, reason):
    candidate = await load_owned_binding(db, user_id=user_id, binding_id=binding_id)
    require_revision(candidate, expected_revision)
    await validate_binding_contract(db, candidate.with_changes(changes))
    impact = await binding_impact(db, user_id=user_id, binding_id=binding_id)
    return await persist_binding_update(db, candidate, changes, reason, impact)
```

列表返回 `priority`, `route_policy`, `fallback_profile_version_ids`, `profile_name`, `api_model_id`, `connection_name`, `provider_name`, `certification_status`, `affected_recipes`。

- [ ] **Step 4: 实现结构化绑定编辑器**

用户先选任务和能力，再从兼容模型版本中选择，连接下拉只显示同提供方且已验证连接。保存前显示受影响组合预设和有效路由预览。

- [ ] **Step 5: 运行绑定和浏览器验证**

Run: `cd backend && python -m pytest -q tests/test_model_binding_resolution.py tests/test_model_center_api.py`

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-recovery.spec.ts --project=chromium --workers=1`

Expected: PASS;页面显示 `single`，不允许不兼容连接，修改后刷新仍保存。

- [ ] **Step 6: 提交绑定维护闭环**

```bash
git add backend/app/features/model_config/binding_management.py backend/app/features/model_config/management_repository.py backend/app/features/model_config/api/bindings.py backend/app/features/model_config/api/schemas.py frontend/src/features/model-center/components/binding-editor.tsx frontend/src/features/model-center/components/model-center-management-panel.tsx frontend/src/features/model-center/hooks/use-model-bindings.ts backend/tests/test_model_binding_resolution.py backend/tests/test_model_center_api.py frontend/e2e/model-center-recovery.spec.ts
git commit -m "feat: complete model binding management"
```

---

## Batch 3 — P1 组合预设、就绪度和测试实验室闭环

### Task 9: 修复组合预设展示并补齐编辑、发布和回滚

**Files:**
- Modify: `backend/app/features/model_config/management.py:73-85,176-190`
- Modify: `backend/app/features/model_config/recipe_management_repository.py`
- Modify: `backend/app/features/model_config/api/recipes.py`
- Create: `frontend/src/features/model-center/components/recipe-detail.tsx`
- Modify: `frontend/src/features/model-center/components/recipe-list.tsx`
- Modify: `frontend/src/features/model-center/components/recipe-editor.tsx`
- Modify: `frontend/src/features/model-center/hooks/use-production-recipes.ts`
- Test: `backend/tests/test_production_recipe_contract.py`
- Test: `backend/tests/test_model_center_api.py`
- Test: `frontend/e2e/model-center-recipes.spec.ts`

- [ ] **Step 1: 写策略展示和前端发布失败测试**

```python
async def test_recipe_list_preserves_safe_strategy_metadata(client, published_recipe):
    response = await client.get("/api/v1/model-center/recipes")
    recipe = response.json()["items"][0]
    assert recipe["strategy"] == "direct_av_first"
    assert recipe["status"] == "published"
    assert "api_key" not in json.dumps(recipe)
```

```typescript
test('creates validates and publishes a recipe from the frontend', async ({ page }) => {
  await page.goto('/llm-config?section=recipes');
  await page.getByRole('button', { name: '新建生产方案' }).click();
  await completeRecipeForm(page);
  await page.getByRole('button', { name: '保存为草稿版本' }).click();
  await page.getByRole('button', { name: '发布方案' }).click();
  await page.getByLabel('发布原因').fill('前端组合验收');
  await page.getByRole('button', { name: '确认发布' }).click();
  await expect(page.getByText('已发布')).toBeVisible();
});
```

- [ ] **Step 2: 运行确认策略显示未声明且前端无发布入口**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py -k recipe_list_preserves`

Run: `cd frontend && npx playwright test e2e/model-center-recipes.spec.ts --project=chromium --workers=1`

Expected: FAIL.

- [ ] **Step 3: 定义明确的安全响应，不再复用阶段脱敏函数**

```python
return {
    "id": row.id,
    "recipe_key": row.recipe_key,
    "name": row.name,
    "version": row.version,
    "status": row.status,
    "strategy": str((row.spec or {}).get("production_strategy") or (row.spec or {}).get("strategy") or ""),
    "stages": safe_recipe_stages(row.spec or {}),
    "revision": row.revision,
}
```

- [ ] **Step 4: 接入已有发布和回滚 Hook**

现有 `publishRecipeVersion()` 和 `rollbackRecipe()` 必须由 `RecipeList/RecipeDetail` 调用；发布前显示校验错误、受影响绑定和发布原因。停用后端尚未实现时，前端不展示停用按钮。

- [ ] **Step 5: 运行组合预设回归**

Run: `cd backend && python -m pytest -q tests/test_production_recipe_contract.py tests/test_model_center_api.py`

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-recipes.spec.ts --project=chromium --workers=1`

Expected: PASS;五个 Legacy 方案显示真实策略，新草稿可从前端发布和回滚。

- [ ] **Step 6: 提交组合预设闭环**

```bash
git add backend/app/features/model_config/management.py backend/app/features/model_config/recipe_management_repository.py backend/app/features/model_config/api/recipes.py frontend/src/features/model-center/components/recipe-detail.tsx frontend/src/features/model-center/components/recipe-list.tsx frontend/src/features/model-center/components/recipe-editor.tsx frontend/src/features/model-center/hooks/use-production-recipes.ts backend/tests/test_production_recipe_contract.py backend/tests/test_model_center_api.py frontend/e2e/model-center-recipes.spec.ts
git commit -m "fix: complete production recipe lifecycle"
```

### Task 10: 建立真实就绪度检查和可搜索测试实验室

**Files:**
- Create: `backend/app/features/model_config/readiness.py`
- Modify: `backend/app/features/model_config/management_repository.py:62-97`
- Modify: `backend/app/features/model_config/certification_repository.py`
- Modify: `backend/app/features/model_config/api/certifications.py`
- Modify: `backend/app/features/model_config/api/schemas.py`
- Create: `frontend/src/features/model-center/components/readiness-checklist.tsx`
- Create: `frontend/src/features/model-center/components/model-version-picker.tsx`
- Create: `frontend/src/features/model-center/hooks/use-certification-history.ts`
- Modify: `frontend/src/features/model-center/components/model-center-overview-panel.tsx`
- Modify: `frontend/src/features/model-center/components/model-center-inspector.tsx`
- Modify: `frontend/src/features/model-center/components/test-lab.tsx`
- Test: `backend/tests/test_model_center_api.py`
- Test: `frontend/e2e/model-center-test-lab.spec.ts`
- Test: `frontend/e2e/model-center-recovery.spec.ts`

- [ ] **Step 1: 写就绪度误报和候选兼容失败测试**

```python
async def test_overview_blocks_uncertified_model_and_missing_prompt(client, production_setup):
    response = await client.get("/api/v1/model-center/overview")
    codes = {item["code"] for item in response.json()["blocking_issues"]}
    assert "model_certification_missing" in codes
    assert "prompt_profile_missing" in codes


async def test_certification_candidates_only_return_compatible_pairs(client, production_setup):
    response = await client.get("/api/v1/model-center/certification-candidates?capability=video_generation&q=seedance")
    assert all(item["profile"]["provider_id"] == item["connection"]["provider_id"] for item in response.json()["items"])
```

- [ ] **Step 2: 运行确认概览只检查连接和组合存在**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py -k 'overview_blocks or certification_candidates'`

Expected: FAIL.

- [ ] **Step 3: 定义完整就绪度规则**

```python
READINESS_CHECKS = (
    check_verified_connection,
    check_published_profile,
    check_active_binding,
    check_prompt_profile_coverage,
    check_published_recipe,
    check_required_certification,
)


async def production_readiness(db, *, user_id: str) -> ReadinessReport:
    issues = []
    for check in READINESS_CHECKS:
        issues.extend(await check(db, user_id=user_id))
    return ReadinessReport(tuple(sorted(issues, key=lambda item: (item.severity, item.code))))
```

每个问题包含 `code`, `message`, `severity`, `section`, `capability`, `resource_id`, `action_label`，前端通过统一 `modelCenterHref()` 生成处理地址。

- [ ] **Step 4: 实现可搜索兼容候选和认证历史**

测试实验室通过 `certification-candidates` 获取模型/连接配对，不再分别加载目录第一页和连接第一页。增加 `GET /certifications?page=&page_size=&level=&status=` 运行历史接口。

- [ ] **Step 5: 前端显示真实检查项并提供快捷处理**

```tsx
<ReadinessChecklist
  issues={overview.blocking_issues}
  hrefFor={(issue) => modelCenterHref({
    section: issue.section,
    capability: issue.capability,
    returnTo: location.returnTo,
    runId: location.runId,
  })}
/>
```

Inspector 不再在所有页面重复显示“没有阻塞项”；它显示当前资源相关问题或最近认证状态。

- [ ] **Step 6: 运行 API、浏览器和无付费认证测试**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py tests/test_model_binding_resolution.py`

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-test-lab.spec.ts e2e/model-center-recovery.spec.ts --project=chromium --workers=1`

Expected: PASS;不兼容配对不出现，认证历史可分页，无真实供应商调用。

- [ ] **Step 7: 提交真实就绪度和测试实验室**

```bash
git add backend/app/features/model_config/readiness.py backend/app/features/model_config/management_repository.py backend/app/features/model_config/certification_repository.py backend/app/features/model_config/api/certifications.py backend/app/features/model_config/api/schemas.py frontend/src/features/model-center/components/readiness-checklist.tsx frontend/src/features/model-center/components/model-version-picker.tsx frontend/src/features/model-center/hooks/use-certification-history.ts frontend/src/features/model-center/components/model-center-overview-panel.tsx frontend/src/features/model-center/components/model-center-inspector.tsx frontend/src/features/model-center/components/test-lab.tsx backend/tests/test_model_center_api.py frontend/e2e/model-center-test-lab.spec.ts frontend/e2e/model-center-recovery.spec.ts
git commit -m "fix: make model center readiness truthful"
```

---

## Batch 4 — 前端闭环、迁移验收和四章回归

### Task 11: 从真实前端完成无费用模型中心和四章确定性验收

**Files:**
- Create: `frontend/e2e/model-center-recovery.spec.ts`
- Modify: `frontend/e2e/model-center-navigation.spec.ts`
- Modify: `frontend/e2e/model-center-prompts.spec.ts`
- Modify: `frontend/e2e/model-center-recipes.spec.ts`
- Modify: `frontend/e2e/model-center-test-lab.spec.ts`
- Modify: `frontend/e2e/four-chapter-series-run.spec.ts`
- Create: `docs/acceptance/model-center-recovery-2026-07-18.md`

**Interfaces:**
- Consumes: Tasks 1-10 全部前后端能力。
- Produces: 可复跑的前端验收证据和实模前置结论。

- [ ] **Step 1: 写覆盖用户症状的浏览器验收**

```typescript
test('sunqy model center recovers prompts and exposes truthful management', async ({ page }) => {
  await loginAsSunqy(page);
  await page.goto('/llm-config?section=prompts');
  await expect(page.getByText(/共 14 个提示词/)).toBeVisible();
  await expect(page.getByLabel('任务模板')).not.toHaveValue('');
  await expect(page.getByRole('button', { name: 'AI 优化' })).toBeVisible();

  await page.goto('/llm-config?section=catalog');
  await expect(page.getByText(/共 220 个模型版本/)).toBeVisible();
  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page).toHaveURL(/page=2/);

  await page.goto('/llm-config?section=bindings');
  await expect(page.getByText('single')).toBeVisible();
  await expect(page.getByRole('button', { name: '编辑绑定' })).toBeVisible();
});
```

测试数据通过隔离 fixture 或只读真实账号验证；不得依赖固定 UUID，按可读名称和业务键定位。

- [ ] **Step 2: 运行完整后端回归**

Run: `cd backend && python -m pytest -q tests/test_model_center_prompt_recovery.py tests/test_prompt_profile_versioning.py tests/test_prompt_skill_routing.py test_prompt_skills.py test_prompt_skill_ai_entrypoints.py tests/test_model_center_api.py tests/test_model_center_repository.py tests/test_model_binding_resolution.py tests/test_production_recipe_contract.py tests/test_model_center_backfill.py tests/test_model_center_shadow_compare.py`

Expected: PASS with zero failures.

- [ ] **Step 3: 运行前端类型、构建和模型中心浏览器回归**

Run: `cd frontend && npm run typecheck && NEXT_DIST_DIR=.next-model-center-recovery npm run build`

Run: `cd frontend && npx playwright test e2e/prompt-skills.spec.ts e2e/model-center-api-contract.spec.ts e2e/model-center-navigation.spec.ts e2e/model-center-prompts.spec.ts e2e/model-center-recipes.spec.ts e2e/model-center-test-lab.spec.ts e2e/model-center-recovery.spec.ts --project=chromium --workers=1`

Expected: PASS with zero failures.

- [ ] **Step 4: 执行真实数据库迁移前检查和备份**

```bash
cd backend
sqlite3 ai_video.db ".backup 'output/ai_video-before-prompt-recovery-20260718.db'"
python scripts/audit_model_center_prompt_links.py --user-id 56ae84de-951f-4e74-ac79-3550d6f6f3b2
python scripts/backfill_model_center.py --check-prompts --user-id 56ae84de-951f-4e74-ac79-3550d6f6f3b2
```

Expected: backup exists; plan reports 14 legacy skills, 14 nonempty bodies, 8 active, 6 inactive, 0 content conflicts.

- [ ] **Step 5: 经决策点确认后执行幂等迁移并复核**

```bash
cd backend
python scripts/backfill_model_center.py \
  --apply-prompts \
  --user-id 56ae84de-951f-4e74-ac79-3550d6f6f3b2 \
  --backup-ack output/ai_video-before-prompt-recovery-20260718.db
python scripts/backfill_model_center.py --check-prompts --user-id 56ae84de-951f-4e74-ac79-3550d6f6f3b2
```

Expected: 14/14 linked, 14/14 content hashes equal, second apply plan contains zero writes.

- [ ] **Step 6: 从真实 Chrome `sunqy` 页面逐项验收**

依次访问：概览 → 连接 → 目录第2页 → 能力绑定 → 组合预设 → 提示词14条及正文 → AI优化建议但不保存 → 测试实验室兼容候选 → 返回工作台。保存每个页面截图和控制台错误摘要。

- [ ] **Step 7: 运行无费用四章确定性回归**

Run: `cd frontend && npx playwright test e2e/four-chapter-series-run.spec.ts --project=chromium --workers=1`

Expected: PASS;四章创建、参考资产、两个关键镜头模拟生成、原生语音策略、字幕策略和一致性评审均使用规范绑定和 Prompt 版本，不调用付费供应商。

- [ ] **Step 8: 编写验收报告**

`docs/acceptance/model-center-recovery-2026-07-18.md` 必须记录：Git SHA、数据库备份路径、迁移前后数量、内容哈希一致性、后端测试结果、前端构建结果、Playwright结果、浏览器截图路径、未执行的付费实模项和剩余风险。不得记录密钥和完整私有 Prompt 正文。

- [ ] **Step 9: 提交验收资产**

```bash
git add frontend/e2e/model-center-recovery.spec.ts frontend/e2e/model-center-navigation.spec.ts frontend/e2e/model-center-prompts.spec.ts frontend/e2e/model-center-recipes.spec.ts frontend/e2e/model-center-test-lab.spec.ts frontend/e2e/four-chapter-series-run.spec.ts docs/acceptance/model-center-recovery-2026-07-18.md
git commit -m "test: verify model center recovery from frontend"
```

---

## Optional Batch 5 — 单独授权后的付费实模验收

该批次不随修复自动执行。取得明确预算、模型、镜头数量、重试策略和存储策略授权后，沿用既有四章实模验收合同：从前端创建四章小说，生成参考资产，选择两个关键镜头，使用当前默认图像/视频模型和指定声音策略，输出七牛公网地址、字幕、音视频同步和多维一致性证据。任何付费失败不自动重试，不自动切换供应商。

---

## Rollback Strategy

- 代码回滚：每个 Task 独立提交，可按批次回退；兼容旧路由始终保留。
- Prompt 数据回滚：恢复迁移前 SQLite 备份；PostgreSQL 环境通过恢复备份和切换 `MODEL_CENTER_READ_MODE=legacy` 回退。
- 发布回滚：已发布 Prompt、模型档案和组合预设不原地修改；复制目标历史版本为新头版本。
- 前端回滚：`/prompt-skills` 和 `/production-adapters` 兼容入口仍存在，可临时指向兼容面板，但不得恢复双写。
- 付费任务：已受理任务不删除、不重提，只轮询或人工核对。

## Planned Commit Sequence

1. `test: characterize model center prompt recovery`
2. `fix: unify legacy prompt profile links`
3. `fix: resolve prompts through one canonical path`
4. `feat: restore prompt detail and assistance api`
5. `fix: restore complete prompt management workbench`
6. `fix: add readable paged model catalog`
7. `feat: complete model profile management`
8. `feat: complete model binding management`
9. `fix: complete production recipe lifecycle`
10. `fix: make model center readiness truthful`
11. `test: verify model center recovery from frontend`

## Completion Checklist

- [ ] 14 条旧提示词全部可见、正文非空、状态正确、内容哈希一致。
- [ ] 14 个 PromptSkill 全部链接到规范版本，迁移二次执行零写入。
- [ ] 所有生产 Prompt 入口解析相同规范版本并持久化版本 ID。
- [ ] AI优化、预览、变量说明和旧入口能力在模型中心可用。
- [ ] 模型目录220条均可分页访问，能力筛选在服务端执行。
- [ ] 提供方和模型名称可读，普通用户不需要填写 UUID。
- [ ] 提供方、档案、绑定和组合预设的前端动作与后端能力一致。
- [ ] 概览和 Inspector 不再误报“没有阻塞项”。
- [ ] 测试实验室候选兼容、可搜索、可查看历史，不局限第一页。
- [ ] 后端目标测试、前端 typecheck/build 和 Playwright 均通过。
- [ ] 真实 Chrome `sunqy` 验收完成并保存截图。
- [ ] 付费实模未在无授权情况下执行。
