# Web 创作工作台、Agent 返修与 Prompt 技能实施计划

> **给执行 Agent 的要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行本计划。任务使用 checkbox（`- [ ]`）语法跟踪进度。

**目标：** 在保留当前 Web 平台底座的前提下，建设统一创作工作台、Agent 监督返修闭环和可版本化 Prompt 技能配置，让个人和小团队能低门槛完成从小说到短剧/漫剧出片的全流程验证与生产。

**架构：** 保留 FastAPI、SQLAlchemy、Next.js 和现有生产控制服务。后端新增薄聚合层、模式策略层和可执行修复动作层；前端新增 `/studio` 创作工作台，避免继续膨胀现有 `/producer` 和 `/workflow` 页面。Prompt 技能只作为受控、可版本化的文本模板配置层，不执行用户编写的代码。

**技术栈：** FastAPI、async SQLAlchemy、SQLite/PostgreSQL 兼容模型、Pydantic、pytest、Next.js 14、React 18、TypeScript、Tailwind CSS、Playwright。

---

## 一、前提和成功标准

- 产品继续走 Web 平台路线，服务个人创作者和小团队；不切换到 Electron，不开放在线执行供应商脚本。
- 现有模块继续作为权威数据来源：`Workflow`、`StoryBible`、`StoryEntity`、`Asset`、`MediaGenerationJob`、`Timeline`、`production_control`、`consistency_preflight`、`prompt_composer`。
- 第一版可用目标不是重做无限画布，而是先做一个统一工作台，减少页面跳转，让用户知道下一步该做什么。
- 测试验证模式允许用户在明确确认并填写原因后临时跳过部分阻断项。
- 生产出片模式必须强制执行阻断限制，并给出明确原因、影响、修复路径和快捷操作入口。
- 每个稳定任务组完成后都要运行对应验证命令，并及时提交，方便后续回退。

## 二、测试模式和生产模式策略

前后端共用下面的模式语义：

```ts
type StudioRunMode = 'test' | 'production';

type StudioBypassPolicy = {
  mode: StudioRunMode;
  allow_test_bypass: boolean;
  bypass_reason?: string;
};
```

后端行为：

- `production`：阻断项仍然阻断；缺少强制条件时，生成或修复执行返回 `422`。
- `test`：只有当 `allow_test_bypass=true` 且 `bypass_reason` 至少 8 个字符时，阻断项才可降级为 `confirmable`。
- 每次跳过都要写入 review run 或 action result 的审计信息。
- Snapshot 查询不能调用付费模型，也不能修改数据。

前端行为：

- 工作台顶部必须显示模式切换：`测试验证模式` / `生产出片模式`。
- 测试模式显示固定提示：`测试验证模式允许临时跳过部分限制，产物不能视为最终出片。`
- 生产模式显示固定提示：`生产出片模式会强制执行资产锁、模型验证、公开素材地址和一致性要求。`
- 每个问题卡片必须给出具体修复入口，例如：`补齐实体引用`、`应用资产锁`、`配置模型`、`上传公网参考图`、`刷新生产合约`、`重新生成镜头`。

## 三、文件结构规划

后端新增或修改：

- 新建 `backend/app/models/studio_review.py`：持久化检查记录、修复动作和跳过审计。
- 新建 `backend/app/models/prompt_skill.py`：可版本化 Prompt 技能配置。
- 修改 `backend/app/models/__init__.py`：导出新增模型。
- 修改 `backend/init_db.py`：确保新表被创建。
- 新建 `backend/app/services/studio_mode.py`：测试/生产模式策略和问题降级逻辑。
- 新建 `backend/app/services/studio_snapshot.py`：只读聚合工作台快照。
- 新建 `backend/app/services/studio_actions.py`：把现有建议和问题标准化为可执行修复动作。
- 新建 `backend/app/services/prompt_skill_service.py`：Prompt 技能解析、验证、渲染、预览、激活、克隆。
- 修改 `backend/app/services/prompt_composer.py`：支持注入 Prompt 技能渲染结果。
- 新建 `backend/app/api/v1/endpoints/studio.py`：工作台快照、检查记录、动作执行接口。
- 新建 `backend/app/api/v1/endpoints/prompt_skills.py`：Prompt 技能 CRUD、预览、激活、克隆接口。
- 修改 `backend/app/api/v1/router.py`：注册 `/studio` 和 `/prompt-skills`。

前端新增或修改：

