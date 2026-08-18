# Server RC Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reproducible, same-origin, backup-first deployment candidate for the clean `main` revision without changing application behavior.

**Architecture:** A production-only Compose file runs Caddy as the sole public entry, Next.js and FastAPI on an internal network, and private PostgreSQL/Redis services with named volumes. Versioned release directories, a server-owned environment file, database backups, health checks, and a `current` symlink provide non-destructive rollout and rollback.

**Tech Stack:** Docker Compose, Caddy, Next.js 14, FastAPI, PostgreSQL 15, Redis 7, POSIX shell.

## Global Constraints

- Do not modify or replace the development `docker-compose.yml`.
- Never store live credentials in Git or the release archive.
- Do not expose PostgreSQL or Redis host ports.
- Persist PostgreSQL data and backend-generated media.
- Build and deploy only the clean commit recorded in `ops/deploy/VERSION`.
- Back up the database before replacing an active release.
- Keep the previous release available for rollback.

---

### Task 1: Lock the production topology

**Files:**
- Create: `backend/tests/test_production_deployment_contract.py`
- Create: `compose.production.yml`
- Create: `ops/deploy/Caddyfile`
- Create: `ops/deploy/production.env.example`
- Modify: `frontend/Dockerfile`

- [ ] Write contract tests for private infrastructure, health checks, secret injection, same-origin routing, and immutable frontend build behavior.
- [ ] Run `pytest -q backend/tests/test_production_deployment_contract.py` and confirm it fails before the files exist.
- [ ] Add the minimal production topology and frontend build argument.
- [ ] Run the contract test and `docker compose --env-file ops/deploy/production.env.example -f compose.production.yml config`.

### Task 2: Add deployment and rollback operations

**Files:**
- Create: `ops/deploy/install-docker-ubuntu.sh`
- Create: `ops/deploy/deploy.sh`
- Create: `ops/deploy/healthcheck.sh`
- Create: `ops/deploy/rollback.sh`
- Create: `ops/deploy/package-release.sh`
- Create: `ops/deploy/VERSION`
- Create: `docs/deployment/server-rc-operations.md`

- [ ] Extend the contract test for strict shell mode, environment validation, backup-before-cutover, health verification, and rollback.
- [ ] Implement focused scripts with no embedded credentials or host-specific passwords.
- [ ] Run `bash -n ops/deploy/*.sh` and the deployment contract test.
- [ ] Build a source archive and verify its SHA-256 manifest.

### Task 3: Verify and stage the server candidate

**Files:**
- Modify only generated release artifacts outside Git.

- [ ] Run frontend typecheck and production build.
- [ ] Run targeted backend deployment, database configuration, authentication, and health tests.
- [ ] Upload the immutable archive and checksum to the remote user's staging directory.
- [ ] Recompute the checksum remotely and record the sudo/Docker installation gate.
