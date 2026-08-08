# Commercial Readiness Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a recoverable repository, branch, CI and commercial-readiness foundation without moving production modules or changing shipped APIs.

**Architecture:** Work only in `codex/commercial-readiness-foundation`, forked from `main`. Reuse the approved code-health ratchet as the machine boundary, add human-readable repository and release truth sources, then archive legacy remote branches before creating the protected `dev` and `releases` lanes.

**Tech Stack:** Git and GitHub CLI, GitHub Actions, Python 3.11 standard library and pytest, Node.js 20, Next.js 14, existing root npm verification scripts.

## Global Constraints

- Preserve shipped behavior, stored data, API contracts, provider calls, budgets and workflow state.
- Never force-push `main`.
- Do not remove any local worktree or branch in this plan.
- Do not delete tracked media until a verified external archive exists.
- Do not move `backend/app/**` or `frontend/src/**` production modules in this plan.
- The code-health scanner is read-only and starts in report-only CI mode.
- Remote `dev` must be archived at the exact legacy SHA before replacement.
- Repository visibility remains unchanged until license and sensitive-history audits complete.
- Every code change starts with a failing test; human-only documentation is validated for links, placeholders and whitespace.

---

## Execution Contract

### Intent Lock

Create a safe governance base from which the project can become commercially operable without destabilizing current product development.

### Scope Boundaries

In scope:

- One baseline behavior repair required to make the current main testable.
- Commercial governance design and phased risk plan.
- Repository directory map and generated-artifact policy.
- Code-health policy, scanner, stable baseline and report-only CI job.
- PR template, CODEOWNERS and dependency update configuration.
- Recoverable remote branch archive and creation of `dev` and `releases`.

Out of scope:

- Authentication migration.
- Alembic/PostgreSQL migration repair.
- Production Docker topology.
- Frontend login, dashboard or Quick Start redesign.
- Billing, quota or provider settlement implementation.
- Git history rewriting or object pruning.

### Verification Commands

```bash
python3 -m pytest -q backend/tests/test_entity_auto_approval_policy.py \
  backend/tests/test_entity_extraction_quality.py \
  backend/tests/test_entity_review_service.py \
  backend/tests/test_series_run_asset_repair.py \
  backend/tests/test_series_run_skill_routing.py
python3 -m pytest -q tools/code_health/tests
npm run verify:code-health
npm run verify:frontend
npm run verify:backend
git diff --check
```

### Decision Points

- D0: Do not replace remote `dev` until `archive/dev-legacy-20260808` resolves to the legacy SHA.
- D1: Do not make code health blocking in CI until a report from the stable baseline has been reviewed.
- D2: Do not change repository visibility during this plan.
- D3: Do not merge to `main` until the final verification suite is green.

---

### Task 1: Restore a Green Stable Baseline

**Files:**

- Create: `backend/app/features/entity_review/approval_policy.py`
- Modify: `backend/app/services/entity_review_service.py`
- Create: `backend/tests/test_entity_auto_approval_policy.py`
- Modify: `backend/tests/test_entity_review_service.py`

**Interfaces:**

- Produces: `can_auto_approve_candidate(quality, *, allow_auto_approve, has_approval_evidence) -> bool`.
- Produces: `mention_has_approval_evidence(mention) -> bool`.
- Preserves: default deterministic candidates remain review candidates.
- Changes only: an explicitly authorized, evidence-backed, high-quality deterministic chapter candidate may be approved.

- [x] **Step 1: Reproduce the two baseline failures**

Run the full backend suite and record the failing asset-repair and series-skill tests.

- [x] **Step 2: Add the caller-authorization contract test**

Require the same verified deterministic candidate to remain `candidate` without authorization and become `approved` with `allow_auto_approve=True`.

- [x] **Step 3: Implement the focused approval policy**

Allow the override only when score is at least 86 and the only quality flag is `deterministic_requires_review`; all evidence, noise and caller gates remain active.

- [x] **Step 4: Verify the affected contract set**

Run the five named entity and series test modules. Expected: all pass.

- [x] **Step 5: Commit separately**

