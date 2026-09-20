"""Tests for B6 ETL script (etl_mysql_to_postgres.py).

These tests exercise the pure helper functions without requiring a live MySQL
or Postgres instance. The full end-to-end run is gated by environment
variables and requires pymysql + psycopg installed.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from scripts.etl_mysql_to_postgres import (
    FK_TARGETS,
    TABLES,
    _aggregate_checksum,
    _fetch_mysql,
    _upsert_postgres,
    get_mysql_config,
    get_postgres_dsn,
    legacy_id_to_uuid,
    run_etl,
    transform_row,
)


class TestHelpers:
    def test_get_mysql_config_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MYSQL_HOST", raising=False)
        monkeypatch.delenv("MYSQL_USER", raising=False)
        monkeypatch.delenv("MYSQL_PASSWORD", raising=False)
        monkeypatch.delenv("MYSQL_DB", raising=False)
        monkeypatch.delenv("MYSQL_PORT", raising=False)
        cfg = get_mysql_config()
        assert cfg["host"] == "localhost"
        assert cfg["port"] == 3306
        assert cfg["user"] == "root"
        assert cfg["password"] == ""
        assert cfg["database"] == "legacy_hris"

    def test_get_mysql_config_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYSQL_HOST", "db.example.com")
        monkeypatch.setenv("MYSQL_PORT", "3307")
        monkeypatch.setenv("MYSQL_USER", "etl")
        monkeypatch.setenv("MYSQL_PASSWORD", "secret")
        monkeypatch.setenv("MYSQL_DB", "src_hris")
        cfg = get_mysql_config()
        assert cfg["host"] == "db.example.com"
        assert cfg["port"] == 3307
        assert cfg["user"] == "etl"
        assert cfg["password"] == "secret"
        assert cfg["database"] == "src_hris"

    def test_get_postgres_dsn_direct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POSTGRES_DSN", "postgresql://u:p@host:5432/db")
        assert get_postgres_dsn() == "postgresql://u:p@host:5432/db"

    def test_get_postgres_dsn_parts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POSTGRES_DSN", raising=False)
        monkeypatch.setenv("POSTGRES_USER", "app")
        monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
        monkeypatch.setenv("POSTGRES_HOST", "pg")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_DB", "target")
        dsn = get_postgres_dsn()
        assert dsn == "postgresql://app:pw@pg:5433/target"

    def test_aggregate_checksum_deterministic(self) -> None:
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        first = _aggregate_checksum(rows)
        second = _aggregate_checksum(rows)
        assert first == second
        assert len(first) == 64

    def test_aggregate_checksum_changes_with_data(self) -> None:
        rows_a = [{"a": 1}]
        rows_b = [{"a": 2}]
        assert _aggregate_checksum(rows_a) != _aggregate_checksum(rows_b)

    def test_transform_row_bool_conversion(self) -> None:
        tbl = next(t for t in TABLES if t["name"] == "divisions")
        row = {"id": "1", "name": "HR", "is_active": 1, "is_deleted": 0}
        out = transform_row(row, tbl["columns"], tbl["type_map"])
        assert out["is_active"] is True
        assert out["is_deleted"] is False

    def test_transform_row_date_conversion(self) -> None:
        tbl = next(t for t in TABLES if t["name"] == "employee_records")
        d = date(2026, 1, 15)
        row = {
            "id": "1",
            "birthdate": d,
            "date_hired": d,
            "employee_code": "E1",
            "first_name": "A",
            "last_name": "B",
            "employment_type": "regular",
            "employee_status": "active",
            "is_active": 1,
            "is_deleted": 0,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        out = transform_row(row, tbl["columns"], tbl["type_map"])
        assert out["birthdate"] == "2026-01-15"
        assert out["date_hired"] == "2026-01-15"


class TestFetchMySQL:
    def test_fetch_mysql_returns_rows(self) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [{"id": 1, "name": "A"}]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        tbl = next(t for t in TABLES if t["name"] == "divisions")
        rows = _fetch_mysql(mock_conn, tbl)
        assert rows == [{"id": 1, "name": "A"}]
        mock_cur.execute.assert_called_once_with("SELECT * FROM division")


class TestRunEtlDryRun:
    @patch("scripts.etl_mysql_to_postgres.pymysql")
    @patch("scripts.etl_mysql_to_postgres.psycopg")
    def test_dry_run_no_writes(
        self, mock_psycopg: MagicMock, mock_pymysql: MagicMock
    ) -> None:
        mock_mysql_conn = MagicMock()
        mock_mysql_cur = MagicMock()
        mock_mysql_cur.fetchall.return_value = []
        mock_mysql_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_mysql_cur)
        mock_mysql_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pymysql.connect.return_value.__enter__ = MagicMock(return_value=mock_mysql_conn)
        mock_pymysql.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_pg_conn = MagicMock()
        mock_pg_conn.__enter__ = MagicMock(return_value=mock_pg_conn)
        mock_pg_conn.__exit__ = MagicMock(return_value=False)
        mock_psycopg.connect.return_value.__enter__ = MagicMock(return_value=mock_pg_conn)
        mock_psycopg.connect.return_value.__exit__ = MagicMock(return_value=False)

        manifest = run_etl(dry_run=True)

        assert manifest["dry_run"] is True
        assert manifest["overall_status"] == "ok"
        for t in manifest["tables"]:
            assert t["source_count"] == 0
            assert t["target_count"] == 0
            assert t["skipped_existing"] == 0

    @patch("scripts.etl_mysql_to_postgres.pymysql")
    @patch("scripts.etl_mysql_to_postgres.psycopg")
    def test_dry_run_with_source_data(
        self, mock_psycopg: MagicMock, mock_pymysql: MagicMock
    ) -> None:
        rows = [
            {
                "id": 1,
                "name": "HR",
                "description": "Human Resources",
                "is_active": 1,
                "is_deleted": 0,
                "deleted_at": None,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        ]
        mock_mysql_conn = MagicMock()
        mock_mysql_cur = MagicMock()
        mock_mysql_cur.fetchall.return_value = rows
        mock_mysql_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_mysql_cur)
        mock_mysql_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pymysql.connect.return_value.__enter__ = MagicMock(return_value=mock_mysql_conn)
        mock_pymysql.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_pg_conn = MagicMock()
        mock_pg_conn.__enter__ = MagicMock(return_value=mock_pg_conn)
        mock_pg_conn.__exit__ = MagicMock(return_value=False)
        mock_psycopg.connect.return_value.__enter__ = MagicMock(return_value=mock_pg_conn)
        mock_psycopg.connect.return_value.__exit__ = MagicMock(return_value=False)

        manifest = run_etl(dry_run=True)

        tbl = next(t for t in manifest["tables"] if t["table"] == "divisions")
        assert tbl["source_count"] == 1
        assert tbl["target_count"] == 0
        assert tbl["skipped_existing"] == 0
        assert tbl["target_checksum"] == ""
        assert tbl["checksum_match"] is False


class TestIdRemapping:
    def test_pk_is_deterministic_uuid(self) -> None:
        tbl = next(t for t in TABLES if t["name"] == "divisions")
        out = transform_row(
            {"id": 7, "name": "HR"}, tbl["columns"], tbl["type_map"], table_name="division"
        )
        assert out["id"] == legacy_id_to_uuid("division", 7)
        # Deterministic across runs.
        assert legacy_id_to_uuid("division", 7) == legacy_id_to_uuid("division", 7)

    def test_fk_is_rewritten_to_referenced_uuid(self) -> None:
        tbl = next(t for t in TABLES if t["name"] == "employee_records")
        id_map = {"division": {"1": "11111111-1111-1111-1111-111111111111"}}
        out = transform_row(
            {"id": 5, "division_id": 1, "position_id": 42},
            tbl["columns"],
            tbl["type_map"],
            table_name="employee_records",
            id_map=id_map,
            fk_targets=FK_TARGETS["employee_records"],
        )
        assert out["division_id"] == "11111111-1111-1111-1111-111111111111"
        # position_id has no migrated counterpart -> NULL (not the legacy int).
        assert out["position_id"] is None

    def test_unmapped_fk_becomes_null(self) -> None:
        tbl = next(t for t in TABLES if t["name"] == "loan")
        out = transform_row(
            {"id": 1, "employee_id": 999},
            tbl["columns"],
            tbl["type_map"],
            table_name="loan",
            id_map={"employee_records": {}},
            fk_targets=FK_TARGETS["loan"],
        )
        assert out["employee_id"] is None

    def test_payroll_rows_forced_readonly(self) -> None:
        tbl = next(t for t in TABLES if t["name"] == "payroll_run")
        out = transform_row(
            {"id": 3, "created_by": 99, "is_readonly": 0},
            tbl["columns"],
            tbl["type_map"],
            table_name="payroll_run",
            fk_targets=FK_TARGETS["payroll_run"],
            force_readonly=True,
        )
        assert out["is_readonly"] is True
        # Legacy created_by user ids have no counterpart.
        assert out["created_by"] is None


def _fake_conn(existing_pks: list, readback_rows: list) -> MagicMock:
    conn = MagicMock()
    results = iter([existing_pks, readback_rows])

    def cursor_factory() -> MagicMock:
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchall.side_effect = lambda: next(results)
        return cur

    conn.cursor.side_effect = cursor_factory
    return conn


class TestTargetChecksumFromDb:
    SIMPLE_TABLE = {
        "name": "division",
        "source_table": "division",
        "target_table": "division",
        "pk": "id",
        "columns": ["id", "name"],
        "type_map": {},
    }

    def test_matching_readback_produces_matching_checksum(self) -> None:
        rows = [{"id": "a", "name": "HR"}]
        conn = _fake_conn(existing_pks=[], readback_rows=[("a", "HR")])
        target_count, skipped, checksum = _upsert_postgres(conn, self.SIMPLE_TABLE, rows)
        assert target_count == 1
        assert skipped == 0
        assert checksum == _aggregate_checksum(rows)

    def test_row_count_mismatch_is_detected(self) -> None:
        rows = [{"id": "a", "name": "HR"}, {"id": "b", "name": "Ops"}]
        # Target only reflects one row -> count/checksum mismatch.
        conn = _fake_conn(existing_pks=[], readback_rows=[("a", "HR")])
        target_count, _, checksum = _upsert_postgres(conn, self.SIMPLE_TABLE, rows)
        assert target_count == 1
        assert checksum != _aggregate_checksum(rows)

    def test_value_mismatch_is_detected(self) -> None:
        rows = [{"id": "a", "name": "HR"}]
        conn = _fake_conn(existing_pks=[], readback_rows=[("a", "TAMPERED")])
        _, _, checksum = _upsert_postgres(conn, self.SIMPLE_TABLE, rows)
        assert checksum != _aggregate_checksum(rows)

    def test_empty_source_yields_empty_checksum(self) -> None:
        conn = _fake_conn(existing_pks=[], readback_rows=[])
        target_count, skipped, checksum = _upsert_postgres(conn, self.SIMPLE_TABLE, [])
        assert target_count == 0
        assert skipped == 0
        assert checksum == ""
