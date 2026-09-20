from __future__ import annotations

import argparse
import hashlib
import sys

import sqlalchemy as sa
from sqlalchemy import text

TABLES = [
    "employee_records",
    "employee_salary",
    "payroll_run",
    "payroll_entry",
]


def _checksum(rows: list[tuple]) -> str:
    payload = "|".join("|".join(str(v) for v in row) for row in rows)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def validate(args: argparse.Namespace) -> int:
    mysql = sa.create_engine(args.mysql_url, pool_pre_ping=True)
    pg = sa.create_engine(args.pg_url, pool_pre_ping=True)

    all_ok = True
    for table in TABLES:
        with mysql.connect() as m, pg.connect() as p:
            legacy_rows = m.execute(text(f"SELECT * FROM {table}")).fetchall()
            target_rows = p.execute(text(f"SELECT * FROM {table}")).fetchall()
            legacy_count = len(legacy_rows)
            target_count = len(target_rows)
            legacy_sum = _checksum([tuple(r) for r in legacy_rows])
            target_sum = _checksum([tuple(r) for r in target_rows])

            match = "MATCH" if legacy_sum == target_sum else "MISMATCH"
            count_ok = legacy_count == target_count
            status = "PASS" if (match == "MATCH" and count_ok) else "FAIL"

            line = f"[{table}] legacy={legacy_count} target={target_count} count={'OK' if count_ok else 'FAIL'} checksum={match} -> {status}"
            sys.stdout.write(line + "\n")
            if status == "FAIL":
                all_ok = False

    if all_ok:
        sys.stdout.write("\nValidation PASSED: all tables match\n")
        return 0
    else:
        sys.stdout.write("\nValidation FAILED: mismatches detected\n")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate migration row counts and checksums")
    parser.add_argument("--mysql-url", required=True)
    parser.add_argument("--pg-url", required=True)
    args = parser.parse_args()
    return validate(args)


if __name__ == "__main__":
    main()