- 新建 `frontend/src/app/studio/page.tsx`：统一创作工作台页面。
- 新建 `frontend/src/components/studio/studio-shell.tsx`：工作台布局和模式状态。
- 新建 `frontend/src/components/studio/studio-context-panel.tsx`：小说、章节、工作流、Story Bible 摘要。
- 新建 `frontend/src/components/studio/studio-production-board.tsx`：镜头、资产、任务、时间线就绪度。
- 新建 `frontend/src/components/studio/studio-agent-panel.tsx`：问题、下一步建议、修复快捷入口、跳过确认。
- 新建 `frontend/src/components/studio/studio-mode-banner.tsx`：模式说明和风险提示。
- 新建 `frontend/src/components/studio/studio-issue-card.tsx`：问题文本、严重程度、修复路径、快捷操作。
- 新建 `frontend/src/components/studio/prompt-skill-panel.tsx`：Prompt 技能预览和当前激活版本摘要。
- 新建 `frontend/src/app/prompt-skills/page.tsx`：Prompt 技能管理页面。
- 新建 `frontend/src/lib/studio-types.ts`：工作台 DTO 类型。
- 新建 `frontend/src/lib/studio-mode.ts`：模式文案和确认辅助逻辑。
- 修改 `frontend/src/lib/api-client.ts`：增加 `studio` 和 `prompt-skills` 方法。
- 修改 `frontend/src/components/layout/top-navigation.tsx`：增加 `创作工作台` 和 `Prompt 技能` 导航。

测试文件：

- 新建 `backend/test_studio_mode.py`。
- 新建 `backend/test_studio_snapshot.py`。
- 新建 `backend/test_studio_actions.py`。
- 新建 `backend/test_prompt_skills.py`。
- 新建 `backend/test_prompt_skill_prompt_composer.py`。
- 新建 `frontend/e2e/studio-workspace.spec.ts`。
- 新建 `frontend/e2e/studio-mode-gates.spec.ts`。
- 新建 `frontend/e2e/prompt-skills.spec.ts`。
- 新建 `frontend/e2e/studio-full-flow.spec.ts`。

## 四、分支和提交策略

- 执行时创建分支：`codex/web-studio-agent-prompt-skills`。
- 不回退当前工作区已有改动；每次编辑前检查相关文件，确保只改当前任务需要的内容。
- 每个任务组验证通过后提交一次。
- 建议提交点：
  - `feat: add studio mode policy and snapshot api`
  - `feat: add web studio workspace`
  - `feat: add studio repair action flow`
  - `feat: add prompt skill configuration api`
  - `feat: add prompt skill management ui`
  - `test: cover studio full flow gates`

## 五、第一阶段：统一创作工作台

### 任务 1.1：新增工作台模式策略

**文件：**

- 新建：`backend/app/services/studio_mode.py`
- 测试：`backend/test_studio_mode.py`

- [ ] 编写测试，覆盖生产模式阻断、测试模式确认跳过、缺少跳过原因时拒绝、warning 保持 warning。
- [ ] 实现 `StudioModePolicy`、`StudioIssue` 和 `apply_mode_policy`。

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class StudioModePolicy:
    mode: str = "production"
    allow_test_bypass: bool = False
    bypass_reason: Optional[str] = None

def apply_mode_policy(issues: List[Dict[str, Any]], policy: StudioModePolicy) -> Dict[str, Any]:
    normalized = []
    bypassed = []
    for issue in issues:
        item = dict(issue)
        is_blocking = item.get("severity") in {"blocking", "error"}
        if policy.mode == "test" and is_blocking and policy.allow_test_bypass:
            if not policy.bypass_reason or len(policy.bypass_reason.strip()) < 8:
                item["severity"] = "blocking"
                item["bypass_error"] = "测试模式跳过需要填写至少 8 个字符的原因"
            else:
                item["original_severity"] = item.get("severity")
                item["severity"] = "confirmable"
                item["bypassed"] = True
                bypassed.append(item)
        normalized.append(item)
    blocking = [item for item in normalized if item.get("severity") in {"blocking", "error"}]
    return {
        "mode": policy.mode,
        "ready": len(blocking) == 0,
        "issues": normalized,
        "blocking_issue_count": len(blocking),
        "bypassed_issue_count": len(bypassed),
        "bypass_audit": {"reason": policy.bypass_reason, "count": len(bypassed)} if bypassed else None,
    }
