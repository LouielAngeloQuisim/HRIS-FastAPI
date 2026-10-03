"""QA-08 / QA-03 — Dashboard daily attendance count and pending-adjustment KPI.

- Pure unit tests for the Asia/Manila day window (UTC boundaries).
- Endpoint tests: distinct employees with a punch today (Manila), excluding
  deleted and absence rows; repeated punches count once; the pending
  adjustment KPI matches the uppercase PENDING status (was lowercase -> 0).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

from app.attendance.adjustment_models import DtrAdjustment
from app.attendance.models import DailyTimeRecord
from app.config.settings import settings
from app.dashboard.services import count_daily_attendance, manila_day_window
from app.employee.models import EmployeeRecords

API = settings.API_V1_STR


def _superuser_id(db: Session) -> uuid.UUID:
    """created_by has FK user.id — the seeded superuser is the only guaranteed row."""
    from app.user.models import User

    return db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one().id


class TestManilaWindow:
    """Fixed-clock assertions — no dependence on the machine's clock/timezone."""

    def test_utc_instant_maps_to_manila_day(self):
        # 2026-10-02T16:30Z == 2026-10-03 00:30 Manila -> the Oct-3 window.
        start, end = manila_day_window(datetime(2026, 10, 2, 16, 30, tzinfo=timezone.utc))
        assert start == datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc)

    def test_just_before_window_start_belongs_to_previous_day(self):
        # 15:59:59.999Z is still Oct 2 Manila (23:59:59 +08).
        start, end = manila_day_window(datetime(2026, 10, 2, 15, 59, 59, tzinfo=timezone.utc))
        assert start == datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc)

    def test_last_instant_included_next_midnight_excluded(self):
        ref = datetime(2026, 10, 3, 15, 59, 59, tzinfo=timezone.utc)
        start, end = manila_day_window(ref)
        assert start <= ref < end
        assert not (start <= end < end)

    def test_window_is_never_server_local(self):
        # Same instant expressed with a +05:00 offset resolves identically.
        a = manila_day_window(datetime(2026, 10, 2, 21, 30, tzinfo=timezone(timedelta(hours=5))))
        b = manila_day_window(datetime(2026, 10, 2, 16, 30, tzinfo=timezone.utc))
        assert a == b


@pytest.fixture
def employee(db: Session) -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"DASH-{uuid.uuid4().hex[:8]}",
        first_name="Count", last_name="Tess", birthdate="1990-01-01",
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _clear_dtrs(db: Session) -> None:
    db.exec(text("DELETE FROM dtr_adjustment"))
    db.exec(text("DELETE FROM daily_time_record"))
    db.commit()


class TestDailyAttendanceCount:
    def test_distinct_employees_within_manila_today(self, db: Session, employee: EmployeeRecords):
        _clear_dtrs(db)
        other = EmployeeRecords(
            employee_code=f"DASH-{uuid.uuid4().hex[:8]}",
            first_name="Other", last_name="Employee", birthdate="1990-01-01",
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        now = datetime.now(timezone.utc)
        start, end = manila_day_window(now)

        def punch(emp: EmployeeRecords, at: datetime, **kw: object) -> DailyTimeRecord:
            row = DailyTimeRecord(
                employee_id=emp.id, login_date=at,
                logout_date=at + timedelta(hours=8), is_deleted=False, **kw,
            )
            db.add(row)
            db.commit()
            return row

        punch(employee, start)                      # first instant today: counts
        punch(employee, end - timedelta(seconds=1))  # last instant today: still 1 employee
        punch(other, start + timedelta(hours=1))     # second employee: counts
        punch(other, start - timedelta(seconds=1))   # just outside: excluded
        punch(other, end)                            # exactly next midnight: excluded
        deleted = punch(employee, start + timedelta(hours=2))
        deleted.is_deleted = True
        db.add(deleted)
        db.commit()
        absence = DailyTimeRecord(employee_id=employee.id, login_date=None, is_absent=True, is_deleted=False)
        db.add(absence)
        db.commit()

        assert count_daily_attendance(db, now) == 2

    def test_endpoint_returns_live_count(self, client: TestClient, superuser_token_headers, db: Session, employee: EmployeeRecords):
        _clear_dtrs(db)
        before = client.get(f"{API}/dashboard/", headers=superuser_token_headers).json()[
            "dtr_records_daily_count"
        ]
        assert isinstance(before, int)

        now = datetime.now(timezone.utc)
        start, _ = manila_day_window(now)
        row = DailyTimeRecord(
            employee_id=employee.id, login_date=start + timedelta(hours=3),
            logout_date=start + timedelta(hours=11), is_deleted=False,
        )
        db.add(row)
        db.commit()

        after = client.get(f"{API}/dashboard/", headers=superuser_token_headers).json()[
            "dtr_records_daily_count"
        ]
        assert after == before + 1

        row.is_deleted = True
        db.add(row)
        db.commit()
        dropped = client.get(f"{API}/dashboard/", headers=superuser_token_headers).json()[
            "dtr_records_daily_count"
        ]
        assert dropped == before

    def test_pending_dtr_adjustments_kpi_uses_uppercase_status(
        self, client: TestClient, superuser_token_headers, db: Session, employee: EmployeeRecords
    ):
        """QA-03: the DTR adjustment state machine stores PENDING/APPROVED/REJECTED
        (unlike leave, which is lowercase); the KPI filter must match."""
        _clear_dtrs(db)
        dtr = DailyTimeRecord(
            employee_id=employee.id, login_date=datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc),
            logout_date=datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc), is_deleted=False,
        )
        db.add(dtr)
        db.commit()
        db.refresh(dtr)

        def adjustment(status: str) -> DtrAdjustment:
            adj = DtrAdjustment(
                daily_time_record_id=dtr.id, employee_id=employee.id,
                original_login_date=dtr.login_date, original_logout_date=dtr.logout_date,
                adjusted_login_date=dtr.login_date, adjusted_logout_date=dtr.logout_date,
                status=status, created_by=_superuser_id(db),
            )
            db.add(adj)
            db.commit()
            db.refresh(adj)
            return adj

        adjustment("PENDING")
        adjustment("APPROVED")
        adjustment("REJECTED")

        body = client.get(f"{API}/dashboard/", headers=superuser_token_headers).json()
        assert body["pending_dtr_adjustments"] == 1

        # Approving the pending one drops the KPI (state-machine consistency).
        pending = db.exec(
            text("UPDATE dtr_adjustment SET status = 'APPROVED' WHERE status = 'PENDING'")
        )
        del pending
        db.commit()
        body2 = client.get(f"{API}/dashboard/", headers=superuser_token_headers).json()
        assert body2["pending_dtr_adjustments"] == 0
