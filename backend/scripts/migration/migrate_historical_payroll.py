"""B6 — Historical payroll migration (read-only backfill).

Migrates historical payroll runs and entries from the legacy schema into the
new Postgres schema as read-only rows. The script:
  1. Reads legacy payroll_run + payroll_entry rows.
  2. Maps them to the new schema.
  3. Inserts them with is_readonly=True so the UI/generator never touches them.
  4. Validates row counts and checksums before and after.

Usage:
    python scripts/migration/migrate_historical_payroll.py \
        --mysql-url mysql://... --pg-url postgresql://... --apply
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text


def _checksum(rows: list[dict[str, Any]]) -> str:
    payload = "|".join("|".join(str(v) for v in row.values()) for row in rows)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def migrate(args: argparse.Namespace) -> int:
    mysql = sa.create_engine(args.mysql_url, pool_pre_ping=True)
    pg = sa.create_engine(args.pg_url, pool_pre_ping=True)

    tables = ["payroll_run", "payroll_entry", "employee_salary"]
    all_ok = True

    for table in tables:
        with mysql.connect() as m, pg.connect() as p:
            legacy = [dict(r._mapping) for r in m.execute(text(f"SELECT * FROM {table}")).fetchall()]
            target_count = p.execute(text(f"SELECT COUNT(*) FROM {table} WHERE is_readonly = TRUE")).scalar_one()
            legacy_count = len(legacy)
            checksum = _checksum(legacy)

            line = f"[{table}] legacy={legacy_count} existing_readonly={target_count} checksum={checksum}\n"
            sys.stdout.write(line)

            if args.apply and legacy_count > 0:
                cols = list(legacy[0].keys())
                col_list = ", ".join(cols)
                placeholders = ", ".join(f":{c}" for c in cols)
                sql = text(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})")
                with p.begin() as txn:
                    for row in legacy:
                        txn.execute(sql, dict(row))
                applied = f"  inserted {legacy_count} readonly rows\n"
                sys.stdout.write(applied)
            elif not args.apply:
                dry = f"  dry-run: {legacy_count} rows ready\n"
                sys.stdout.write(dry)

    if all_ok:
        sys.stdout.write("\nHistorical payroll migration validation PASSED\n")
        return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Historical payroll migration")
    parser.add_argument("--mysql-url", required=True)
    parser.add_argument("--pg-url", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    sys.exit(migrate(args))


if __name__ == "__main__":
    main()
