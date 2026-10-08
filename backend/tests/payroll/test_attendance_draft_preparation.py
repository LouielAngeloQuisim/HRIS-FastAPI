"""The attendance payroll preparation route persists blocked, auditable drafts."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.attendance.models import (
    DailyTimeRecord,
    EmployeeShiftAssignment,
    Shift,
)
from app.audit.models import AuditLog
from app.common.security import get_password_hash
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import (
    EmployeePayGroupAssignment,
    EmployeeSalary,
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
from app.payroll.routes import _payroll_entry_inputs_are_current
from app.user.models import User
from tests.utils.user import user_authentication_headers

API = f"{settings.API_V1_STR}/payroll"


def test_prepare_creates_replayable_draft_and_keeps_finalization_blocked(
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
        effective_from=date(2026, 10, 1),
        effective_to=date(2026, 10, 31),
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
            "statutory_sources_reviewed": [
                "https://www.sss.gov.ph/pay-contribution/",
                "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
                "https://www.pagibigfund.gov.ph/",
            ],
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
    assert replacement_entry["gross_pay"] == "13000.00"
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
    assert second_entry["taxable_income"] == "10850.00", second_entry["blockers"]
    assert second_entry["deductions"]["bir_withholding"] == "64.95"
    assert second_entry["deductions"]["statutory"] == {
        "sss": "1300.00",
        "philhealth": "650.00",
        "pagibig": "200.00",
    }
    schedule_snapshots = second_entry["input_snapshot"]["monthly_contributions"]["schemes"]
    for scheme in ("sss", "philhealth", "pagibig"):
        schedule_rows = schedule_snapshots[scheme]["schedule_rows"]
        assert schedule_rows
        assert schedule_rows[0]["updated_at"]
        assert schedule_rows[0]["values"]
    payroll_entry = db.get(PayrollEntry, uuid.UUID(second_entry["id"]))
    assert payroll_entry is not None
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


def test_december_draft_uses_annualized_tax_and_opening_balance(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    employee = EmployeeRecords(
        employee_code=f"YEAR-END-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Year End",
        birthdate=date(1990, 1, 1),
        date_hired=date(2020, 1, 1),
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
                opening_as_of=date(2026, 12, 15),
                taxable_compensation_ytd="300000.00",
                tax_withheld_ytd="4000.00",
                previous_employer_included=True,
                source_reference="QA verified opening YTD example",
                is_verified=True,
            ),
            PayrollPolicyVersion(
                version=910_000 + int(uuid.uuid4().hex[:6], 16),
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
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
    # Full-month attendance is needed to establish the once-monthly statutory
    # contribution basis, even though this is the final half-month run.
    for day in range(1, 32):
        work_date = date(2026, 12, day)
        if work_date.weekday() >= 5:
            continue
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=datetime(2026, 12, day, tzinfo=timezone.utc),
                logout_date=datetime(2026, 12, day, tzinfo=timezone.utc)
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
            "date_from": "2026-12-16",
            "date_to": "2026-12-31",
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
    assert annual_taxable == Decimal("311981.82")
    assert annual_tax_due == Decimal("9297.27")
    assert prior_withheld == Decimal("4000.00")
    assert withholding_adjustment == Decimal("5297.27")


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
        trace = entry["input_snapshot"]["bir_calculation"]
        if tax_classification == "ordinary":
            assert trace["method"] == "cumulative_average_rr_11_2018"
            # November 1–15, 2025 has 10 weekdays. Monthly proration uses the
            # configured 22-day divisor, so current taxable pay is 35,000 * 10 / 22.
            assert trace["cumulative_taxable_compensation"] == "195909.09"
            assert trace["cumulative_period_count"] == 7
            assert trace["average_period_compensation"] == "27987.01"
            assert trace["prior_tax_withheld"] == "11000.40"
        else:
            assert trace["method"] == "mwe_exemption_rr_8_2018"
            assert trace["taxable_compensation"] == "0.00"
            assert trace["withholding"] == "0.00"
        assert Decimal(trace["withholding"]) == Decimal(
            entry["deductions"]["bir_withholding"]
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
    assert entry["earnings"]["provisional"] is True
    assert "pay_basis_unsupported" not in {
        blocker["code"] for blocker in entry["blockers"]
    }
    assert "bir_withholding" in entry["deductions"]


@pytest.mark.parametrize(
    ("year", "pay_type", "basic_rate"),
    [
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
    for day in range(1, 32):
        work_date = date(year, 10, day)
        if work_date.weekday() >= 5:
            continue
        db.add(
            DailyTimeRecord(
                employee_id=employee.id,
                shift_id=shift.id,
                login_date=datetime(year, 10, day, tzinfo=timezone.utc),
                logout_date=datetime(year, 10, day, tzinfo=timezone.utc)
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
    hours_per_shift = (
        Decimal(8) if pay_type == PayType.HOURLY else Decimal(1)
    )
    daily_basis_before_change = base_rate * hours_per_shift
    daily_basis_after_change = updated_rate * hours_per_shift
    days_before_change = sum(
        1 for day in range(1, 16) if date(year, 10, day).weekday() < 5
    )
    days_after_change = period_days
    expected_period_gross = daily_basis_after_change * Decimal(days_after_change)
    assert Decimal(entry["gross_pay"]) == expected_period_gross, entry["blockers"]
    assert not any(
        blocker["code"].startswith("monthly_contribution_")
        or blocker["code"] == "statutory_schedule_unavailable"
        for blocker in entry["blockers"]
    ), entry["blockers"]
    bases = entry["input_snapshot"]["monthly_contributions"]["schemes"]
    expected_actual = (
        daily_basis_before_change * Decimal(days_before_change)
        + daily_basis_after_change * Decimal(days_after_change)
    ).quantize(Decimal("0.01"))
    expected_philhealth_basis = (
        daily_basis_before_change
        * Decimal("22")
        * Decimal("15")
        / Decimal("31")
        + daily_basis_after_change
        * Decimal("22")
        * Decimal("16")
        / Decimal("31")
    ).quantize(Decimal("0.01"))
    assert bases["sss"]["basis"] == str(expected_actual)
    assert bases["philhealth"]["basis"] == str(expected_philhealth_basis)
    assert bases["pagibig"]["basis"] == str(expected_actual)
