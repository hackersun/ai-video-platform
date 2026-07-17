# Code Health Ratchet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-behavior-change code-health ratchet that prevents new large files, long functions, oversized React components, endpoint boundary violations, and growth of registered legacy hotspots.

**Architecture:** Keep policy, baseline, scanner and tests under `tools/code_health/`. The scanner is read-only, uses Python AST for backend rules and the repository TypeScript compiler for frontend rules, and emits both terminal and JSON reports. CI first records the stable baseline, then blocks only new violations or increases beyond that baseline.

**Tech Stack:** Python 3.11 standard library, TypeScript compiler API from `frontend/node_modules/typescript`, Node.js 20, pytest, GitHub Actions, existing root npm scripts.

## Global Constraints

- Preserve all shipped behavior, stored data, API contracts, persisted workflow state, provider calls, budgets, and UI behavior.
- Do not edit `backend/app/**` or `frontend/src/**` in this plan.
- Do not generate the authoritative baseline from a dirty or mixed worktree without explicit user approval.
- The scanner must be read-only and must not import application modules, initialize the database, start servers, call providers, or write outside its explicit report path.
- New production files: target 300 lines, hard maximum 500 lines.
- New Python/TypeScript logic functions: target 50 lines, hard maximum 80 lines.
- FastAPI route handlers: hard maximum 60 lines.
- React route pages: hard maximum 300 lines; feature components: hard maximum 200 lines.
- Existing registered hotspots may keep their recorded value but must not grow.
- Endpoint modules must not import endpoint modules. Services and lower layers must not import endpoint modules.
- Exceptions require a finite maximum, reason, owner and removal condition.
- Every task is independently testable and committed separately.

---

## Execution Contract

### Intent Lock

Make architecture deterioration mechanically visible and prevent new deterioration without requiring an unsafe whole-repository refactor.

### Scope Boundaries

In scope:

- Policy schema and validation.
- Python and TypeScript/TSX code metrics.
- Import-boundary detection.
- Legacy baseline and ratchet comparison.
- Human-readable and JSON reports.
- Root npm command and CI integration.

Out of scope:

- Moving production code.
- Fixing existing large files.
- Enabling global TypeScript strict.
- Automatically rewriting files.
- Blocking on existing duplicate code in the first rollout.

### Decision Points

- D0: Stop before Task 6 if the intended baseline commit has not been selected or the worktree is not clean.
- D1: Review the first report before changing CI from report-only to required.
- D2: Any exception above the current measured value requires user approval.

### Verification Commands

```bash
python3 -m pytest -q tools/code_health/tests
python3 tools/code_health/check.py --policy tools/code_health/policy.json --baseline tools/code_health/baseline.json
npm run verify:code-health
git diff --check
```

---

### Task 1: Define and Validate the Machine-Readable Policy

**Files:**

- Create: `tools/code_health/policy.json`
- Create: `tools/code_health/policy.py`
- Create: `tools/code_health/tests/test_policy.py`
- Create: `tools/code_health/tests/__init__.py`

**Interfaces:**

- Produces: `load_policy(path: Path) -> Policy`.
- Produces: immutable `Policy`, `Limits`, `BoundaryRule`, and `ExceptionRule` dataclasses.
- Consumes: no application code.

- [ ] **Step 1: Write failing policy tests**

Create `tools/code_health/tests/test_policy.py` with tests that require finite limits and complete exceptions:

```python
from pathlib import Path

import pytest

from tools.code_health.policy import PolicyError, load_policy


def test_repository_policy_loads():
    policy = load_policy(Path("tools/code_health/policy.json"))
    assert policy.version == 1
    assert policy.limits.new_file_lines == 500
    assert policy.limits.function_lines == 80
    assert policy.limits.route_lines == 60
    assert policy.limits.react_page_lines == 300
    assert policy.limits.react_component_lines == 200


def test_exception_requires_reason_owner_and_removal_condition(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        '{"version":1,"roots":[],"exclude":[],"limits":{},'
        '"boundaries":[],"exceptions":[{"path":"legacy.py","max_file_lines":900}]}',
        encoding="utf-8",
    )
    with pytest.raises(PolicyError, match="reason.*owner.*remove_when"):
        load_policy(path)
```