```

- [ ] 运行：`cd backend && pytest test_studio_mode.py -q`
- [ ] 预期：全部通过。
- [ ] 提交：`feat: add studio mode policy`

### 任务 1.2：新增只读工作台快照接口

**文件：**

- 新建：`backend/app/services/studio_snapshot.py`
- 新建：`backend/app/api/v1/endpoints/studio.py`
- 修改：`backend/app/api/v1/router.py`
- 测试：`backend/test_studio_snapshot.py`

- [ ] 编写测试，覆盖一个包含小说、Story Bible、镜头、资产锁、媒体任务、时间线元数据的工作流。
- [ ] 实现 `build_studio_snapshot(db, user_id, workflow_id, mode_policy)`。
- [ ] 返回字段包含：

```json
{
  "workflow": {},
  "story_context": {},
  "story_bible": {},
  "state_machine": {},
  "production": {},
  "shots": [],
  "assets": {},
  "jobs": {},
  "timeline": {},
  "issues": [],
  "actions": [],
  "mode_policy": {}
}
```

- [ ] 快照查询要限制数量：最多 80 个镜头、100 个资产、100 个媒体任务、最新时间线。
- [ ] 快照接口不能调用外部 AI 服务。
- [ ] 新增接口：`GET /api/v1/studio/workflows/{workflow_id}/snapshot`。
- [ ] 运行：`cd backend && pytest test_studio_snapshot.py test_production_control.py test_consistency_context.py -q`
- [ ] 预期：全部通过。
- [ ] 提交：`feat: add studio snapshot api`

### 任务 1.3：新增前端工作台外壳

**文件：**

- 新建：`frontend/src/app/studio/page.tsx`
- 新建：`frontend/src/components/studio/studio-shell.tsx`
- 新建：`frontend/src/components/studio/studio-mode-banner.tsx`
- 新建：`frontend/src/lib/studio-types.ts`
- 新建：`frontend/src/lib/studio-mode.ts`
- 修改：`frontend/src/lib/api-client.ts`
- 修改：`frontend/src/components/layout/top-navigation.tsx`
- 测试：`frontend/e2e/studio-workspace.spec.ts`

- [ ] 在 API Client 中新增：

```ts
async getStudioSnapshot(workflowId: string, params: {
  mode?: 'test' | 'production';
  allow_test_bypass?: boolean;
  bypass_reason?: string;
} = {}) {
  const searchParams = new URLSearchParams();
  if (params.mode) searchParams.set('mode', params.mode);
  if (params.allow_test_bypass !== undefined) searchParams.set('allow_test_bypass', String(params.allow_test_bypass));
  if (params.bypass_reason) searchParams.set('bypass_reason', params.bypass_reason);
  const qs = searchParams.toString();
  return this.request<any>(`/studio/workflows/${workflowId}/snapshot${qs ? `?${qs}` : ''}`);
}
```

- [ ] 页面结构使用工作型布局：顶部工作流选择、明显的模式切换、上下文面板、生产看板、Agent 面板。
- [ ] 不做营销落地页，不使用大 Hero。
- [ ] 空状态要给出明确下一步：创建工作流、导入小说、选择章节、生成 Story Bible。
- [ ] 运行：`cd frontend && npm run build`
- [ ] 运行：`cd frontend && npx playwright test e2e/studio-workspace.spec.ts`
- [ ] 预期：构建成功，桌面和移动宽度下页面都能正常渲染。
- [ ] 提交：`feat: add web studio workspace shell`

### 任务 1.4：新增生产看板

**文件：**

- 新建：`frontend/src/components/studio/studio-context-panel.tsx`
- 新建：`frontend/src/components/studio/studio-production-board.tsx`
- 新建：`frontend/src/components/studio/studio-issue-card.tsx`
- 测试：`frontend/e2e/studio-workspace.spec.ts`

- [ ] 展示工作流链路：小说、章节、剧本、分镜、镜头、媒体、时间线。
- [ ] 展示就绪指标：实体覆盖率、Story Bible 状态、资产锁覆盖率、模型验证、媒体可用性、字幕可用性、时间线就绪度。
- [ ] 每个问题展示原因、严重程度、影响和修复快捷入口。
- [ ] UI 要适合快速扫读：紧凑卡片、表格、徽标和明确按钮。
- [ ] 运行：`cd frontend && npm run build`
- [ ] 运行：`cd frontend && npx playwright test e2e/studio-workspace.spec.ts`
- [ ] 预期：核心指标和修复入口可见。
- [ ] 提交：`feat: add studio production board`

## 六、第二阶段：Agent 监督返修闭环

### 任务 2.1：新增检查记录和修复动作模型

**文件：**

- 新建：`backend/app/models/studio_review.py`
- 修改：`backend/app/models/__init__.py`
- 修改：`backend/init_db.py`
- 测试：`backend/test_studio_actions.py`

- [ ] 新增 `StudioReviewRun`，字段包含 `workflow_id`、`mode`、`summary`、`issues`、`actions`、`bypass_audit`、`status`。
- [ ] 新增 `StudioRepairAction`，字段包含 `run_id`、`workflow_id`、`code`、`label`、`severity`、`status`、`input_payload`、`result_payload`、`requires_confirmation`、`created_at`、`executed_at`。
- [ ] 测试能按 `user_id` 和 `workflow_id` 创建与查询记录。
- [ ] 运行：`cd backend && pytest test_studio_actions.py -q`
- [ ] 预期：全部通过。
- [ ] 提交：`feat: add studio review action models`

### 任务 2.2：将现有检查标准化为修复动作

**文件：**

- 新建：`backend/app/services/studio_actions.py`
- 修改：`backend/app/services/studio_snapshot.py`
- 测试：`backend/test_studio_actions.py`

- [ ] 将现有问题码映射为修复动作：

```python
ACTION_MAP = {
    "missing_entity_refs": {"code": "fill_entity_refs", "label": "AI 补齐实体引用", "risk": "safe"},
    "missing_asset_locks": {"code": "apply_asset_locks", "label": "应用资产锁", "risk": "safe"},
    "model_unverified": {"code": "open_model_config", "label": "去验证模型配置", "risk": "navigation"},
    "model_api_key_missing": {"code": "open_model_config", "label": "去配置 API Key", "risk": "navigation"},
    "reference_image_not_public": {"code": "open_asset_upload", "label": "上传公网参考图", "risk": "navigation"},
    "shot_quality_blocker": {"code": "open_shot_editor", "label": "编辑镜头信息", "risk": "navigation"},
    "missing_media_file": {"code": "rerun_media_generation", "label": "重新生成缺失媒体", "risk": "confirm"},
}
```

- [ ] safe 动作可从工作台直接执行。
- [ ] navigation 动作返回 `href`。
- [ ] confirm 动作必须用户确认；生产模式下若预检仍阻断则不能执行。
- [ ] 运行：`cd backend && pytest test_studio_actions.py test_production_control.py -q`
- [ ] 预期：动作映射和既有生产控制测试均通过。
- [ ] 提交：`feat: normalize studio repair actions`

### 任务 2.3：新增检查和动作执行接口

**文件：**

- 修改：`backend/app/api/v1/endpoints/studio.py`
- 测试：`backend/test_studio_actions.py`

- [ ] 新增 `POST /api/v1/studio/workflows/{workflow_id}/review`。
- [ ] 新增 `POST /api/v1/studio/workflows/{workflow_id}/actions/{action_code}/execute`。
- [ ] 新增 `GET /api/v1/studio/workflows/{workflow_id}/review-runs`。
- [ ] 第一版只执行这些安全动作：`apply_asset_locks`、`refresh_contracts`、`quality_check`、`media_audit`。
- [ ] 生产模式下，如果动作会跳过必需输入，返回 `422`。
- [ ] 测试模式下，确认后返回 `confirmable` 并写入跳过审计。
- [ ] 运行：`cd backend && pytest test_studio_actions.py test_workflow_routes.py test_short_video_production.py -q`
- [ ] 预期：全部通过。
- [ ] 提交：`feat: add studio review execution api`

### 任务 2.4：新增 Agent 面板和跳过确认体验

**文件：**

- 新建：`frontend/src/components/studio/studio-agent-panel.tsx`
- 修改：`frontend/src/components/studio/studio-shell.tsx`
- 修改：`frontend/src/lib/api-client.ts`
- 测试：`frontend/e2e/studio-mode-gates.spec.ts`

- [ ] 顶部展示下一步推荐动作。
- [ ] 每个问题卡片包含：问题、影响、修复路径、主操作、辅助导航入口。
- [ ] 测试模式跳过按钮文案：`确认临时跳过并继续验证`。
- [ ] 跳过弹窗必须填写原因，并显示：`此操作只用于测试验证，生产出片仍需修复该问题。`
- [ ] 生产模式禁用跳过，只显示必须执行的修复动作。
- [ ] 运行：`cd frontend && npm run build`
- [ ] 运行：`cd frontend && npx playwright test e2e/studio-mode-gates.spec.ts`
- [ ] 预期：测试模式可填写原因后确认跳过；生产模式不能跳过。
- [ ] 提交：`feat: add studio agent repair panel`

### 任务 2.5：个人和小团队全流程验证

**文件：**

- 新建：`frontend/e2e/studio-full-flow.spec.ts`
- 如路由文案变化，修改：`frontend/e2e/workflow-production-guidance.spec.ts`

- [ ] 编写快速创作流程：登录、创建或选择工作流、打开工作台、运行检查、应用资产锁、运行质量检查、跳转到缺失项修复入口。
- [ ] 编写测试验证流程：开启测试模式、填写原因确认跳过、验证 review 结果中有审计记录。
- [ ] 编写生产流程：开启生产模式、验证阻断项会阻止不安全执行，并显示修复按钮。
- [ ] 运行后端聚焦测试：

```bash
cd backend
pytest test_studio_mode.py test_studio_snapshot.py test_studio_actions.py test_production_control.py test_consistency_checker.py test_short_video_production.py -q
```

- [ ] 运行前端检查：

```bash
cd frontend
npm run build
npx playwright test e2e/studio-workspace.spec.ts e2e/studio-mode-gates.spec.ts e2e/studio-full-flow.spec.ts
```

- [ ] 预期：全部通过。
- [ ] 提交：`test: cover studio review full flow`

## 七、第三阶段：Prompt 技能配置

### 任务 3.1：新增 Prompt 技能模型和内置数据

**文件：**

- 新建：`backend/app/models/prompt_skill.py`
- 修改：`backend/app/models/__init__.py`
- 修改：`backend/init_db.py`
- 新建：`backend/app/services/prompt_skill_service.py`
- 测试：`backend/test_prompt_skills.py`

- [ ] 新增 `PromptSkill`，字段包含：`id`、`user_id`、`name`、`task_type`、`version`、`status`、`system_prompt`、`user_prompt_template`、`variables_schema`、`model_constraints`、`is_builtin`、`is_active`、`test_status`、`last_test_result`、`created_at`、`updated_at`。
- [ ] 内置技能包含：`script_generation`、`storyboard_generation`、`shot_video`、`tts_dialogue`、`consistency_review`、`repair_suggestion`。
- [ ] 同一 `user_id` 和 `task_type` 只能有一个激活技能。
- [ ] 运行：`cd backend && pytest test_prompt_skills.py -q`
- [ ] 预期：模型创建、内置数据、克隆、激活、唯一性测试均通过。
- [ ] 提交：`feat: add prompt skill model`

### 任务 3.2：新增 Prompt 技能 API

**文件：**

- 新建：`backend/app/api/v1/endpoints/prompt_skills.py`
- 修改：`backend/app/api/v1/router.py`
- 测试：`backend/test_prompt_skills.py`

- [ ] 新增接口：
  - `GET /api/v1/prompt-skills`
  - `POST /api/v1/prompt-skills`
  - `GET /api/v1/prompt-skills/{skill_id}`
  - `PUT /api/v1/prompt-skills/{skill_id}`
  - `POST /api/v1/prompt-skills/{skill_id}/clone`
  - `POST /api/v1/prompt-skills/{skill_id}/activate`
  - `POST /api/v1/prompt-skills/{skill_id}/preview`
- [ ] 内置技能只允许克隆，不允许直接编辑。
- [ ] 预览接口返回最终渲染 prompt 和缺失变量，不调用 AI 服务。
- [ ] 运行：`cd backend && pytest test_prompt_skills.py -q`
- [ ] 预期：API 测试通过。
- [ ] 提交：`feat: add prompt skill api`

### 任务 3.3：将 Prompt 技能接入 Prompt 组合

**文件：**

- 修改：`backend/app/services/prompt_composer.py`
- 修改：`backend/app/services/consistency_context.py`
- 测试：`backend/test_prompt_skill_prompt_composer.py`

- [ ] 生成 prompt 前，根据 `user_id` 和任务类型解析当前激活技能。
- [ ] 从现有上下文渲染技能变量：Story Bible、状态机、资产锁、镜头字段、模型路由、用户 prompt。
- [ ] 没有激活技能时继续使用确定性的默认 prompt。
- [ ] 生成元数据写入 `prompt_skill_id` 和 `prompt_skill_version`。
- [ ] 运行：`cd backend && pytest test_prompt_skill_prompt_composer.py test_prompt_composer_locked_assets.py test_consistency_context.py -q`
- [ ] 预期：prompt 输出包含激活技能内容，并保留现有资产锁约束。
- [ ] 提交：`feat: use prompt skills in generation prompts`

### 任务 3.4：新增 Prompt 技能管理界面

**文件：**

- 新建：`frontend/src/app/prompt-skills/page.tsx`
- 新建：`frontend/src/components/studio/prompt-skill-panel.tsx`
- 修改：`frontend/src/lib/api-client.ts`
- 修改：`frontend/src/components/layout/top-navigation.tsx`
- 测试：`frontend/e2e/prompt-skills.spec.ts`

- [ ] 按任务类型展示技能。
- [ ] 支持从内置技能克隆、编辑克隆技能、预览变量、激活版本、通过激活旧克隆完成回滚。
- [ ] 在 `/studio` 显示当前激活技能摘要。
- [ ] 显示明确提示：`Prompt 技能会影响生成质量。修改后建议先用测试验证模式跑完整流程。`
- [ ] 运行：`cd frontend && npm run build`
- [ ] 运行：`cd frontend && npx playwright test e2e/prompt-skills.spec.ts`
- [ ] 预期：用户可以克隆、编辑、预览、激活，并在工作台看到当前激活版本。
- [ ] 提交：`feat: add prompt skill management ui`

### 任务 3.5：完整回归和候选版本

**文件：**

- 只有选择器或文案变化时才修改测试。
- 不提交生成的媒体文件。

- [ ] 运行后端回归：

```bash
cd backend
pytest test_studio_mode.py test_studio_snapshot.py test_studio_actions.py test_prompt_skills.py test_prompt_skill_prompt_composer.py test_production_control.py test_consistency_checker.py test_workflow_routes.py test_short_video_production.py test_story_state_machine.py -q
```

- [ ] 运行前端构建：

```bash
cd frontend
npm run build
```

- [ ] 运行聚焦 e2e：

```bash
cd frontend
npx playwright test e2e/studio-workspace.spec.ts e2e/studio-mode-gates.spec.ts e2e/studio-full-flow.spec.ts e2e/prompt-skills.spec.ts e2e/workflow-production-guidance.spec.ts
```

- [ ] 运行本地手工冒烟测试：
  - 打开 `http://localhost:3000/studio`。
  - 选择一个工作流。
  - 执行 `制片检查`。
  - 执行一个安全修复动作。
  - 切换到测试模式，填写原因并确认一次跳过。
  - 切换到生产模式，验证同一问题被阻断。
  - 打开 `Prompt 技能`，克隆一个技能，预览，激活，并确认 `/studio` 显示激活版本。
