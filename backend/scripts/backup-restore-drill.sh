#!/usr/bin/env bash
# ============================================================================
# Backend Phase B7 — Backup/Restore Drill
#
# Usage:
#   1. Ensure the current backend database is reachable (compose up -d).
#   2. Run: bash scripts/backup-restore-drill.sh
#
# The script dumps the current Postgres database to a timestamped SQL file
# under backend/backups/, then restores it into a throwaway database named
# `hris_backup_drill` to verify the dump is valid and non-empty.
# It exits non-zero on any failure so CI can gate on it.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Repo root is two levels up from backend/scripts (backend -> repo root), which
# is where the shared .env lives.
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="$SCRIPT_DIR/../backups"
DRILL_DB="hris_backup_drill"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="$BACKUP_DIR/drill_dump_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

# Load env vars if present
if [[ -f "$REPO_ROOT/.env" ]]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

POSTGRES_USER="${POSTGRES_USER:-hris}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-hris_secret}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-hris}"

export PGPASSWORD="$POSTGRES_PASSWORD"

echo "[1/3] Dumping database '$POSTGRES_DB' -> $DUMP_FILE ..."
pg_dump \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    > "$DUMP_FILE"

DUMP_SIZE=$(wc -c < "$DUMP_FILE")
echo "      Dump size: ${DUMP_SIZE} bytes"

if [[ "$DUMP_SIZE" -lt 1024 ]]; then
    echo "ERROR: Dump file is suspiciously small ($DUMP_SIZE bytes)" >&2
    exit 1
fi

echo "[2/3] Creating drill database '$DRILL_DB' ..."
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DRILL_DB\";" >/dev/null 2>&1 || true
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$DRILL_DB\";" >/dev/null

echo "[3/3] Restoring dump into '$DRILL_DB' ..."
psql \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$DRILL_DB" \
    -f "$DUMP_FILE" \
    >/dev/null

TABLE_COUNT=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$DRILL_DB" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
echo "      Tables restored: $TABLE_COUNT"

if [[ "$TABLE_COUNT" -lt 10 ]]; then
    echo "ERROR: Restored database has too few tables ($TABLE_COUNT)" >&2
    psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE \"$DRILL_DB\";" >/dev/null 2>&1 || true
    exit 1
fi

echo "[cleanup] Removing drill database ..."
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE \"$DRILL_DB\";" >/dev/null 2>&1 || true

echo "DRILL PASSED: dump=$DUMP_FILE size=${DUMP_SIZE}B tables=$TABLE_COUNT"