- [ ] **Step 2: Run the tests and verify the import failure**

Run:

```bash
python3 -m pytest -q tools/code_health/tests/test_policy.py
```

Expected: FAIL because `tools.code_health.policy` does not exist.

- [ ] **Step 3: Implement the policy dataclasses and validation**

Create `tools/code_health/policy.py` with these public types and rules:

```python
@dataclass(frozen=True)
class Limits:
    new_file_lines: int
    function_lines: int
    route_lines: int
    react_page_lines: int
    react_component_lines: int
    endpoint_routes: int


@dataclass(frozen=True)
class BoundaryRule:
    source_glob: str
    forbidden_module_prefix: str
    code: str


@dataclass(frozen=True)
class ExceptionRule:
    path: str
    max_file_lines: int | None
    reason: str
    owner: str
    remove_when: str


class PolicyError(ValueError):
    pass


def load_policy(path: Path) -> Policy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Validate version == 1, positive integer limits, roots, boundaries,
    # and complete finite exceptions before constructing Policy.
```

Create `tools/code_health/policy.json` with the exact initial policy:

```json
{
  "version": 1,
  "roots": ["backend/app", "frontend/src"],
  "exclude": ["**/__pycache__/**", "**/.next*/**", "**/node_modules/**", "**/static/**"],
  "limits": {
    "new_file_lines": 500,
    "function_lines": 80,
    "route_lines": 60,
    "react_page_lines": 300,
    "react_component_lines": 200,
    "endpoint_routes": 10
  },
  "boundaries": [
    {
      "source_glob": "backend/app/api/v1/endpoints/**/*.py",
      "forbidden_module_prefix": "app.api.v1.endpoints",
      "code": "endpoint_imports_endpoint"
    },
    {
      "source_glob": "backend/app/services/**/*.py",
      "forbidden_module_prefix": "app.api.v1.endpoints",
      "code": "service_imports_endpoint"
    }
  ],
  "exceptions": []
}
```

- [ ] **Step 4: Run policy tests**

Run:

```bash
python3 -m pytest -q tools/code_health/tests/test_policy.py
```

Expected: PASS.

- [ ] **Step 5: Commit the policy task**

```bash
git add tools/code_health/policy.json tools/code_health/policy.py tools/code_health/tests
git commit -m "chore: define code health policy"
```

---

### Task 2: Scan Python Files and Import Boundaries

**Files:**

- Create: `tools/code_health/python_scan.py`
- Create: `tools/code_health/models.py`
- Create: `tools/code_health/tests/fixtures/python/oversized_route.py`
- Create: `tools/code_health/tests/fixtures/python/service_imports_endpoint.py`
- Create: `tools/code_health/tests/test_python_scan.py`

**Interfaces:**

- Produces: `scan_python_file(path: Path, repo_root: Path, policy: Policy) -> FileMetrics`.
- Produces: `Violation(code, path, line, actual, allowed, message)`.
- `FileMetrics` contains `effective_lines`, `functions`, `route_count`, `imports`, and `violations`.

- [ ] **Step 1: Write failing AST scanner tests**

```python
def test_route_over_60_lines_is_reported(repo_root, policy):
    metrics = scan_python_file(
        repo_root / "tools/code_health/tests/fixtures/python/oversized_route.py",
        repo_root,
        policy,
    )
    assert [(item.code, item.allowed) for item in metrics.violations] == [
        ("route_too_long", 60)
    ]


def test_service_importing_endpoint_is_reported(repo_root, policy):
    metrics = scan_python_file(
        repo_root / "tools/code_health/tests/fixtures/python/service_imports_endpoint.py",
        repo_root,
        policy,
    )
    assert any(item.code == "service_imports_endpoint" for item in metrics.violations)
```

