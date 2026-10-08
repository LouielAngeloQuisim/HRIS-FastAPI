"""The attendance payroll preparation route persists blocked, auditable drafts."""

import calendar
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.attendance.models import (
    DailyTimeRecord,
    DtrAttendanceInterval,
    EmployeeShiftAssignment,
    Shift,
)
from app.audit.models import AuditLog
from app.common.security import get_password_hash
from app.config.settings import settings
from app.employee.models import EmployeeRecords, EmployeeStatus
from app.leave.models import HolidayConfig, HolidayInstance, LeavePolicy, LeaveRequest
from app.payroll.models import (
    EmployeePayGroupAssignment,
    EmployeeSalary,
    EmployeeTaxBenefit,
    EmployeeTaxYearDeclaration,
    PagIBIGBracket,
    PayrollContributionLedger,
    PayrollDeliveryOutbox,
    PayrollPayGroup,
    PayrollPolicyVersion,
    PayrollRunStatus,
    PayType,
    PhilHealthBracket,
    SSSBracket,
)
from app.payroll.payroll_tables import PayrollEntry, PayrollRun
from app.payroll.routes import (
    StatutoryScheduleUnavailable,
    _fixed_recurring_allowance_for_period,
    _payroll_entry_inputs_are_current,
)
from app.user.models import User
from tests.utils.user import user_authentication_headers

API = f"{settings.API_V1_STR}/payroll"


def test_fixed_allowance_uses_effective_policy_segments() -> None:
    salary = SimpleNamespace(
        id=uuid.uuid4(),
        effective_date=date(2026, 10, 1),
        non_taxable_allowance=Decimal("3100.00"),
        de_minimis_monthly={},
    )
    common_policy = {
        "allowance_tax_treatment": {
            "fixed_recurring": "taxable",
            "proration": "calendar_days",
            "absence": "not_deducted",
        },
        "rounding_mode": "half_up",
    }
    first = SimpleNamespace(
        id=uuid.uuid4(),
        version=990_000 + int(uuid.uuid4().hex[:6], 16),
        effective_from=date(2026, 10, 1),
        effective_to=date(2026, 10, 7),
        policy=common_policy,
        confirmed=True,
    )
    second = SimpleNamespace(
        id=uuid.uuid4(),
        version=first.version + 1,
        effective_from=date(2026, 10, 8),
        effective_to=date(2026, 10, 31),
        policy=common_policy,
        confirmed=True,
    )

    assert _fixed_recurring_allowance_for_period(
        salaries=[salary],
        employee=None,
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 15),
        policies=[first, second],
    ) == Decimal("1500.00")

    overlapping = SimpleNamespace(
        id=uuid.uuid4(),
        version=second.version + 1,
        effective_from=date(2026, 10, 7),
        effective_to=date(2026, 10, 31),
        policy=common_policy,
        confirmed=True,
    )
    with pytest.raises(StatutoryScheduleUnavailable, match="Exactly one confirmed"):
        _fixed_recurring_allowance_for_period(
            salaries=[salary],
            employee=None,
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 15),
            policies=[first, second, overlapping],
        )