Commit message: `fix: reconcile entity approval safety gates`.

---

### Task 2: Publish Repository and Commercial Governance Truth Sources

**Files:**

- Create: `docs/superpowers/specs/2026-08-08-commercial-readiness-governance-design.md`
- Create: `docs/architecture/repository-layout.md`
- Create: `docs/release/branching-strategy.md`
- Create: `docs/release/commercial-release-gates.md`
- Create: `docs/security/commercial-security-baseline.md`
- Create: `docs/product/commercial-readiness-roadmap.md`
- Modify: `README.md`

**Interfaces:**

- `repository-layout.md` owns directory responsibilities and generated-artifact placement.
- `branching-strategy.md` owns branch naming, merge direction and hotfix back-propagation.
- `commercial-release-gates.md` owns release evidence and rollback requirements.
- `commercial-security-baseline.md` owns auth, RBAC, audit and secret-management requirements.
- `commercial-readiness-roadmap.md` owns the ordered P0/P1/P2 program.

- [ ] **Step 1: Write the repository layout map**

Document every current top-level directory, its target location, allowed contents and migration rule. Explicitly mark `backend/static`, `test-results`, `.playwright-cli`, `tmp` and runtime databases as non-source artifacts.

- [ ] **Step 2: Write the branch strategy**

Define the exact `feature/* -> dev -> releases -> main -> vX.Y.Z` flow, required checks, hotfix back-propagation and archive procedure.

- [ ] **Step 3: Write the commercial release gates**

Require build, SQLite/PostgreSQL tests, security, backup/restore, model canary, media delivery, cost ledger, provider reconciliation and formal UAT evidence.

- [ ] **Step 4: Write the security baseline and roadmap**

Record fail-closed production configuration, token rotation, RBAC matrix, audit log, rate limits, data retention and phased product/UX work.

- [ ] **Step 5: Correct README navigation only**

Replace links to absent architecture with links to the real repository map, branch strategy and release gates. Do not claim Docker or commercial readiness that is not verified.

- [ ] **Step 6: Validate and commit**

```bash
rg -n "T[B]D|T[O]DO|implement[ ]later|fill[ ]in" \
  docs/architecture/repository-layout.md docs/release docs/security docs/product
git diff --check
```

Expected: no placeholder matches and no whitespace errors. Commit message: `docs: define repository and release governance`.

---

### Task 3: Implement the Existing Code-Health Ratchet Plan

**Files:**

- Follow: `docs/superpowers/plans/2026-07-12-code-health-ratchet-implementation.md`, Tasks 1 through 7.
- Create: `tools/code_health/**`
- Modify: `package.json`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**

- Produces: `npm run verify:code-health`.
- Produces: a policy-bound, stable-commit `tools/code_health/baseline.json`.
- Produces: `/tmp/ai-video-code-health.json` in CI report mode.
- Does not import application modules, initialize a database or modify production sources.

- [ ] **Step 1: Execute policy, Python and TypeScript scanner TDD cycles**

Follow Tasks 1-3 of the ratchet plan and commit each independent scanner layer.

- [ ] **Step 2: Execute baseline and CLI TDD cycles**

Follow Tasks 4-5. Prove growth fails, shrinkage passes and report-only remains exit zero.

- [ ] **Step 3: Generate the stable baseline**

Run only from a clean worktree and bind the snapshot to the exact governance branch commit.

- [ ] **Step 4: Add root command and report-only CI**

Follow Task 7. Do not promote it to blocking during this plan.

- [ ] **Step 5: Verify and commit**

```bash
python3 -m pytest -q tools/code_health/tests
npm run verify:code-health
git diff --check
```

Expected: all commands exit zero. Commit message for CI integration: `ci: report code health ratchet`.

---

### Task 4: Add GitHub Collaboration Controls

**Files:**

- Create: `.github/CODEOWNERS`
- Create: `.github/pull_request_template.md`
- Create: `.github/dependabot.yml`

**Interfaces:**