The oversized fixture must contain one `@router.post` async function spanning exactly 61 effective source lines. The boundary fixture must import `app.api.v1.endpoints.video`.

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m pytest -q tools/code_health/tests/test_python_scan.py
```

Expected: FAIL because the scanner does not exist.

- [ ] **Step 3: Implement AST metrics**

Use `ast.parse` without importing application modules. Treat `FunctionDef` and `AsyncFunctionDef` decorated by `router.get/post/put/patch/delete` as routes. Record both absolute span and effective non-comment line count, using effective lines for policy enforcement and absolute line numbers for reporting.

The public result types must be:

```python
@dataclass(frozen=True)
class FunctionMetrics:
    name: str
    line: int
    end_line: int
    effective_lines: int
    is_route: bool


@dataclass(frozen=True)
class Violation:
    code: str
    path: str
    line: int
    actual: int | str
    allowed: int | str
    message: str


@dataclass(frozen=True)
class FileMetrics:
    path: str
    language: str
    effective_lines: int
    functions: tuple[FunctionMetrics, ...]
    route_count: int
    imports: tuple[str, ...]
    violations: tuple[Violation, ...]
```

- [ ] **Step 4: Run scanner tests**

```bash
python3 -m pytest -q tools/code_health/tests/test_python_scan.py
```

Expected: PASS.

- [ ] **Step 5: Commit the Python scanner**

```bash
git add tools/code_health/models.py tools/code_health/python_scan.py tools/code_health/tests
git commit -m "chore: scan python code health"
```

---

### Task 3: Scan TypeScript and React Functions

**Files:**

- Create: `tools/code_health/typescript_scan.mjs`
- Create: `tools/code_health/typescript_scan.py`
- Create: `tools/code_health/tests/fixtures/typescript/oversized-page.tsx`
- Create: `tools/code_health/tests/fixtures/typescript/oversized-component.tsx`
- Create: `tools/code_health/tests/test_typescript_scan.py`

**Interfaces:**

- Node command: `node tools/code_health/typescript_scan.mjs "$PWD" /tmp/ai-video-code-health-files.json` writes JSON to stdout.
- Python wrapper: `scan_typescript_files(paths, repo_root, policy) -> tuple[FileMetrics, ...]`.
- Uses `frontend/node_modules/typescript`; missing dependency is a fatal diagnostic with install guidance.

- [ ] **Step 1: Write failing TSX scanner tests**

```python
def test_route_page_over_300_lines_is_reported(repo_root, policy):
    metrics = scan_typescript_files(
        [repo_root / "tools/code_health/tests/fixtures/typescript/oversized-page.tsx"],
        repo_root,
        policy,
    )[0]
    assert any(item.code == "react_page_too_long" for item in metrics.violations)


def test_feature_component_over_200_lines_is_reported(repo_root, policy):
    metrics = scan_typescript_files(
        [repo_root / "tools/code_health/tests/fixtures/typescript/oversized-component.tsx"],
        repo_root,
        policy,
    )[0]
    assert any(item.code == "react_component_too_long" for item in metrics.violations)
```

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m pytest -q tools/code_health/tests/test_typescript_scan.py
```

Expected: FAIL because the TypeScript scanner does not exist.

- [ ] **Step 3: Implement the compiler-API scanner**

The Node scanner must use `ts.createSourceFile`, visit function declarations, methods, arrow functions and function expressions, and classify:

```javascript
const isRoutePage = normalizedPath.startsWith('frontend/src/app/') && normalizedPath.endsWith('/page.tsx');
const isComponent = fileName.endsWith('.tsx') && /^[A-Z]/.test(functionName);
```

Return JSON objects matching `FileMetrics`. Do not use regex to match braces or JSX structure.

- [ ] **Step 4: Run TSX scanner tests**

```bash
python3 -m pytest -q tools/code_health/tests/test_typescript_scan.py
```

Expected: PASS.

- [ ] **Step 5: Commit the TypeScript scanner**

```bash
git add tools/code_health/typescript_scan.mjs tools/code_health/typescript_scan.py tools/code_health/tests
git commit -m "chore: scan typescript code health"
```

---

### Task 4: Implement Baseline Serialization and Comparison

**Files:**

