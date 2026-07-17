# AI 模型平台配置化与 Prompt 自适应实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持当前四章小说动漫生产流程、已有配置 ID、API 合同和付费安全门禁不变的前提下，把文本、视觉、图像、声音、视频、字幕、渲染与存储能力收敛为可从前端配置、测试、发布、组合、版本化和回滚的统一 AI 模型平台。

**Architecture:** 采用“统一业务能力契约 + 版本化模型档案 + 供应商协议驱动 + 生产方案绑定 + 不可变执行快照”。模型 ID、端点、能力、限制、参数 Schema、价格、默认绑定、Prompt Profile 和生产方案进入持久化配置；认证签名、SDK、异步轮询、安全解析、加解密和预算门禁继续由经过审核的驱动代码拥有。现有 `LLMProvider/LLMModel/LLMConfig`、`ExternalAPIProvider/ExternalAPIConfig` 和旧 API 先通过兼容门面接入新读模型，不做一次性替换。

**Tech Stack:** FastAPI、Pydantic、async SQLAlchemy、SQLite/PostgreSQL、Next.js 14、React 18、TypeScript、Tailwind CSS、Playwright、pytest。

## Global Constraints

- 保留 `/api/v1/llm/*`、`/api/v1/external/*`、`/api/v1/prompt-skills/*` 的响应兼容；新增字段只能增量添加。
- 保留当前 `sunqy` 模型配置、七牛连接、默认模型和历史任务 ID；迁移脚本不得删除、覆盖或重新加密真实数据，除非先通过只读预检并显式执行。
- 当前四章小说、两个关键镜头、原生音频视频、独立 TTS、字幕、合成和七牛交付链路在每一批结束时都必须保持确定性回归通过。
- 未知模型、未知驱动、缺少执行契约或不兼容组合必须 fail closed；目录可见不等于生产可用。
- 配置测试和正式调用必须复用同一驱动、同一请求构建器和同一响应解析器。
- 任何付费图像、TTS、视频调用不得自动重试或自动切换供应商；已受理和状态不明任务只允许轮询或人工核对。
- API Key、API Secret、签名密钥和 Schema 标记为 secret 的字段必须加密保存、掩码返回、禁止进入日志、Prompt、错误和执行快照。
- 生产模式缺少稳定 `FERNET_KEY` 时必须拒绝启动；开发模式仍可给出明确警告。
- 新数据只允许使用规范能力 ID：`text_generation`、`vision_analysis`、`image_generation`、`speech_generation`、`video_generation`、`subtitle_generation`、`media_render`、`object_storage`。
- 旧值 `text-to-video`、`text_to_video`、`video-generation`、`tts`、`audio` 等只能通过一个兼容别名模块归一化，不能在新业务代码中继续扩散。
- 每次生成必须持久化模型档案版本、连接 ID、绑定版本、生产方案版本、Prompt Profile 版本、执行契约版本和脱敏参数哈希。
- 内置目录只作为首次安装种子；产品运行时不得在列表接口中用 Python 常量覆盖用户已持久化的修改。
- 普通用户界面不得要求编辑原始 JSON；高级 JSON 仅供专家模式查看和导入，保存前必须经过服务端 Schema 校验。
- 继续执行仓库代码健康棘轮：新 Python/TypeScript 文件目标不超过 300 行、上限 500 行；FastAPI 路由方法不超过 60 行；React route page 不超过 300 行；React feature component 不超过 200 行。
- 所有数据库测试使用隔离数据库；真实 `backend/ai_video.db` 只允许只读诊断和经批准的迁移执行。
- 实模测试必须单独获得费用授权；本计划的确定性测试、浏览器测试和迁移预检不得产生供应商费用。

---

## Execution Contract

### Intent Lock

把“新增或切换模型需要多处改代码”收敛为“同协议模型通过界面配置即可发布；新协议只新增一个驱动及其一致性测试”。

### Scope Boundaries

- 本计划不重写小说、Story Bible、资产、分镜、任务中心或渲染业务。
- 本计划不移除旧表、旧路由或旧页面，直到新旧读模型对比和四章回归全部通过。
- 本计划不实现自动选择最便宜模型、自动跨供应商付费降级或后台自动付费重试。
- 本计划不允许从界面上传或执行任意 Python/JavaScript 适配代码。
- 本计划不顺带清理与模型平台无关的遗留文件和运行产物。

### Acceptance Criteria

1. 使用已有驱动新增模型版本时，只需前端填写档案、测试、发布，不修改生产流程代码。
2. 新协议只需实现 `CapabilityDriver` 和标准一致性测试，小说、工作流、资产和镜头模块不增加供应商分支。
3. 用户可以按全局、项目、系列范围绑定文本、图像、视频、声音、字幕、渲染和存储能力。
4. 用户可以保存并发布两类声音方案：`video_native_audio` 与 `separate_tts`。
5. Prompt Profile 可同时发布任务通用、供应商、模型家族和精确模型版本，历史版本不可变且可回滚。
6. 修改模型、连接、Prompt 或方案后，已提交任务继续使用原执行快照。
7. 旧 `/llm-config`、`/production-adapters`、`/prompt-skills` 地址仍可进入对应的新工作区并保留返回上下文。
8. 当前 `sunqy` 四个默认能力和七牛连接迁移后保持同一业务含义，不产生重复默认项。
9. 产品目录不再返回 `deterministic-acceptance`、`contract-*`、`preflight-*` 或其他内部测试记录。
10. 确定性后端测试、前端 typecheck、生产构建和浏览器验收均通过后，才允许申请新的四章实模费用授权。

### Verification Commands

```bash
cd backend
python -m pytest -q \
  test_text_model_config.py \
  test_production_adapters.py \
  test_prompt_skills.py \
  tests/test_model_center_domain.py \
  tests/test_model_center_migrations.py \
  tests/test_model_driver_contract.py \
  tests/test_model_binding_resolution.py \
  tests/test_production_recipe_contract.py \
  tests/test_prompt_profile_versioning.py \
  tests/test_model_execution_snapshot.py \
  tests/test_model_center_api.py \
  tests/test_workflow_media_public_contract.py

cd ../frontend
npm run typecheck
NEXT_DIST_DIR=.next-model-center npm run build
npx playwright test \
  e2e/model-center-api-contract.spec.ts \
  e2e/model-center-navigation.spec.ts \
  e2e/model-center-connections.spec.ts \
  e2e/model-center-recipes.spec.ts \
  e2e/model-center-prompts.spec.ts \
  e2e/model-center-test-lab.spec.ts \
  e2e/model-center-four-chapter-workflow.spec.ts \
  e2e/four-chapter-series-run.spec.ts \
  --project=chromium --workers=1
```

### Decision Points

- Batch 1 完成后检查密钥兼容和产品目录，不进入 schema 迁移前必须确认没有真实配置被改写。
- Batch 2 完成后检查新旧读模型差异；差异非零时不得切换任何生产读取。
- Batch 3 完成后检查当前四种实模驱动的请求合同；配置测试与正式调用不一致时不得继续。
- Batch 6 的确定性验收完成后，再单独申请新一轮四章实模费用授权。
- 删除旧常量、旧表或旧页面属于后续独立计划，不在本计划内执行。

---

## Target File Structure

### Backend model configuration ownership

```text
backend/app/features/model_config/
├── __init__.py
├── public.py                         # 其它 feature 唯一允许导入的公开门面
├── domain.py                         # 规范能力、状态、作用域和不可变值对象
├── schemas.py                        # 应用层 command/result，不含 FastAPI
├── repository.py                     # 新表与旧表兼容读取
├── catalog.py                        # 目录、版本、发布与可见性
├── connections.py                    # 连接、密钥引用、掩码和测试新鲜度
├── bindings.py                       # 作用域优先级和任务绑定解析
├── recipes.py                        # 动漫生产方案校验和版本发布
├── certifications.py                # 连接/契约/小额实模分级认证
├── snapshots.py                     # 不可变执行快照
├── settings.py                      # legacy/shadow/canonical 读取模式
├── backfill.py                      # 旧表到规范记录的只读预检与幂等回填
├── shadow_compare.py                # legacy/canonical 解析差异审计
└── legacy_projection.py              # `/llm` 与 `/external` 兼容投影
```

### Backend driver ownership

```text
backend/app/features/model_drivers/
├── __init__.py
├── public.py
├── domain.py                         # CapabilityDriver 和四类 command/result
├── registry.py                       # driver_key -> driver factory
├── executor.py                       # 测试和生产共用执行内核
└── adapters/
    ├── openai_compatible_text.py
    ├── minimax_text.py
    ├── minimax_image.py
    ├── minimax_speech.py
    ├── volcano_ark_image.py
    ├── volcano_ark_video.py
    ├── volcano_openspeech.py
    ├── dashscope_video.py
    ├── local_ffmpeg.py
    └── qiniu_kodo.py
```

### Prompt version ownership

```text
backend/app/features/prompt_profiles/
├── __init__.py
├── public.py
├── domain.py
├── repository.py
├── versioning.py
├── routing.py
└── evaluation.py
```

### Thin API ownership

```text
backend/app/features/model_config/api/
├── __init__.py
├── schemas.py
├── connections.py
├── catalog.py
├── bindings.py
├── recipes.py
├── prompts.py
└── certifications.py
```

### Frontend feature ownership

```text
frontend/src/features/model-center/
├── api.ts
├── types.ts
├── hooks/
│   ├── use-model-center-overview.ts
│   ├── use-model-connections.ts
│   ├── use-model-bindings.ts
│   ├── use-production-recipes.ts
│   ├── use-prompt-profiles.ts
│   └── use-certification-run.ts
└── components/
    ├── model-center-shell.tsx
    ├── model-center-sidebar.tsx
    ├── model-center-overview.tsx
    ├── connection-list.tsx
    ├── connection-editor.tsx
    ├── model-catalog.tsx
    ├── model-binding-list.tsx
    ├── recipe-editor.tsx
    ├── recipe-pipeline.tsx
    ├── prompt-profile-editor.tsx
    ├── prompt-profile-diff.tsx
    ├── test-lab.tsx
    ├── certification-run-panel.tsx
    ├── advanced-parameters-drawer.tsx
    └── impact-dialog.tsx
```

---

## Batch 1 — Stabilize catalog and secrets without changing production routing

### Task 1: Lock current product catalog visibility

**Files:**
- Modify: `backend/app/api/v1/endpoints/llm_config.py:219-347`
- Modify: `frontend/src/lib/model-configs.ts:1-135`
- Test: `backend/test_text_model_config.py`
- Test: `frontend/e2e/model-center-config.spec.ts`

**Interfaces:**
- Consumes: existing `/api/v1/llm/providers`, `/models`, `/configs`.
- Produces: `is_product_visible_provider(provider) -> bool` and `is_product_visible_model(model) -> bool`, moved to `features/model_config/catalog.py` in Task 5; this task first locks legacy behavior with tests.

- [ ] **Step 1: Add failing backend regression for leaked contract providers**

```python
@pytest.mark.asyncio
async def test_llm_catalog_hides_contract_and_deterministic_providers() -> None:
    async with isolated_llm_catalog() as client:
        await seed_provider(client.db, id="deterministic-acceptance", name="deterministic-acceptance")
        await seed_provider(client.db, id="contract-text", name="contract-text")
        response = client.http.get("/api/v1/llm/providers")
        assert response.status_code == 200
        assert {item["id"] for item in response.json()}.isdisjoint(
            {"deterministic-acceptance", "contract-text"}
        )
```

- [ ] **Step 2: Run the regression and confirm the current leak**

Run: `cd backend && python -m pytest -q test_text_model_config.py::test_llm_catalog_hides_contract_and_deterministic_providers`

Expected: FAIL because the current endpoint returns one or both internal providers.

- [ ] **Step 3: Extend the single legacy visibility predicate**

```python
INTERNAL_PROVIDER_PREFIXES = (
    "preflight-",
    "test-provider-",
    "placeholder-provider-",
    "contract-",
)
INTERNAL_PROVIDER_IDS = frozenset({"deterministic-acceptance"})


def _is_internal_test_provider(provider: LLMProvider | None) -> bool:
    if provider is None:
        return False
    values = [provider.id, provider.name, provider.name_en, provider.name_cn]
    normalized = " ".join(str(value or "").strip().lower() for value in values)
    return (
        str(provider.id or "").lower() in INTERNAL_PROVIDER_IDS
        or any(part.startswith(INTERNAL_PROVIDER_PREFIXES) for part in normalized.split())
        or "预检供应商" in str(provider.name_cn or "")
    )
```

- [ ] **Step 4: Add frontend defense-in-depth cases for stale cached data**

```typescript
export function isInternalProviderConfig(provider: { id?: string; name?: string; name_cn?: string }) {
  const id = String(provider.id || '').toLowerCase();
  const text = [provider.id, provider.name, provider.name_cn].filter(Boolean).join(' ').toLowerCase();
  return id === 'deterministic-acceptance' || /(^|\s)(contract-|preflight-|test-provider-)/.test(text);
}
```

- [ ] **Step 5: Run catalog regression and browser selector test**

Run: `cd backend && python -m pytest -q test_text_model_config.py`

Expected: all tests PASS.

Run: `cd frontend && npx playwright test e2e/model-center-config.spec.ts --project=chromium --workers=1`

Expected: provider selectors contain no internal catalog records.

- [ ] **Step 6: Commit the isolated catalog fix**

```bash
git add backend/app/api/v1/endpoints/llm_config.py backend/test_text_model_config.py frontend/src/lib/model-configs.ts frontend/e2e/model-center-config.spec.ts
git commit -m "fix: hide internal model catalog records"
```