- CODEOWNERS assigns root governance, auth/security, migrations, providers, workflow and frontend production surfaces.
- PR template requires intent, compatibility, data, security, cost, UX, tests and rollback evidence.
- Dependabot scans GitHub Actions and both npm lockfiles weekly; pip is documented but only enabled after a supported pinned manifest is introduced.

- [ ] **Step 1: Add CODEOWNERS**

Use `@hackersun` as the initial owner for the repository and sensitive paths.

- [ ] **Step 2: Add the PR template**

Include checked sections for scope, API/data/provider compatibility, verification commands, screenshots, rollout and rollback.

- [ ] **Step 3: Add Dependabot**

Configure `github-actions`, root `npm` and `/frontend` `npm` update groups with a weekly schedule and five-open-PR limit.

- [ ] **Step 4: Validate YAML and commit**

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
yaml.safe_load(Path('.github/dependabot.yml').read_text())
PY
git diff --check
```

Expected: YAML parses and whitespace check passes. Commit message: `chore: add repository collaboration controls`.

---

### Task 5: Create Recoverable Remote Branch Lanes

**Files:**

- No source files.
- Remote refs: `archive/dev-legacy-20260808`, optional legacy feature archives, `dev`, `releases`.

**Interfaces:**

- Consumes the exact remote SHAs from `git ls-remote --heads origin`.
- Produces archive refs that preserve every replaced SHA.
- Produces `dev` and `releases` from the accepted protected main SHA.

- [ ] **Step 1: Capture remote refs**

```bash
git ls-remote --heads origin > /tmp/ai-video-remote-heads-before.txt
```

- [ ] **Step 2: Push and verify archives**

Push each legacy SHA to its archive branch, re-read `ls-remote`, and compare exact values before replacing anything.

- [ ] **Step 3: Establish branch lanes**

After the governance branch is accepted into `main`, create `releases` and rebuild `dev` from that same main SHA. Never force `main`.

- [ ] **Step 4: Apply GitHub rules**

Use GitHub rulesets or branch protection to require PRs, checks, approvals, conversation resolution, and prohibit force-push/delete on all three lanes.

- [ ] **Step 5: Verify remote state**

```bash
git ls-remote --heads origin main dev releases archive/dev-legacy-20260808
gh api repos/hackersun/ai-video-platform/rulesets
```

Expected: archive equals the old dev SHA; new lanes equal the accepted main SHA; active rulesets are visible.

---

### Task 6: Final Verification and Integration Handoff

**Files:**

- Review all files changed since `379efa6132b1ac6b41814b38623fcb3d27d9f5ec`.

- [ ] **Step 1: Run focused governance tests**

```bash
python3 -m pytest -q tools/code_health/tests
npm run verify:code-health
```

- [ ] **Step 2: Run complete local verification**

```bash
npm run verify:frontend
npm run verify:backend
git diff --check
```

- [ ] **Step 3: Review scope and commits**

```bash
git status --short
git log --oneline 379efa6132b1ac6b41814b38623fcb3d27d9f5ec..HEAD
git diff --stat 379efa6132b1ac6b41814b38623fcb3d27d9f5ec..HEAD
```

Expected: clean worktree, scoped commits, no generated artifacts.

- [ ] **Step 4: Perform inline code review**

Check security boundaries, false-positive/false-negative scanner cases, baseline provenance, documentation truthfulness and remote rollback instructions. Resolve all critical and important findings.

- [ ] **Step 5: Present integration options**

Use the finishing-development-branch workflow. Do not merge, push or remove the worktree without the selected integration action.

---

## Follow-Up Projects

The following remain independent plans because they touch different high-risk systems:

1. PostgreSQL/Alembic and production container recovery.
2. Authentication, session rotation and organization RBAC.
3. Persistent task queue, idempotency and provider reconciliation.
4. Object storage, media retention and signed delivery.
5. Login/register/reset unification and landing-page commercialization.
6. Dashboard data truth and Quick Start commercial production mode.
7. Usage ledger, quota, settlement, refund and finance operations.

Each follow-up must have its own design, TDD plan, migration/rollback path and commercial acceptance evidence.
