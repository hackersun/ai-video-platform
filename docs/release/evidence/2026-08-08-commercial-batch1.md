# Commercial Batch 1 Verification Evidence

Branch: `codex/commercial-batch1-deployment-v2`

## Database and deployment

- Production Compose fails before deployment when a required secret is absent.
- Production and staging overlays pass `docker compose ... config --quiet`.
- Isolated production topology started on frontend port 3300 and API port 8800.
- PostgreSQL and Redis exposed no host ports.
- One-shot migration exited with code 0 and recorded `20260808_0001`.
- PostgreSQL contained 66 public tables after migration.
- API `/health` returned HTTP 200; frontend root returned HTTP 200.
- API and frontend containers both ran as `appuser`.
- The isolated containers, networks, and volumes were removed after verification.

## Automated verification

```text
Migration/deployment contracts: 5 passed
Focused database contracts: 26 passed
Full backend suite: 2226 passed, 2 skipped
Code-health ratchet: 0 blockers
Frontend typecheck and production build: passed (46 routes)
Backend image cold build: passed
Frontend image cold build: passed
git diff --check: passed
```

## Compatibility and rollback

- Existing API routes, table names, and local SQLite startup remain unchanged.
- `init_db.py` remains available for two release candidates while deployment uses
  `scripts/upgrade_database.py` as the versioned entry point.
- Schema downgrade is intentionally disabled. Operational rollback requires the
  pre-migration database snapshot and the previous image digest.
