"""The attendance payroll preparation route persists blocked, auditable drafts."""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.attendance.models import (
    DailyTimeRecord,
    EmployeeShiftAssignment,
    Shift,
)
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import (
    EmployeePayGroupAssignment,
    EmployeeSalary,
    PayrollPayGroup,
    PayrollPolicyVersion,
    PayType,
)
from app.payroll.payroll_tables import PayrollRun

API = f"{settings.API_V1_STR}/payroll"


def test_prepare_creates_replayable_draft_and_keeps_finalization_blocked(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    employee = EmployeeRecords(
        employee_code=f"DRAFT-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Payroll",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    group = PayrollPayGroup(
        code=f"QA-{uuid.uuid4().hex[:8]}",
        name="QA monthly",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    db.add(employee)
    db.add(group)
    shift = Shift(
        code=f"QA-{uuid.uuid4().hex[:8]}",
        name="Sample 8-hour weekday shift",
        start_time="08:00",
        end_time="17:00",
        lunch_break_duration=60,
        total_hours_minus_lunch=480,
    )
    db.add(shift)
    db.flush()
    db.add(
        EmployeeSalary(
            employee_id=employee.id,
            basic_rate="26000.00",
            effective_date=date(2026, 10, 1),
            pay_type=PayType.MONTHLY,
        )
    )
    db.add(
        EmployeePayGroupAssignment(
            employee_id=employee.id,
            pay_group_id=group.id,
            effective_from=date(2026, 10, 1),
        )
    )
    db.add(
        EmployeeShiftAssignment(
            employee_id=employee.id,
            shift_id=shift.id,
            effective_from=date(2026, 10, 1),
        )
    )
    absent_date = date(2026, 10, 5)
    for day in range(1, 16):
        work_date = date(2026, 10, day)
        if work_date.weekday() >= 5:
            continue
        is_absent = work_date == absent_date
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=(
                    None
                    if is_absent
                    else datetime(2026, 10, day, tzinfo=timezone.utc)
                ),
                logout_date=(
                    None
                    if is_absent
                    else datetime(2026, 10, day, tzinfo=timezone.utc)
                    + timedelta(hours=9)
                ),
                work_date=work_date,
                rendered_minutes=None if is_absent else 480,
                overtime_minutes=0,
                is_absent=is_absent,
                is_time_calculated=not is_absent,
            )
        )
    policy = PayrollPolicyVersion(
        version=900_000 + int(uuid.uuid4().hex[:6], 16),
        effective_from=date(2026, 9, 1),
        effective_to=None,
        policy={
            "timezone": "Asia/Manila",
            "monthly_divisor": "22",
            "daily_partial_work": "pro_rated",
            "paid_leave": False,
            "paid_holidays": False,
            "break_minutes": 60,
            "grace_minutes": 0,
            "overtime_rule": {"multiplier": "1.25"},
            "premium_rules": {},
            "allowance_tax_treatment": {},
            "rounding_mode": "half_up",
            "contribution_collection": {
                "frequency": "once_monthly",
                "collection_period": "last_period",
            },
            "statutory_sources_reviewed": ["https://www.sss.gov.ph/pay-contribution/"],
        },
        confirmed=True,
    )
    db.add(policy)
    db.commit()

    payload = {
        "pay_group_id": str(group.id),
        "date_from": "2026-10-01",
        "date_to": "2026-10-15",
    }
    first = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json=payload,
        headers=superuser_token_headers,
    )
    assert first.status_code == 201, first.text
    data = first.json()
    assert data["workflow_status"] == "draft"
    entry = next(row for row in data["entries"] if row["employee_id"] == str(employee.id))
    assert entry["review_state"] == "blocked"
    assert entry["gross_pay"] == "13000.00", entry["blockers"]
    assert entry["total_deductions"] == "1181.82"
    assert entry["net_pay"] == "11818.18"
    assert entry["earnings"]["provisional"] is True
    assert any(
        blocker["code"] == "bir_ytd_unavailable"
        for blocker in entry["blockers"]
    )
    assert entry["input_fingerprint"]

    replay = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json=payload,
        headers=superuser_token_headers,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == data["id"]
    assert len(db.exec(select(PayrollRun).where(PayrollRun.pay_group_id == group.id)).all()) == 1

    review = client.post(
        f"{API}/runs/{data['id']}/start-review", headers=superuser_token_headers
    )
    assert review.status_code == 409
