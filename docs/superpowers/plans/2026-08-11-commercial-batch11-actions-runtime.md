# CI Actions Node 24 Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate GitHub Actions Node 20 deprecation warnings while keeping the existing CI jobs, commands, artifacts, and branch gates unchanged.

**Architecture:** Keep `.github/workflows/ci.yml` as the single workflow owner. Add one repository-level contract test that rejects every deprecated action major observed in remote CI, then upgrade only those action references to official Node 24-compatible releases.

**Tech Stack:** GitHub Actions YAML, Python 3.11, pytest.

## Global Constraints

- Do not change job names, dependencies, permissions, triggers, test commands, artifact names, or branch protection contexts.
- Only `actions/checkout`, `actions/setup-python`, `actions/setup-node`, `actions/upload-artifact`, `codecov/codecov-action`, and `docker/setup-buildx-action` are in scope.
- The accepted majors are v7 for the four `actions/*` references and Codecov, plus v4 for Docker Buildx. Official references are Node 24-compatible.
- Preserve the current commercial release gate and its G0-G8 behavior.
- User's dirty primary worktree remains untouched.

## Execution Contract

- **Intent Lock:** Replace deprecated Node 20 action runtimes with official Node 24 action majors and prevent regression.
- **Out of Scope:** Application code, dependency versions, provider integrations, billing, data schemas, UI, and production deployment.
- **Acceptance:** Contract test fails before the workflow update, passes afterward, YAML parses, all local release checks pass, and the remote PR shows no Node 20 action-runtime annotation.
- **Verification:** `pytest -q backend/tests/test_ci_action_runtime.py`; YAML parse; code health; full backend; frontend typecheck/build; remote eight-check CI.
- **Decision Point:** Never promote to `main`; merge only to `dev`, then `releases`, after all checks pass.

---

### Task 1: Add the CI action runtime ratchet and upgrade the workflow

**Files:**
- Create: `backend/tests/test_ci_action_runtime.py`
- Modify: `.github/workflows/ci.yml`
- Create: `docs/release/evidence/2026-08-11-commercial-batch11.md`

**Interfaces:**
- Consumes: GitHub Actions `uses:` references in `.github/workflows/ci.yml`.
- Produces: A pytest contract that requires v7 for the four official actions and a workflow using Node 24 action runtimes.

- [x] **Step 1: Write the failing contract test**

```python
from pathlib import Path
import re


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
REQUIRED_ACTION_MAJORS = {
    "actions/checkout": {"v7"},
    "actions/setup-python": {"v7"},
    "actions/setup-node": {"v7"},
    "actions/upload-artifact": {"v7"},
    "codecov/codecov-action": {"v7"},
    "docker/setup-buildx-action": {"v4"},
}


def test_ci_uses_node24_action_majors() -> None:
    references = re.findall(
        r"uses:\s*([\w.-]+/[\w.-]+)@(v\d+)",
        WORKFLOW.read_text(encoding="utf-8"),
    )
    observed = {
        action: {major for name, major in references if name == action}
        for action in REQUIRED_ACTION_MAJORS
    }

    assert observed == REQUIRED_ACTION_MAJORS


def test_codecov_v7_uses_supported_files_input() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "file: ./backend/coverage.xml" not in workflow
    assert "files: ./backend/coverage.xml" in workflow
```

- [x] **Step 2: Run the test and verify RED**

Run: `pytest -q backend/tests/test_ci_action_runtime.py`

Expected: FAIL because at least one observed Action still uses a Node 20-era major.

- [x] **Step 3: Apply the minimal workflow update**

Replace every in-scope `uses:` reference with its accepted major. Make no other workflow changes.

- [x] **Step 4: Run focused GREEN verification**

Run: `pytest -q backend/tests/test_ci_action_runtime.py backend/tests/test_commercial_release_attestation.py`

Expected: all tests pass.

- [x] **Step 5: Record evidence and run batch verification**

Record the root cause, official release/runtime evidence, exact diff, local verification, rollback, and remote acceptance in `docs/release/evidence/2026-08-11-commercial-batch11.md`.

Run:

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
python tools/code_health/check.py --policy tools/code_health/policy.json --baseline tools/code_health/baseline.json
pytest -q backend/tests
cd frontend && npm run typecheck && npm run build
```

- [ ] **Step 6: Commit, push, and verify the release path**

Commit only the three task files. Create a PR to `dev`, wait for all eight checks, confirm the run has no Node 20 deprecation annotation, merge, promote `dev` to `releases`, and leave `main` unchanged.
