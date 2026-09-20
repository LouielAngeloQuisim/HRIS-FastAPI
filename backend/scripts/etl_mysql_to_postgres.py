"""Phase B6 ETL: legacy MySQL -> new Postgres payroll data.

Usage:
    uv run python scripts/etl_mysql_to_postgres.py --dry-run

Configuration via environment variables:
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
    POSTGRES_DSN (or individual POSTGRES_HOST/PORT/USER/PASSWORD/DB)

The script is idempotent: rows whose PK already exists in Postgres are
skipped. A JSON manifest is written to ``scripts/etl_manifest.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

try:
    import pymysql  # type: ignore[import-untyped]
except ImportError:
    pymysql = None  # type: ignore[assignment]

try:
    import psycopg  # type: ignore[import-untyped]
except ImportError:
    psycopg = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Table mapping configuration
# ---------------------------------------------------------------------------

TABLES: list[dict[str, Any]] = [
    {
        "name": "divisions",
        "source_table": "division",
        "target_table": "division",
        "pk": "id",
        "columns": [
            "id",
            "name",
            "description",
            "is_active",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_active": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
        },
    },
    {
        "name": "departments",
        "source_table": "department",
        "target_table": "department",
        "pk": "id",
        "columns": [
            "id",
            "name",
            "description",
            "division_id",
            "is_active",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_active": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
        },
    },
    {
        "name": "employee_records",
        "source_table": "employee_records",
        "target_table": "employee_records",
        "pk": "id",
        "columns": [
            "id",
            "employee_code",
            "first_name",
            "last_name",
            "birthdate",
            "email",
            "contact_number",
            "employment_type",
            "employee_status",
            "date_hired",
            "position_id",
            "division_id",
            "department_id",
            "subdivision_id",
            "is_active",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_active": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
            "birthdate": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
            "date_hired": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
        },
    },
    {
        "name": "employee_salary",
        "source_table": "employee_salary",
        "target_table": "employee_salary",
        "pk": "id",
        "columns": [
            "id",
            "employee_id",
            "basic_rate",
            "currency",
            "effective_date",
            "pay_type",
            "overtime_rate",
            "absent_penalty_rate",
            "non_taxable_allowance",
            "de_minimis_monthly",
            "thirteenth_month_exempt_portion",
            "is_active",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_active": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
            "effective_date": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
        },
    },
    {
        "name": "payroll_run",
        "source_table": "payroll_run",
        "target_table": "payroll_run",
        "pk": "id",
        "columns": [
            "id",
            "cutoff_type",
            "date_from",
            "date_to",
            "status",
            "adjustment_type",
            "created_by",
            "is_readonly",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_readonly": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
            "date_from": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
            "date_to": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
        },
    },
    {
        "name": "payroll_entry",
        "source_table": "payroll_entry",
        "target_table": "payroll_entry",
        "pk": "id",
        "columns": [
            "id",
            "payroll_run_id",
            "employee_id",
            "basic_rate",
            "rate_date_from",
            "rate_date_to",
            "earnings",
            "deductions",
            "gross_pay",
            "total_deductions",
            "net_pay",
            "overtime_pay",
            "thirteenth_month",
            "non_taxable_income",
            "taxable_income",
            "is_readonly",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_readonly": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
            "rate_date_from": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
            "rate_date_to": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
        },
    },
    {
        "name": "loan",
        "source_table": "loan",
        "target_table": "loan",
        "pk": "id",
        "columns": [
            "id",
            "employee_id",
            "loan_type",
            "principal",
            "balance",
            "terms_months",
            "start_date",
            "is_active",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_active": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
            "start_date": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
        },
    },
    {
        "name": "loan_amortization",
        "source_table": "loan_amortization",
        "target_table": "loan_amortization",
        "pk": "id",
        "columns": [
            "id",
            "loan_id",
            "due_date",
            "amount",
            "remaining_balance",
            "is_paid",
            "paid_date",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        ],
        "type_map": {
            "is_paid": lambda v: bool(v),
            "is_deleted": lambda v: bool(v),
            "due_date": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
            "paid_date": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v),
        },
    },
]


# FK columns that reference another migrated table (legacy int -> new UUID).
# ``None`` means the legacy value has no counterpart in the new schema (e.g.
# legacy ``created_by`` user ids and un-migrated lookup tables) and is forced to
# SQL NULL. See docs/etl-column-mapping.md §ID Mapping Strategy.
FK_TARGETS: dict[str, dict[str, str | None]] = {
    "departments": {"division_id": "division"},
    "employee_records": {
        "position_id": None,
        "division_id": "division",
        "department_id": "department",
        "subdivision_id": None,
    },
    "employee_salary": {"employee_id": "employee_records"},
    "payroll_run": {"created_by": None},
    "payroll_entry": {"payroll_run_id": "payroll_run", "employee_id": "employee_records"},
    "loan": {"employee_id": "employee_records"},
    "loan_amortization": {"loan_id": "loan"},
}

# Historical payroll data must be immutable in the new system (plan §7 / §5.5).
READONLY_TABLES = {"payroll_run", "payroll_entry"}

_ID_NAMESPACE = uuid.UUID("6f1c4a2e-0f9b-4d3a-9f6e-9c2b7a5d1e30")


def legacy_id_to_uuid(table: str, legacy_id: Any) -> str:
    """Deterministically derive a UUID for a legacy integer PK.

    Deterministic (uuid5) so re-running the ETL is idempotent and FK targets can
    always be resolved from the legacy id alone.
    """
    return str(uuid.uuid5(_ID_NAMESPACE, f"{table}:{legacy_id}"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def get_mysql_config() -> dict[str, Any]:
    return {
        "host": _env("MYSQL_HOST", "localhost"),
        "port": int(_env("MYSQL_PORT", "3306")),
        "user": _env("MYSQL_USER", "root"),
        "password": _env("MYSQL_PASSWORD", ""),
        "database": _env("MYSQL_DB", "legacy_hris"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor if pymysql else None,
    }


def get_postgres_dsn() -> str:
    dsn = _env("POSTGRES_DSN")
    if dsn:
        return dsn
    return (
        f"postgresql://{_env('POSTGRES_USER', 'postgres')}:{_env('POSTGRES_PASSWORD', 'postgres')}"
        f"@{_env('POSTGRES_HOST', 'localhost')}:{_env('POSTGRES_PORT', '5432')}"
        f"/{_env('POSTGRES_DB', 'hris')}"
    )


def _canonical_value(value: Any) -> Any:
    """Normalise a value so source (MySQL) and target (Postgres) match.

    Numeric types collapse to a canonical decimal string, datetimes to ISO, and
    containers are normalised recursively.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        try:
            return format(Decimal(str(value)).normalize(), "f")
        except Exception:
            return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _canonical_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(v) for v in value]
    return str(value)


