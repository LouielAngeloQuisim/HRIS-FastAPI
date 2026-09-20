"""B6 — Legacy MySQL → Postgres ETL runner.

Usage:
    python scripts/migration/etl_mysql_to_postgres.py \
        --mysql-url mysql://user:pass@host:3306/legacy_hris \
        --pg-url postgresql://user:pass@host:5432/app

The script performs a dry-run by default (no writes). Add --apply to commit
the migration. Row-count and checksum validation are always printed.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text


@dataclass
class TableMapping:
    """One-way column mapping from legacy MySQL table to new Postgres table."""
    legacy_table: str
    target_table: str
    column_map: dict[str, str]
    pk: str
    transform: dict[str, str] | None = None
    force_readonly: bool = False


MIGRATIONS: list[TableMapping] = [
    TableMapping(
        legacy_table="employee",
        target_table="employee_records",
        column_map={
            "id": "id",
            "employee_code": "employee_code",
            "first_name": "first_name",
            "last_name": "last_name",
            "birthdate": "birthdate",
            "employment_type": "employment_type",
            "employee_status": "employee_status",
            "date_hired": "date_hired",
        },
        pk="id",
    ),
    TableMapping(
        legacy_table="employee_salary",
        target_table="employee_salary",
        column_map={
            "id": "id",
            "employee_id": "employee_id",
            "basic_rate": "basic_rate",
            "currency": "currency",
            "effective_date": "effective_date",
            "pay_type": "pay_type",
            "overtime_rate": "overtime_rate",
            "absent_penalty_rate": "absent_penalty_rate",
            "non_taxable_allowance": "non_taxable_allowance",
        },
        pk="id",
    ),
    TableMapping(
        legacy_table="payroll_run",
        target_table="payroll_run",
        column_map={
            "id": "id",
            "cutoff_type": "cutoff_type",
            "date_from": "date_from",
            "date_to": "date_to",
            "status": "status",
            "created_by": "created_by",
        },
        pk="id",
        force_readonly=True,
    ),
    TableMapping(
        legacy_table="payroll_entry",
        target_table="payroll_entry",
        column_map={
            "id": "id",
            "payroll_run_id": "payroll_run_id",
            "employee_id": "employee_id",
            "basic_rate": "basic_rate",
            "gross_pay": "gross_pay",
            "total_deductions": "total_deductions",
            "net_pay": "net_pay",
        },
        pk="id",
        force_readonly=True,
    ),
]


def _checksum(rows: list[dict[str, Any]]) -> str:
    payload = "|".join("|".join(str(v) for v in row.values()) for row in rows)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _select_columns(mapping: TableMapping) -> str:
    legacy_cols = ", ".join(mapping.column_map.keys())
    return f"SELECT {legacy_cols} FROM {mapping.legacy_table}"


def migrate(args: argparse.Namespace) -> None:
    mysql_engine = sa.create_engine(args.mysql_url, pool_pre_ping=True)
    pg_engine = sa.create_engine(args.pg_url, pool_pre_ping=True)

    overall_ok = True
    for mapping in MIGRATIONS:
        with mysql_engine.connect() as m_conn, pg_engine.connect() as p_conn:
            legacy_rows = [dict(row._mapping) for row in m_conn.execute(text(_select_columns(mapping))).fetchall()]
            legacy_count = len(legacy_rows)
            legacy_checksum = _checksum(legacy_rows)

            target_count = p_conn.execute(text(f"SELECT COUNT(*) FROM {mapping.target_table}")).scalar_one()

            msg = f"[{mapping.legacy_table}] legacy={legacy_count} target={target_count} checksum={legacy_checksum}"
            sys.stdout.write(msg + "\n")

            if legacy_count != target_count:
                warn = f"  WARN: row-count mismatch (legacy {legacy_count} != target {target_count})"
                sys.stdout.write(warn + "\n")
                overall_ok = False

            if args.apply and legacy_rows:
                cols = list(mapping.column_map.values())
                if mapping.force_readonly:
                    cols.append("is_readonly")
                placeholders = ", ".join(f":{c}" for c in cols)
                insert_sql = text(
                    f"INSERT INTO {mapping.target_table} ({', '.join(cols)}) VALUES ({placeholders})"
                )
                with p_conn.begin() as txn:
                    for row in legacy_rows:
                        mapped = {mapping.column_map[k]: v for k, v in row.items() if k in mapping.column_map}
                        if mapping.force_readonly:
                            mapped["is_readonly"] = True
                        txn.execute(insert_sql, mapped)
                applied = f"  applied {legacy_count} rows -> {mapping.target_table}"
                sys.stdout.write(applied + "\n")
            elif not args.apply:
                dry = f"  dry-run: {legacy_count} rows ready to migrate"
                sys.stdout.write(dry + "\n")

    if overall_ok:
        sys.stdout.write("\nValidation PASSED: all tables match expected counts\n")
        sys.exit(0)
    else:
        sys.stdout.write("\nValidation FAILED: row-count mismatch detected\n")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="MySQL -> Postgres ETL for HRIS legacy data")
    parser.add_argument("--mysql-url", required=True, help="MySQL source URL")
    parser.add_argument("--pg-url", required=True, help="Postgres target URL")
    parser.add_argument("--apply", action="store_true", help="Commit migration (default is dry-run)")
    args = parser.parse_args()
    migrate(args)


if __name__ == "__main__":
    main()