### Task 2: Encrypt all LLM secrets and fail closed in production

**Files:**
- Modify: `backend/app/models/llm_config.py:20-225`
- Modify: `backend/app/api/v1/endpoints/llm_config.py:2022-2290`
- Create: `backend/scripts/audit_llm_secret_storage.py`
- Test: `backend/tests/test_model_center_security.py`
- Test: `backend/test_text_model_config.py`

**Interfaces:**
- Consumes: existing `encrypt_key()` and `decrypt_key()`.
- Produces: `LLMConfig.set_api_secret_encrypted()`, `LLMConfig.get_api_secret_decrypted()`, `require_stable_encryption_key()` and a read-only audit command.

- [ ] **Step 1: Write failing secret-storage tests**

```python
def test_llm_api_secret_is_encrypted_and_round_trips(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    config = LLMConfig(id="cfg", user_id="user", model_id="model", name="name")
    config.set_api_secret_encrypted("secret-value")
    assert config.api_secret != "secret-value"
    assert config.get_api_secret_decrypted() == "secret-value"


def test_production_requires_stable_fernet_key(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.delenv("FERNET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        require_stable_encryption_key()
```

- [ ] **Step 2: Confirm both tests fail before implementation**

Run: `cd backend && python -m pytest -q tests/test_model_center_security.py`

Expected: FAIL because the new methods and startup guard do not exist.

- [ ] **Step 3: Add encrypted secret helpers and startup guard**

```python
def require_stable_encryption_key() -> None:
    dev_mode = os.getenv("DEV_MODE", "true").lower() in {"true", "1", "yes"}
    if not dev_mode and not os.getenv("FERNET_KEY"):
        raise RuntimeError("FERNET_KEY is required when DEV_MODE=false")


class LLMConfig(Base):
    # existing columns remain unchanged
    def get_api_secret_decrypted(self) -> str:
        return decrypt_key(self.api_secret or "")

    def set_api_secret_encrypted(self, plain_secret: str | None) -> None:
        self.api_secret = encrypt_key(plain_secret) if plain_secret else None
```

- [ ] **Step 4: Route every create/update through encryption helpers**

```python
if request.api_key:
    config.set_api_key_encrypted(request.api_key)
if request.api_secret is not None:
    config.set_api_secret_encrypted(request.api_secret)
```

- [ ] **Step 5: Implement a read-only secret audit script**

```python
def classify_secret(value: str | None) -> str:
    if not value:
        return "empty"
    return "encrypted" if value.startswith("gAAAAA") else "legacy_plaintext"


def main() -> int:
    rows = load_secret_columns_read_only()
    counts = Counter(classify_secret(value) for value in rows)
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0
```

The script must open the configured database read-only and must not provide an `--apply` option in this task.

- [ ] **Step 6: Run security and legacy config regression**

Run: `cd backend && python -m pytest -q tests/test_model_center_security.py test_text_model_config.py`

Expected: PASS with no API response containing plaintext key or secret.

- [ ] **Step 7: Commit the security boundary**

```bash
git add backend/app/models/llm_config.py backend/app/api/v1/endpoints/llm_config.py backend/scripts/audit_llm_secret_storage.py backend/tests/test_model_center_security.py backend/test_text_model_config.py
git commit -m "fix: secure persisted model credentials"
```

---

## Batch 2 — Create the canonical model domain and additive persistence

### Task 3: Define canonical capabilities, statuses and profile contracts

**Files:**
- Create: `backend/app/features/model_config/__init__.py`
- Create: `backend/app/features/model_config/domain.py`
- Create: `backend/app/features/model_config/schemas.py`
- Create: `backend/app/features/model_config/public.py`
- Test: `backend/tests/test_model_center_domain.py`

**Interfaces:**
- Consumes: legacy `model_type` and `capabilities` strings.
- Produces: `ModelCapability`, `ProfileStatus`, `CertificationLevel`, `normalize_capabilities()`, `ModelProfileContract`, `ResolvedModelBinding`.

- [ ] **Step 1: Write failing canonicalization tests**

```python
@pytest.mark.parametrize(
    ("model_type", "capabilities", "expected"),
    [
        ("video-generation", ["text-to-video", "image_to_video"], {"video_generation"}),
        ("tts", ["text-to-speech"], {"speech_generation"}),
        ("vision", ["image_understanding"], {"vision_analysis"}),
        ("image", ["text_to_image"], {"image_generation"}),
    ],
)
def test_normalize_capabilities_uses_canonical_ids(model_type, capabilities, expected):
    assert normalize_capabilities(model_type, capabilities) == expected
```

- [ ] **Step 2: Run and confirm missing-domain failure**

Run: `cd backend && python -m pytest -q tests/test_model_center_domain.py`

Expected: FAIL because `features.model_config.domain` does not exist.

- [ ] **Step 3: Implement the canonical domain**

```python
ModelCapability = Literal[
    "text_generation",
    "vision_analysis",
    "image_generation",
    "speech_generation",
    "video_generation",
    "subtitle_generation",
    "media_render",
    "object_storage",
]


class ProfileStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class CertificationLevel(str, Enum):
    NONE = "none"
    CONNECTION = "connection"
    CONTRACT = "contract"
    LIVE = "live"


class BindingScope(str, Enum):
    REQUEST = "request"
    SERIES = "series"
    PROJECT = "project"
    USER = "user"
    SYSTEM = "system"

CAPABILITY_ALIASES: dict[str, ModelCapability] = {
    "chat": "text_generation",
    "completion": "text_generation",
    "text-generation": "text_generation",
    "vision": "vision_analysis",
    "vision-analysis": "vision_analysis",
    "image-understanding": "vision_analysis",
    "image": "image_generation",
    "image-generation": "image_generation",
    "text-to-image": "image_generation",
    "tts": "speech_generation",
    "audio": "speech_generation",
    "text-to-speech": "speech_generation",
    "video": "video_generation",
    "video-generation": "video_generation",
    "text-to-video": "video_generation",
    "image-to-video": "video_generation",
    "subtitle-generation": "subtitle_generation",
    "render": "media_render",
    "media-render": "media_render",
    "storage": "object_storage",
    "object-storage": "object_storage",
}


def normalize_capabilities(model_type: str | None, capabilities: Sequence[str]) -> set[ModelCapability]:
    values = [str(model_type or "").lower(), *(str(item).lower() for item in capabilities)]
    normalized = {CAPABILITY_ALIASES[item.replace("_", "-")] for item in values if item.replace("_", "-") in CAPABILITY_ALIASES}
    return normalized
```

- [ ] **Step 4: Define immutable profile and binding types**

```python
@dataclass(frozen=True)
class ModelProfileContract:
    profile_version_id: str
    provider_id: str
    api_model_id: str
    driver_key: str
    capabilities: frozenset[ModelCapability]
    input_contract: Mapping[str, Any]
    output_contract: Mapping[str, Any]
    parameter_schema: Mapping[str, Any]
    default_params: Mapping[str, Any]
    limits: Mapping[str, Any]
    pricing: Mapping[str, Any]
    prompt_profile_key: str | None
    contract_version: str


@dataclass(frozen=True)
class ResolvedModelBinding:
    task: str
    capability: ModelCapability
    profile: ModelProfileContract
    connection_id: str | None
    binding_version: int
    source_scope: Literal["request", "series", "project", "user", "system"]
```

- [ ] **Step 5: Run domain tests**

Run: `cd backend && python -m pytest -q tests/test_model_center_domain.py`

Expected: PASS for all legacy alias and immutable-contract cases.

- [ ] **Step 6: Commit the domain boundary**

```bash
git add backend/app/features/model_config backend/tests/test_model_center_domain.py
git commit -m "feat: define canonical model configuration domain"
```

### Task 4: Add versioned persistence and concurrency-safe migrations

**Files:**
- Create: `backend/app/models/model_center.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/db_migrations/model_center.py`
- Modify: `backend/app/db_migrations/runner.py`
- Test: `backend/tests/test_model_center_migrations.py`
- Test: `backend/tests/test_database_config.py`

**Interfaces:**
- Consumes: canonical types from Task 3 and existing user/provider/model/config IDs.
- Produces: ORM models `ModelProvider`, `ModelProfile`, `ModelConnection`, `ModelProfileVersion`, `ModelBinding`, `ProductionRecipeVersion`, `ModelCertificationRun`, `ModelExecutionSnapshot`, `ModelConfigAuditEvent`.

- [ ] **Step 1: Write failing create-all and idempotent-migration tests**

```python
def test_model_center_tables_are_created(tmp_path):
    engine = sqlite_engine(tmp_path / "model-center.db")
    register_production_models()
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert {
        "model_providers",
        "model_profiles",
        "model_connections",
        "model_profile_versions",
        "model_bindings",
        "production_recipe_versions",
        "model_certification_runs",
        "model_execution_snapshots",
        "model_config_audit_events",
    } <= tables


def test_model_center_migration_is_idempotent(tmp_path):
    engine = legacy_model_database(tmp_path / "legacy.db")
    add_model_center_links(engine)
    add_model_center_links(engine)
    assert "connection_id" in column_names(engine, "llm_configs")
    assert "connection_id" in column_names(engine, "external_api_configs")
```

- [ ] **Step 2: Run and confirm the tables are absent**

Run: `cd backend && python -m pytest -q tests/test_model_center_migrations.py`

Expected: FAIL because the new models and migration are not registered.

- [ ] **Step 3: Add the additive ORM models**

```python
class ModelProvider(Base):
    __tablename__ = "model_providers"

    id = Column(String(36), primary_key=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    display_name = Column(String(120), nullable=False)
    provider_family = Column(String(80), nullable=False, index=True)
    is_builtin = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ModelProfile(Base):
    __tablename__ = "model_profiles"
    __table_args__ = (
        UniqueConstraint("provider_id", "profile_key", name="uq_model_profile_key"),
    )

    id = Column(String(36), primary_key=True)
    provider_id = Column(String(36), nullable=False, index=True)
    profile_key = Column(String(120), nullable=False)
    display_name = Column(String(160), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ModelConnection(Base):
    __tablename__ = "model_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider_id", "name", name="uq_model_connection_name"),)

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    provider_id = Column(String(36), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    api_key = Column(Text)  # Fernet ciphertext only; write through set_api_key_encrypted()
    api_secret = Column(Text)  # Fernet ciphertext only; write through set_api_secret_encrypted()
    endpoint_overrides = Column(JSON, nullable=False, default=dict)
    connection_params = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="draft", index=True)
    tested_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ModelProfileVersion(Base):
    __tablename__ = "model_profile_versions"
    __table_args__ = (UniqueConstraint("model_id", "version", name="uq_model_profile_version"),)

    id = Column(String(36), primary_key=True)
    model_id = Column(String(36), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    api_model_id = Column(String(200), nullable=False, index=True)
    driver_key = Column(String(80), nullable=False, index=True)
    capabilities = Column(JSON, nullable=False, default=list)
    input_contract = Column(JSON, nullable=False, default=dict)
    output_contract = Column(JSON, nullable=False, default=dict)
    parameter_schema = Column(JSON, nullable=False, default=dict)
    default_params = Column(JSON, nullable=False, default=dict)
    limits = Column(JSON, nullable=False, default=dict)
    pricing = Column(JSON, nullable=False, default=dict)
    prompt_profile_key = Column(String(120))
    contract_version = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    checksum = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class ModelBinding(Base):
    __tablename__ = "model_bindings"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope_type", "scope_id", "task", "capability", "version",
            name="uq_model_binding_version",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    scope_type = Column(String(20), nullable=False, index=True)
    scope_id = Column(String(36), nullable=False, default="", index=True)
    task = Column(String(100), nullable=False, index=True)
    capability = Column(String(40), nullable=False, index=True)
    profile_version_id = Column(String(36), nullable=False, index=True)
    connection_id = Column(String(36), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=100)
    route_policy = Column(String(30), nullable=False, default="single")
    fallback_profile_version_ids = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ProductionRecipeVersion(Base):
    __tablename__ = "production_recipe_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "recipe_key", "version", name="uq_production_recipe_version"),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    recipe_key = Column(String(100), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    spec = Column(JSON, nullable=False)
    checksum = Column(String(64), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    published_at = Column(DateTime)


class ModelCertificationRun(Base):
    __tablename__ = "model_certification_runs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    profile_version_id = Column(String(36), nullable=False, index=True)
    connection_id = Column(String(36), nullable=False, index=True)
    level = Column(String(20), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)
    request_fingerprint = Column(String(64), nullable=False, index=True)
    sanitized_evidence = Column(JSON, nullable=False, default=dict)
    estimated_cost_rmb = Column(Numeric(10, 4), nullable=False, default=0)
    actual_cost_rmb = Column(Numeric(10, 4), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    completed_at = Column(DateTime)


class ModelExecutionSnapshot(Base):
    __tablename__ = "model_execution_snapshots"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    run_id = Column(String(36), index=True)
    job_id = Column(String(36), index=True)
    task = Column(String(100), nullable=False, index=True)
    capability = Column(String(40), nullable=False, index=True)
    profile_version_id = Column(String(36), nullable=False, index=True)
    connection_id = Column(String(36), nullable=False, index=True)
    binding_id = Column(String(36), nullable=False, index=True)
    binding_version = Column(Integer, nullable=False)
    recipe_version_id = Column(String(36), index=True)
    prompt_profile_version_id = Column(String(36), index=True)
    model_contract_version = Column(String(100), nullable=False)
    sanitized_params = Column(JSON, nullable=False, default=dict)
    checksum = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class ModelConfigAuditEvent(Base):
    __tablename__ = "model_config_audit_events"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    resource_type = Column(String(40), nullable=False, index=True)
    resource_id = Column(String(36), nullable=False, index=True)
    action = Column(String(40), nullable=False, index=True)
    from_version_id = Column(String(36))
    to_version_id = Column(String(36))
    reason = Column(String(200), nullable=False)
    sanitized_change_summary = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
```

