#!/usr/bin/env bash
# Wave4: init schema on docker Postgres; run PG-appropriate contracts only.
# HTTP TestClient suites that share one asyncpg connection stay on SQLite
# (see run_sqlite_media_contracts.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export AVP_TEST_DATABASE_URL="${AVP_TEST_DATABASE_URL:-postgresql+asyncpg://avp:avp_wave4_local@127.0.0.1:55432/ai_video_platform}"
export DATABASE_URL="$AVP_TEST_DATABASE_URL"
# Do not inherit a live Redis into readiness unit semantics during this job.
unset REDIS_URL || true
REPORT_DIR="${WAVE4_REPORT_DIR:-$ROOT/docs/audits/wave4-evidence}"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/pg-publication-contracts-$(date +%Y%m%d-%H%M%S).txt"
cd "$ROOT/backend"

{
  echo "database=$AVP_TEST_DATABASE_URL"
  echo "started_at=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "scope=publication_one_click+postgresql_runtime+deployment_compose_contract"
} | tee "$REPORT"

for i in $(seq 1 40); do
  if ./venv/bin/python - <<'PY'
import asyncio, asyncpg, os
async def main():
    url = os.environ["AVP_TEST_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    await conn.close()
asyncio.run(main())
PY
  then break; fi
  sleep 1
done

./venv/bin/python init_db.py 2>&1 | tee -a "$REPORT"

set +e
./venv/bin/python -m pytest -q \
  tests/test_publication_pipeline_one_click.py \
  tests/test_postgresql_runtime_contract.py \
  tests/test_production_deployment_contract.py \
  2>&1 | tee -a "$REPORT"
CODE=${PIPESTATUS[0]}
set -e
echo "pytest_exit=$CODE" | tee -a "$REPORT"
if [[ "$CODE" -eq 0 ]]; then echo "STATUS=PASS" | tee -a "$REPORT"; else echo "STATUS=FAIL" | tee -a "$REPORT"; fi
echo "report=$REPORT"
exit "$CODE"
