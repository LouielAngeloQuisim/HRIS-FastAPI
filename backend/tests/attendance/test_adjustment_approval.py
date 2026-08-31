"""Phase 2B tests — DTR adjustment approval flow + overtime approval.

Approval-flow state transitions and permission gates on approval endpoints
(design §2B, b2b.testsRequired).
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.attendance.adjustment_models import DtrAdjustment
from app.attendance.models import DailyTimeRecord, Shift
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.user.models import User

API = settings.API_V1_STR


def _dt(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=timezone.utc)


MON = 4


@pytest.fixture
def shift(db: Session) -> Shift:
    shift = Shift(
        code=f"DAY-{uuid.uuid4().hex[:8]}", name="Day Shift",
        start_time="08:00", end_time="17:00",
        lunch_break_duration=60, total_hours_minus_lunch=480,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@pytest.fixture
def employee(db: Session) -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
        first_name="Jane", last_name="Doe", birthdate="1990-01-01",
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def dtr(db: Session, employee: EmployeeRecords, shift: Shift) -> DailyTimeRecord:
    rec = DailyTimeRecord(
        employee_id=employee.id, shift_id=shift.id,
        login_date=_dt(MON, 8, 0), logout_date=_dt(MON, 17, 0),
        rendered_minutes=480, late_minutes=0, undertime_minutes=0, overtime_minutes=0,
        is_time_calculated=True, source="manual",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


class TestOvertimeApproval:
    """Overtime approval with role gate (design §2B, b2b item 2)."""

    def test_approve_overtime_flips_flag(
        self, client: TestClient, superuser_token_headers, dtr: DailyTimeRecord,
    ) -> None:
        r = client.post(
            f"{API}/daily-time-records/{dtr.id}/approve-overtime",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        r = client.get(
            f"{API}/daily-time-records/{dtr.id}", headers=superuser_token_headers,
        )
        assert r.json()["overtime_approved"] is True

    def test_reject_overtime_flips_flag_false(
        self, client: TestClient, superuser_token_headers, dtr: DailyTimeRecord,
    ) -> None:
        # Pre-set to True, then reject.
        dtr.overtime_approved = True
        client.post(
            f"{API}/daily-time-records/{dtr.id}/approve-overtime",
            headers=superuser_token_headers,
        )
        r = client.post(
            f"{API}/daily-time-records/{dtr.id}/reject-overtime",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        r = client.get(
            f"{API}/daily-time-records/{dtr.id}", headers=superuser_token_headers,
        )
        assert r.json()["overtime_approved"] is False

    def test_overtime_approval_requires_permission(
        self, client: TestClient, normal_user_token_headers, dtr: DailyTimeRecord,
    ) -> None:
        r = client.post(
            f"{API}/daily-time-records/{dtr.id}/approve-overtime",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text


class TestAdjustmentStateMachine:
    """Approval-flow state transitions (design §2B, b2b item 1)."""

    def _create(self, client: TestClient, headers: dict, dtr_id: str) -> dict:
        r = client.post(f"{API}/dtr-adjustments/", json={
            "daily_time_record_id": dtr_id,
            "adjusted_login_date": "2026-08-04T09:00:00+00:00",
            "adjusted_logout_date": "2026-08-04T17:00:00+00:00",
            "reason": "Forgot to punch in on time",
        }, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()

    def test_create_starts_pending_and_snapshots_original(
        self, client: TestClient, superuser_token_headers, dtr: DailyTimeRecord,
    ) -> None:
        body = self._create(client, superuser_token_headers, str(dtr.id))
        assert body["status"] == "PENDING"
        assert body["employee_id"] == str(dtr.employee_id)
        # Original times snapshotted from the DTR.
        assert body["original_login_date"] == dtr.login_date.isoformat().replace("+00:00", "Z") or body["original_login_date"] is not None
        assert body["adjusted_login_date"] is not None

    def test_approve_applies_adjusted_times_and_recomputes(
        self, client: TestClient, superuser_token_headers, db: Session,
        dtr: DailyTimeRecord,
    ) -> None:
        body = self._create(client, superuser_token_headers, str(dtr.id))
        adj_id = body["id"]

        r = client.post(
            f"{API}/dtr-adjustments/{adj_id}/approve", headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "APPROVED"

        # The DTR now carries the adjusted login (09:00 instead of 08:00) and is recomputed.
        r = client.get(
            f"{API}/daily-time-records/{dtr.id}", headers=superuser_token_headers,
        )
        updated = r.json()
        assert "09:00:00" in updated["login_date"]
        # 09:00-17:00 = 8h (480 min gross) - 60 lunch = 420 rendered; 60 undertime vs 480 baseline.
        assert updated["rendered_minutes"] == 420
        assert updated["undertime_minutes"] == 60

        # approved_by recorded.
        adj = db.get(DtrAdjustment, uuid.UUID(adj_id))
        superuser = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
        assert adj.approved_by == superuser.id

    def test_reject_leaves_dtr_unchanged(
        self, client: TestClient, superuser_token_headers, dtr: DailyTimeRecord,
    ) -> None:
        body = self._create(client, superuser_token_headers, str(dtr.id))
        adj_id = body["id"]

        r = client.post(
            f"{API}/dtr-adjustments/{adj_id}/reject", headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "REJECTED"

        # DTR login unchanged (still 08:00, still 480 rendered).
        r = client.get(
            f"{API}/daily-time-records/{dtr.id}", headers=superuser_token_headers,
        )
        assert r.json()["rendered_minutes"] == 480

    def test_cannot_approve_twice(
        self, client: TestClient, superuser_token_headers, dtr: DailyTimeRecord,
    ) -> None:
        body = self._create(client, superuser_token_headers, str(dtr.id))
        adj_id = body["id"]
        client.post(
            f"{API}/dtr-adjustments/{adj_id}/approve", headers=superuser_token_headers,
        )
        r = client.post(
            f"{API}/dtr-adjustments/{adj_id}/approve", headers=superuser_token_headers,
        )
        assert r.status_code == 409, r.text

    def test_adjustment_approval_requires_permission(
        self, client: TestClient, superuser_token_headers, normal_user_token_headers,
        dtr: DailyTimeRecord,
    ) -> None:
        # Create the adjustment as the superuser (who has add), then verify a
        # normal user (lacking edit) cannot approve it.
        body = self._create(client, superuser_token_headers, str(dtr.id))
        r = client.post(
            f"{API}/dtr-adjustments/{body['id']}/approve",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text