- [ ] **Step 4: Add only additive compatibility columns**

```python
_LINK_COLUMNS = {
    "llm_configs": {"connection_id": "VARCHAR(36)"},
    "external_api_configs": {"connection_id": "VARCHAR(36)"},
    "prompt_skills": {"prompt_profile_version_id": "VARCHAR(36)"},
}
```

Implement sync and async migration paths using the duplicate-only recovery pattern already used by `live_canary_provider_operations.py`.

- [ ] **Step 5: Register models before `create_all()` and migrations after it**

```python
def register_production_models() -> None:
    from app.models.model_center import (
        ModelBinding,
        ModelCertificationRun,
        ModelConfigAuditEvent,
        ModelConnection,
        ModelExecutionSnapshot,
        ModelProfile,
        ModelProfileVersion,
        ModelProvider,
        ProductionRecipeVersion,
    )
    _ = (
        ModelBinding,
        ModelCertificationRun,
        ModelConfigAuditEvent,
        ModelConnection,
        ModelExecutionSnapshot,
        ModelProfile,
        ModelProfileVersion,
        ModelProvider,
        ProductionRecipeVersion,
    )
```

- [ ] **Step 6: Run migration and concurrency tests**

Run: `cd backend && python -m pytest -q tests/test_model_center_migrations.py tests/test_database_config.py`

Expected: PASS for fresh SQLite, legacy SQLite, sync double-run and async double-run.

- [ ] **Step 7: Commit the additive schema**

```bash
git add backend/app/models/model_center.py backend/app/models/__init__.py backend/app/db_migrations/model_center.py backend/app/db_migrations/runner.py backend/tests/test_model_center_migrations.py backend/tests/test_database_config.py
git commit -m "feat: persist versioned model center records"
```

### Target Persistence Contracts

`ModelProvider` must persist:

```text
id, code, display_name, provider_family, is_builtin,
enabled, revision, created_at, updated_at
```

`ModelProfile` must persist:

```text
id, provider_id, profile_key, display_name,
enabled, revision, created_at, updated_at
```

`ModelProfileVersion` must persist:

```text
id, model_id, version, api_model_id, driver_key, capabilities,
input_contract, output_contract, parameter_schema, default_params,
limits, pricing, prompt_profile_key, contract_version, status, checksum, created_at
```

`ModelBinding` must persist:

```text
id, user_id, scope_type, scope_id, task, capability,
profile_version_id, connection_id, priority, route_policy,
fallback_profile_version_ids, version, is_active, created_at, updated_at
```

`ProductionRecipeVersion` must persist:

```text
id, user_id, recipe_key, name, version, status, spec,
checksum, created_at, published_at
```

`ModelCertificationRun` must persist:

```text
id, user_id, profile_version_id, connection_id,
level, status, request_fingerprint, sanitized_evidence,
estimated_cost_rmb, actual_cost_rmb, created_at, completed_at
```

`ModelExecutionSnapshot` must persist:

```text
id, user_id, run_id, job_id, task, capability,
profile_version_id, connection_id, binding_id, binding_version,
recipe_version_id, prompt_profile_version_id,
model_contract_version, sanitized_params, checksum, created_at
```

`ModelConfigAuditEvent` must persist:

```text
id, user_id, resource_type, resource_id, action,
from_version_id, to_version_id, reason,
sanitized_change_summary, created_at
```

Every version table uses append-only rows after `status=published`; editing a published record creates `version + 1`.

---

## Batch 3 — Unify catalog reads, drivers, tests and production execution

### Task 5: Build the canonical repository and legacy projection

**Files:**
- Create: `backend/app/features/model_config/repository.py`
- Create: `backend/app/features/model_config/catalog.py`
- Create: `backend/app/features/model_config/legacy_projection.py`
- Modify: `backend/app/features/model_config/public.py`
- Test: `backend/tests/test_model_center_repository.py`
- Test: `backend/test_text_model_config.py`
- Test: `backend/test_production_adapters.py`

**Interfaces:**
- Consumes: new model-center tables, existing LLM/external tables and canonical domain types.
- Produces: `list_product_catalog()`, `resolve_profile_version()`, `project_legacy_llm_models()`, `project_legacy_external_providers()`, `compare_legacy_and_canonical_catalogs()`.

- [ ] **Step 1: Write failing repository tests against mixed old/new rows**

```python
@pytest.mark.asyncio
async def test_product_catalog_prefers_published_profile_without_losing_legacy_config(db_session):
    legacy = await seed_verified_llm_config(db_session, provider="volcano", model="seed-tts-2.0")
    profile = await seed_profile_version(
        db_session,
        model_id=legacy.model_id,
        version=1,
        status="published",
        driver_key="volcano_openspeech_v3",
        capabilities=["speech_generation"],
    )
    catalog = await list_product_catalog(db_session, legacy.user_id)
    item = next(item for item in catalog.models if item.api_model_id == "seed-tts-2.0")
    assert item.profile_version_id == profile.id
    assert item.legacy_config_id == legacy.config_id
    assert item.certification_status == "connection_verified"
```

- [ ] **Step 2: Run and confirm repository symbols are missing**

Run: `cd backend && python -m pytest -q tests/test_model_center_repository.py`

Expected: FAIL on missing repository/public functions.

- [ ] **Step 3: Implement one repository-owned product visibility rule**

```python
PRODUCT_VISIBILITY = "product"


def is_product_visible(identifier: str, visibility: str | None) -> bool:
    if visibility:
        return visibility == PRODUCT_VISIBILITY
    normalized = identifier.strip().lower()
    return not (
        normalized == "deterministic-acceptance"
        or normalized.startswith(("contract-", "preflight-", "test-", "placeholder-"))
    )
```

- [ ] **Step 4: Implement canonical-first, legacy-compatible resolution**

```python
async def resolve_profile_version(
    db: AsyncSession,
    *,
    profile_version_id: str | None = None,
    legacy_model_id: str | None = None,
) -> ModelProfileContract:
    if profile_version_id:
        row = await load_published_profile(db, profile_version_id)
        if row is None:
            raise ModelConfigurationError("model_profile_not_published")
        return profile_contract(row)
    if legacy_model_id:
        return await build_legacy_profile_contract(db, legacy_model_id)
    raise ModelConfigurationError("model_profile_required")
```

- [ ] **Step 5: Add a shadow comparison report with no runtime mutation**

```python
@dataclass(frozen=True)
class CatalogComparison:
    legacy_provider_ids: frozenset[str]
    canonical_provider_ids: frozenset[str]
    legacy_model_keys: frozenset[str]
    canonical_model_keys: frozenset[str]

    @property
    def equivalent(self) -> bool:
        return (
            self.legacy_provider_ids == self.canonical_provider_ids
            and self.legacy_model_keys == self.canonical_model_keys
        )
```

- [ ] **Step 6: Route legacy GET endpoints through the projection only under a test flag**

Use `MODEL_CENTER_CANONICAL_READS=shadow` to compute and log a redacted comparison while returning the original response. `MODEL_CENTER_CANONICAL_READS=on` may return the projection only after the Batch 3 decision point.

- [ ] **Step 7: Run repository and legacy contract tests**

Run: `cd backend && python -m pytest -q tests/test_model_center_repository.py test_text_model_config.py test_production_adapters.py`

Expected: PASS; shadow mode performs no writes and old response fields remain present.

- [ ] **Step 8: Commit the canonical read model**

```bash
git add backend/app/features/model_config backend/tests/test_model_center_repository.py backend/test_text_model_config.py backend/test_production_adapters.py
git commit -m "feat: add canonical model catalog projection"
```

### Task 6: Define the provider-neutral driver SDK

**Files:**
- Create: `backend/app/features/model_drivers/__init__.py`
- Create: `backend/app/features/model_drivers/domain.py`
- Create: `backend/app/features/model_drivers/registry.py`
- Create: `backend/app/features/model_drivers/executor.py`
- Create: `backend/app/features/model_drivers/public.py`
- Test: `backend/tests/test_model_driver_contract.py`

**Interfaces:**
- Consumes: `ModelProfileContract`, decrypted connection secrets and normalized generation intent.
- Produces: `TextCommand`, `ImageCommand`, `SpeechCommand`, `VideoCommand`, `CapabilityDriver`, `DriverRegistry`, `execute_connection_test()`, `execute_generation()`.

- [ ] **Step 1: Write failing driver conformance tests**

```python
class EchoTextDriver:
    key = "echo_text_v1"
    capabilities = frozenset({"text_generation"})

    async def test_connection(self, context):
        return DriverTestResult(status="connection_verified", message="ok", sanitized_evidence={})

    async def submit(self, command, context):
        return DriverSubmission(status="completed", provider_task_id=None, output={"text": command.prompt})

    async def poll(self, provider_task_id, context):
        raise AssertionError("sync driver must not poll")


@pytest.mark.asyncio
async def test_same_driver_builds_connection_test_and_generation():
    registry = DriverRegistry([EchoTextDriver()])
    tested = await execute_connection_test(registry, "echo_text_v1", connection_context())
    generated = await execute_generation(
        registry,
        TextCommand(prompt="hello", output_contract="plain_text", params={}),
        generation_context(driver_key="echo_text_v1"),
    )
    assert tested.status == "connection_verified"
    assert generated.output == {"text": "hello"}
```

- [ ] **Step 2: Run and confirm missing-driver failure**

Run: `cd backend && python -m pytest -q tests/test_model_driver_contract.py`

Expected: FAIL because the driver SDK does not exist.

- [ ] **Step 3: Implement discriminated generation commands**

```python
@dataclass(frozen=True)
class TextCommand:
    capability: Literal["text_generation"] = "text_generation"
    prompt: str = ""
    output_contract: str = "plain_text"
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageCommand:
    capability: Literal["image_generation"] = "image_generation"
    prompt: str = ""
    reference_images: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeechCommand:
    capability: Literal["speech_generation"] = "speech_generation"
    text: str = ""
    voice_id: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoCommand:
    capability: Literal["video_generation"] = "video_generation"
    prompt: str = ""
    reference_images: tuple[str, ...] = ()
    reference_videos: tuple[str, ...] = ()
    reference_audios: tuple[str, ...] = ()
    native_audio: bool = False
    dialogue_contract: Mapping[str, Any] | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Implement the driver protocol and registry**

```python
Command = TextCommand | ImageCommand | SpeechCommand | VideoCommand


class CapabilityDriver(Protocol):
    key: str
    capabilities: frozenset[str]

    async def test_connection(self, context: DriverContext) -> DriverTestResult: ...
    async def submit(self, command: Command, context: DriverContext) -> DriverSubmission: ...
    async def poll(self, provider_task_id: str, context: DriverContext) -> DriverSubmission: ...


class DriverRegistry:
    def __init__(self, drivers: Iterable[CapabilityDriver]):
        self._drivers = {driver.key: driver for driver in drivers}

    def require(self, key: str) -> CapabilityDriver:
        driver = self._drivers.get(key)
        if driver is None:
            raise DriverUnavailableError(key)
        return driver
```

- [ ] **Step 5: Add fail-closed executor checks**

```python
async def execute_generation(registry, command, context):
    driver = registry.require(context.driver_key)
    if command.capability not in driver.capabilities:
        raise DriverCapabilityError(context.driver_key, command.capability)
    validate_params(context.profile.parameter_schema, command.params)
    validate_command_limits(command, context.profile.limits)
    return await driver.submit(command, context)
```

- [ ] **Step 6: Run conformance and unknown-driver cases**

Run: `cd backend && python -m pytest -q tests/test_model_driver_contract.py`

Expected: PASS for sync, async, wrong capability, unknown driver, secret-safe evidence and limit validation.

- [ ] **Step 7: Commit the driver SDK**

```bash
git add backend/app/features/model_drivers backend/tests/test_model_driver_contract.py
git commit -m "feat: add capability driver execution contract"
```

### Task 7: Wrap the currently used providers without rewriting them

**Files:**
- Create: `backend/app/features/model_drivers/adapters/minimax_text.py`
- Create: `backend/app/features/model_drivers/adapters/minimax_image.py`
- Create: `backend/app/features/model_drivers/adapters/minimax_speech.py`
- Create: `backend/app/features/model_drivers/adapters/volcano_ark_image.py`
- Create: `backend/app/features/model_drivers/adapters/volcano_ark_video.py`
- Create: `backend/app/features/model_drivers/adapters/volcano_openspeech.py`
- Create: `backend/app/features/model_drivers/adapters/dashscope_video.py`
- Create: `backend/app/features/model_drivers/adapters/local_ffmpeg.py`
- Create: `backend/app/features/model_drivers/adapters/qiniu_kodo.py`
- Create: `backend/app/features/model_drivers/text_execution.py`
- Modify: `backend/app/features/model_drivers/registry.py`
- Modify: `backend/app/core/api_key_utils.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py:2104-2240`
- Modify: `backend/app/api/v1/endpoints/external_api.py:435-511`
- Test: `backend/tests/test_model_driver_contract.py`
- Test: `backend/tests/test_text_generation_adapter_compatibility.py`
- Test: `backend/tests/test_minimax_tts_request_contract.py`
- Test: `backend/tests/test_workflow_media_tts_model_config.py`
- Test: `backend/tests/test_image_provider_response_contract.py`
- Test: `backend/tests/test_media_delivery_qiniu.py`

**Interfaces:**
- Consumes: existing tested service functions and the driver SDK.
- Produces: built-in driver keys used by persisted model profile versions.

- [ ] **Step 1: Add a parameterized conformance matrix before wrapping**

```python
@pytest.mark.parametrize(
    ("driver_key", "capability"),
    [
        ("minimax_text_v2", "text_generation"),
        ("minimax_image_v1", "image_generation"),
        ("minimax_speech_v2", "speech_generation"),
        ("volcano_ark_image_v3", "image_generation"),
        ("volcano_ark_video_v3", "video_generation"),
        ("volcano_openspeech_v3", "speech_generation"),
        ("dashscope_video_v1", "video_generation"),
        ("local_ffmpeg_v1", "media_render"),
        ("qiniu_kodo_v1", "object_storage"),
    ],
)
def test_builtin_driver_registry_has_current_production_drivers(driver_key, capability):
    driver = build_builtin_driver_registry().require(driver_key)
    assert capability in driver.capabilities
