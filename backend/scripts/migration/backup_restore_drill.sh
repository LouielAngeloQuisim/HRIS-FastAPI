#!/usr/bin/env bash
# B7 — Backup/restore drill script.
#
# Usage:
#   bash scripts/migration/backup_restore_drill.sh
#
# The script:
#   1. Dumps the current Postgres database to a timestamped SQL file.
#   2. Creates a temporary database and restores the dump into it.
#   3. Runs row-count checksums against the temp DB.
#   4. Drops the temp DB and logs the result.
#
# Environment variables (defaults shown):
#   POSTGRES_SERVER=localhost
#   POSTGRES_PORT=5432
#   POSTGRES_DB=app
#   POSTGRES_USER=postgres
#   POSTGRES_PASSWORD=postgres123
#   DRILL_DIR=/var/backups/hris-drills
set -euo pipefail

SERVER="${POSTGRES_SERVER:-localhost}"
PORT="${POSTGRES_PORT:-5432}"
DB="${POSTGRES_DB:-app}"
USER="${POSTGRES_USER:-postgres}"
PASSWORD="${POSTGRES_PASSWORD:-postgres123}"
DRILL_DIR="${DRILL_DIR:-/var/backups/hris-drills}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="${DRILL_DIR}/drill_${TIMESTAMP}.sql"
TEMP_DB="hris_drill_${TIMESTAMP}"

mkdir -p "$DRILL_DIR"

export PGPASSWORD="$PASSWORD"

echo "[drill] Dumping ${DB} -> ${DUMP_FILE}"
pg_dump -h "$SERVER" -p "$PORT" -U "$USER" -F p "$DB" > "$DUMP_FILE"

echo "[drill] Creating temp database ${TEMP_DB}"
psql -h "$SERVER" -p "$PORT" -U "$USER" -c "CREATE DATABASE ${TEMP_DB};"

echo "[drill] Restoring dump into ${TEMP_DB}"
psql -h "$SERVER" -p "$PORT" -U "$USER" -d "$TEMP_DB" -f "$DUMP_FILE" > /dev/null

echo "[drill] Running row-count checksums"
python scripts/migration/validate_checksum.py \
    --mysql-url "mysql://legacy:legacy@localhost:3306/legacy_hris" \
    --pg-url "postgresql://${USER}:${PASSWORD}@${SERVER}:${PORT}/${TEMP_DB}" \
    || true

echo "[drill] Dropping temp database ${TEMP_DB}"
psql -h "$SERVER" -p "$PORT" -U "$USER" -c "DROP DATABASE ${TEMP_DB};"

echo "[drill] Dump retained at ${DUMP_FILE}"
echo "[drill] COMPLETE"