- Create: `tools/code_health/baseline.py`
- Create: `tools/code_health/tests/test_baseline.py`

**Interfaces:**

- Produces: `write_baseline(report, path, commit_sha) -> None`.
- Produces: `compare_to_baseline(report, baseline) -> tuple[Violation, ...]`.

- [ ] **Step 1: Write failing ratchet tests**

```python
def test_legacy_hotspot_may_shrink_but_not_grow():
    baseline = baseline_with("legacy.py", effective_lines=900)
    assert compare_to_baseline(report_with("legacy.py", effective_lines=899), baseline) == ()
    violations = compare_to_baseline(report_with("legacy.py", effective_lines=901), baseline)
    assert [item.code for item in violations] == ["legacy_file_grew"]


def test_new_file_uses_hard_limit():
    violations = compare_to_baseline(report_with("new.py", effective_lines=501), empty_baseline())
    assert [item.code for item in violations] == ["new_file_too_long"]
```

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m pytest -q tools/code_health/tests/test_baseline.py
```

Expected: FAIL because baseline comparison does not exist.

- [ ] **Step 3: Implement deterministic baseline serialization**

Construct the serialized payload from runtime values, never from copied audit numbers:

```python
payload = {
    "version": 1,
    "commit": commit_sha,
    "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
    "files": {
        item.path: {
            "effective_lines": item.effective_lines,
            "max_function_lines": max(
                (function.effective_lines for function in item.functions),
                default=0,
            ),
            "route_count": item.route_count,
        }
        for item in sorted(report.files, key=lambda value: value.path)
    },
}
```

Serialization must sort file keys and use two-space indentation. The real numeric values come only from the scanner at the selected clean commit; do not copy numbers from an older audit.

- [ ] **Step 4: Run baseline tests and commit**

```bash
python3 -m pytest -q tools/code_health/tests/test_baseline.py
git add tools/code_health/baseline.py tools/code_health/tests/test_baseline.py
git commit -m "chore: implement code health baseline comparison"
```

Expected: tests PASS and the commit contains only baseline comparison code and tests.

---

### Task 5: Build the Read-Only CLI and Reports

**Files:**

- Create: `tools/code_health/check.py`
- Create: `tools/code_health/report.py`
- Create: `tools/code_health/tests/test_cli.py`

**Interfaces:**

- CLI report mode exits `0` with no violations and `1` with blocking violations.
- `--report-only` always exits `0` after printing violations.
- `--json-report /tmp/ai-video-code-health.json` writes only the requested report file.
- `--snapshot` requires a clean worktree and writes the baseline.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_cli_is_read_only_and_returns_one_for_growth(tmp_path, repo_fixture):
    before = snapshot_tree(repo_fixture)
    result = run_cli(repo_fixture, baseline_lines=10, current_lines=11)
    after = snapshot_tree(repo_fixture)
    assert result.returncode == 1
    assert "legacy_file_grew" in result.stdout
    assert before == after


def test_report_only_returns_zero_with_visible_violations(repo_fixture):
    result = run_cli(repo_fixture, baseline_lines=10, current_lines=11, report_only=True)
    assert result.returncode == 0
    assert "legacy_file_grew" in result.stdout
```

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m pytest -q tools/code_health/tests/test_cli.py
```

Expected: FAIL because the CLI does not exist.

- [ ] **Step 3: Implement the CLI**

The CLI flow must be exactly:

```python
policy = load_policy(args.policy)
paths = discover_source_files(repo_root, policy)
report = scan_repository(paths, repo_root, policy)
violations = compare_to_baseline(report, load_baseline(args.baseline))
print(render_text_report(report, violations))
if args.json_report:
    write_json_report(args.json_report, report, violations)