```

- [ ] **Step 2: Run and confirm registry gaps**

Run: `cd backend && python -m pytest -q tests/test_model_driver_contract.py::test_builtin_driver_registry_has_current_production_drivers`

Expected: FAIL for every adapter not yet registered.

- [ ] **Step 3: Wrap existing request builders instead of copying payloads**

```python
class VolcanoOpenSpeechDriver:
    key = "volcano_openspeech_v3"
    capabilities = frozenset({"speech_generation"})

    async def test_connection(self, context):
        result = await test_volcano_speech_connection(
            context.api_key,
            configure_volcano_speech_endpoint(context.base_url, context.connection_params),
            "模型中心连接测试",
        )
        return normalize_test_result(result)

    async def submit(self, command, context):
        request = build_volcano_speech_request(
            model_id=context.profile.api_model_id,
            text=command.text,
            voice_id=command.voice_id,
            params=command.params,
            connection_params=context.connection_params,
        )
        return await submit_volcano_speech_request(request, context.api_key, context.base_url)
```

Every adapter must call the existing production request builder or move that builder into the adapter and make the old service import it. No adapter may copy a request body already owned elsewhere.

- [ ] **Step 4: Extract the oversized legacy text adapter without changing behavior**

Before moving code, add `test_text_generation_adapter_compatibility.py` cases for every provider currently accepted by `create_text_generation_service()`. Move `TextGenerationServiceAdapter`, `create_text_generation_service()`, and `get_user_text_generation_service()` from the 800-line `core/api_key_utils.py` into `features/model_drivers/text_execution.py`; keep compatibility re-exports in `api_key_utils.py`. Run the characterization test before and after the move and require identical provider class, API model ID, base URL, and extracted response text.

- [ ] **Step 5: Replace endpoint provider branches with the driver executor**

```python
profile, connection = await resolve_test_context(db, user_id, config_id)
result = await execute_connection_test(
    build_builtin_driver_registry(),
    profile.driver_key,
    build_driver_context(profile, connection),
)
return legacy_test_response(result)
```

- [ ] **Step 6: Lock sanitized request equivalence**

```python
def test_volcano_speech_config_test_and_production_share_request_contract():
    test_request = capture_driver_request(mode="connection_test", driver_key="volcano_openspeech_v3")
    production_request = capture_driver_request(mode="production", driver_key="volcano_openspeech_v3")
    assert test_request.contract_version == production_request.contract_version
    assert test_request.payload_keys == production_request.payload_keys
    assert "text" not in test_request.safe_evidence
    assert "api_key" not in test_request.safe_evidence
```

- [ ] **Step 7: Run provider contract suites**

Run: `cd backend && python -m pytest -q tests/test_model_driver_contract.py tests/test_text_generation_adapter_compatibility.py tests/test_minimax_tts_request_contract.py tests/test_workflow_media_tts_model_config.py tests/test_image_provider_response_contract.py tests/test_media_delivery_qiniu.py test_text_model_config.py test_production_adapters.py`

Expected: PASS; legacy endpoints return their prior response shapes and no provider branch remains in configuration endpoints.

- [ ] **Step 8: Commit current-provider wrappers**

```bash
git add backend/app/features/model_drivers backend/app/core/api_key_utils.py backend/app/api/v1/endpoints/llm_config.py backend/app/api/v1/endpoints/external_api.py backend/tests/test_model_driver_contract.py backend/tests/test_text_generation_adapter_compatibility.py backend/tests/test_minimax_tts_request_contract.py backend/tests/test_workflow_media_tts_model_config.py backend/tests/test_image_provider_response_contract.py backend/tests/test_media_delivery_qiniu.py backend/test_text_model_config.py backend/test_production_adapters.py
git commit -m "refactor: route model tests through provider drivers"
```

---

## Batch 4 — Persist task bindings, production recipes, Prompt versions and snapshots

### Task 8: Resolve scoped model bindings with deterministic precedence

**Files:**
- Create: `backend/app/features/model_config/bindings.py`
- Modify: `backend/app/features/model_config/repository.py`
- Modify: `backend/app/features/model_config/public.py`
- Modify: `backend/app/services/production_strategy_routing.py`
- Test: `backend/tests/test_model_binding_resolution.py`
- Test: `backend/tests/test_production_strategy_routing.py`

**Interfaces:**
- Consumes: published `ModelProfileVersion`, verified `ModelConnection`, existing explicit config IDs and legacy strategy labels.
- Produces: `resolve_model_binding()` with precedence `request > series > project > user > system > legacy`.

- [ ] **Step 1: Write failing precedence and safety tests**

```python
@pytest.mark.asyncio
async def test_binding_precedence_is_request_series_project_user_system(db_session):
    fixtures = await seed_binding_precedence_fixture(db_session)
    resolved = await resolve_model_binding(
        db_session,
        user_id=fixtures.user_id,
        task="shot_video",
        capability="video_generation",
        explicit_profile_version_id=fixtures.request_profile_id,
        project_id=fixtures.project_id,
        series_id=fixtures.series_id,
    )
    assert resolved.profile.profile_version_id == fixtures.request_profile_id
    assert resolved.source_scope == "request"


@pytest.mark.asyncio
async def test_media_binding_does_not_auto_fallback_after_provider_acceptance(db_session):
    binding = await seed_video_binding_with_fallback(db_session)
    operation = accepted_provider_operation(binding.id)
    with pytest.raises(ModelBindingError, match="status_only"):
        await resolve_retry_binding(db_session, binding, operation)
```

- [ ] **Step 2: Run and confirm missing resolver failure**

Run: `cd backend && python -m pytest -q tests/test_model_binding_resolution.py`

Expected: FAIL because scoped binding resolution is not implemented.

- [ ] **Step 3: Implement explicit scope precedence**

```python
SCOPE_PRECEDENCE = ("request", "series", "project", "user", "system")


async def resolve_model_binding(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
    explicit_profile_version_id: str | None = None,
    explicit_config_id: str | None = None,
    project_id: str | None = None,
    series_id: str | None = None,
) -> ResolvedModelBinding:
    candidates = await load_binding_candidates(
        db,
        user_id=user_id,
        task=task,
        capability=capability,
        project_id=project_id,
        series_id=series_id,
    )
    selected = select_binding_candidate(
        candidates,
        explicit_profile_version_id=explicit_profile_version_id,
        explicit_config_id=explicit_config_id,
    )
    if selected is None:
        return await resolve_legacy_binding(db, user_id, task, capability, explicit_config_id)
    return await hydrate_resolved_binding(db, selected)
```

- [ ] **Step 4: Persist route policy without executing paid fallbacks**

```python
class RoutePolicy(TypedDict):
    allow_pre_submit_fallback: bool
    allow_post_acceptance_fallback: Literal[False]
    retry_policy: Literal["never", "confirmed_pre_acceptance_only", "status_poll_only"]
```

- [ ] **Step 5: Replace hardcoded strategy model IDs with binding aliases**

```python
STRATEGY_BINDING_KEYS = {
    "draft_fast": "video.draft_fast",
    "final_quality": "video.final_quality",
    "low_cost": "video.low_cost",
    "direct_av_first": "video.direct_av",
    "separate_video_tts": "video.separate_tts",
}
```

The strategy service resolves this binding key; it no longer owns concrete Seedance model IDs.

- [ ] **Step 6: Run binding and legacy strategy regressions**

Run: `cd backend && python -m pytest -q tests/test_model_binding_resolution.py tests/test_production_strategy_routing.py`

Expected: PASS for all scope combinations, explicit overrides, legacy fallback and post-acceptance retry blocking.

- [ ] **Step 7: Commit scoped bindings**

```bash
git add backend/app/features/model_config backend/app/services/production_strategy_routing.py backend/tests/test_model_binding_resolution.py backend/tests/test_production_strategy_routing.py
git commit -m "feat: resolve scoped model bindings"
```

### Task 9: Validate and publish anime production recipes

**Files:**
- Create: `backend/app/features/model_config/recipes.py`
- Modify: `backend/app/features/model_config/repository.py`
- Modify: `backend/app/features/model_config/public.py`
- Test: `backend/tests/test_production_recipe_contract.py`
- Test: `backend/tests/test_workflow_media_public_contract.py`

**Interfaces:**
- Consumes: binding IDs and model capabilities from Task 8.
- Produces: `ProductionRecipeSpec`, `validate_recipe()`, `create_recipe_version()`, `publish_recipe_version()`.

- [ ] **Step 1: Write failing native-audio and separate-TTS recipe tests**

```python
def test_native_audio_recipe_requires_native_audio_video_and_no_tts_binding():
    spec = recipe_spec(
        audio_mode="video_native_audio",
        video_capabilities={"video_generation"},
        tts_binding_id="tts-binding",
    )
    errors = validate_recipe(spec)
    assert {error.code for error in errors} == {
        "native_audio_capability_required",
        "tts_binding_forbidden_for_native_audio",
    }


def test_separate_tts_recipe_requires_tts_subtitles_and_render():
    spec = recipe_spec(
        audio_mode="separate_tts",
        tts_binding_id=None,
        subtitle_source=None,
        render_binding_id=None,
    )
    assert {error.code for error in validate_recipe(spec)} == {
        "tts_binding_required",
        "subtitle_source_required",
        "render_binding_required",
    }
```

- [ ] **Step 2: Run and confirm recipe validator is absent**

Run: `cd backend && python -m pytest -q tests/test_production_recipe_contract.py`

Expected: FAIL because recipe types and validation do not exist.

- [ ] **Step 3: Define the persisted recipe contract**

```python
class RecipeStage(TypedDict, total=False):
    binding_id: str
    required: bool
    params: dict[str, Any]


class ProductionRecipeSpec(TypedDict):
    text: RecipeStage
    vision: RecipeStage
    image: RecipeStage
    video: RecipeStage
    audio: dict[str, Any]
    subtitle: dict[str, Any]
    render: RecipeStage
    storage: RecipeStage
```

- [ ] **Step 4: Implement mutually exclusive audio validation**

```python
def validate_audio_route(spec: ProductionRecipeSpec, resolved: ResolvedRecipeBindings) -> list[RecipeError]:
    mode = spec["audio"].get("mode")
    errors: list[RecipeError] = []
    if mode == "video_native_audio":
        if not resolved.video.supports("native_audio"):
            errors.append(RecipeError("native_audio_capability_required", "当前视频模型不支持原生音频"))
        if spec["audio"].get("binding_id"):
            errors.append(RecipeError("tts_binding_forbidden_for_native_audio", "原生音频方案不能同时绑定 TTS"))
    elif mode == "separate_tts":
        if not spec["audio"].get("binding_id"):
            errors.append(RecipeError("tts_binding_required", "独立配音方案必须绑定声音模型"))
    else:
        errors.append(RecipeError("audio_mode_invalid", "声音方案必须选择原生音频或独立 TTS"))
    return errors
```

- [ ] **Step 5: Make published versions immutable**

```python
async def update_recipe(db, recipe_version, patch):
    if recipe_version.status == "published":
        return await create_recipe_version(
            db,
            recipe_key=recipe_version.recipe_key,
            version=recipe_version.version + 1,
            spec=apply_patch(recipe_version.spec, patch),
            status="draft",
        )
    recipe_version.spec = apply_patch(recipe_version.spec, patch)
    recipe_version.checksum = stable_json_hash(recipe_version.spec)
    return recipe_version
```

- [ ] **Step 6: Run recipe and workflow-media contract tests**

Run: `cd backend && python -m pytest -q tests/test_production_recipe_contract.py tests/test_workflow_media_public_contract.py`

Expected: PASS for both audio routes, subtitle source validation, render/storage requirements and immutable publish behavior.

- [ ] **Step 7: Commit recipe versioning**

```bash
git add backend/app/features/model_config backend/tests/test_production_recipe_contract.py backend/tests/test_workflow_media_public_contract.py
git commit -m "feat: add versioned anime production recipes"
```

### Task 10: Route production model resolution through published profiles

**Files:**
- Modify: `backend/app/features/video_generation/application/model_config.py`
- Modify: `backend/app/features/workflow_media/application/prepare_separate_media.py`
- Modify: `backend/app/services/image_generation_pipeline.py`
- Modify: `backend/app/features/model_drivers/text_execution.py`
- Modify: `backend/app/features/model_config/public.py`
- Test: `backend/tests/test_model_binding_resolution.py`
- Test: `backend/tests/test_workflow_media_public_contract.py`
- Test: `backend/tests/test_production_preflight_gates.py`

**Interfaces:**
- Consumes: `resolve_model_binding()` from Task 8, recipe versions from Task 9 and `ModelProfileContract` from Task 3.
- Produces: production paths that accept a resolved binding and do not inspect provider names or model ID strings.

- [ ] **Step 1: Write a failing no-provider-branch characterization**

```python
def test_workflow_media_resolves_driver_from_binding_not_provider_name():
    source = Path("app/features/workflow_media/application/prepare_separate_media.py").read_text()
    assert 'provider_id == "volcano"' not in source
    assert 'provider_id == "minimax"' not in source
    assert "resolve_model_binding" in source
