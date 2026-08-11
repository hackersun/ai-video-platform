# Commercial Batch 1: Reproducible Deployment and Migration Plan

**Goal:** Make one commit produce reproducible frontend/backend images and a versioned database bootstrap without changing existing APIs, table names, or local SQLite startup.

## Execution Contract

### Intent Lock

The same source revision and required environment values must produce the same service topology and a database stamped at the same migration revision.

### Scope Boundaries

In scope:

- Keep the root Compose file as an explicitly development-only compatibility entry.
- Add staging and production Compose definitions with no example secrets, host-exposed data services, or source mounts.
- Add an Alembic version ledger and a transitional upgrade command.
- Preserve `init_db.py` as the schema bootstrap/compatibility implementation for two release candidates while all legacy migration functions are moved into Alembic revisions incrementally.
- Add deployment and migration contract tests plus CI gates.

Out of scope:

- Authentication/session behavior, organization RBAC, billing, private object storage, and durable task queues.
- Renaming tables, changing API routes, or rewriting existing migration functions.
- Automatic destructive downgrade or production database restore.

### Constraints

- Production configuration fails before container start when database password, Fernet key, or public URLs are absent.
- PostgreSQL and Redis are reachable only on the private Compose network.
- Application containers run as their existing non-root users.
- Migration is a one-shot service; the API starts only after it succeeds.
- Existing databases are upgraded by the compatibility bootstrap and then stamped; empty databases follow the same path.
- No schema downgrade is claimed safe. Rollback means restore a pre-migration snapshot and the previous image.

### Acceptance Criteria

1. `docker compose -f infra/compose/production.yml config` succeeds with explicit test secrets and fails when a required secret is missing.
2. Production Compose contains no fixed password, host-published PostgreSQL/Redis port, source bind mount, or development command.
3. A blank SQLite database upgrades to Alembic head and contains application tables plus `alembic_version`.
4. An existing legacy SQLite database upgrades without losing a sentinel row and is stamped at head.
5. The PostgreSQL CI job upgrades through the migration command and runs the existing dialect contract.
6. Backend/frontend images build and the production topology passes health checks.

### Verification Commands

```bash
python3 -m pytest -q backend/tests/test_deployment_compose_contract.py \
  backend/tests/test_alembic_bridge.py
DATABASE_URL=sqlite+aiosqlite:////tmp/ai-video-migration.db \
  python3 backend/scripts/upgrade_database.py
docker compose --env-file infra/compose/test.env \
  -f infra/compose/production.yml config
npm run verify:code-health
npm run verify:backend
npm run verify:frontend
git diff --check
```

### Rollback

- Do not run a schema downgrade.
- Stop the new application image, restore the database snapshot taken before the one-shot migration, and redeploy the previous image digest.
- `init_db.py` remains callable during two release candidates for local/tests and emergency compatibility only.

## Tasks

1. Add failing deployment and migration contract tests.
2. Add Alembic configuration, baseline marker, and the transitional upgrade command.
3. Add production/staging Compose definitions and required-environment examples without real secrets.
4. Wire CI to exercise SQLite, PostgreSQL, Compose configuration, and Docker builds.
5. Run the full verification set, review the diff, open a PR to `dev`, and merge only after all required checks pass.