return 0 if args.report_only or not violations else 1
```

- [ ] **Step 4: Run the complete tool suite**

```bash
python3 -m pytest -q tools/code_health/tests
```

Expected: PASS.

- [ ] **Step 5: Run report-only against the repository**

```bash
python3 tools/code_health/check.py --report-only --json-report /tmp/ai-video-code-health.json
python3 -m json.tool /tmp/ai-video-code-health.json >/dev/null
```

Expected: exit `0`, visible legacy findings, valid JSON, no repository changes.

- [ ] **Step 6: Commit the CLI**

```bash
git add tools/code_health/check.py tools/code_health/report.py tools/code_health/tests/test_cli.py
git commit -m "chore: add code health ratchet cli"
```

---

### Task 6: Select and Record the Stable Baseline

**Files:**

- Create: `tools/code_health/baseline.json`

**Interfaces:**

- Consumes: the scanner, policy and current clean commit.
- Produces: the authoritative version-1 baseline bound to one exact commit SHA.

- [ ] **Step 1: Enforce the clean-worktree precondition**

Run:

```bash
git status --porcelain=v1
git rev-parse HEAD
```

Expected: no status output and one commit SHA. If the worktree is not clean, stop at Decision Point D0; do not generate `baseline.json`.

- [ ] **Step 2: Generate and review the baseline**

Run:

```bash
python3 tools/code_health/check.py --snapshot --output tools/code_health/baseline.json
python3 -m json.tool tools/code_health/baseline.json >/dev/null
git diff -- tools/code_health/baseline.json
```

Expected: valid JSON containing the selected HEAD SHA and all scanned production files. Review every exception before continuing.

- [ ] **Step 3: Prove the baseline ratchet**

Run the CLI against the unchanged tree, then use the test fixtures to prove growth fails and shrinkage passes:

```bash
python3 tools/code_health/check.py --policy tools/code_health/policy.json --baseline tools/code_health/baseline.json
python3 -m pytest -q tools/code_health/tests/test_baseline.py tools/code_health/tests/test_cli.py
```

Expected: both commands PASS.

- [ ] **Step 4: Commit the reviewed baseline**

```bash
git add tools/code_health/baseline.json
git commit -m "chore: record code health baseline"
```

Expected: the commit contains only `baseline.json`.

---

### Task 7: Add Root Command and Report-Only CI

**Files:**

- Modify: `package.json`
- Modify: `.github/workflows/ci.yml`
- Test: `tools/code_health/tests/test_cli.py`

**Interfaces:**

- Produces npm script `verify:code-health`.
- Produces CI artifact `/tmp/ai-video-code-health.json`.

- [ ] **Step 1: Re-read overlapping user changes**

```bash
git diff -- package.json .github/workflows/ci.yml
```

Expected: understand and preserve every current user change. If either file has unresolved concurrent edits, stop and rebase this task before patching.

- [ ] **Step 2: Add the root command**

Add this exact script to root `package.json`:

```json
"verify:code-health": "python3 tools/code_health/check.py --policy tools/code_health/policy.json --baseline tools/code_health/baseline.json"
```

- [ ] **Step 3: Add a report-only CI step**

Before backend tests, add:

```yaml
  code-health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci --prefix frontend
      - name: Generate code health report
        run: python3 tools/code_health/check.py --report-only --json-report /tmp/ai-video-code-health.json
      - uses: actions/upload-artifact@v4
        with:
          name: code-health-report
          path: /tmp/ai-video-code-health.json
```

- [ ] **Step 4: Verify locally**

```bash
python3 -m pytest -q tools/code_health/tests
npm run verify:code-health
git diff --check
```

Expected: tests PASS, health command exits according to the selected baseline, and no whitespace errors.

- [ ] **Step 5: Commit report-only CI**

```bash
git add package.json .github/workflows/ci.yml
git commit -m "ci: report code health ratchet"
```

---

### Task 8: Promote the Ratchet to Required

**Files:**

- Modify: `.github/workflows/ci.yml`
- Modify: `docs/architecture/ai-development-governance.md`
- Test: `tools/code_health/tests/test_cli.py`

**Interfaces:**

- Makes `code-health` a required dependency for backend tests, frontend tests and Docker build.

- [ ] **Step 1: Review the report at Decision Point D1**

Confirm:

- Every failing item is either a real new violation or a finite registered legacy baseline.
- No source file is missing because of an exclude pattern.
- TypeScript scanning ran successfully.
- The scanner changed no repository file.

Do not continue if any condition is false.

- [ ] **Step 2: Remove report-only mode from CI**

Change the CI command to:

```yaml
- name: Enforce code health ratchet
  run: python3 tools/code_health/check.py --json-report /tmp/ai-video-code-health.json