```

- [ ] **Step 2: Run and confirm current provider-name branching**

Run: `cd backend && python -m pytest -q tests/test_model_binding_resolution.py::test_workflow_media_resolves_driver_from_binding_not_provider_name`

Expected: FAIL because current code special-cases providers.

- [ ] **Step 3: Replace runtime dictionaries with a resolved binding adapter**

```python
async def resolve_generation_context(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    capability: ModelCapability,
    explicit_config_id: str | None,
    project_id: str | None,
    series_id: str | None,
) -> GenerationContext:
    binding = await resolve_model_binding(
        db,
        user_id=user_id,
        task=task,
        capability=capability,
        explicit_config_id=explicit_config_id,
        project_id=project_id,
        series_id=series_id,
    )
    return await build_generation_context_from_binding(db, binding)
```

- [ ] **Step 4: Keep legacy fallback behind one adapter**

When no published binding exists, `resolve_model_binding()` may construct a version-0 legacy binding from the existing verified `LLMConfig`; all production callers still receive `ResolvedModelBinding`.

- [ ] **Step 5: Run production resolver and preflight regressions**

Run: `cd backend && python -m pytest -q tests/test_model_binding_resolution.py tests/test_workflow_media_public_contract.py tests/test_production_preflight_gates.py test_text_model_config.py`

Expected: PASS; explicit config IDs still override scoped defaults, and unverified legacy configurations still fail closed.

- [ ] **Step 6: Commit production resolution convergence**

```bash
git add backend/app/features/video_generation/application/model_config.py backend/app/features/workflow_media/application/prepare_separate_media.py backend/app/services/image_generation_pipeline.py backend/app/features/model_drivers/text_execution.py backend/app/features/model_config backend/tests/test_model_binding_resolution.py backend/tests/test_workflow_media_public_contract.py backend/tests/test_production_preflight_gates.py backend/test_text_model_config.py
git commit -m "refactor: resolve generation through model bindings"
```

### Task 11: Replace mutable Prompt Skill versions with immutable Prompt Profiles

**Files:**
- Create: `backend/app/models/prompt_profile.py`
- Create: `backend/app/features/prompt_profiles/__init__.py`
- Create: `backend/app/features/prompt_profiles/domain.py`
- Create: `backend/app/features/prompt_profiles/repository.py`
- Create: `backend/app/features/prompt_profiles/versioning.py`
- Create: `backend/app/features/prompt_profiles/routing.py`
- Create: `backend/app/features/prompt_profiles/evaluation.py`
- Create: `backend/app/features/prompt_profiles/public.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/services/prompt_template_router.py`
- Modify: `backend/app/services/prompt_skill_service.py`
- Test: `backend/tests/test_prompt_profile_versioning.py`
- Test: `backend/tests/test_prompt_skill_routing.py`
- Test: `backend/test_prompt_skills.py`

**Interfaces:**
- Consumes: current `PromptSkill` rows, `ModelProfileContract.prompt_profile_key`, task/output contracts and model capabilities.
- Produces: `PromptProfile`, `PromptProfileVersion`, `select_prompt_profile_version()`, legacy Prompt Skill projection and evaluation results.

- [ ] **Step 1: Write failing immutable-history and concurrent-routing tests**

```python
@pytest.mark.asyncio
async def test_published_prompt_edit_creates_new_draft_and_preserves_history(db_session):
    published = await seed_published_prompt_profile(db_session, version=3, content="old")
    draft = await edit_prompt_profile(db_session, published.id, {"content": "new"})
    assert draft.version == 4
    assert draft.status == "draft"
    assert published.content == "old"


@pytest.mark.asyncio
async def test_same_task_can_publish_different_model_specific_profiles(db_session):
    minimax = await seed_prompt_version(db_session, task="script_generation", model_filter=["MiniMax-M3"], status="published")
    doubao = await seed_prompt_version(db_session, task="script_generation", model_filter=["doubao-seed-*"], status="published")
    assert await select_prompt_profile_version(db_session, task="script_generation", provider_id="minimax", model_id="MiniMax-M3") == minimax
    assert await select_prompt_profile_version(db_session, task="script_generation", provider_id="volcano", model_id="doubao-seed-1-8-251228") == doubao
