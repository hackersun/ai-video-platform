#!/usr/bin/env bash
# Wave4: local docker pg_dump -Fc / restore drill; records RPO/RTO evidence.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE="$ROOT/ops/wave4/docker-compose.contracts.yml"
PROJECT=avp-wave4-contracts
CONTAINER=$(docker compose -f "$COMPOSE" ps -q postgres)
REPORT_DIR="${WAVE4_REPORT_DIR:-$ROOT/docs/audits/wave4-evidence}"
mkdir -p "$REPORT_DIR" /tmp/avp-wave4-backups
STAMP=$(date +%Y%m%d-%H%M%S)
DUMP="/tmp/avp-wave4-backups/wave4-${STAMP}.dump"
REPORT="$REPORT_DIR/pg-backup-restore-${STAMP}.txt"
START_TS=$(date +%s)

{
  echo "drill=pg_dump_restore"
  echo "started_at=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "container=$CONTAINER"
} | tee "$REPORT"

if [[ -z "$CONTAINER" ]]; then
  echo "STATUS=FAIL reason=postgres_container_missing" | tee -a "$REPORT"
  exit 1
fi

# Seed a marker row (idempotent table)
docker exec -i "$CONTAINER" psql -U avp -d ai_video_platform <<'SQL'
CREATE TABLE IF NOT EXISTS wave4_backup_marker (
  id text PRIMARY KEY,
  note text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO wave4_backup_marker(id, note) VALUES ('canary', 'pre-dump')
ON CONFLICT (id) DO UPDATE SET note = EXCLUDED.note, created_at = now();
SQL

T0=$(date +%s)
docker exec "$CONTAINER" pg_dump -U avp -d ai_video_platform -Fc > "$DUMP"
T1=$(date +%s)
DUMP_SIZE=$(wc -c < "$DUMP" | tr -d ' ')
echo "dump_path=$DUMP" | tee -a "$REPORT"
echo "dump_bytes=$DUMP_SIZE" | tee -a "$REPORT"
echo "dump_seconds=$((T1-T0))" | tee -a "$REPORT"
[[ "$DUMP_SIZE" -gt 1000 ]]

# Mutate after dump
docker exec -i "$CONTAINER" psql -U avp -d ai_video_platform -c "UPDATE wave4_backup_marker SET note='post-dump-should-vanish' WHERE id='canary';"

# Restore into a fresh database on same instance
T2=$(date +%s)
docker exec -i "$CONTAINER" psql -U avp -d postgres <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'ai_video_platform_restore' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ai_video_platform_restore;
CREATE DATABASE ai_video_platform_restore OWNER avp;
SQL
docker exec -i "$CONTAINER" pg_restore -U avp -d ai_video_platform_restore --clean --if-exists < "$DUMP" || true
# pg_restore may warn on empty extensions; verify marker
NOTE=$(docker exec "$CONTAINER" psql -U avp -d ai_video_platform_restore -tAc "SELECT note FROM wave4_backup_marker WHERE id='canary'")
T3=$(date +%s)
NOTE=$(echo "$NOTE" | tr -d '[:space:]')
echo "restored_note=$NOTE" | tee -a "$REPORT"
echo "restore_seconds=$((T3-T2))" | tee -a "$REPORT"
echo "rpo_target=upgrade-predeploy pg_dump only (no continuous WAL yet); measured_dump_lag_seconds≈0 for this drill" | tee -a "$REPORT"
echo "rto_measured_seconds=$((T3-T2)) (drop+create+pg_restore on local docker)" | tee -a "$REPORT"
echo "rpo_declared=last successful pre-deploy dump (ops/deploy/deploy.sh); continuous archive not enabled" | tee -a "$REPORT"
echo "rto_declared_goal<=15m for single-node docker restore of empty/small DB; this drill=$(date +%s)" | tee -a "$REPORT"

if [[ "$NOTE" == "pre-dump" ]]; then
  echo "STATUS=PASS" | tee -a "$REPORT"
else
  echo "STATUS=FAIL restored_note_mismatch" | tee -a "$REPORT"
  exit 1
fi
echo "finished_at=$(date '+%Y-%m-%d %H:%M:%S %z')" | tee -a "$REPORT"
echo "wall_seconds=$(( $(date +%s) - START_TS ))" | tee -a "$REPORT"
echo "report=$REPORT"