```

Set the other jobs to depend on `code-health` where appropriate.

- [ ] **Step 3: Record activation**

Add an activation section to `docs/architecture/ai-development-governance.md` containing the baseline commit SHA, activation date, CI job name and command. Use real values from the merge commit; do not use placeholders.

- [ ] **Step 4: Run final verification**

```bash
python3 -m pytest -q tools/code_health/tests
npm run verify:code-health
npm run verify:frontend
git diff --check
```

Expected: all commands exit `0`. No backend full regression is required because production code is unchanged, but CI must run it before merge.

- [ ] **Step 5: Commit required enforcement**

```bash
git add .github/workflows/ci.yml docs/architecture/ai-development-governance.md
git commit -m "ci: enforce code health ratchet"
```

---

### Task 9: Create Follow-Up Plans From the Stable Report

**Files:**

- Create: `docs/superpowers/plans/2026-07-12-backend-boundary-repair.md`
- Create: `docs/superpowers/plans/2026-07-12-workflow-use-case-extraction.md`
- Create: `docs/superpowers/plans/2026-07-12-frontend-feature-client-split.md`

**Interfaces:**

- Consumes: the required code-health JSON report and current stable source.
- Produces: three independently reviewable implementation plans; no production edits.

- [ ] **Step 1: Generate the stable report**

```bash
npm run verify:code-health -- --json-report /tmp/ai-video-code-health-stable.json
```

Expected: exit `0` and a valid report tied to the stable baseline.

- [ ] **Step 2: Write the backend boundary repair plan**

The plan must cover only:

- endpoint-to-endpoint imports,
- service-to-endpoint imports,
- `series_run_live_preflight`/`series_run_orchestrator` cycle,
- visual-contract/prompt-context cycle.

It must preserve every existing route and include characterization tests before import changes.

- [ ] **Step 3: Write the workflow extraction plan**

The plan must treat these as separate tasks and commits:

- `generate_workflow_media_batch`,
- `render_workflow_package`,
- `concatenate_videos`.

Each task must name the new application service, adapter, request/result type and exact existing regression tests.

- [ ] **Step 4: Write the frontend split plan**

The plan must first extract shared HTTP transport and domain clients from `api-client.ts`, then split one page at a time. It must preserve exported types and the singleton compatibility facade until all callers migrate.

- [ ] **Step 5: Self-review and commit only the plans**

```bash
rg -n "T[B]D|T[O]DO|implement[ ]later|fill[ ]in" \
  docs/superpowers/plans/2026-07-12-backend-boundary-repair.md \
  docs/superpowers/plans/2026-07-12-workflow-use-case-extraction.md \
  docs/superpowers/plans/2026-07-12-frontend-feature-client-split.md
git diff --check
git add \
  docs/superpowers/plans/2026-07-12-backend-boundary-repair.md \
  docs/superpowers/plans/2026-07-12-workflow-use-case-extraction.md \
  docs/superpowers/plans/2026-07-12-frontend-feature-client-split.md
git commit -m "docs: plan legacy hotspot reduction"
```

Expected: `rg` returns no placeholder matches and the commit contains only plan documents.

---

## Final Acceptance

The Phase 1 governance rollout is complete only when:

1. `tools/code_health` tests pass.
2. `npm run verify:code-health` exits `0` on the selected stable baseline.
3. A new 501-line production file fails.
4. A registered legacy file growing by one effective line fails.
5. A registered legacy file shrinking passes.
6. A new endpoint-to-endpoint import fails.
7. A new service-to-endpoint import fails.
8. TypeScript scanning cannot silently skip.
9. CI uploads a report and then enforces the ratchet after D1 approval.
10. No production file, database, media artifact, provider configuration or shipped API behavior changed in this phase.