```

- [ ] **Step 2: Run and confirm current one-active-per-task limitation**

Run: `cd backend && python -m pytest -q tests/test_prompt_profile_versioning.py`

Expected: FAIL because current updates overwrite one `PromptSkill` row and activation deactivates all user skills for the task.

- [ ] **Step 3: Define immutable Prompt Profile models**

```python
class PromptProfile(Base):
    __tablename__ = "prompt_profiles"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    key = Column(String(120), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    task = Column(String(80), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class PromptProfileVersion(Base):
    __tablename__ = "prompt_profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "version", name="uq_prompt_profile_version"),)
    id = Column(String(36), primary_key=True)
    profile_id = Column(String(36), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    stage = Column(String(80))
    content = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=dict)
    routing = Column(JSON, nullable=False, default=dict)
    output_contract = Column(String(120))
    evaluation = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="draft", index=True)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    published_at = Column(DateTime)
```

- [ ] **Step 4: Implement explicit routing precedence**

```python
ROUTING_PRECEDENCE = {
    "exact_model": 500,
    "model_family": 400,
    "provider": 300,
    "capability": 200,
    "task_generic": 100,
}


def routing_specificity(routing, provider_id, model_id, capabilities, output_contract):
    if exact_model_match(routing, provider_id, model_id, output_contract):
        return ROUTING_PRECEDENCE["exact_model"]
    if model_family_match(routing, provider_id, model_id, output_contract):
        return ROUTING_PRECEDENCE["model_family"]
    if provider_match(routing, provider_id, output_contract):
        return ROUTING_PRECEDENCE["provider"]
    if capability_match(routing, capabilities, output_contract):
        return ROUTING_PRECEDENCE["capability"]
    return ROUTING_PRECEDENCE["task_generic"] if not routing else None
```

- [ ] **Step 5: Preserve legacy Prompt Skill APIs through projection**

`GET /prompt-skills` returns the latest projected version fields. `PUT /prompt-skills/{id}` creates a new draft version when the source is published. `activate` becomes `publish` in the canonical service but retains the old response fields.

- [ ] **Step 6: Persist routing and evaluation evidence**

```python
return PromptSelection(
    profile_version_id=selected.id,
    profile_key=profile.key,
    version=selected.version,
    prompt=render(selected.content, context),
    routing_reason=reason,
    fallback_reason=fallback,
    output_contract=selected.output_contract,
    checksum=selected.checksum,
)
```

- [ ] **Step 7: Run Prompt routing and legacy API suites**

Run: `cd backend && python -m pytest -q tests/test_prompt_profile_versioning.py tests/test_prompt_skill_routing.py test_prompt_skills.py`

Expected: PASS for immutable history, multiple published model-specific profiles, legacy response compatibility, clone, preview and deletion safety.

- [ ] **Step 8: Commit Prompt Profile versioning**

```bash
git add backend/app/models/prompt_profile.py backend/app/models/__init__.py backend/app/features/prompt_profiles backend/app/services/prompt_template_router.py backend/app/services/prompt_skill_service.py backend/tests/test_prompt_profile_versioning.py backend/tests/test_prompt_skill_routing.py backend/test_prompt_skills.py
git commit -m "feat: version model-aware prompt profiles"
```

### Task 12: Persist immutable execution snapshots for every generation

**Files:**
- Create: `backend/app/features/model_config/snapshots.py`
- Modify: `backend/app/features/model_config/public.py`
- Modify: `backend/app/features/workflow_media/application/generate_media.py`
- Modify: `backend/app/features/video_generation/application/lineage.py`
- Modify: `backend/app/services/image_generation_pipeline.py`
- Modify: `backend/app/features/model_drivers/text_execution.py`
- Test: `backend/tests/test_model_execution_snapshot.py`
- Test: `backend/tests/test_workflow_media_public_contract.py`

**Interfaces:**
- Consumes: resolved binding, recipe version, Prompt selection and sanitized execution parameters.
- Produces: `create_execution_snapshot()` and `load_execution_snapshot()`; all provider submissions require a snapshot ID.

- [ ] **Step 1: Write failing immutability and secret-redaction tests**

```python
@pytest.mark.asyncio
async def test_config_edit_does_not_change_existing_execution_snapshot(db_session):
    binding = await seed_published_video_binding(db_session, api_model_id="model-v1")
    snapshot = await create_execution_snapshot(db_session, snapshot_command(binding))
    await publish_new_profile_version(db_session, binding.profile.model_id, api_model_id="model-v2")
    reloaded = await load_execution_snapshot(db_session, snapshot.id)
    assert reloaded.api_model_id == "model-v1"
    assert reloaded.profile_version_id == binding.profile.profile_version_id


def test_execution_snapshot_rejects_secrets():
    with pytest.raises(UnsafeSnapshotError):
        sanitize_snapshot_params({"api_key": "secret", "prompt": "full private prompt"})
```

- [ ] **Step 2: Run and confirm snapshots are not universally persisted**

Run: `cd backend && python -m pytest -q tests/test_model_execution_snapshot.py`

Expected: FAIL because there is no universal snapshot service.

- [ ] **Step 3: Implement an explicit snapshot command**

```python
@dataclass(frozen=True)
class ExecutionSnapshotCommand:
    user_id: str
    run_id: str | None
    job_id: str | None
    task: str
    capability: ModelCapability
    binding: ResolvedModelBinding
    recipe_version_id: str | None
    prompt_profile_version_id: str | None
    model_contract_version: str
    sanitized_params: Mapping[str, Any]
```

- [ ] **Step 4: Hash and persist only allowlisted fields**

```python
SNAPSHOT_PARAM_ALLOWLIST = frozenset({
    "duration",
    "resolution",
    "aspect_ratio",
    "native_audio",
    "reference_image_count",
    "reference_video_count",
    "reference_audio_count",
    "voice_id",
    "output_contract",
})


def sanitize_snapshot_params(params: Mapping[str, Any]) -> dict[str, Any]:
    forbidden = {"api_key", "api_secret", "authorization", "prompt", "text"} & set(params)
    if forbidden:
        raise UnsafeSnapshotError(sorted(forbidden))
    return {key: params[key] for key in SNAPSHOT_PARAM_ALLOWLIST if key in params}
```

- [ ] **Step 5: Require snapshot creation before provider submission**

```python
snapshot = await create_execution_snapshot(db, snapshot_command)
submission = await execute_generation(
    registry,
    command,
    replace(driver_context, execution_snapshot_id=snapshot.id),
)
```

- [ ] **Step 6: Run snapshot and workflow regressions**

Run: `cd backend && python -m pytest -q tests/test_model_execution_snapshot.py tests/test_workflow_media_public_contract.py tests/test_production_preflight_gates.py`

Expected: PASS; every mocked provider submission receives a persisted snapshot ID and no snapshot contains credentials or prompt正文.

- [ ] **Step 7: Commit execution snapshots**

```bash
git add backend/app/features/model_config backend/app/features/workflow_media/application/generate_media.py backend/app/features/video_generation/application/lineage.py backend/app/services/image_generation_pipeline.py backend/app/features/model_drivers/text_execution.py backend/tests/test_model_execution_snapshot.py backend/tests/test_workflow_media_public_contract.py backend/tests/test_production_preflight_gates.py
git commit -m "feat: persist immutable model execution snapshots"
```

---

## Batch 5 — Thin management APIs and the unified Model Center

### Task 13: Publish one versioned Model Center API surface

**Files:**

- Create: `backend/app/features/model_config/api/__init__.py`
- Create: `backend/app/features/model_config/api/connections.py`
- Create: `backend/app/features/model_config/api/catalog.py`
- Create: `backend/app/features/model_config/api/bindings.py`
- Create: `backend/app/features/model_config/api/recipes.py`
- Create: `backend/app/features/model_config/api/prompts.py`
- Create: `backend/app/features/model_config/api/certifications.py`
- Create: `backend/app/features/model_config/api/schemas.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py`
- Modify: `backend/app/api/v1/endpoints/prompt_skills.py`
- Test: `backend/tests/test_model_center_api.py`
- Test: `backend/test_text_model_config.py`
- Test: `backend/test_prompt_skills.py`

- [ ] **Step 1: Write API contract tests before adding routes**

```python
MODEL_CENTER_ROUTES = {
    ("get", "/api/v1/model-center/overview"),
    ("get", "/api/v1/model-center/drivers"),
    ("post", "/api/v1/model-center/providers"),
    ("put", "/api/v1/model-center/providers/{provider_id}"),
    ("get", "/api/v1/model-center/connections"),
    ("post", "/api/v1/model-center/connections"),
    ("put", "/api/v1/model-center/connections/{connection_id}"),
    ("post", "/api/v1/model-center/connections/{connection_id}/test"),
    ("get", "/api/v1/model-center/catalog"),
    ("post", "/api/v1/model-center/profiles"),
    ("post", "/api/v1/model-center/profiles/{profile_id}/versions"),
    ("put", "/api/v1/model-center/profile-versions/{profile_version_id}"),
    ("post", "/api/v1/model-center/profile-versions/{profile_version_id}/publish"),
    ("post", "/api/v1/model-center/profile-versions/{profile_version_id}/disable"),
    ("post", "/api/v1/model-center/profiles/{profile_id}/rollback"),
    ("get", "/api/v1/model-center/bindings"),
    ("post", "/api/v1/model-center/bindings"),
    ("put", "/api/v1/model-center/bindings/{binding_id}"),
    ("get", "/api/v1/model-center/recipes"),
    ("post", "/api/v1/model-center/recipes"),
    ("post", "/api/v1/model-center/recipe-versions/{recipe_version_id}/publish"),
    ("post", "/api/v1/model-center/recipe-versions/{recipe_version_id}/disable"),
    ("post", "/api/v1/model-center/recipes/{recipe_key}/rollback"),
    ("get", "/api/v1/model-center/prompt-profiles"),
    ("post", "/api/v1/model-center/prompt-profiles"),
    ("post", "/api/v1/model-center/prompt-profiles/{profile_id}/versions"),
    ("post", "/api/v1/model-center/prompt-profile-versions/{version_id}/publish"),
    ("post", "/api/v1/model-center/prompt-profile-versions/{version_id}/disable"),
    ("post", "/api/v1/model-center/prompt-profiles/{profile_id}/rollback"),
    ("post", "/api/v1/model-center/certifications"),
    ("get", "/api/v1/model-center/certifications/{run_id}"),
    ("get", "/api/v1/model-center/impact"),
}


def test_model_center_routes_are_registered(app):
    document = app.openapi()
    registered = {
        (method, path)
        for path, operations in document["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert MODEL_CENTER_ROUTES <= registered


async def test_connection_response_never_exposes_secret(client, authenticated_user):
    response = await client.get("/api/v1/model-center/connections")
    payload = response.json()["items"][0]
    assert payload["has_secret"] is True
    assert payload["secret_hint"].startswith("****")
    assert "api_key" not in payload
    assert "encrypted_secret" not in payload


async def test_publish_returns_impact_and_audit_record(client, draft_profile_version):
    response = await client.post(
        f"/api/v1/model-center/profile-versions/{draft_profile_version.id}/publish",
        json={"expected_revision": 2, "reason": "认证通过"},
    )
    assert response.status_code == 200
    assert response.json()["impact"]["affected_bindings"] == 2
    assert response.json()["audit_event_id"]
```

- [ ] **Step 2: Run and confirm the API surface is absent**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py`

Expected: FAIL because `/api/v1/model-center/*` is not registered.

- [ ] **Step 3: Define stable request and response envelopes**

```python
class PageMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class PublishRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=200)


class PublishResponse(BaseModel):
    published_version_id: str
    previous_version_id: str | None
    impact: ResourceImpact
    audit_event_id: str
```

Rules:

- all collection endpoints use `items + meta` pagination;
- secrets are write-only and responses return only `has_secret`, `secret_hint`, and `secret_updated_at`;
- every update uses `expected_revision` optimistic concurrency;
- every publish, disable, rollback, or secret replacement requires a human-readable `reason` and creates an audit record;
- internal provider payloads and exception traces never cross the API boundary.

- [ ] **Step 4: Keep handlers thin and split them by resource**

```python
router = APIRouter(prefix="/model-center")
router.include_router(connections.router, tags=["模型中心-连接"])
router.include_router(catalog.router, tags=["模型中心-目录"])
router.include_router(bindings.router, tags=["模型中心-绑定"])
router.include_router(recipes.router, tags=["模型中心-方案"])
router.include_router(prompts.router, tags=["模型中心-提示词"])
router.include_router(certifications.router, tags=["模型中心-测试"])
```

Each route handler must validate the request, call one application service, and map one response. No handler may invoke a provider SDK or import another endpoint module.

- [ ] **Step 5: Register the feature router without growing legacy endpoints**

```python
from app.features.model_config.api import router as model_center_router

api_router.include_router(model_center_router, prefix="", tags=["模型中心"])
```

Legacy `/api/v1/llm/*` and `/api/v1/prompt-skills/*` endpoints remain available during migration but delegate reads and writes to the canonical services created in Tasks 5 and 11. Their existing response fields remain unchanged.

`GET /drivers` exposes only installed driver keys, supported capabilities, parameter schema, and contract version. `POST /providers`, `POST /profiles`, and `POST /profiles/{id}/versions` let an operator configure a new model that reuses an installed protocol driver. A provider requiring an uninstalled signing, polling, upload, or response protocol remains `draft` until that driver is added in code and passes Task 6's contract suite.

Disable and rollback endpoints never mutate a published version. Disable creates the next version with `status=disabled`; rollback copies the selected historical content into the next version, revalidates it, and publishes that new head with an audit event. Provider and connection updates use `enabled=false` soft disable; no Model Center endpoint physically deletes history.

- [ ] **Step 6: Add error codes that a user can act on**

```python
MODEL_CENTER_ERRORS = {
    "secret_unreadable": "密钥无法解密，请重新保存当前连接的密钥后重试。",
    "connection_failed": "连接失败，请检查服务地址、密钥和网络后重试。",
    "contract_mismatch": "模型返回结构与当前驱动不兼容，请切换驱动版本或查看原始脱敏响应。",
    "capability_mismatch": "该模型不支持当前任务所需能力，请更换绑定。",
    "binding_in_use": "该绑定正被生产方案使用，请先查看影响范围再修改。",
    "revision_conflict": "配置已被其他操作更新，请刷新后重新提交。",
    "certification_required": "该版本尚未通过要求的认证级别，不能发布。",
}
```

- [ ] **Step 7: Run API and compatibility tests**

Run: `cd backend && python -m pytest -q tests/test_model_center_api.py test_text_model_config.py test_prompt_skills.py`

Expected: PASS; new routes obey pagination, redaction, optimistic concurrency, and audit rules while legacy contracts remain green.

- [ ] **Step 8: Commit the management API**

```bash
git add backend/app/features/model_config/api backend/app/api/v1/router.py backend/app/api/v1/endpoints/llm_config.py backend/app/api/v1/endpoints/prompt_skills.py backend/tests/test_model_center_api.py backend/test_text_model_config.py backend/test_prompt_skills.py
git commit -m "feat: add versioned model center management api"
```

### Task 14: Add a typed frontend Model Center client without growing `api-client.ts`

**Files:**

- Create: `frontend/src/features/model-center/types.ts`
- Create: `frontend/src/features/model-center/api.ts`
- Create: `frontend/src/features/model-center/hooks/use-model-center-overview.ts`
- Create: `frontend/src/features/model-center/hooks/use-model-connections.ts`
- Create: `frontend/src/features/model-center/hooks/use-model-bindings.ts`
- Create: `frontend/src/features/model-center/hooks/use-production-recipes.ts`
- Create: `frontend/src/features/model-center/hooks/use-prompt-profiles.ts`
- Create: `frontend/src/features/model-center/hooks/use-certification-run.ts`
- Test: `frontend/e2e/model-center-api-contract.spec.ts`

- [ ] **Step 1: Define frontend contract types matching the backend enums**

```typescript
export type ModelCapability =
  | 'text_generation'
  | 'vision_analysis'
  | 'image_generation'
  | 'speech_generation'
  | 'video_generation'
  | 'subtitle_generation'
  | 'media_render'
  | 'object_storage';
export type ConfigurationState = 'draft' | 'published' | 'disabled';
export type CertificationLevel = 'none' | 'connection' | 'contract' | 'live';
export type ModelCenterSection =
  | 'overview'
  | 'connections'
  | 'catalog'
  | 'bindings'
  | 'recipes'
  | 'prompts'
  | 'test-lab';

export interface PageResponse<T> {
  items: T[];
  meta: { page: number; page_size: number; total: number };
}

export interface ModelConnectionView {
  id: string;
  provider_id: string;
  name: string;
  base_url: string | null;
  has_secret: boolean;
  secret_hint: string | null;
  secret_updated_at: string | null;
  enabled: boolean;
  revision: number;
}
```

- [ ] **Step 2: Write browser contract tests for redaction and error mapping**

```typescript
test('connection list never renders a raw API key', async ({ page }) => {
  await mockConnections(page, [{
    id: 'conn-1', provider_id: 'volcengine', name: '主连接', base_url: null,
    has_secret: true, secret_hint: '****ef09', secret_updated_at: '2026-07-17T09:00:00Z',
    enabled: true, revision: 3,
  }]);
  await page.goto('/llm-config?section=connections');
  await expect(page.getByText('****ef09')).toBeVisible();
  await expect(page.getByText('raw-secret-value')).toHaveCount(0);
});
```

- [ ] **Step 3: Run and confirm the feature client does not exist**

Run: `cd frontend && npx playwright test e2e/model-center-api-contract.spec.ts --project=chromium`

Expected: FAIL because the Model Center client and pages are absent.

- [ ] **Step 4: Implement one typed API module using the existing public client**

```typescript
import { apiClient } from '@/lib/api-client';
import type { ModelConnectionView, PageResponse } from './types';

export const modelCenterApi = {
  listConnections: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ModelConnectionView>>(
      `/model-center/connections?page=${page}&page_size=${pageSize}`,
    ),
  testConnection: (connectionId: string) =>
    apiClient.request<CertificationRun>(
      `/model-center/connections/${connectionId}/test`,
      { method: 'POST' },
    ),
  publishProfileVersion: (profileVersionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(
      `/model-center/profile-versions/${profileVersionId}/publish`,
      { method: 'POST', body: JSON.stringify(input) },
    ),
};
```

Do not add Model Center methods to the existing hotspot `frontend/src/lib/api-client.ts`; it remains only the shared transport owner.

- [ ] **Step 5: Implement narrowly scoped hooks with invalidation ownership**

Every mutation hook must invalidate the overview and its own resource list. A publish mutation also invalidates bindings, recipes, and impact queries. Hooks must not duplicate server-side eligibility rules.

- [ ] **Step 6: Run frontend contract and type checks**

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-api-contract.spec.ts --project=chromium`

Expected: PASS with no TypeScript casts around response envelopes.

- [ ] **Step 7: Commit the typed client**

```bash
git add frontend/src/features/model-center frontend/e2e/model-center-api-contract.spec.ts
git commit -m "feat: add typed model center frontend client"
```

### Task 15: Replace fragmented settings pages with one task-oriented Model Center shell

**Files:**

- Create: `frontend/src/features/model-center/components/model-center-shell.tsx`
- Create: `frontend/src/features/model-center/components/model-center-sidebar.tsx`
- Create: `frontend/src/features/model-center/components/model-center-overview.tsx`
- Create: `frontend/src/features/model-center/components/connection-list.tsx`
- Create: `frontend/src/features/model-center/components/connection-editor.tsx`
- Create: `frontend/src/features/model-center/components/model-catalog.tsx`
- Create: `frontend/src/features/model-center/components/model-binding-list.tsx`
- Create: `frontend/src/features/model-center/components/status-badge.tsx`
- Create: `frontend/src/features/model-center/navigation.ts`
- Modify: `frontend/src/app/llm-config/page.tsx`
- Modify: `frontend/src/app/production-adapters/page.tsx`
- Modify: `frontend/src/app/prompt-skills/page.tsx`
- Modify: `frontend/src/components/layout/top-navigation.tsx`
- Modify: `frontend/src/components/production/preflight-issue-list.tsx`
- Modify: `frontend/src/features/series-runs/hooks/use-series-run-recovery.ts`
- Test: `frontend/e2e/model-center-navigation.spec.ts`
- Test: `frontend/e2e/model-center-connections.spec.ts`

- [ ] **Step 1: Lock the information architecture**

| Section | Primary question answered | Primary action |
|---|---|---|
| Overview | 当前生产是否可用 | 查看阻塞、跳转修复 |
| Connections | 密钥和服务地址是否可连接 | 新增、测试、停用连接 |
| Catalog | 模型版本支持什么能力 | 新建版本、查看契约、发布 |
| Bindings | 某个作用域实际会用哪个模型 | 修改并预览继承结果 |
| Recipes | 一条生产链如何组合文本、图像、视频和声音 | 草稿、校验、发布、回滚 |
| Prompts | 不同模型版本使用哪套提示词 | 新版本、对比、发布、回滚 |
| Test Lab | 当前配置经过哪一级验证 | 连接测试、契约测试、实模测试 |

Normal mode displays forms, state, capability badges, impact, and actionable errors. Raw request templates, provider response payloads, and JSON overrides live only in an explicitly opened “高级参数” drawer.

- [ ] **Step 2: Write navigation and context-return tests first**

```typescript
test('legacy production adapter link opens bindings and preserves return context', async ({ page }) => {
  await page.goto('/production-adapters?returnTo=%2Fstudio%3FrunId%3Drun-4');
  await expect(page).toHaveURL(/\/llm-config\?section=bindings/);
  await expect(page.getByRole('link', { name: '返回工作台' })).toHaveAttribute(
    'href', '/studio?runId=run-4',
  );
});

test('recovery action targets the exact failing capability', async ({ page }) => {
  await page.goto('/studio?runId=run-4');
  await page.getByRole('link', { name: '修复语音模型配置' }).click();
  await expect(page).toHaveURL(/section=bindings&capability=speech_generation&runId=run-4/);
});
```

- [ ] **Step 3: Run and confirm navigation is still fragmented**

Run: `cd frontend && npx playwright test e2e/model-center-navigation.spec.ts --project=chromium`

Expected: FAIL because legacy pages do not converge on one shell and do not consistently preserve return context.

- [ ] **Step 4: Make `llm-config/page.tsx` a thin server page**

```tsx
export default function ModelCenterPage({ searchParams }: Props) {
  return (
    <ModelCenterShell
      initialSection={parseModelCenterSection(searchParams.section)}
      capability={parseCapability(searchParams.capability)}
      runId={searchParams.runId}
      returnTo={safeInternalReturnTo(searchParams.returnTo)}
    />
  );
}
```

The route page only parses parameters and composes the feature. It must remain below 100 lines. Each feature component must remain below 200 lines.

- [ ] **Step 5: Add a deterministic navigation builder shared by every shortcut**

```typescript
export function modelCenterHref(input: {
  section: ModelCenterSection;
  capability?: ModelCapability;
  runId?: string;
  returnTo?: string;
}) {
  const params = new URLSearchParams({ section: input.section });
  if (input.capability) params.set('capability', input.capability);
  if (input.runId) params.set('runId', input.runId);
  if (input.returnTo) params.set('returnTo', safeInternalReturnTo(input.returnTo));
  return `/llm-config?${params.toString()}`;
}
```

Use this builder in preflight issues, recovery actions, Studio model status, TTS, video generation, Quick Start, and the top navigation. No caller may build Model Center query strings by hand.

- [ ] **Step 6: Convert legacy pages into compatibility redirects**

```tsx
// /production-adapters
redirect(modelCenterHref({
  section: 'bindings',
  returnTo: searchParams.returnTo,
  capability: parseCapability(searchParams.capability),
}));

// /prompt-skills
redirect(modelCenterHref({
  section: 'prompts',
  returnTo: searchParams.returnTo,
  capability: parseCapability(searchParams.capability),
}));
```

These paths remain valid bookmarks; they do not own a second copy of model or prompt state.

- [ ] **Step 7: Implement overview, connection, catalog, and binding sections**

Overview must show:

- publishable production recipes and their active versions;
- missing or failed bindings grouped by `text/image/video/speech`;
- connections whose credentials are unreadable or tests expired;
- active Prompt Profile coverage for every published binding;
- last contract and live certification times;
- “去处理” actions carrying exact `section`, `capability`, `runId`, and `returnTo` values.

Connection editing must use replace-only secret inputs. Existing keys are never placed back into a form. Bindings must show inherited source, effective model version, connection, certification level, and affected recipe count before save.

- [ ] **Step 8: Run navigation, connection, and current Studio regressions**

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-navigation.spec.ts e2e/model-center-connections.spec.ts e2e/studio-workspace.spec.ts --project=chromium`

Expected: PASS; all quick actions reach the exact Model Center section and can return to the originating Studio run.

- [ ] **Step 9: Commit the Model Center shell**

```bash
git add frontend/src/app/llm-config frontend/src/app/production-adapters frontend/src/app/prompt-skills frontend/src/features/model-center/components frontend/src/features/model-center/navigation.ts frontend/src/components/layout/top-navigation.tsx frontend/src/components/production/preflight-issue-list.tsx frontend/src/features/series-runs/hooks/use-series-run-recovery.ts frontend/e2e/model-center-navigation.spec.ts frontend/e2e/model-center-connections.spec.ts
git commit -m "feat: unify model configuration in model center"
```

### Task 16: Add recipe composition, Prompt versioning, and tiered certification UX

**Files:**

- Create: `frontend/src/features/model-center/components/recipe-list.tsx`
- Create: `frontend/src/features/model-center/components/recipe-editor.tsx`
- Create: `frontend/src/features/model-center/components/recipe-pipeline.tsx`
- Create: `frontend/src/features/model-center/components/prompt-profile-list.tsx`
- Create: `frontend/src/features/model-center/components/prompt-profile-editor.tsx`
- Create: `frontend/src/features/model-center/components/prompt-profile-diff.tsx`
- Create: `frontend/src/features/model-center/components/test-lab.tsx`
- Create: `frontend/src/features/model-center/components/certification-run-panel.tsx`
- Create: `frontend/src/features/model-center/components/impact-dialog.tsx`
- Create: `frontend/src/features/model-center/components/advanced-parameters-drawer.tsx`
- Test: `frontend/e2e/model-center-recipes.spec.ts`
- Test: `frontend/e2e/model-center-prompts.spec.ts`
- Test: `frontend/e2e/model-center-test-lab.spec.ts`

- [ ] **Step 1: Write recipe composition tests before implementing the editor**

```typescript
test('native-audio video recipe disables separate TTS but keeps subtitle policy', async ({ page }) => {
  await page.goto('/llm-config?section=recipes');
  await page.getByRole('button', { name: '新建生产方案' }).click();
  await page.getByLabel('视频内生语音').check();
  await expect(page.getByLabel('独立语音合成')).toBeDisabled();
  await expect(page.getByLabel('字幕来源')).toHaveValue('video_dialogue_timeline');
  await expect(page.getByText('首帧仅作为生成约束，不进入成片')).toBeVisible();
});

test('publishing a prompt profile displays affected model versions and recipes', async ({ page }) => {
  await page.goto('/llm-config?section=prompts');
  await page.getByRole('button', { name: '发布此版本' }).click();
  await expect(page.getByRole('dialog', { name: '发布影响确认' })).toContainText('2 个模型版本');
  await expect(page.getByRole('dialog', { name: '发布影响确认' })).toContainText('1 个生产方案');
});
```

- [ ] **Step 2: Run and confirm the composition UI is absent**

Run: `cd frontend && npx playwright test e2e/model-center-recipes.spec.ts e2e/model-center-prompts.spec.ts e2e/model-center-test-lab.spec.ts --project=chromium`

Expected: FAIL because recipe, Prompt Profile, and certification panels do not exist.

- [ ] **Step 3: Implement a constrained production pipeline editor**

The editor renders ordered task slots rather than an unrestricted graph:

```text
小说理解(text.analysis)
  -> 剧本与分镜(text.storyboard)
  -> 参考资产(image.reference)
  -> 镜头视频(video.shot; native_audio=true|false)
  -> 独立配音(speech.dialogue; only when native_audio=false)
  -> 字幕(subtitle.source=video_dialogue_timeline|tts_timeline)
  -> 合成(local_ffmpeg)
  -> 一致性评审(text.review + deterministic metrics)
```

For each slot the user selects a binding, not a raw provider/model ID. The editor shows the effective model, driver, contract version, inherited scope, Prompt Profile, and latest certification. Invalid combinations are rejected before save.

- [ ] **Step 4: Expose strategy labels, not concrete model names, in production choices**

The selectable strategy labels are `draft_fast`, `final_quality`, `low_cost`, `direct_av_first`, and `separate_video_tts`. Their resolved bindings remain visible in the detail panel, but business workflows persist only the published recipe version ID.

- [ ] **Step 5: Implement Prompt Profile editing with immutable version history**

The editor has structured fields for system contract, task template, input mapping, output schema, negative constraints, model-family overrides, validation fixtures, and release notes. Publishing requires:

- JSON schema validation;
- at least one deterministic fixture pass;
- coverage for every capability and model family targeted by the profile;
- impact preview and publish reason;
- a one-click rollback that republishes the selected historical version as a new head version.

- [ ] **Step 6: Implement three explicit certification levels**

| Level | Provider call | Cost warning | Required before |
|---|---:|---:|---|
| Connection | Yes, minimal health request | Low/known | Saving an enabled connection |
| Contract | Mock or low-cost real request selected by driver | Show estimate | Publishing a model profile version |
| Live | Real text/image/audio/video output | Mandatory budget and no-retry choice | Marking a recipe `production_ready` |

The live form requires user scope, recipe version, chapter/run context, selected shots, budget ceiling, retry policy, storage policy, and an explicit “本次会产生真实费用” acknowledgement. Connection and contract tests must remain runnable without a four-chapter workflow.

- [ ] **Step 7: Add actionable failure presentation**

Every failed run shows: failed stage, stable error code, plain-language reason, sanitized provider request summary, sanitized response evidence, cost already incurred, retry eligibility, and one or more actions among “修改连接后重试”, “切换绑定后重试”, “修改高级参数后重试”, “从失败阶段继续”, and “返回工作台”.

- [ ] **Step 8: Run Model Center UI, accessibility, and build checks**

Run: `cd frontend && npm run typecheck && npm run build && npx playwright test e2e/model-center-recipes.spec.ts e2e/model-center-prompts.spec.ts e2e/model-center-test-lab.spec.ts --project=chromium`

Expected: PASS; no UI stores a provider/model ID in a production recipe and no publish operation skips impact confirmation.

- [ ] **Step 9: Commit recipe, Prompt, and certification UX**

```bash
git add frontend/src/features/model-center/components frontend/e2e/model-center-recipes.spec.ts frontend/e2e/model-center-prompts.spec.ts frontend/e2e/model-center-test-lab.spec.ts
git commit -m "feat: add recipe prompt and certification workflows"
```

---

## Batch 6 — Data migration, shadow cutover, and four-chapter acceptance

### Task 17: Backfill canonical records and compare them with legacy reads

**Files:**

- Create: `backend/app/features/model_config/backfill.py`
- Create: `backend/app/features/model_config/shadow_compare.py`
- Create: `backend/app/features/model_config/settings.py`
- Create: `backend/scripts/backfill_model_center.py`
- Modify: `backend/app/features/model_config/repository.py`
- Modify: `backend/app/features/model_config/bindings.py`
- Test: `backend/tests/test_model_center_backfill.py`
- Test: `backend/tests/test_model_center_shadow_compare.py`

- [ ] **Step 1: Write idempotent backfill tests against an isolated database**

```python
async def test_backfill_links_existing_config_without_copying_plaintext_secret(db_session, legacy_config):
    report = await backfill_model_center(db_session, apply=True)
    connection = await get_connection_for_legacy_config(db_session, legacy_config.id)
    assert report.connections_created == 1
    assert connection.legacy_config_id == legacy_config.id
    assert connection.encrypted_secret == legacy_config.encrypted_api_key
    assert connection.encrypted_secret != legacy_config.api_key


async def test_backfill_is_idempotent(db_session, seeded_legacy_catalog):
    first = await backfill_model_center(db_session, apply=True)
    second = await backfill_model_center(db_session, apply=True)
    assert first.created_total > 0
    assert second.created_total == 0
    assert second.updated_total == 0


async def test_check_mode_never_writes(db_session, seeded_legacy_catalog):
    before = await table_counts(db_session)
    report = await backfill_model_center(db_session, apply=False)
    assert report.planned_total > 0
    assert await table_counts(db_session) == before
```

- [ ] **Step 2: Run and confirm the backfill is absent**

Run: `cd backend && python -m pytest -q tests/test_model_center_backfill.py tests/test_model_center_shadow_compare.py`

Expected: FAIL because no canonical backfill or comparison service exists.

- [ ] **Step 3: Implement check-first backfill rules**

Backfill mapping is deterministic:

| Legacy source | Canonical target | Identity rule |
|---|---|---|
| `LLMProvider` | `ModelProvider` | normalized provider code |
| `LLMModel` | `ModelProfile` + initial `ModelProfileVersion` | provider code + API model ID + capability |
| `LLMConfig` | `ModelConnection` | user ID + legacy config ID |
| current default config | user-level `ModelBinding` | user ID + task + capability |
| production strategy metadata | initial `ProductionRecipeVersion` | strategy code + schema version |
| active `PromptSkill` | initial `PromptProfileVersion` | task + provider/model selector + content hash |

Existing encrypted secret bytes are linked or copied as encrypted bytes only; the script must never print, decrypt, or re-encrypt them during backfill.

- [ ] **Step 4: Provide explicit CLI modes**

```bash
cd backend
python scripts/backfill_model_center.py --check --user-id dev-user-001
python scripts/backfill_model_center.py --apply --user-id dev-user-001 --report output/model-center-backfill.json
python scripts/backfill_model_center.py --compare --user-id dev-user-001 --sample-size 100
```

`--check` is the default when no mode flag is supplied. `--apply` refuses to run without a database backup acknowledgement flag in non-SQLite environments. Reports contain IDs, counts, hashes, and differences but no credentials or prompt bodies.

- [ ] **Step 5: Introduce an explicit read-mode enum**

```python
class ModelCenterReadMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"


MODEL_CENTER_READ_MODE: ModelCenterReadMode = ModelCenterReadMode.SHADOW
```

In `shadow` mode, legacy results drive production and canonical results are compared asynchronously after resolution. Differences are recorded as sanitized audit events. In `canonical` mode, canonical results drive production while legacy routes remain compatibility projections. Switching back to `legacy` requires no data rollback.

- [ ] **Step 6: Require zero high-severity diffs before canonical cutover**

High severity means different capability, provider, API model ID, credential connection, Prompt version, native-audio policy, or output contract. Canonical reads may be enabled only after:

- 100 sampled resolutions across text, image, video, and speech have zero high-severity differences;
- deterministic four-chapter browser tests pass in both modes;
- the operator exports the comparison report and records the cutover reason.

- [ ] **Step 7: Run migration and compatibility checks**

Run: `cd backend && python -m pytest -q tests/test_model_center_backfill.py tests/test_model_center_shadow_compare.py test_text_model_config.py test_prompt_skills.py tests/test_production_strategy_routing.py`

Expected: PASS; backfill is idempotent, check mode is read-only, and legacy mode resolves exactly as before.

- [ ] **Step 8: Commit backfill and shadow cutover**

```bash
git add backend/app/features/model_config/backfill.py backend/app/features/model_config/shadow_compare.py backend/app/features/model_config/settings.py backend/scripts/backfill_model_center.py backend/app/features/model_config/repository.py backend/app/features/model_config/bindings.py backend/tests/test_model_center_backfill.py backend/tests/test_model_center_shadow_compare.py
git commit -m "feat: add safe model center backfill and shadow reads"
```

### Task 18: Run deterministic end-to-end acceptance from the frontend

**Files:**

- Create: `frontend/e2e/model-center-four-chapter-workflow.spec.ts`
- Modify: `frontend/e2e/four-chapter-series-run.spec.ts`
- Create: `backend/tests/test_model_center_four_chapter_contract.py`
- Create: `docs/testing/model-center-four-chapter-acceptance.md`

- [ ] **Step 1: Define the deterministic four-chapter fixture**

The fixture contains exactly four ordered chapters, recurring characters, two recurring locations, one continuity prop, dialogue in every chapter, and two selected key shots. Provider calls are mocked at the driver boundary while real frontend routes, backend APIs, persistence, polling, Qiniu URL mapping, synthesis, subtitles, and consistency aggregation remain active.

- [ ] **Step 2: Write the frontend journey before enabling canonical reads**

```typescript
test('creates and completes a four-chapter series through a published recipe', async ({ page }) => {
  await loginAsDevUser(page);
  await page.goto('/quick-start');
  await createFourChapterNovel(page, fourChapterFixture);
  await selectProductionRecipe(page, 'final_quality');
  await startSeriesRun(page);
  await expectEpisodeTabs(page, 4);
  await approveReferenceAssets(page);
  await selectKeyShots(page, ['chapter-1-shot-2', 'chapter-4-shot-3']);
  await generateSelectedShots(page);
  await expectNativeAudioAndSubtitles(page, 2);
  await expectPublicQiniuMedia(page);
  await expectConsistencyEvidence(page, ['style', 'character', 'scene', 'prop', 'event', 'voice', 'story']);
  await returnToStudio(page);
});
```

- [ ] **Step 3: Run and confirm the new acceptance test fails before cutover wiring**

Run: `cd frontend && npx playwright test e2e/model-center-four-chapter-workflow.spec.ts --project=chromium`

Expected: FAIL at recipe selection or canonical binding evidence.

- [ ] **Step 4: Add deterministic provider fixtures per capability**

Fixtures must cover:

- text: structured screenplay/storyboard and consistency-review schemas;
- image: synchronous response, asynchronous task response, and MiniMax non-standard response;
- video: asynchronous Seedance-style result with native audio and no reference image inserted into output;
- speech: standard TTS response for the separate-audio recipe even though the native-audio acceptance path does not call it;
- delivery: Qiniu public URL mapping and expired-signature refresh;
- subtitles: dialogue-timeline subtitle file and final burn-in or sidecar policy evidence.

- [ ] **Step 5: Exercise both read modes in backend contract tests**

```python
@pytest.mark.parametrize("read_mode", ["legacy", "canonical"])
async def test_four_chapter_contract_is_behaviorally_equivalent(read_mode, app, four_chapter_fixture):
    result = await execute_fixture(app, four_chapter_fixture, read_mode=read_mode)
    assert result.chapter_count == 4
    assert result.selected_video_count == 2
    assert result.public_media_count >= 4
    assert result.subtitle_count == 2
    assert result.consistency_dimensions == {
        "style", "character", "scene", "prop", "event", "voice", "story"
    }
```

- [ ] **Step 6: Run targeted backend and frontend acceptance**

Run: `cd backend && python -m pytest -q tests/test_model_center_four_chapter_contract.py tests/test_workflow_media_public_contract.py tests/test_media_delivery_qiniu.py tests/test_production_preflight_gates.py`

Expected: PASS in both `legacy` and `canonical` modes.

Run: `cd frontend && npm run typecheck && npx playwright test e2e/model-center-four-chapter-workflow.spec.ts e2e/four-chapter-series-run.spec.ts --project=chromium`

Expected: PASS with four visible episodes, two completed key-shot videos, native audio, subtitles, public media URLs, and seven-dimensional consistency evidence.

- [ ] **Step 7: Record the operator acceptance guide**

The guide must contain exact frontend entry points, fixture name, expected visible states, evidence download locations, safe cleanup, and separate instructions for deterministic and paid-real runs. It must explicitly state that a mocked deterministic pass is not proof that a provider credential or paid endpoint is live.

- [ ] **Step 8: Commit deterministic acceptance coverage**

```bash
git add frontend/e2e/model-center-four-chapter-workflow.spec.ts frontend/e2e/four-chapter-series-run.spec.ts backend/tests/test_model_center_four_chapter_contract.py docs/testing/model-center-four-chapter-acceptance.md
git commit -m "test: cover model center four chapter production flow"
```

### Task 19: Perform a separately authorized paid-real acceptance run

**Files:**

- Create on execution day: `docs/testing/evidence/YYYY-MM-DD-model-center-live-acceptance.md`
- Create on execution day: `output/model-center-live-acceptance/manifest.json`
- Do not modify product code during the acceptance run.

- [ ] **Step 1: Obtain fresh run-specific authorization**

Authorization must name the user configuration (`sunqy` unless changed), maximum spend, number of generated videos, retry policy, and whether native video audio or separate TTS is required. Prior authorization from an older run is not reused.

- [ ] **Step 2: Preflight without spending**

From the frontend Test Lab:

1. select the published recipe version;
2. run connection and contract certification for text, image, video, and speech bindings;
3. verify Qiniu public mapping and signed-URL refresh;
4. confirm the estimated total is within the newly authorized budget;
5. set automatic retries to the authorized value, defaulting to zero;
6. save the certification IDs and selected model/profile versions.

- [ ] **Step 3: Create a new four-chapter novel from Quick Start**

The test must originate from the visible frontend, not a direct database or API seed. Record the resulting novel ID, chapter IDs, series-run ID, recipe version ID, execution snapshot IDs, and screenshot of four episode tabs.

- [ ] **Step 4: Generate reference assets and only two selected key-shot videos**

The selected shots must exercise one recurring character and one recurring prop across distant chapters. For `direct_av_first`, enable the video model's native-audio switch, pass dialogue and audio constraints to the video request, do not call TTS, and generate subtitles from the persisted dialogue timeline. Reference images constrain generation but must not appear as an extra first frame in the final video.

- [ ] **Step 5: Poll to terminal states and collect sanitized evidence**

Collect provider task IDs, timestamps, model/profile/driver/Prompt versions, public Qiniu URLs, duration, audio-stream metadata, subtitle timeline, cost, retries, layout score, layout threshold, failed stage if any, and seven-dimensional consistency scores. Never record API keys, authorization headers, full private prompts, or unredacted provider bodies.

- [ ] **Step 6: Verify the deliverables from the frontend**

Acceptance requires all of the following:

- the new novel and four ordered chapters are visible;
- the Studio shows four episodes and can return from every repair link;
- two selected videos play from public Qiniu URLs;
- neither video contains a spurious reference-image first frame;
- each video contains the expected native voice and audible dialogue;
- subtitle text, timing, speaker order, and video audio agree;
- style, character, scene, prop, event, voice, and story consistency each have evidence and a result;
- the exact model combination can be reproduced from execution snapshots;
- no automatic retry occurred when retry count was set to zero.

- [ ] **Step 7: Stop on failure; do not patch product code inside the paid run**

If a failure occurs, preserve the failed job and sanitized evidence, classify the failed stage, return to the relevant Model Center or Studio repair action, and end the paid run unless the current authorization explicitly allows retry. Product fixes start a new TDD batch and a fresh paid authorization is required after the fix.

- [ ] **Step 8: Write the evidence report**

The report concludes with separate results for code contract, frontend operation, provider availability, media delivery, audiovisual sync, subtitles, consistency, budget, and overall acceptance. “Configured” and “live verified” must be reported as different states.

---

## Release sequence and rollback matrix

| Gate | Default mode after gate | Promotion condition | Rollback action |
|---|---|---|---|
| Batch 1 | legacy reads | catalog redaction and stable secret restart test pass | revert catalog/secret commit; no schema change |
| Batch 2 | legacy reads | additive migration and driver contract suites pass | leave additive tables unused; restore previous code |
| Batch 3 | legacy reads | every existing provider passes canonical driver contract | route calls back to existing adapters |
| Batch 4 | shadow-ready | bindings, recipes, Prompt versions, and snapshots pass | disable canonical resolver and continue legacy reads |
| Batch 5 | shadow | new Model Center and legacy UI/API compatibility pass | restore legacy page entry points; keep canonical data |
| Batch 6 deterministic | canonical candidate | zero high-severity shadow diffs and full deterministic E2E pass | set `MODEL_CENTER_READ_MODE=legacy` |
| Batch 6 paid-real | canonical | newly authorized live run passes all acceptance dimensions | retain canonical data, set read mode to shadow or legacy, publish prior recipe version |

Database rollback does not drop additive tables in production. Code rollback changes read mode and routing only. Published profile, Prompt, binding, and recipe versions are immutable; operational rollback publishes or reactivates a prior version instead of editing history.

## Required verification at each boundary

### Backend targeted gate

```bash
cd backend
python -m pytest -q \
  tests/test_model_center_security.py \
  tests/test_model_center_domain.py \
  tests/test_model_center_migrations.py \
  tests/test_model_center_repository.py \
  tests/test_model_driver_contract.py \
  tests/test_model_binding_resolution.py \
  tests/test_production_recipe_contract.py \
  tests/test_prompt_profile_versioning.py \
  tests/test_model_execution_snapshot.py \
  tests/test_model_center_api.py \
  tests/test_model_center_backfill.py \
  tests/test_model_center_shadow_compare.py
```

Expected: PASS with no network dependency.

### Existing backend behavior gate

```bash
cd backend
python -m pytest -q \
  test_text_model_config.py \
  test_prompt_skills.py \
  test_production_adapters.py \
  tests/test_model_execution_contract.py \
  tests/test_production_strategy_routing.py \
  tests/test_workflow_media_public_contract.py \
  tests/test_minimax_tts_request_contract.py \
  tests/test_workflow_media_tts_model_config.py \
  tests/test_image_provider_response_contract.py \
  tests/test_media_delivery_qiniu.py
```

Expected: PASS; shipped provider, strategy, media, TTS, image-response, and public-delivery behavior remains stable.

### Frontend gate

```bash
cd frontend
npm run typecheck
npm run build
npx playwright test \
  e2e/model-center-api-contract.spec.ts \
  e2e/model-center-navigation.spec.ts \
  e2e/model-center-connections.spec.ts \
  e2e/model-center-recipes.spec.ts \
  e2e/model-center-prompts.spec.ts \
  e2e/model-center-test-lab.spec.ts \
  e2e/model-center-four-chapter-workflow.spec.ts \
  e2e/four-chapter-series-run.spec.ts \
  --project=chromium
```

Expected: PASS; the new frontend entry point, every repair shortcut, and the deterministic four-chapter flow are browser-verified.

### Final repository gate

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Before each batch commit, stage only that batch's files; pre-existing media, build output, and user changes remain untracked or unstaged.

## Commit sequence

1. `fix: hide internal model catalog records`
2. `fix: secure persisted model credentials`
3. `feat: define canonical model configuration domain`
4. `feat: persist versioned model center records`
5. `feat: add canonical model catalog projection`
6. `feat: add capability driver execution contract`
7. `refactor: route model tests through provider drivers`
8. `feat: resolve scoped model bindings`
9. `feat: add versioned anime production recipes`
10. `refactor: resolve generation through model bindings`
11. `feat: version model-aware prompt profiles`
12. `feat: persist immutable model execution snapshots`
13. `feat: add versioned model center management api`
14. `feat: add typed model center frontend client`
15. `feat: unify model configuration in model center`
16. `feat: add recipe prompt and certification workflows`
17. `feat: add safe model center backfill and shadow reads`
18. `test: cover model center four chapter production flow`

Task 19 is evidence collection and produces no product-code commit. If an operational evidence commit is desired, create it separately after reviewing the report for secrets.

## Definition of done

- [ ] Text, image, video, and speech tasks resolve through the same capability-driver and scoped-binding contracts.
- [ ] A user can add, test, publish, combine, disable, and roll back providers and model versions from the frontend without editing code.
- [ ] Production workflows persist recipe and immutable execution-snapshot IDs rather than hard-coded model IDs.
- [ ] Prompt adaptation is versioned, model-family aware, fixture-tested, publishable, and reversible.
- [ ] Secrets are replace-only, encrypted with a stable key, redacted from every response and report, and survive process restart.
- [ ] Existing `/llm`, `/prompt-skills`, `/production-adapters`, workflow, media, and Studio contracts remain compatible during cutover.
- [ ] Every failure is displayed with failed stage, stable error code, human-readable recovery action, and exact return context.
- [ ] Deterministic frontend acceptance creates four chapters, exposes four episodes, generates two selected videos, preserves public Qiniu delivery, includes audio and subtitles, and produces seven-dimensional consistency evidence.
- [ ] Paid-real certification is never inferred from saved configuration and is never run without fresh budget/retry authorization.
- [ ] Canonical reads can be disabled with one configuration switch without deleting data.

## Plan self-review result

- [x] Tasks 1–18 each begin with a named failing test and expected failure; Task 19 is evidence-only and changes no behavior.
- [x] Every new interface has one owning module and one compatibility path for legacy callers.
- [x] Backend, frontend, persisted-data, URL-filter, and test capability/status enum values use the same canonical spelling.
- [x] Every schema change is additive and registered through the repository's `create_all + db_migrations` mechanism.
- [x] No planned endpoint imports an endpoint and no planned service imports an endpoint.
- [x] No listed legacy hotspot grows; the oversized `llm-config/page.tsx` is reduced to a thin route page before new UI behavior is added.
- [x] No plan step exposes, logs, copies as plaintext, or commits a credential.
- [x] Deterministic tests and live-provider certification are reported as different evidence levels.
- [x] Every paid action is isolated behind fresh authorization and an explicit cost/retry boundary.
- [x] Every rollout gate has a non-destructive read-mode or version rollback action.