def row_checksum(row: dict[str, Any]) -> str:
    payload = json.dumps(_canonical_value(row), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def transform_row(
    row: dict[str, Any],
    columns: list[str],
    type_map: dict[str, Any],
    *,
    table_name: str | None = None,
    id_map: dict[str, dict[str, str]] | None = None,
    fk_targets: dict[str, str | None] | None = None,
    force_readonly: bool = False,
) -> dict[str, Any]:
    """Transform a legacy MySQL row into the Postgres shape.

    - generates a deterministic UUID for the legacy PK,
    - rewrites FK columns to the UUID of the referenced migrated row,
    - forces ``is_readonly = TRUE`` for historical payroll tables,
    - applies the per-column ``type_map``.
    """
    out: dict[str, Any] = {}
    legacy_id = row.get("id")
    for col in columns:
        val = row.get(col)
        if col in type_map and val is not None:
            val = type_map[col](val)
        if col == "id" and table_name is not None and legacy_id is not None:
            val = legacy_id_to_uuid(table_name, legacy_id)
        elif fk_targets and col in fk_targets:
            target_table = fk_targets[col]
            if target_table is None or val is None:
                val = None
            else:
                mapped = (id_map or {}).get(target_table, {}).get(str(val))
                val = mapped  # None when the referenced row was not migrated
        if val is None:
            out[col] = None
        elif hasattr(val, "isoformat"):
            out[col] = val.isoformat()
        else:
            out[col] = val
    if force_readonly and "is_readonly" in out:
        out["is_readonly"] = True
    return out


# ---------------------------------------------------------------------------
# Core ETL
# ---------------------------------------------------------------------------


def run_etl(dry_run: bool = False) -> dict[str, Any]:
    if pymysql is None:
        raise RuntimeError("pymysql is not installed")
    if psycopg is None:
        raise RuntimeError("psycopg is not installed")

    mysql_cfg = get_mysql_config()
    pg_dsn = get_postgres_dsn()
    manifest: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "tables": [],
    }

    id_map: dict[str, dict[str, str]] = {tbl["name"]: {} for tbl in TABLES}

    # Pre-compute the legacy-id -> new-UUID map for every table so cross-table
    # FK rewrites can resolve regardless of insert order.
    with pymysql.connect(**mysql_cfg) as mysql_conn:  # type: ignore[arg-type]
        all_source_rows: dict[str, list[dict[str, Any]]] = {}
        for tbl in TABLES:
            rows = _fetch_mysql(mysql_conn, tbl)
            all_source_rows[tbl["name"]] = rows
            for r in rows:
                if r.get("id") is not None:
                    id_map[tbl["name"]][str(r["id"])] = legacy_id_to_uuid(tbl["name"], r["id"])
        manifest["id_map"] = id_map

        with psycopg.connect(pg_dsn) as pg_conn:  # type: ignore[arg-type]
            pg_conn.autocommit = True
            for tbl in TABLES:
                source_rows = all_source_rows[tbl["name"]]
                transformed = [
                    transform_row(
                        r,
                        tbl["columns"],
                        tbl["type_map"],
                        table_name=tbl["name"],
                        id_map=id_map,
                        fk_targets=FK_TARGETS.get(tbl["name"]),
                        force_readonly=tbl["name"] in READONLY_TABLES,
                    )
                    for r in source_rows
                ]
                source_count = len(source_rows)
                source_checksum = _aggregate_checksum(transformed)

                if dry_run:
                    target_count = 0
                    target_checksum = ""
                    skipped = 0
                else:
                    target_count, skipped, target_checksum = _upsert_postgres(
                        pg_conn, tbl, transformed
                    )

                checksum_match = (
                    source_checksum == target_checksum
                    if target_checksum
                    else (source_count == 0 and target_count == 0)
                )
                table_result = {
                    "table": tbl["name"],
                    "source_table": tbl["source_table"],
                    "target_table": tbl["target_table"],
                    "source_count": source_count,
                    "target_count": target_count,
                    "skipped_existing": skipped,
                    "source_checksum": source_checksum,
                    "target_checksum": target_checksum,
                    "checksum_match": checksum_match,
                }
                manifest["tables"].append(table_result)

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    # Zero-row tables count as matched (nothing to copy); every non-dry-run table
    # must match for the run to be considered OK.
    manifest["overall_status"] = (
        "ok"
        if dry_run or all(t.get("checksum_match") for t in manifest["tables"])
        else "mismatch"
    )
    return manifest


