#!/usr/bin/env bash
# Wave4: media/readiness contracts on isolated SQLite (safe for TestClient).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
unset AVP_TEST_DATABASE_URL DATABASE_URL REDIS_URL || true
REPORT_DIR="${WAVE4_REPORT_DIR:-$ROOT/docs/audits/wave4-evidence}"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/sqlite-media-contracts-$(date +%Y%m%d-%H%M%S).txt"
cd "$ROOT/backend"
{
  echo "started_at=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "scope=health_readiness+object_storage_g4+private_media_access"
} | tee "$REPORT"
set +e
./venv/bin/python -m pytest -q \
  tests/test_health_readiness.py \
  tests/test_object_storage_g4.py \
  tests/test_private_media_access.py \
  2>&1 | tee -a "$REPORT"
CODE=${PIPESTATUS[0]}
set -e
echo "pytest_exit=$CODE" | tee -a "$REPORT"
if [[ "$CODE" -eq 0 ]]; then echo "STATUS=PASS" | tee -a "$REPORT"; else echo "STATUS=FAIL" | tee -a "$REPORT"; fi
echo "report=$REPORT"
exit "$CODE"