- [ ] 提交：`test: validate studio prompt skill release candidate`

## 八、低门槛创作体验要求

- 第一屏必须是实际工作台，不是落地页。
- 主操作始终是下一步安全动作：`开始检查`、`执行下一步`、`补齐实体引用`、`应用资产锁`、`去配置模型`、`生成预览`。
- 高级配置收进清晰面板里；默认用户应能通过导入/选择内容和下一步按钮完成流程。
- 每个阻断消息都要回答：
  - 缺了什么。
  - 为什么会阻断或带来风险。
  - 点击哪个按钮修复。
  - 测试模式是否能临时跳过。
- 小团队协作要能看到 review 历史：谁运行了检查、执行了哪些动作、哪些问题被跳过。

## 九、风险控制

- 范围风险：第一阶段只做只读快照和统一工作台，不做无限画布。
- 回归风险：第三阶段集成测试通过前，不改现有生成端点行为。
- 成本风险：快照和 Prompt 预览不调用付费服务；Agent 检查优先使用规则和已有检查器。
- 安全风险：Prompt 技能只是文本模板，不执行用户编写的 TypeScript 或 Python。
- 数据风险：新表都是增量表；现有 workflow、asset、shot、job 数据继续有效。
- 跳过风险：跳过只允许测试模式，必须填写原因，必须审计，不能标记为生产就绪。
- 体验风险：生产限制必须附带修复入口，不能只给错误字符串。
- 脏工作区风险：每次提交前运行 `git status --short`，只 stage 当前任务相关文件。

## 十、自检结果

- 需求覆盖：第一阶段覆盖统一工作台，第二阶段覆盖 Agent 检查和返修，第三阶段覆盖 Prompt 技能配置；同时覆盖测试/生产模式、全面测试、明确修复路径和稳定提交点。
- 占位扫描：文档没有开放式占位项；文件、接口、字段、命令和验收结果均已明确。
- 类型一致性：全篇统一使用 `StudioRunMode`、`StudioModePolicy`、`StudioReviewRun`、`StudioRepairAction`、`PromptSkill` 等命名。