def _fetch_mysql(conn: Any, tbl: dict[str, Any]) -> list[dict[str, Any]]:
    sql = f"SELECT * FROM {tbl['source_table']}"
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def _aggregate_checksum(rows: list[dict[str, Any]]) -> str:
    combined = "".join(row_checksum(r) for r in rows)
    return hashlib.sha256(combined.encode()).hexdigest()


def _upsert_postgres(conn: Any, tbl: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[int, int, str]:
    """Insert new rows, then verify by reading the target back.

    The target checksum is computed from the *actual* Postgres rows (queried
    after insert) — not the in-memory source rows — so a dropped/failed insert
    or a bad type mapping shows up as a checksum/count mismatch.
    """
    cols = tbl["columns"]
    pk = tbl["pk"]
    target_table = tbl["target_table"]

    with conn.cursor() as cur:
        cur.execute(f"SELECT {pk} FROM {target_table}")
        existing_pks = {str(r[0]) for r in cur.fetchall()}

    to_insert = [r for r in rows if str(r.get(pk)) not in existing_pks]
    skipped = len(rows) - len(to_insert)

    if to_insert:
        cols_sql = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        with conn.cursor() as cur:
            sql = f"INSERT INTO {target_table} ({cols_sql}) VALUES ({placeholders})"
            for r in to_insert:
                row_vals = []
                for c in cols:
                    val = r.get(c)
                    if isinstance(val, dict):
                        val = json.dumps(val)
                    row_vals.append(val)
                cur.execute(sql, row_vals)

    if not rows:
        return 0, skipped, ""

    # Read back the migrated rows from Postgres and checksum those.
    wanted = [str(r.get(pk)) for r in rows]
    cols_sql = ", ".join(cols)
    target_rows: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(f"SELECT {cols_sql} FROM {target_table}")
        for raw in cur.fetchall():
            row = dict(zip(cols, raw, strict=False))
            if str(row.get(pk)) in wanted:
                target_rows.append(row)

    target_checksum = _aggregate_checksum(target_rows) if target_rows else ""
    return len(target_rows), skipped, target_checksum


def write_manifest(manifest: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B6 ETL: MySQL -> Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing")
    parser.add_argument(
        "--manifest",
        default=os.path.join(os.path.dirname(__file__), "etl_manifest.json"),
        help="Output manifest path",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger.info("Starting ETL ..." + (" (dry-run)" if args.dry_run else ""))
    try:
        manifest = run_etl(dry_run=args.dry_run)
    except RuntimeError as exc:
        logger.error("FATAL: %s", exc)
        return 1

    for t in manifest["tables"]:
        logger.info(
            "  %-20s source=%6d  target=%6d  skipped=%4d  checksum=%s",
            t["table"],
            t["source_count"],
            t["target_count"],
            t["skipped_existing"],
            "ok" if t["checksum_match"] else "n/a" if not t["target_count"] else "MISMATCH",
        )

    write_manifest(manifest, args.manifest)
    logger.info("Manifest written to %s", args.manifest)
    logger.info("Status: %s", manifest["overall_status"])
    return 0 if manifest["overall_status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