def test_attendance_preview_applies_configured_holiday_multipliers(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = EmployeeRecords(
        employee_code=f"HOL-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Holiday",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    group = PayrollPayGroup(
        code=f"HOL-{uuid.uuid4().hex[:8]}",
        name="Holiday multiplier QA",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    shift = Shift(
        code=f"HOL-{uuid.uuid4().hex[:8]}",
        name="Holiday QA weekday shift",
        start_time="08:00",
        end_time="17:00",
        lunch_break_duration=60,
        total_hours_minus_lunch=480,
    )
    db.add_all([employee, group, shift])
    db.flush()
    holiday = HolidayConfig(
        code=f"HOL-{uuid.uuid4().hex[:8]}",
        name="QA regular holiday",
        month_day="10-05",
        type="regular",
        multiplier_regular=Decimal("2"),
        multiplier_overtime=Decimal("2.6"),
        is_recurring=False,
    )
    payroll_policy = PayrollPolicyVersion(
        version=980_000 + int(uuid.uuid4().hex[:6], 16),
        effective_from=date(2032, 10, 1),
        effective_to=date(2032, 10, 31),
        policy={
            "timezone": "Asia/Manila",
            "monthly_divisor": "22",
            "monthly_salary_proration": "scheduled_workday_fraction",
            "monthly_holiday_pay_divisor": "22",
            "daily_partial_work": "pro_rated",
            "paid_leave": False,
            "paid_holidays": False,
            "grace_minutes": 0,
            "overtime_rule": {"multiplier": "1.25"},
            "rounding_mode": "half_up",
        },
        confirmed=True,
    )
    db.add_all(
        [
            EmployeeSalary(
                employee_id=employee.id,
                basic_rate=Decimal("120"),
                overtime_rate=Decimal("120"),
                effective_date=date(2032, 10, 1),
                pay_type=PayType.HOURLY,
            ),
            EmployeePayGroupAssignment(
                employee_id=employee.id,
                pay_group_id=group.id,
                effective_from=date(2032, 10, 1),
            ),
            EmployeeShiftAssignment(
                employee_id=employee.id,
                shift_id=shift.id,
                effective_from=date(2032, 10, 1),
            ),
            holiday,
            payroll_policy,
        ]
    )
    db.flush()
    db.add(
        HolidayInstance(
            config_id=holiday.id,
            observed_date=date(2032, 10, 5),
            raw_date=date(2032, 10, 5),
            leave_year=2032,
        )
    )
    for day in range(1, 16):
        work_date = date(2032, 10, day)
        if work_date.weekday() >= 5:
            continue
        is_holiday = work_date == date(2032, 10, 5)
        login = datetime(2032, 10, day, tzinfo=timezone.utc)
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=login,
                logout_date=login + timedelta(hours=9 if is_holiday else 8),
                work_date=work_date,
                rendered_minutes=540 if is_holiday else 480,
                overtime_minutes=60 if is_holiday else 0,
                overtime_approved=True if is_holiday else None,
                overtime_approved_minutes=60 if is_holiday else None,
                is_absent=False,
                is_time_calculated=True,
            )
        )
    db.commit()

    response = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    entry = next(
        row for row in response.json()["entries"] if row["employee_id"] == str(employee.id)
    )
    assert not entry["blockers"], entry["blockers"]
    assert entry["regular_earnings"] == "10560.00"
    assert entry["holiday_premium"] == "960.00"
    assert entry["approved_overtime"] == "312.00"
    assert entry["gross_before_statutory"] == "11832.00"
    assert any("regular factor 2.000" in line for line in entry["formula"])
    assert any(f"holiday:{holiday.id}:regular:2032-10-05" == ref for ref in entry["source_references"])

    second_regular_holiday = HolidayConfig(
        code=f"HOL-{uuid.uuid4().hex[:8]}",
        name="QA second regular holiday",
        month_day="10-05",
        type="regular",
        multiplier_regular=Decimal("2"),
        multiplier_overtime=Decimal("2.6"),
        is_recurring=False,
    )
    db.add(second_regular_holiday)
    db.flush()
    second_holiday_instance = HolidayInstance(
        config_id=second_regular_holiday.id,
        observed_date=date(2032, 10, 5),
        raw_date=date(2032, 10, 5),
        leave_year=2032,
    )
    db.add(second_holiday_instance)
    db.commit()
    double_regular_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert double_regular_preview.status_code == 200, double_regular_preview.text
    double_entry = next(
        row
        for row in double_regular_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not double_entry["blockers"], double_entry["blockers"]
    assert double_entry["holiday_premium"] == "1920.00"
    assert double_entry["approved_overtime"] == "468.00"
    assert double_entry["gross_before_statutory"] == "12948.00"
    assert any("2 regular holiday(s), statutory-safe premium" in line for line in double_entry["formula"])
    assert any(
        f"holiday:{second_regular_holiday.id}:regular:2032-10-05" == ref
        for ref in double_entry["source_references"]
    )
    holiday_dtr = db.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee.id,
            DailyTimeRecord.work_date == date(2032, 10, 5),
        )
    ).one()
    worked_state = (
        holiday_dtr.login_date,
        holiday_dtr.logout_date,
        holiday_dtr.rendered_minutes,
        holiday_dtr.overtime_minutes,
        holiday_dtr.overtime_approved,
        holiday_dtr.overtime_approved_minutes,
        holiday_dtr.is_absent,
    )
    holiday_dtr.login_date = None
    holiday_dtr.logout_date = None
    holiday_dtr.rendered_minutes = 0
    holiday_dtr.overtime_minutes = 0
    holiday_dtr.overtime_approved = None
    holiday_dtr.overtime_approved_minutes = None
    holiday_dtr.is_absent = True
    db.add(holiday_dtr)
    db.commit()
    unworked_double_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert unworked_double_preview.status_code == 200, unworked_double_preview.text
    unworked_entry = next(
        row
        for row in unworked_double_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert any(
        blocker["code"] == "double_holiday_unworked_unresolved"
        for blocker in unworked_entry["blockers"]
    )
    (
        holiday_dtr.login_date,
        holiday_dtr.logout_date,
        holiday_dtr.rendered_minutes,
        holiday_dtr.overtime_minutes,
        holiday_dtr.overtime_approved,
        holiday_dtr.overtime_approved_minutes,
        holiday_dtr.is_absent,
    ) = worked_state
    db.add(holiday_dtr)
    second_holiday_instance.is_active = False
    db.add_all([holiday_dtr, second_holiday_instance])
    db.commit()

    prepared = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert prepared.status_code == 201, prepared.text
    prepared_entry_data = next(
        row
        for row in prepared.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    prepared_entry = db.get(PayrollEntry, uuid.UUID(prepared_entry_data["id"]))
    assert prepared_entry is not None
    assert prepared_entry.gross_pay == Decimal("11832.00")
    assert prepared_entry.earnings["holiday_premium"] == "960.00"
    assert prepared_entry.input_snapshot["holiday_config_revisions"][0][
        "multiplier_regular"
    ] == "2.000"
    assert _payroll_entry_inputs_are_current(db, prepared_entry)

    holiday.multiplier_regular = Decimal("2.5")
    db.add(holiday)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, prepared_entry)

    holiday.multiplier_regular = None
    db.add(holiday)
    db.commit()
    missing_factor = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert missing_factor.status_code == 200, missing_factor.text
    missing_entry = next(
        row
        for row in missing_factor.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert any(
        blocker["code"] == "holiday_multiplier_incomplete"
        for blocker in missing_entry["blockers"]
    )

    holiday.multiplier_regular = Decimal("2")
    holiday.region_code = "NCR"
    db.add(holiday)
    db.commit()
    regional = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert regional.status_code == 200, regional.text
    regional_entry = next(
        row for row in regional.json()["entries"] if row["employee_id"] == str(employee.id)
    )
    assert any(
        blocker["code"] == "holiday_region_unresolved"
        for blocker in regional_entry["blockers"]
    )

    holiday.region_code = None
    holiday.multiplier_regular = None
    holiday.multiplier_overtime = None
    no_work_holiday = db.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee.id,
            DailyTimeRecord.work_date == date(2032, 10, 5),
        )
    ).one()
    no_work_holiday.login_date = None
    no_work_holiday.logout_date = None
    no_work_holiday.rendered_minutes = None
    no_work_holiday.overtime_minutes = 0
    no_work_holiday.overtime_approved = None
    no_work_holiday.overtime_approved_minutes = None
    no_work_holiday.is_absent = True
    db.add_all([holiday, no_work_holiday])
    db.commit()
    eligible_no_work_holiday = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert eligible_no_work_holiday.status_code == 200, eligible_no_work_holiday.text
    eligible_entry = next(
        row
        for row in eligible_no_work_holiday.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not eligible_entry["blockers"], eligible_entry["blockers"]
    assert eligible_entry["regular_earnings"] == "10560.00"
    assert any(
        "prior scheduled workday eligibility met" in line
        for line in eligible_entry["formula"]
    )

    employee.date_separated = date(2032, 10, 4)
    db.add(employee)
    db.commit()
    separated_before_holiday = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert separated_before_holiday.status_code == 200, separated_before_holiday.text
    separated_entry = next(
        row
        for row in separated_before_holiday.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not separated_entry["blockers"], separated_entry["blockers"]
    assert separated_entry["regular_earnings"] == "1920.00"
    assert not any(
        reference.startswith("holiday:")
        for reference in separated_entry["source_references"]
    )
    employee.date_separated = None
    employee.date_hired = date(2032, 10, 5)
    db.add(employee)
    db.commit()
    hired_on_holiday = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert hired_on_holiday.status_code == 200, hired_on_holiday.text
    hired_entry = next(
        row
        for row in hired_on_holiday.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not hired_entry["blockers"], hired_entry["blockers"]
    assert hired_entry["regular_earnings"] == "7680.00"
    assert any(
        "prior scheduled workday eligibility not met" in line
        for line in hired_entry["formula"]
    )
    employee.date_hired = date(2020, 1, 1)
    db.add(employee)
    db.commit()

    prior_workday = db.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee.id,
            DailyTimeRecord.work_date == date(2032, 10, 4),
        )
    ).one()
    prior_workday.login_date = None
    prior_workday.logout_date = None
    prior_workday.rendered_minutes = None
    prior_workday.is_absent = True
    db.add(prior_workday)
    db.commit()
    ineligible_no_work_holiday = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert ineligible_no_work_holiday.status_code == 200, ineligible_no_work_holiday.text
    ineligible_entry = next(
        row
        for row in ineligible_no_work_holiday.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not ineligible_entry["blockers"], ineligible_entry["blockers"]
    assert ineligible_entry["regular_earnings"] == "8640.00"
    assert any(
        "prior scheduled workday eligibility not met" in line
        for line in ineligible_entry["formula"]
    )
    prior_workday.login_date = datetime(2032, 10, 4, tzinfo=timezone.utc)
    prior_workday.logout_date = prior_workday.login_date + timedelta(hours=8)
    prior_workday.rendered_minutes = 480
    prior_workday.is_absent = False
    db.add(prior_workday)
    holiday.multiplier_regular = Decimal("2")
    holiday.multiplier_overtime = Decimal("2.6")
    no_work_holiday.login_date = datetime(2032, 10, 5, tzinfo=timezone.utc)
    no_work_holiday.logout_date = no_work_holiday.login_date + timedelta(hours=9)
    no_work_holiday.rendered_minutes = 540
    no_work_holiday.overtime_minutes = 60
    no_work_holiday.overtime_approved = True
    no_work_holiday.overtime_approved_minutes = 60
    no_work_holiday.is_absent = False
    db.add_all([holiday, no_work_holiday])
    db.commit()

    rest_day_holiday = HolidayConfig(
        code=f"HOL-{uuid.uuid4().hex[:8]}",
        name="QA holiday on rest day",
        month_day="10-02",
        type="regular",
        multiplier_regular_rest_day=Decimal("2.6"),
        multiplier_overtime_rest_day=Decimal("3.38"),
        is_recurring=False,
    )
    db.add(rest_day_holiday)
    db.flush()
    db.add(
        HolidayInstance(
            config_id=rest_day_holiday.id,
            observed_date=date(2032, 10, 2),
            raw_date=date(2032, 10, 2),
            leave_year=2032,
        )
    )
    rest_day_login = datetime(2032, 10, 2, 0, tzinfo=timezone.utc)
    db.add(
        DailyTimeRecord(
            employee_id=employee.id,
            shift_id=shift.id,
            login_date=rest_day_login,
            logout_date=rest_day_login + timedelta(hours=9),
            work_date=date(2032, 10, 2),
            rendered_minutes=540,
            overtime_minutes=60,
            overtime_approved=True,
            overtime_approved_minutes=60,
            is_absent=False,
            is_time_calculated=True,
        )
    )
    db.commit()
    rest_day_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert rest_day_preview.status_code == 200, rest_day_preview.text
    rest_day_entry = next(
        row
        for row in rest_day_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not rest_day_entry["blockers"], rest_day_entry["blockers"]
    assert rest_day_entry["regular_earnings"] == "11520.00"
    assert rest_day_entry["holiday_premium"] == "2496.00"
    assert rest_day_entry["approved_overtime"] == "717.60"
    assert rest_day_entry["gross_before_statutory"] == "14733.60"
    assert any(
        "1 regular holiday(s), statutory-safe premium on rest day; regular factor 2.600"
        in line
        for line in rest_day_entry["formula"]
    )

    salary_record = db.exec(
        select(EmployeeSalary).where(EmployeeSalary.employee_id == employee.id)
    ).one()
    salary_record.pay_type = PayType.MONTHLY
    db.add(salary_record)
    db.commit()
    monthly_rest_day_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert monthly_rest_day_preview.status_code == 200, monthly_rest_day_preview.text
    monthly_rest_day_entry = next(
        row
        for row in monthly_rest_day_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not monthly_rest_day_entry["blockers"], monthly_rest_day_entry["blockers"]
    assert monthly_rest_day_entry["regular_earnings"] == "60.00"
    assert monthly_rest_day_entry["holiday_premium"] == "14.18"
    assert monthly_rest_day_entry["approved_overtime"] == "717.60"
    assert monthly_rest_day_entry["gross_before_statutory"] == "791.78"
    payroll_policy.policy = {
        key: value
        for key, value in payroll_policy.policy.items()
        if key != "monthly_holiday_pay_divisor"
    }
    db.add(payroll_policy)
    db.commit()
    missing_monthly_holiday_basis = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert missing_monthly_holiday_basis.status_code == 200
    monthly_blocked = next(
        row
        for row in missing_monthly_holiday_basis.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert "monthly_holiday_basis_unconfirmed" in {
        blocker["code"] for blocker in monthly_blocked["blockers"]
    }
    payroll_policy.policy = {
        **payroll_policy.policy,
        "monthly_holiday_pay_divisor": "22",
        "premium_rules": {
            "rest_day_regular_multiplier": "1.30",
            "rest_day_overtime_multiplier": "1.69",
        },
    }
    db.add(payroll_policy)
    db.commit()
    salary_record.pay_type = PayType.HOURLY
    rest_day_instance = db.exec(
        select(HolidayInstance).where(
            HolidayInstance.config_id == rest_day_holiday.id
        )
    ).one()
    rest_day_instance.is_active = False
    db.add_all([salary_record, rest_day_instance])
    db.commit()
    ordinary_rest_day_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2032-10-01",
            "date_to": "2032-10-15",
        },
        headers=superuser_token_headers,
    )
    assert ordinary_rest_day_preview.status_code == 200, ordinary_rest_day_preview.text
    ordinary_rest_day_entry = next(
        row
        for row in ordinary_rest_day_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not ordinary_rest_day_entry["blockers"], ordinary_rest_day_entry["blockers"]
    assert ordinary_rest_day_entry["rest_day_premium"] == "288.00"
    assert any(
        "ordinary rest-day work" in line
        for line in ordinary_rest_day_entry["formula"]
    )


def test_prepare_creates_replayable_draft_and_guards_then_finalizes(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = EmployeeRecords(
        employee_code=f"DRAFT-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Payroll",
        email=f"qa-payroll-{uuid.uuid4().hex[:8]}@example.test",
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
            non_taxable_allowance="3100.00",
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
    late_date = date(2026, 10, 6)
    for day in range(1, 16):
        work_date = date(2026, 10, day)
        if work_date.weekday() >= 5:
            continue
        is_absent = work_date == absent_date
        is_late = work_date == late_date
        login_at = datetime(2026, 10, day, tzinfo=timezone.utc) + timedelta(
            minutes=15 if is_late else 0
        )
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=(
                    None
                    if is_absent
                    else login_at
                ),
                logout_date=(
                    None
                    if is_absent
                    else login_at + timedelta(hours=9)
                ),
                work_date=work_date,
                rendered_minutes=None if is_absent else 465 if is_late else 480,
                overtime_minutes=0,
                is_absent=is_absent,
                is_time_calculated=not is_absent,
            )
        )
    policy = PayrollPolicyVersion(
        version=900_000 + int(uuid.uuid4().hex[:6], 16),
        effective_from=date(2026, 10, 1),
        effective_to=date(2026, 10, 7),
        policy={
            "timezone": "Asia/Manila",
            "monthly_divisor": "22",
            "monthly_salary_proration": "scheduled_workday_fraction",
            "daily_partial_work": "pro_rated",
            "monthly_partial_work": "deduct_after_grace",
            "paid_leave": True,
            "paid_holidays": False,
            "break_minutes": 60,
            "grace_minutes": 10,
            "overtime_rule": {"multiplier": "1.25"},
            "premium_rules": {},
            "allowance_tax_treatment": {
                "fixed_recurring": "taxable",
                "proration": "calendar_days",
                "absence": "not_deducted",
            },
            "rounding_mode": "half_up",
            "contribution_collection": {
                "frequency": "once_monthly",
                "collection_period": "last_period",
            },
            "statutory_sources_reviewed": [
                "https://www.sss.gov.ph/pay-contribution/",
                "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
                "https://www.pagibigfund.gov.ph/",
            ],
        },
        confirmed=True,
    )
    policy_after_change = PayrollPolicyVersion(
        version=policy.version + 1,
        effective_from=date(2026, 10, 8),
        effective_to=date(2026, 10, 31),
        policy={**policy.policy, "overtime_rule": {"multiplier": "1.5"}},
        confirmed=True,
    )
    leave_policy = LeavePolicy(
        code=f"UNPAID-{uuid.uuid4().hex[:8]}",
        name="Unpaid QA leave",
        is_paid=False,
    )
    db.add(leave_policy)
    db.flush()
    leave_request = LeaveRequest(
        employee_id=employee.id,
        policy_id=leave_policy.id,
        date_start=absent_date,
        date_end=absent_date,
        leave_year=2026,
        total_days_requested=Decimal("1.00"),
        status="approved",
    )
    db.add(leave_request)
    db.add_all([policy, policy_after_change])
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
    assert entry["gross_pay"] == "14500.00", entry["blockers"]
    assert entry["total_deductions"] == "1194.13"
    assert entry["net_pay"] == "13305.87"
    assert entry["taxable_income"] == "13305.87"
    assert entry["earnings"]["fixed_recurring_allowance"] == "1500.00"
    assert entry["input_snapshot"]["fixed_recurring_allowance"]["amount"] == "1500.00"
    assert entry["earnings"]["provisional"] is True
    assert entry["deductions"]["attendance_breakdown"] == {
        "unpaid_absence": "1181.82",
        "monthly_short_time_after_grace": "12.31",
    }
    assert any(
        blocker["code"] == "bir_ytd_unavailable"
        for blocker in entry["blockers"]
    )
    assert entry["input_fingerprint"]
    assert len(entry["input_snapshot"]["policy_versions"]) == 2
    assert {
        row["effective_from"] for row in entry["input_snapshot"]["policy_versions"]
    } == {"2026-10-01", "2026-10-08"}
    assert entry["input_snapshot"]["leave_policy_revisions"] == [
        {
            "id": str(leave_policy.id),
            "updated_at": leave_policy.updated_at.isoformat()
            if leave_policy.updated_at
            else None,
            "is_paid": False,
            "is_active": True,
            "is_deleted": False,
        }
    ]
    attendance_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2026-10-01",
            "date_to": "2026-10-15",
        },
        headers=superuser_token_headers,
    )
    assert attendance_preview.status_code == 200, attendance_preview.text
    attendance_preview_entry = next(
        row
        for row in attendance_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert attendance_preview_entry["fixed_recurring_allowance"] == "1500.00"
    assert attendance_preview_entry["gross_before_statutory"] == "14500.00"
    assert any(
        "Fixed recurring allowance: 1500.00 taxable" in formula
        for formula in attendance_preview_entry["formula"]
    )
    frozen_entry = db.get(PayrollEntry, uuid.UUID(entry["id"]))
    assert frozen_entry is not None
    leave_policy.is_paid = True
    db.add(leave_policy)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, frozen_entry)
    leave_policy.is_paid = False
    db.add(leave_policy)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, frozen_entry)
    leave_request.requested_hours = Decimal("4.00")
    db.add(leave_request)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, frozen_entry)
    leave_request.requested_hours = None
    db.add(leave_request)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, frozen_entry)

    preview_params = {
        "pay_group_id": str(group.id),
        "date_from": "2026-10-01",
        "date_to": "2026-10-15",
    }
    partial_leave_date = date(2026, 10, 7)
    partial_dtr = db.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee.id,
            DailyTimeRecord.work_date == partial_leave_date,
        )
    ).one()
    partial_dtr.logout_date = partial_dtr.login_date + timedelta(hours=5)  # type: ignore[operator]
    partial_dtr.rendered_minutes = 240
    db.add(partial_dtr)
    partial_leave_request = LeaveRequest(
        employee_id=employee.id,
        policy_id=leave_policy.id,
        date_start=partial_leave_date,
        date_end=partial_leave_date,
        leave_year=2026,
        requested_hours=Decimal("4.00"),
        total_days_requested=Decimal("0.50"),
        status="approved",
    )
    db.add(partial_leave_request)
    db.commit()
    hourly_leave_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params=preview_params,
        headers=superuser_token_headers,
    )
    assert hourly_leave_preview.status_code == 200, hourly_leave_preview.text
    hourly_leave_entry = next(
        row
        for row in hourly_leave_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert not any(
        blocker["code"].startswith("partial_leave_")
        for blocker in hourly_leave_entry["blockers"]
    ), hourly_leave_entry["blockers"]
    assert any("240 approved hourly leave minutes; unpaid treatment" in formula
               for formula in hourly_leave_entry["formula"])
    assert hourly_leave_entry["attendance_deduction"] == "1785.04"
    assert hourly_leave_entry["short_time_deduction"] == "12.31"
    duplicate_partial_request = LeaveRequest(
        employee_id=employee.id,
        policy_id=leave_policy.id,
        date_start=partial_leave_date,
        date_end=partial_leave_date,
        leave_year=2026,
        requested_hours=Decimal("2.00"),
        total_days_requested=Decimal("0.25"),
        status="approved",
    )
    db.add(duplicate_partial_request)
    db.commit()
    duplicate_partial_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params=preview_params,
        headers=superuser_token_headers,
    )
    duplicate_partial_entry = next(
        row
        for row in duplicate_partial_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert duplicate_partial_preview.status_code == 200, duplicate_partial_preview.text
    assert any(
        blocker["code"] == "multiple_partial_leave_requests_unresolved"
        for blocker in duplicate_partial_entry["blockers"]
    )
    db.delete(duplicate_partial_request)
    db.commit()
    partial_leave_request.requested_hours = Decimal("4.01")
    db.add(partial_leave_request)
    db.commit()
    fractional_leave_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params=preview_params,
        headers=superuser_token_headers,
    )
    fractional_leave_entry = next(
        row
        for row in fractional_leave_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert fractional_leave_preview.status_code == 200, fractional_leave_preview.text
    assert any(
        blocker["code"] == "partial_leave_minute_precision_invalid"
        for blocker in fractional_leave_entry["blockers"]
    )
    partial_leave_request.requested_hours = Decimal("4.25")
    db.add(partial_leave_request)
    db.commit()
    overlapping_leave_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params=preview_params,
        headers=superuser_token_headers,
    )
    overlapping_leave_entry = next(
        row
        for row in overlapping_leave_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert overlapping_leave_preview.status_code == 200, overlapping_leave_preview.text
    assert any(
        blocker["code"] == "partial_leave_attendance_overlap"
        for blocker in overlapping_leave_entry["blockers"]
    )
    partial_leave_request.requested_hours = Decimal("4.00")
    db.add(partial_leave_request)
    db.commit()
    leave_policy.is_paid = True
    db.add(leave_policy)
    db.commit()
    paid_hourly_leave_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params=preview_params,
        headers=superuser_token_headers,
    )
    assert paid_hourly_leave_preview.status_code == 200, paid_hourly_leave_preview.text
    paid_hourly_leave_entry = next(
        row
        for row in paid_hourly_leave_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert any("240 approved hourly leave minutes; paid treatment" in formula
               for formula in paid_hourly_leave_entry["formula"])
    assert paid_hourly_leave_entry["attendance_deduction"] == "12.31"
    assert paid_hourly_leave_entry["short_time_deduction"] == "12.31"
    leave_policy.is_paid = False
    db.add(leave_policy)
    db.commit()
    partial_leave_request.requested_hours = None
    partial_leave_request.policy_id = None
    db.add(partial_leave_request)
    db.commit()
    unclassified_leave_preview = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params=preview_params,
        headers=superuser_token_headers,
    )
    assert unclassified_leave_preview.status_code == 200, unclassified_leave_preview.text
    unclassified_leave_entry = next(
        row
        for row in unclassified_leave_preview.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert any(
        blocker["code"] == "leave_policy_unavailable"
        for blocker in unclassified_leave_entry["blockers"]
    )
    partial_dtr.logout_date = partial_dtr.login_date + timedelta(hours=9)  # type: ignore[operator]
    partial_dtr.rendered_minutes = 480
    db.add(partial_dtr)
    db.delete(partial_leave_request)
    db.commit()

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
    assert review.status_code == 200, review.text
    assert review.json()["workflow_status"] == "in_review"

    # A reviewed tax-year opening input allows the supported ordinary
    # semi-monthly path to calculate the current-period BIR withholding.
    resolved_absence = db.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee.id,
            DailyTimeRecord.work_date == absent_date,
        )
    ).first()
    assert resolved_absence is not None
    resolved_absence.login_date = datetime(2026, 10, 5, tzinfo=timezone.utc)
    resolved_absence.logout_date = datetime(2026, 10, 5, tzinfo=timezone.utc) + timedelta(hours=9)
    resolved_absence.rendered_minutes = 480
    resolved_absence.is_absent = False
    resolved_absence.is_time_calculated = True
    db.add(resolved_absence)
    original_run = db.get(PayrollRun, uuid.UUID(data["id"]))
    assert original_run is not None and original_run.input_fingerprint
    rebuilt = client.post(
        f"{API}/runs/{original_run.id}/rebuild-attendance-draft",
        json={
            "expected_run_fingerprint": original_run.input_fingerprint,
            "reason": "Attendance was corrected after draft preparation",
        },
        headers=superuser_token_headers,
    )
    assert rebuilt.status_code == 201, rebuilt.text
    replacement = rebuilt.json()
    assert replacement["id"] != data["id"]
    db.refresh(original_run)
    assert original_run.status == PayrollRunStatus.VOID
    replacement_entry = next(
        row for row in replacement["entries"] if row["employee_id"] == str(employee.id)
    )
    assert replacement_entry["gross_pay"] == "14500.00"
    rebuild_audit = db.exec(
        select(AuditLog).where(
            AuditLog.action == "rebuild_attendance_draft",
            AuditLog.path == f"/api/v1/payroll/runs/{original_run.id}/rebuild-attendance-draft",
        )
    ).first()
    assert rebuild_audit is not None
    assert rebuild_audit.extra is not None
    assert rebuild_audit.extra["replacement_run_id"] == replacement["id"]

    for day in range(16, 32):
        work_date = date(2026, 10, day)
        if work_date.weekday() >= 5:
            continue
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=datetime(2026, 10, day, tzinfo=timezone.utc),
                logout_date=datetime(2026, 10, day, tzinfo=timezone.utc) + timedelta(hours=9),
                work_date=work_date,
                rendered_minutes=480,
                overtime_minutes=0,
                is_absent=False,
                is_time_calculated=True,
            )
        )
    db.add(
        EmployeeTaxYearDeclaration(
            employee_id=employee.id,
            tax_year=2026,
            tax_classification="ordinary",
            opening_as_of=date(2026, 9, 30),
            taxable_compensation_ytd="0.00",
            tax_withheld_ytd="0.00",
            previous_employer_included=False,
            is_verified=True,
        )
    )
    db.commit()
    second = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json={**payload, "date_from": "2026-10-16", "date_to": "2026-10-31"},
        headers=superuser_token_headers,
    )
    assert second.status_code == 201, second.text
    second_entry = next(
        row for row in second.json()["entries"] if row["employee_id"] == str(employee.id)
    )
    assert not second_entry["blockers"], second_entry["blockers"]
    assert second_entry["taxable_income"] == "12300.00", {
        "gross": second_entry["gross_pay"],
        "taxable_income": second_entry["taxable_income"],
        "statutory": second_entry["deductions"]["statutory"],
        "contribution_bases": {
            scheme: values["basis"]
            for scheme, values in second_entry["input_snapshot"][
                "monthly_contributions"
            ]["schemes"].items()
        },
    }
    assert second_entry["gross_pay"] == "14600.00"
    assert second_entry["earnings"]["fixed_recurring_allowance"] == "1600.00"
    assert second_entry["deductions"]["bir_withholding"] == "282.45"
    assert second_entry["deductions"]["statutory"] == {
        "sss": "1450.00",
        "philhealth": "650.00",
        "pagibig": "200.00",
    }, second_entry["input_snapshot"]["monthly_contributions"]
    schedule_snapshots = second_entry["input_snapshot"]["monthly_contributions"]["schemes"]
    assert Decimal(schedule_snapshots["sss"]["basis"]) == Decimal(
        schedule_snapshots["pagibig"]["basis"]
    )
    assert Decimal(schedule_snapshots["sss"]["basis"]) >= Decimal("28750.00")
    assert Decimal(schedule_snapshots["sss"]["basis"]) <= Decimal("29249.99")
    assert Decimal(schedule_snapshots["philhealth"]["basis"]) == Decimal(
        "26000.00"
    )
    for scheme in ("sss", "philhealth", "pagibig"):
        schedule_rows = schedule_snapshots[scheme]["schedule_rows"]
        assert schedule_rows
        assert schedule_rows[0]["updated_at"]
        assert schedule_rows[0]["values"]
    payroll_entry = db.get(PayrollEntry, uuid.UUID(second_entry["id"]))
    assert payroll_entry is not None
    assert _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_employee = db.get(EmployeeRecords, employee.id)
    assert payroll_employee is not None
    payroll_employee.date_separated = date(2026, 10, 20)
    db.add(payroll_employee)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_employee.date_separated = None
    payroll_employee.employee_status = EmployeeStatus.TERMINATED
    db.add(payroll_employee)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_employee.employee_status = EmployeeStatus.ACTIVE
    db.add(payroll_employee)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    # Frozen attendance fields are compared directly as well as by revision and
    # timestamp, so an out-of-band write cannot preserve a stale review.
    attendance_revision = payroll_entry.input_snapshot["attendance_revisions"][0]
    payroll_dtr = db.get(DailyTimeRecord, uuid.UUID(attendance_revision["id"]))
    assert payroll_dtr is not None and payroll_dtr.rendered_minutes is not None
    original_rendered_minutes = payroll_dtr.rendered_minutes
    payroll_dtr.rendered_minutes += 1
    db.add(payroll_dtr)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_dtr.rendered_minutes = original_rendered_minutes
    db.add(payroll_dtr)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    # A shift definition can change while the employee's assignment row stays
    # identical. It still changes scheduled hours and must invalidate review.
    shift_revision = payroll_entry.input_snapshot["shift_revisions"][0]
    payroll_shift = db.get(Shift, uuid.UUID(shift_revision["id"]))
    assert payroll_shift is not None
    original_shift_minutes = payroll_shift.total_hours_minus_lunch
    payroll_shift.total_hours_minus_lunch += 30
    db.add(payroll_shift)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_shift.total_hours_minus_lunch = original_shift_minutes
    db.add(payroll_shift)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    # Every salary input that feeds payroll must be frozen directly, not only
    # by a mutable update timestamp and the base rate.
    salary_revision = payroll_entry.input_snapshot["salary_versions"][0]
    payroll_salary = db.get(EmployeeSalary, uuid.UUID(salary_revision["id"]))
    assert payroll_salary is not None
    original_overtime_rate = payroll_salary.overtime_rate
    payroll_salary.overtime_rate += Decimal("0.125")
    db.add(payroll_salary)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_salary.overtime_rate = original_overtime_rate
    db.add(payroll_salary)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    # Effective-dated assignment edits are frozen as values, not inferred only
    # from their row IDs and updated_at timestamps.
    shift_assignment_revision = payroll_entry.input_snapshot["shift_assignments"][0]
    payroll_shift_assignment = db.get(
        EmployeeShiftAssignment, uuid.UUID(shift_assignment_revision["id"])
    )
    assert payroll_shift_assignment is not None
    original_shift_end = payroll_shift_assignment.effective_to
    payroll_shift_assignment.effective_to = date(2035, 1, 1)
    db.add(payroll_shift_assignment)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_shift_assignment.effective_to = original_shift_end
    db.add(payroll_shift_assignment)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    group_assignment_revision = payroll_entry.input_snapshot["pay_group_assignments"][0]
    payroll_group_assignment = db.get(
        EmployeePayGroupAssignment, uuid.UUID(group_assignment_revision["id"])
    )
    assert payroll_group_assignment is not None
    original_group_start = payroll_group_assignment.effective_from
    payroll_group_assignment.effective_from = original_group_start - timedelta(days=1)
    db.add(payroll_group_assignment)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_group_assignment.effective_from = original_group_start
    db.add(payroll_group_assignment)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    policy_revision = payroll_entry.input_snapshot["policy_versions"][0]
    payroll_policy = db.get(
        PayrollPolicyVersion, uuid.UUID(policy_revision["id"])
    )
    assert payroll_policy is not None
    original_policy = dict(payroll_policy.policy)
    changed_policy = dict(original_policy)
    changed_policy["monthly_divisor"] = str(
        Decimal(str(original_policy["monthly_divisor"])) + Decimal("1")
    )
    payroll_policy.policy = changed_policy
    db.add(payroll_policy)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_policy.policy = original_policy
    db.add(payroll_policy)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    pay_group_revision = payroll_entry.input_snapshot["pay_group"]
    payroll_group = db.get(PayrollPayGroup, uuid.UUID(pay_group_revision["id"]))
    assert payroll_group is not None
    original_payment_offset = payroll_group.payment_offset_days
    payroll_group.payment_offset_days = original_payment_offset + 1
    db.add(payroll_group)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_group.payment_offset_days = original_payment_offset
    db.add(payroll_group)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    tax_reference = payroll_entry.input_snapshot["tax_year_declaration"]
    tax_declaration = db.get(
        EmployeeTaxYearDeclaration, uuid.UUID(tax_reference["id"])
    )
    assert tax_declaration is not None
    original_taxable_ytd = tax_declaration.taxable_compensation_ytd
    tax_declaration.taxable_compensation_ytd += Decimal("1.00")
    db.add(tax_declaration)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    tax_declaration.taxable_compensation_ytd = original_taxable_ytd
    db.add(tax_declaration)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    # Name, code and email are frozen inputs to the reviewed payslip/outbox
    # recipient, so an identity change requires renewed review.
    original_email = payroll_employee.email
    payroll_employee.email = "revised-recipient@example.com"
    db.add(payroll_employee)
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, payroll_entry)
    payroll_employee.email = original_email
    db.add(payroll_employee)
    db.commit()
    assert _payroll_entry_inputs_are_current(db, payroll_entry)

    # An in-place edit must invalidate the frozen draft even when its row ID
    # and effective date remain unchanged.
    for scheme, model, field, increment in (
        ("sss", SSSBracket, "employee_ss", Decimal("1.00")),
        ("philhealth", PhilHealthBracket, "employee_share", Decimal("0.01")),
        ("pagibig", PagIBIGBracket, "employee_rate", Decimal("0.001")),
    ):
        schedule_row = schedule_snapshots[scheme]["schedule_rows"][0]
        bracket = db.get(model, uuid.UUID(schedule_row["id"]))
        assert bracket is not None
        original_value = getattr(bracket, field)
        setattr(bracket, field, original_value + increment)
        db.add(bracket)
        db.commit()
        assert not _payroll_entry_inputs_are_current(db, payroll_entry)
        setattr(bracket, field, original_value)
        db.add(bracket)
        db.commit()
        assert _payroll_entry_inputs_are_current(db, payroll_entry)

    run_id = second.json()["id"]
    start_review = client.post(
        f"{API}/runs/{run_id}/start-review", headers=superuser_token_headers
    )
    assert start_review.status_code == 200, start_review.text
    for candidate in second.json()["entries"]:
        action = "excluded" if candidate["blockers"] else "reviewed"
        review = client.post(
            f"{API}/runs/{run_id}/entries/{candidate['id']}/review",
            json={
                "action": action,
                "reason": "Unrelated QA fixture has no payroll setup" if action == "excluded" else None,
                "expected_input_fingerprint": candidate["input_fingerprint"],
            },
            headers=superuser_token_headers,
        )
        assert review.status_code == 200, review.text
    assert review.json()["workflow_status"] == "ready_for_finalization"

    password = "qa-finalizer-password"
    finalizer = User(
        email=f"payroll-finalizer-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash(password),
        is_superuser=True,
    )
    db.add(finalizer)
    db.commit()
    finalizer_headers = user_authentication_headers(
        client=client, email=finalizer.email, password=password
    )
    monkeypatch.setattr(settings, "PAYROLL_FINALIZATION_ENABLED", True)
    late_member = EmployeeRecords(
        employee_code=f"LATE-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Late Roster Member",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    db.add(late_member)
    db.flush()
    late_assignment = EmployeePayGroupAssignment(
        employee_id=late_member.id,
        pay_group_id=payroll_entry.input_snapshot["pay_group_assignments"][0]["pay_group_id"],
        effective_from=date(2026, 10, 1),
    )
    db.add(late_assignment)
    db.commit()
    stale_roster = client.post(f"{API}/runs/{run_id}/finalize", headers=finalizer_headers)
    assert stale_roster.status_code == 409
    assert "employee roster changed" in stale_roster.json()["detail"]
    other_group = PayrollPayGroup(
        code=f"OTHER-{uuid.uuid4().hex[:8]}",
        name="QA other pay group",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    db.add(other_group)
    db.flush()
    late_assignment.pay_group_id = other_group.id
    db.add(late_assignment)
    db.commit()
    provisional_entry = db.get(PayrollEntry, uuid.UUID(second_entry["id"]))
    assert provisional_entry is not None
    assert second_entry["review_state"] == "ready"
    assert provisional_entry.calculation_version == "attendance-v1"
    assert provisional_entry.earnings["provisional"] is False
    provisional_entry.calculation_version = "attendance-v1-provisional"
    provisional_entry.earnings = {**provisional_entry.earnings, "provisional": True}
    db.add(provisional_entry)
    db.commit()
    rejected_provisional = client.post(
        f"{API}/runs/{run_id}/finalize", headers=finalizer_headers
    )
    assert rejected_provisional.status_code == 409
    assert "uses provisional attendance earnings" in rejected_provisional.json()["detail"]
    finalized_run = db.get(PayrollRun, uuid.UUID(run_id))
    assert finalized_run is not None
    db.refresh(finalized_run)
    assert finalized_run.workflow_status == "ready_for_finalization"
    assert finalized_run.frozen_snapshot is None
    provisional_entry.calculation_version = "attendance-v1"
    provisional_entry.earnings = {**provisional_entry.earnings, "provisional": False}
    db.add(provisional_entry)
    db.commit()
    finalized = client.post(f"{API}/runs/{run_id}/finalize", headers=finalizer_headers)
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["workflow_status"] == "finalized"
    finalized_run = db.get(PayrollRun, uuid.UUID(run_id))
    assert finalized_run is not None
    assert finalized_run.frozen_snapshot is not None
    assert finalized_run.finalized_by == finalizer.id
    assert finalized_run.created_by != finalized_run.finalized_by
    ledgers = db.exec(
        select(PayrollContributionLedger).where(
            PayrollContributionLedger.payroll_entry_id == payroll_entry.id
        )
    ).all()
    assert {row.scheme for row in ledgers} == {"sss", "philhealth", "pagibig"}
    outbox = db.exec(
        select(PayrollDeliveryOutbox).where(
            PayrollDeliveryOutbox.payroll_entry_id == payroll_entry.id
        )
    ).one()
    assert outbox.status == "scheduled"
    assert outbox.recipient_snapshot == employee.email

    payslip = client.get(
        f"{API}/runs/{run_id}/entries/{payroll_entry.id}/payslip.pdf",
        headers=superuser_token_headers,
    )
    assert payslip.status_code == 200, payslip.text
    assert payslip.headers["content-type"] == "application/pdf"
    assert payslip.content.startswith(b"%PDF-")


@pytest.mark.parametrize(
    ("period_start", "period_end", "opening_as_of", "separation_date", "employee_status", "trigger", "expected_taxable", "expected_tax_due", "expected_withholding"),
    [
        (date(2026, 12, 16), date(2026, 12, 31), date(2026, 12, 15), None, EmployeeStatus.ACTIVE, "year_end", Decimal("323000.00"), Decimal("10950.00"), Decimal("6950.00")),
        (date(2026, 6, 1), date(2026, 6, 15), date(2026, 5, 31), date(2026, 6, 15), EmployeeStatus.RESIGNED, "termination_final_pay", Decimal("321500.00"), Decimal("10725.00"), Decimal("6725.00")),
    ],
)
def test_final_pay_period_uses_annualized_tax_and_opening_balance(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    period_start: date,
    period_end: date,
    opening_as_of: date,
    separation_date: date | None,
    employee_status: EmployeeStatus,
    trigger: str,
    expected_taxable: Decimal,
    expected_tax_due: Decimal,
    expected_withholding: Decimal,
) -> None:
    employee = EmployeeRecords(
        employee_code=f"YEAR-END-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Year End",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
        date_separated=separation_date,
        employee_status=employee_status,
    )
    group = PayrollPayGroup(
        code=f"YE-{uuid.uuid4().hex[:8]}",
        name="QA twice-monthly year-end",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    shift = Shift(
        code=f"YE-{uuid.uuid4().hex[:8]}",
        name="Year-end 8-hour weekday shift",
        start_time="08:00",
        end_time="17:00",
        lunch_break_duration=60,
        total_hours_minus_lunch=480,
    )
    db.add_all([employee, group, shift])
    db.flush()
    db.add_all(
        [
            EmployeeSalary(
                employee_id=employee.id,
                basic_rate="26000.00",
                effective_date=date(2026, 1, 1),
                pay_type=PayType.MONTHLY,
            ),
            EmployeePayGroupAssignment(
                employee_id=employee.id,
                pay_group_id=group.id,
                effective_from=date(2026, 1, 1),
            ),
            EmployeeShiftAssignment(
                employee_id=employee.id,
                shift_id=shift.id,
                effective_from=date(2026, 1, 1),
            ),
            EmployeeTaxYearDeclaration(
                employee_id=employee.id,
                tax_year=2026,
                tax_classification="ordinary",
                opening_as_of=opening_as_of,
                taxable_compensation_ytd="300000.00",
                tax_withheld_ytd="4000.00",
                previous_employer_included=True,
                opening_benefits_exempt_ytd="70000.00",
                opening_benefits_reconciled=True,
                opening_de_minimis_annual_ytd={
                    "uniform_clothing": "0.00",
                    "actual_medical_assistance": "0.00",
                    "achievement_award": "0.00",
                    "christmas_anniversary_gift": "0.00",
                    "cba_productivity_incentive": "0.00",
                },
                opening_de_minimis_monthly_ytd={
                    "medical_cash_dependents": "0.00",
                    "rice_subsidy": "0.00",
                    "laundry_allowance": "0.00",
                },
                source_reference="QA verified opening YTD example",
                is_verified=True,
            ),
            EmployeeTaxBenefit(
                employee_id=employee.id,
                tax_year=2026,
                paid_on=period_start + timedelta(days=1),
                benefit_type="thirteenth_month",
                gross_amount="30000.00",
                source_reference="QA verified 13th-month payment record",
            ),
            PayrollPolicyVersion(
                version=910_000 + int(uuid.uuid4().hex[:6], 16),
                effective_from=period_start,
                effective_to=period_end,
                policy={
                    "timezone": "Asia/Manila",
                    "monthly_divisor": "22",
                    "monthly_salary_proration": "scheduled_workday_fraction",
                    "daily_partial_work": "pro_rated",
                    "monthly_partial_work": "deduct_after_grace",
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
                    "statutory_sources_reviewed": [
                        "https://www.sss.gov.ph/pay-contribution/",
                        "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
                        "https://www.pagibigfund.gov.ph/",
                    ],
                },
                confirmed=True,
            ),
        ]
    )
    # Year-end covers the full month; termination covers the employee's final
    # configured semi-monthly period and stops on the recorded separation date.
    for day in range(1, calendar.monthrange(period_end.year, period_end.month)[1] + 1):
        work_date = date(period_end.year, period_end.month, day)
        if work_date.weekday() >= 5:
            continue
        if separation_date is not None and work_date > separation_date:
            continue
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=datetime(period_end.year, period_end.month, day, tzinfo=timezone.utc),
                logout_date=datetime(period_end.year, period_end.month, day, tzinfo=timezone.utc)
                + timedelta(hours=9),
                work_date=work_date,
                rendered_minutes=480,
                overtime_minutes=0,
                is_absent=False,
                is_time_calculated=True,
            )
        )
    db.commit()

    response = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json={
            "pay_group_id": str(group.id),
            "date_from": period_start.isoformat(),
            "date_to": period_end.isoformat(),
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 201, response.text
    entry = next(
        item
        for item in response.json()["entries"]
        if item["employee_id"] == str(employee.id)
    )
    assert "bir_year_end_adjustment_unavailable" not in {
        blocker["code"] for blocker in entry["blockers"]
    }
    assert "bir_ytd_history_unavailable" not in {
        blocker["code"] for blocker in entry["blockers"]
    }
    assert entry["input_snapshot"]["bir_year_to_date_history"]["complete"] is True
    assert entry["input_snapshot"]["bir_year_to_date_history"]["finalized_entries"] == []
    assert entry["input_snapshot"]["bir_calculation"]["method"] == (
        "annualized_rr_11_2018_2023_onward"
    )
    assert entry["input_snapshot"]["bir_calculation"]["annualization_trigger"] == trigger
    blocker_codes = {blocker["code"] for blocker in entry["blockers"]}
    assert "bir_annual_benefits_unavailable" not in blocker_codes
    benefit_reconciliation = entry["input_snapshot"]["bir_benefit_reconciliation"]
    assert {
        key: benefit_reconciliation[key]
        for key in (
            "exemption_cap",
            "opening_exempt_benefits",
            "opening_reconciled",
            "current_employer_benefits_gross",
            "current_employer_benefits_exempt",
            "current_employer_benefits_taxable_excess",
        )
    } == {
        "exemption_cap": "90000.00",
        "opening_exempt_benefits": "70000.00",
        "opening_reconciled": True,
        "current_employer_benefits_gross": "30000.00",
        "current_employer_benefits_exempt": "20000.00",
        "current_employer_benefits_taxable_excess": "10000.00",
    }
    benefit_row = benefit_reconciliation["current_employer_benefit_payments"][0]
    assert benefit_row["paid_on"] == (period_start + timedelta(days=1)).isoformat()
    assert benefit_row["benefit_type"] == "thirteenth_month"
    assert benefit_row["gross_amount"] == "30000.00"
    assert benefit_row["taxable_other_benefit_amount"] == "30000.00"
    monthly_contributions = entry["input_snapshot"].get("monthly_contributions")
    if trigger == "termination_final_pay":
        assert monthly_contributions is not None
        assert {
            scheme: values["employee"]
            for scheme, values in monthly_contributions["schemes"].items()
        } == {
            "sss": "650.00",
            "philhealth": "650.00",
            "pagibig": "200.00",
        }
        assert "termination_monthly_contribution_timing_unavailable" not in blocker_codes
        assert "bir_2316_termination_delivery_unavailable" in blocker_codes
    else:
        # The year-end test intentionally has no 2026 contribution schedules.
        # It exercises annual BIR math from the available provisional taxable
        # basis while proving missing statutory inputs still block finalization.
        assert "statutory_schedule_unavailable" in blocker_codes
        assert monthly_contributions is None
        assert "termination_monthly_contribution_timing_unavailable" not in blocker_codes
        assert "bir_2316_termination_delivery_unavailable" not in blocker_codes
    annual_taxable = Decimal(
        entry["input_snapshot"]["bir_calculation"]["annual_taxable_compensation"]
    )
    annual_tax_due = Decimal(
        entry["input_snapshot"]["bir_calculation"]["annual_tax_due"]
    )
    prior_withheld = Decimal(
        entry["input_snapshot"]["bir_calculation"]["prior_tax_withheld"]
    )
    withholding_adjustment = Decimal(entry["deductions"]["bir_withholding"])
    assert annual_taxable == expected_taxable, entry
    assert annual_tax_due == expected_tax_due
    assert prior_withheld == Decimal("4000.00")
    assert withholding_adjustment == expected_withholding
    prepared_entry = db.exec(
        select(PayrollEntry).where(PayrollEntry.id == uuid.UUID(entry["id"]))
    ).one()
    assert _payroll_entry_inputs_are_current(db, prepared_entry)
    db.add(
        EmployeeTaxBenefit(
            employee_id=employee.id,
            tax_year=2026,
            paid_on=period_start + timedelta(days=2),
            benefit_type="other_benefit",
            gross_amount="100.00",
            source_reference="QA additional benefit payment",
        )
    )
    db.commit()
    assert not _payroll_entry_inputs_are_current(db, prepared_entry)


@pytest.mark.parametrize(
    ("tax_classification", "source_reference", "basic_rate", "pay_type"),
    [
        ("ordinary", "QA reviewed Form 2316", "35000.00", PayType.MONTHLY),
        (
            "minimum_wage_earner",
            "QA DOLE wage-order evidence for assigned workplace",
            "650.00",
            PayType.DAILY,
        ),
    ],
)
def test_verified_tax_classification_uses_supported_bir_treatment(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    tax_classification: str,
    source_reference: str,
    basic_rate: str,
    pay_type: PayType,
) -> None:
    employee = EmployeeRecords(
        employee_code=f"CUMULATIVE-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Cumulative Tax",
        birthdate=date(1990, 1, 1),
        date_hired=date(2025, 11, 1),
    )
    group = PayrollPayGroup(
        code=f"CA-{uuid.uuid4().hex[:8]}",
        name="QA cumulative semi-monthly",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    shift = Shift(
        code=f"CA-{uuid.uuid4().hex[:8]}",
        name="QA cumulative weekday shift",
        start_time="08:00",
        end_time="17:00",
        lunch_break_duration=60,
        total_hours_minus_lunch=480,
    )
    db.add_all([employee, group, shift])
    db.flush()
    policy = PayrollPolicyVersion(
        version=930_000 + int(uuid.uuid4().hex[:6], 16),
        effective_from=date(2025, 11, 1),
        effective_to=date(2025, 11, 15),
        policy={
            "timezone": "Asia/Manila",
            "monthly_divisor": "22",
            "monthly_salary_proration": "scheduled_workday_fraction",
            "daily_partial_work": "pro_rated",
            "monthly_partial_work": "deduct_after_grace",
            "paid_leave": False,
            "paid_holidays": False,
            "break_minutes": 60,
            "grace_minutes": 0,
            "overtime_rule": {"multiplier": "1.25"},
            "premium_rules": {},
            "allowance_tax_treatment": {
                "fixed_recurring": "taxable",
                "proration": "calendar_days",
                "absence": "not_deducted",
            },
            "rounding_mode": "half_up",
            "contribution_collection": {
                "frequency": "once_monthly",
                "collection_period": "last_period",
            },
            "statutory_sources_reviewed": [
                "https://www.sss.gov.ph/pay-contribution/",
                "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
                "https://www.pagibigfund.gov.ph/",
            ],
        },
        confirmed=True,
    )
    db.add_all(
        [
            EmployeeSalary(
                employee_id=employee.id,
                basic_rate=basic_rate,
                effective_date=date(2025, 11, 1),
                pay_type=pay_type,
                non_taxable_allowance=(
                    Decimal("600.00")
                    if tax_classification == "minimum_wage_earner"
                    else Decimal("0.00")
                ),
            ),
            EmployeePayGroupAssignment(
                employee_id=employee.id,
                pay_group_id=group.id,
                effective_from=date(2025, 11, 1),
            ),
            EmployeeShiftAssignment(
                employee_id=employee.id,
                shift_id=shift.id,
                effective_from=date(2025, 11, 1),
            ),
            EmployeeTaxYearDeclaration(
                employee_id=employee.id,
                tax_year=2025,
                tax_classification=tax_classification,
                opening_as_of=date(2025, 10, 31),
                taxable_compensation_ytd="180000.00",
                tax_withheld_ytd="11000.40",
                opening_pay_period_count=6,
                opening_pay_period_type="semi_monthly",
                previous_employer_included=True,
                opening_de_minimis_annual_ytd={
                    "uniform_clothing": "0.00",
                    "actual_medical_assistance": "0.00",
                    "achievement_award": "0.00",
                    "christmas_anniversary_gift": "0.00",
                    "cba_productivity_incentive": "0.00",
                },
                opening_de_minimis_monthly_ytd={
                    "medical_cash_dependents": "0.00",
                    "rice_subsidy": "0.00",
                    "laundry_allowance": "0.00",
                },
                source_reference=source_reference,
                is_verified=True,
            ),
            policy,
        ]
    )
    for day in range(1, 16):
        work_date = date(2025, 11, day)
        if work_date.weekday() < 5:
            db.add(
                DailyTimeRecord(
                    employee_id=employee.id,
                    shift_id=shift.id,
                    login_date=datetime(2025, 11, day, tzinfo=timezone.utc),
                    logout_date=datetime(2025, 11, day, tzinfo=timezone.utc)
                    + timedelta(hours=9),
                    work_date=work_date,
                    rendered_minutes=480,
                    overtime_minutes=0,
                    is_absent=False,
                    is_time_calculated=True,
                )
            )
    db.commit()

    run_id: uuid.UUID | None = None
    try:
        response = client.post(
            f"{API}/runs/prepare-attendance-draft",
            json={
                "pay_group_id": str(group.id),
                "date_from": "2025-11-01",
                "date_to": "2025-11-15",
            },
            headers=superuser_token_headers,
        )
        assert response.status_code == 201, response.text
        run_id = uuid.UUID(response.json()["id"])
        entry = next(
            row
            for row in response.json()["entries"]
            if row["employee_id"] == str(employee.id)
        )
        assert "bir_cumulative_history_unavailable" not in {
            blocker["code"] for blocker in entry["blockers"]
        }
        assert "bir_cumulative_opening_unavailable" not in {
            blocker["code"] for blocker in entry["blockers"]
        }
        if tax_classification == "ordinary":
            trace = entry["input_snapshot"]["bir_calculation"]
            assert trace["method"] == "cumulative_average_rr_11_2018"
            # A semi-monthly monthly-salary base is half the monthly salary,
            # independent of how many weekdays fall in the cutoff.
            assert trace["cumulative_taxable_compensation"] == "197500.00"
            assert trace["cumulative_period_count"] == 7
            assert trace["average_period_compensation"] == "28214.29"
            assert trace["prior_tax_withheld"] == "11000.40"
            assert Decimal(trace["withholding"]) == Decimal(
                entry["deductions"]["bir_withholding"]
            )
        else:
            assert "bir_calculation" not in entry["input_snapshot"]
            assert any(
                blocker["code"] == "bir_mwe_taxable_allowance_ineligible"
                for blocker in entry["blockers"]
            )
        declaration = entry["input_snapshot"]["tax_year_declaration"]
        assert declaration["opening_pay_period_count"] == 6
        if tax_classification == "ordinary":
            history = entry["input_snapshot"]["bir_year_to_date_history"]
            assert history["opening_pay_period_count"] == 6
            assert history["complete"] is True
    finally:
        # The module-scoped test database persists rows across test cases. This
        # fixed-period policy and draft must not contaminate later test cases.
        if run_id is not None:
            db.exec(
                delete(PayrollEntry).where(PayrollEntry.payroll_run_id == run_id)
            )
            db.exec(delete(PayrollRun).where(PayrollRun.id == run_id))
        db.delete(policy)
        db.commit()


@pytest.mark.parametrize(
    ("pay_type", "basic_rate"),
    [(PayType.DAILY, "1000.00"), (PayType.HOURLY, "125.00")],
)
def test_daily_and_hourly_pay_bases_are_calculated_for_nonfinal_periods(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    pay_type: PayType,
    basic_rate: str,
) -> None:
    # Use historic periods that do not overlap broad/open-ended policies from
    # other payroll API tests sharing the session-scoped database.
    tax_year = 2023 if pay_type == PayType.DAILY else 2024
    period_from = date(tax_year, 11, 1)
    period_to = date(tax_year, 11, 15)
    employee = EmployeeRecords(
        employee_code=f"NONMONTHLY-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Nonmonthly",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    group = PayrollPayGroup(
        code=f"NM-{uuid.uuid4().hex[:8]}",
        name="QA twice-monthly nonmonthly basis",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    shift = Shift(
        code=f"NM-{uuid.uuid4().hex[:8]}",
        name="QA 8-hour weekday shift",
        start_time="08:00",
        end_time="17:00",
        lunch_break_duration=60,
        total_hours_minus_lunch=480,
    )
    db.add_all([employee, group, shift])
    db.flush()
    db.add_all(
        [
            EmployeeSalary(
                employee_id=employee.id,
                basic_rate=basic_rate,
                effective_date=period_from,
                pay_type=pay_type,
            ),
            EmployeePayGroupAssignment(
                employee_id=employee.id,
                pay_group_id=group.id,
                effective_from=period_from,
            ),
            EmployeeShiftAssignment(
                employee_id=employee.id,
                shift_id=shift.id,
                effective_from=period_from,
            ),
            EmployeeTaxYearDeclaration(
                employee_id=employee.id,
                tax_year=tax_year,
                tax_classification="ordinary",
                opening_as_of=date(tax_year, 1, 1),
                taxable_compensation_ytd="0.00",
                tax_withheld_ytd="0.00",
                previous_employer_included=False,
                is_verified=True,
            ),
            PayrollPolicyVersion(
                version=920_000 + int(uuid.uuid4().hex[:6], 16),
                effective_from=period_from,
                effective_to=period_to,
                policy={
                    "timezone": "Asia/Manila",
                    "monthly_divisor": "22",
                    "monthly_salary_proration": "scheduled_workday_fraction",
                    "daily_partial_work": "pro_rated",
                    "monthly_partial_work": "deduct_after_grace",
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
                    "statutory_sources_reviewed": [
                        "https://www.sss.gov.ph/pay-contribution/",
                        "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
                        "https://www.pagibigfund.gov.ph/",
                    ],
                },
                confirmed=True,
            ),
        ]
    )
    for day in range(1, 16):
        work_date = date(tax_year, 11, day)
        if work_date.weekday() >= 5:
            continue
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=datetime(tax_year, 11, day, tzinfo=timezone.utc),
                logout_date=datetime(tax_year, 11, day, tzinfo=timezone.utc)
                + timedelta(hours=9),
                work_date=work_date,
                rendered_minutes=480,
                overtime_minutes=0,
                is_absent=False,
                is_time_calculated=True,
            )
        )
    db.commit()

    response = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json={
            "pay_group_id": str(group.id),
            "date_from": period_from.isoformat(),
            "date_to": period_to.isoformat(),
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 201, response.text
    entry = next(
        row
        for row in response.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert entry["gross_pay"] == "11000.00", {
        "blockers": entry["blockers"],
        "earnings": entry["earnings"],
        "basic_rate": entry["basic_rate"],
        "salaries": entry["input_snapshot"]["salary_versions"],
        "attendance_count": len(entry["input_snapshot"]["attendance_revisions"]),
    }
    assert entry["blockers"] == []
    assert entry["earnings"]["provisional"] is False
    assert entry["calculation_version"] == "attendance-v1"
    assert "pay_basis_unsupported" not in {
        blocker["code"] for blocker in entry["blockers"]
    }
    assert "bir_withholding" in entry["deductions"]


@pytest.mark.parametrize(
    ("year", "pay_type", "basic_rate"),
    [
        (2029, PayType.MONTHLY, "22000.00"),
        (2027, PayType.DAILY, "1000.00"),
        (2028, PayType.HOURLY, "125.00"),
    ],
)
def test_final_semi_monthly_run_collects_one_month_of_time_based_contributions(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    year: int,
    pay_type: PayType,
    basic_rate: str,
) -> None:
    employee = EmployeeRecords(
        employee_code=f"MONTHLY-CONT-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Contribution",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    group = PayrollPayGroup(
        code=f"MC-{uuid.uuid4().hex[:8]}",
        name="QA contribution twice-monthly",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    shift = Shift(
        code=f"MC-{uuid.uuid4().hex[:8]}",
        name="Weekday eight-hour shift",
        start_time="08:00",
        end_time="17:00",
        total_hours_minus_lunch=480,
    )
    db.add_all([employee, group, shift])
    db.flush()
    base_rate = Decimal(basic_rate)
    updated_rate = base_rate * Decimal("1.2")
    db.add_all(
        [
            EmployeeSalary(
                employee_id=employee.id,
                basic_rate=basic_rate,
                effective_date=date(year, 1, 1),
                pay_type=pay_type,
            ),
            EmployeeSalary(
                employee_id=employee.id,
                basic_rate=updated_rate,
                effective_date=date(year, 10, 16),
                pay_type=pay_type,
                non_taxable_allowance="6200.00",
            ),
            EmployeePayGroupAssignment(
                employee_id=employee.id,
                pay_group_id=group.id,
                effective_from=date(year, 1, 1),
            ),
            EmployeeShiftAssignment(
                employee_id=employee.id,
                shift_id=shift.id,
                effective_from=date(year, 1, 1),
            ),
            EmployeeTaxYearDeclaration(
                employee_id=employee.id,
                tax_year=year,
                tax_classification="ordinary",
                opening_as_of=date(2025, 12, 31),
                taxable_compensation_ytd="0.00",
                tax_withheld_ytd="0.00",
                previous_employer_included=False,
                is_verified=True,
            ),
            PayrollPolicyVersion(
                version=930_000 + int(uuid.uuid4().hex[:6], 16),
                effective_from=date(year, 1, 1),
                effective_to=date(year, 12, 31),
                policy={
                    "timezone": "Asia/Manila",
                    "monthly_divisor": "22",
                    "monthly_salary_proration": "scheduled_workday_fraction",
                    "daily_partial_work": "pro_rated",
                    "monthly_partial_work": "deduct_after_grace",
                    "paid_leave": False,
                    "paid_holidays": False,
                    "break_minutes": 60,
                    "grace_minutes": 0,
                    "overtime_rule": {"multiplier": "1.25"},
                    "premium_rules": {},
                    "allowance_tax_treatment": {
                        "fixed_recurring": "taxable",
                        "proration": "calendar_days",
                        "absence": "not_deducted",
                    },
                    "rounding_mode": "half_up",
                    "contribution_collection": {
                        "frequency": "once_monthly",
                        "collection_period": "last_period",
                    },
                    "statutory_sources_reviewed": [
                        "https://www.sss.gov.ph/pay-contribution/",
                        "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
                        "https://www.pagibigfund.gov.ph/document/pdf/circulars/provident/HDMF%20Circular%20No.%20274.pdf",
                    ],
                },
                confirmed=True,
            ),
        ]
    )
    first_late_workday = next(
        date(year, 10, candidate)
        for candidate in range(16, 32)
        if date(year, 10, candidate).weekday() < 5
    )
    for day in range(1, 32):
        work_date = date(year, 10, day)
        if work_date.weekday() >= 5:
            continue
        is_absent = work_date == date(year, 10, 5)
        is_late = work_date == first_late_workday
        login_at = datetime(year, 10, day, tzinfo=timezone.utc) + timedelta(
            minutes=15 if is_late else 0
        )
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=None if is_absent else login_at,
                # Keep the scheduled 17:00 Manila clock-out fixed. A late
                # login therefore reduces payable shift minutes instead of
                # shifting the whole nine-hour interval later.
                logout_date=(
                    None
                    if is_absent
                    else datetime(year, 10, day, tzinfo=timezone.utc)
                    + timedelta(hours=9)
                ),
                work_date=work_date,
                rendered_minutes=0 if is_absent else 465 if is_late else 480,
                overtime_minutes=0,
                is_absent=is_absent,
                is_time_calculated=True,
            )
        )
    db.commit()

    response = client.post(
        f"{API}/runs/prepare-attendance-draft",
        json={
            "pay_group_id": str(group.id),
            "date_from": f"{year}-10-16",
            "date_to": f"{year}-10-31",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 201, response.text
    entry = next(
        row
        for row in response.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    period_days = sum(
        1 for day in range(16, 32) if date(year, 10, day).weekday() < 5
    )
    divisor = Decimal("22")
    hours_per_shift = Decimal(8) if pay_type == PayType.HOURLY else Decimal(1)
    if pay_type == PayType.MONTHLY:
        daily_basis_before_change = base_rate / divisor
        daily_basis_after_change = updated_rate / divisor
    else:
        daily_basis_before_change = base_rate * hours_per_shift
        daily_basis_after_change = updated_rate * hours_per_shift
    days_before_change = sum(
        1
        for day in range(1, 16)
        if date(year, 10, day).weekday() < 5 and day != 5
    )
    days_after_change = period_days
    partial_day_reduction = daily_basis_after_change * Decimal(15) / Decimal(480)
    expected_period_gross = daily_basis_after_change * Decimal(days_after_change)
    if pay_type == PayType.MONTHLY:
        expected_period_gross = updated_rate / Decimal("2")
    else:
        expected_period_gross -= partial_day_reduction
    expected_period_gross += Decimal("3200.00")
    assert Decimal(entry["gross_pay"]) == expected_period_gross, entry
    assert entry["earnings"]["fixed_recurring_allowance"] == "3200.00"
    if pay_type == PayType.MONTHLY:
        assert Decimal(entry["deductions"]["attendance"]) == partial_day_reduction
        assert (
            Decimal(
                entry["deductions"]["attendance_breakdown"][
                    "monthly_short_time_after_grace"
                ]
            )
            == partial_day_reduction
        )
    assert not any(
        blocker["code"].startswith("monthly_contribution_")
        or blocker["code"] == "statutory_schedule_unavailable"
        for blocker in entry["blockers"]
    ), entry["blockers"]
    bases = entry["input_snapshot"]["monthly_contributions"]["schemes"]
    if pay_type == PayType.MONTHLY:
        expected_actual = (
            base_rate / Decimal("2")
            + updated_rate / Decimal("2")
            - base_rate / divisor
            - partial_day_reduction
        ).quantize(Decimal("0.01"))
    else:
        expected_actual = (
            daily_basis_before_change * Decimal(days_before_change)
            + daily_basis_after_change * Decimal(days_after_change)
            - partial_day_reduction
        ).quantize(Decimal("0.01"))
    expected_actual += Decimal("3200.00")
    monthly_equivalent_before_change = (
        base_rate if pay_type == PayType.MONTHLY else base_rate * hours_per_shift * divisor
    )
    monthly_equivalent_after_change = (
        updated_rate
        if pay_type == PayType.MONTHLY
        else updated_rate * hours_per_shift * divisor
    )
    expected_philhealth_basis = (
        monthly_equivalent_before_change * Decimal("15") / Decimal("31")
        + monthly_equivalent_after_change * Decimal("16") / Decimal("31")
    ).quantize(Decimal("0.01"))
    assert bases["sss"]["basis"] == str(expected_actual)
    assert bases["philhealth"]["basis"] == str(expected_philhealth_basis)
    assert bases["pagibig"]["basis"] == str(expected_actual)


def test_resigned_or_terminated_employee_needs_separation_date_for_payroll(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = EmployeeRecords(
        employee_code=f"END-DATE-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Separated",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
        employee_status=EmployeeStatus.TERMINATED,
    )
    group = PayrollPayGroup(
        code=f"END-DATE-{uuid.uuid4().hex[:8]}",
        name="QA terminated employee boundary",
        cadence="monthly",
        weekend_rule="next_business_day",
    )
    db.add_all([employee, group])
    db.commit()

    response = client.get(
        f"{API}/runs/preflight",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    entry = next(
        row
        for row in response.json()["entries"]
        if row["employee_id"] == str(employee.id)
    )
    assert "employment_end_date_missing" in {
        blocker["code"] for blocker in entry["blockers"]
    }


def test_attendance_preview_calculates_night_differential_from_current_intervals(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = EmployeeRecords(
        employee_code=f"NIGHT-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Night Worker",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    group = PayrollPayGroup(
        code=f"NIGHT-{uuid.uuid4().hex[:8]}",
        name="QA night shift pay group",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    shift = Shift(
        code=f"NIGHT-{uuid.uuid4().hex[:8]}",
        name="QA 10pm to 6am shift",
        start_time="22:00",
        end_time="06:00",
        lunch_break_duration=0,
        total_hours_minus_lunch=480,
    )
    db.add_all([employee, group, shift])
    db.flush()
    assignment = EmployeeShiftAssignment(
        employee_id=employee.id,
        shift_id=shift.id,
        effective_from=date(2092, 10, 1),
    )
    pay_assignment = EmployeePayGroupAssignment(
        employee_id=employee.id,
        pay_group_id=group.id,
        effective_from=date(2092, 10, 1),
    )
    salary = EmployeeSalary(
        employee_id=employee.id,
        basic_rate=Decimal("120"),
        overtime_rate=Decimal("120"),
        effective_date=date(2092, 10, 1),
        pay_type=PayType.HOURLY,
    )
    policy = PayrollPolicyVersion(
        version=990_000 + int(uuid.uuid4().hex[:6], 16),
        effective_from=date(2092, 10, 1),
        effective_to=date(2092, 10, 31),
        confirmed=True,
        policy={
            "timezone": "Asia/Manila",
            "monthly_divisor": "22",
            "monthly_salary_proration": "scheduled_workday_fraction",
            "monthly_holiday_pay_divisor": "22",
            "daily_partial_work": "pro_rated",
            "monthly_partial_work": "deduct_after_grace",
            "paid_leave": False,
            "paid_holidays": False,
            "break_minutes": 0,
            "grace_minutes": 0,
            "overtime_rule": {"multiplier": "1.25"},
            "premium_rules": {"night_differential_rate": "0.10"},
            "allowance_tax_treatment": {"configured": False},
            "rounding_mode": "half_up",
            "contribution_collection": {
                "frequency": "once_monthly",
                "collection_period": "last_period",
            },
            "statutory_sources_reviewed": ["QA fixture only"],
        },
    )
    db.add_all([assignment, pay_assignment, salary, policy])
    db.flush()

    zone = ZoneInfo("Asia/Manila")
    for day in range(1, 16):
        work_date = date(2092, 10, day)
        if work_date.weekday() >= 5:
            continue
        local_start = datetime.combine(work_date, datetime.min.time(), tzinfo=zone).replace(
            hour=22
        )
        local_end = local_start + timedelta(hours=8)
        start_utc = local_start.astimezone(timezone.utc)
        end_utc = local_end.astimezone(timezone.utc)
        dtr = DailyTimeRecord(
            employee_id=employee.id,
            shift_id=shift.id,
            login_date=start_utc,
            logout_date=end_utc,
            work_date=work_date,
            rendered_minutes=480,
            overtime_minutes=0,
            is_absent=False,
            is_time_calculated=True,
            interval_revision=1,
        )
        db.add(dtr)
        db.flush()
        db.add(
            DtrAttendanceInterval(
                daily_time_record_id=dtr.id,
                revision=1,
                sequence=0,
                start_at=start_utc,
                end_at=end_utc,
            )
        )
    db.commit()

    response = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2092-10-01",
            "date_to": "2092-10-15",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    entry = next(
        row for row in response.json()["entries"] if row["employee_id"] == str(employee.id)
    )
    assert not entry["blockers"], entry["blockers"]
    assert entry["regular_earnings"] == "10560.00"
    assert entry["night_differential"] == "1056.00"
    assert entry["gross_before_statutory"] == "11616.00"
    assert any("480 regular and 0 approved overtime night minutes" in line for line in entry["formula"])


def test_attendance_preview_calculates_ordinary_rest_day_premium(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = EmployeeRecords(
        employee_code=f"REST-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Rest Day Worker",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
    )
    group = PayrollPayGroup(
        code=f"REST-{uuid.uuid4().hex[:8]}",
        name="QA rest day pay group",
        cadence="semi_monthly",
        first_period_end_day=15,
        second_period_end_day=31,
        weekend_rule="next_business_day",
    )
    shift = Shift(
        code=f"REST-{uuid.uuid4().hex[:8]}",
        name="QA Monday to Saturday shift",
        start_time="08:00",
        end_time="16:00",
        lunch_break_duration=0,
        total_hours_minus_lunch=480,
        days_of_week=["1", "2", "3", "4", "5", "6"],
    )
    db.add_all([employee, group, shift])
    db.flush()
    db.add_all(
        [
            EmployeeShiftAssignment(
                employee_id=employee.id,
                shift_id=shift.id,
                effective_from=date(2090, 10, 1),
            ),
            EmployeePayGroupAssignment(
                employee_id=employee.id,
                pay_group_id=group.id,
                effective_from=date(2090, 10, 1),
            ),
            EmployeeSalary(
                employee_id=employee.id,
                basic_rate=Decimal("960"),
                overtime_rate=Decimal("120"),
                effective_date=date(2090, 10, 1),
                pay_type=PayType.DAILY,
            ),
            PayrollPolicyVersion(
                version=991_000 + int(uuid.uuid4().hex[:6], 16),
                effective_from=date(2090, 10, 1),
                effective_to=date(2090, 10, 31),
                confirmed=True,
                policy={
                    "timezone": "Asia/Manila",
                    "monthly_divisor": "22",
                    "monthly_salary_proration": "scheduled_workday_fraction",
                    "monthly_holiday_pay_divisor": "22",
                    "daily_partial_work": "pro_rated",
                    "monthly_partial_work": "deduct_after_grace",
                    "paid_leave": False,
                    "paid_holidays": False,
                    "break_minutes": 0,
                    "grace_minutes": 0,
                    "overtime_rule": {"multiplier": "1.25"},
                    "premium_rules": {
                        "rest_day_regular_multiplier": "1.30",
                        "rest_day_overtime_multiplier": "1.69",
                    },
                    "allowance_tax_treatment": {"configured": False},
                    "rounding_mode": "half_up",
                    "contribution_collection": {
                        "frequency": "once_monthly",
                        "collection_period": "last_period",
                    },
                    "statutory_sources_reviewed": ["QA fixture only"],
                },
            ),
        ]
    )
    db.flush()
    zone = ZoneInfo("Asia/Manila")
    for day in range(1, 16):
        work_date = date(2090, 10, day)
        if work_date.weekday() < 6:
            start_local = datetime.combine(work_date, datetime.min.time(), tzinfo=zone).replace(
                hour=8
            )
            worked_minutes = 480
        elif work_date == date(2090, 10, 8):
            start_local = datetime.combine(work_date, datetime.min.time(), tzinfo=zone).replace(
                hour=8
            )
            worked_minutes = 480
        else:
            continue
        start_utc = start_local.astimezone(timezone.utc)
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=start_utc,
                logout_date=start_utc + timedelta(minutes=worked_minutes),
                work_date=work_date,
                rendered_minutes=worked_minutes,
                overtime_minutes=0,
                is_absent=False,
                is_time_calculated=True,
            )
        )
    db.commit()

    response = client.get(
        f"{API}/runs/attendance-calculation-preview",
        params={
            "pay_group_id": str(group.id),
            "date_from": "2090-10-01",
            "date_to": "2090-10-15",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    entry = next(
        row for row in response.json()["entries"] if row["employee_id"] == str(employee.id)
    )
    assert not entry["blockers"], entry["blockers"]
    assert entry["regular_earnings"] == "12480.00"
    assert entry["rest_day_premium"] == "288.00"
    assert entry["gross_before_statutory"] == "12768.00"
    assert any("ordinary rest-day work" in line for line in entry["formula"])
