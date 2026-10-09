"""Reviewed tax classification and year-to-date opening input API tests."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.attendance.models import DailyTimeRecord
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.leave.models import (
    EmployeeLeaveEnrollment,
    LeaveLedgerEntry,
    LeaveLedgerSource,
    LeavePolicy,
)
from app.payroll.models import EmployeeTaxBenefit, EmployeeTaxYearDeclaration
from app.payroll.routes import _bir_tax_benefit_rows

API = f"{settings.API_V1_STR}/payroll"


def _vacation_policy_and_balance(
    db: Session, employee: EmployeeRecords, days: Decimal
) -> tuple[LeavePolicy, EmployeeLeaveEnrollment]:
    policy = LeavePolicy(
        code=f"VAC-{uuid.uuid4().hex[:8]}",
        name="Vacation leave",
        is_paid=True,
        tax_exempt_unused_vacation_leave=True,
    )
    db.add(policy)
    db.flush()
    enrollment = EmployeeLeaveEnrollment(
        employee_id=employee.id,
        policy_id=policy.id,
        leave_year=2026,
        granted_days=days,
        is_active=True,
    )
    db.add(enrollment)
    db.flush()
    db.add(
        LeaveLedgerEntry(
            employee_id=employee.id,
            policy_id=policy.id,
            enrollment_id=enrollment.id,
            leave_year=2026,
            source=LeaveLedgerSource.GRANT,
            amount=days,
            reference=f"QA-vacation-grant:{enrollment.id}",
        )
    )
    db.commit()
    return policy, enrollment


@pytest.fixture
def employee_record(db: Session) -> EmployeeRecords:
    employee = EmployeeRecords(
        employee_code=f"TAX-{uuid.uuid4().hex[:8]}",
        first_name="Tax",
        last_name="Test",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def test_tax_year_declaration_upsert_and_get(
    client: TestClient,
    db: Session,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    employee = employee_record
    url = f"{API}/employees/{employee.id}/tax-year-declarations/2026"
    payload = {
        "tax_classification": "ordinary",
        "opening_as_of": "2026-06-30",
        "taxable_compensation_ytd": "120000.00",
        "tax_withheld_ytd": "5000.00",
        "opening_pay_period_count": 12,
        "opening_pay_period_type": "monthly",
        "previous_employer_included": True,
        "previous_employer_period_from": "2026-01-01",
        "previous_employer_period_to": "2026-03-31",
        "opening_benefits_exempt_ytd": "70000.00",
        "opening_benefits_reconciled": True,
        "opening_de_minimis_annual_ytd": {
            "uniform_clothing": "0.00",
            "actual_medical_assistance": "0.00",
            "achievement_award": "0.00",
            "christmas_anniversary_gift": "0.00",
            "cba_productivity_incentive": "0.00",
        },
        "opening_de_minimis_monthly_ytd": {
            "medical_cash_dependents": "0.00",
            "rice_subsidy": "0.00",
            "laundry_allowance": "0.00",
        },
        "source_reference": "Prior payroll tax records reviewed",
        "is_verified": True,
    }

    assert client.get(url, headers=superuser_token_headers).status_code == 404
    created = client.put(url, json=payload, headers=superuser_token_headers)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["employee_id"] == str(employee.id)
    assert body["tax_year"] == 2026
    assert body["opening_as_of"] == "2026-06-30"
    assert body["taxable_compensation_ytd"] == "120000.00"
    assert body["tax_withheld_ytd"] == "5000.00"
    assert body["opening_pay_period_count"] == 12
    assert body["opening_pay_period_type"] == "monthly"
    assert body["previous_employer_included"] is True
    assert "employee_tin" not in body
    assert "previous_employer_name" not in body
    assert "certificate_identity_verified" not in body
    assert body["opening_benefits_exempt_ytd"] == "70000.00"
    assert body["opening_benefits_reconciled"] is True
    assert body["is_verified"] is True
    assert body["verified_by"]
    assert body["verified_at"]

    updated = client.put(
        url,
        json={**payload, "taxable_compensation_ytd": "140000.00"},
        headers=superuser_token_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == body["id"]
    assert updated.json()["taxable_compensation_ytd"] == "140000.00"
    assert client.get(url, headers=superuser_token_headers).json()["id"] == body["id"]
    assert db.get(EmployeeTaxYearDeclaration, uuid.UUID(body["id"])) is not None


def test_previous_employer_period_must_belong_to_declared_tax_year(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.put(
        f"{API}/employees/{employee_record.id}/tax-year-declarations/2026",
        json={
            "opening_as_of": "2026-06-30",
            "opening_pay_period_count": 6,
            "opening_pay_period_type": "monthly",
            "previous_employer_included": True,
            "opening_benefits_reconciled": True,
            "opening_de_minimis_annual_ytd": {
                "uniform_clothing": "0.00",
                "actual_medical_assistance": "0.00",
                "achievement_award": "0.00",
                "christmas_anniversary_gift": "0.00",
                "cba_productivity_incentive": "0.00",
            },
            "opening_de_minimis_monthly_ytd": {
                "medical_cash_dependents": "0.00",
                "rice_subsidy": "0.00",
                "laundry_allowance": "0.00",
            },
            "source_reference": "Reviewed source form",
            "previous_employer_period_from": "2025-12-01",
            "previous_employer_period_to": "2026-03-31",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 422
    assert "within the declared tax year" in response.text


def test_previous_employer_period_cannot_exceed_opening_balance_cutoff(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.put(
        f"{API}/employees/{employee_record.id}/tax-year-declarations/2026",
        json={
            "opening_as_of": "2026-06-30",
            "opening_pay_period_count": 6,
            "opening_pay_period_type": "monthly",
            "previous_employer_included": True,
            "opening_benefits_reconciled": True,
            "opening_de_minimis_annual_ytd": {
                "uniform_clothing": "0.00",
                "actual_medical_assistance": "0.00",
                "achievement_award": "0.00",
                "christmas_anniversary_gift": "0.00",
                "cba_productivity_incentive": "0.00",
            },
            "opening_de_minimis_monthly_ytd": {
                "medical_cash_dependents": "0.00",
                "rice_subsidy": "0.00",
                "laundry_allowance": "0.00",
            },
            "source_reference": "Reviewed source form",
            "previous_employer_period_from": "2026-01-01",
            "previous_employer_period_to": "2026-07-31",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 422
    assert "cannot extend beyond the opening balance cutoff" in response.text


def test_tax_year_benefit_ledger_is_auditable_and_supports_one_full_reversal(
    client: TestClient,
    db: Session,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-benefits/2026"
    payment = client.post(
        url,
        json={
            "paid_on": "2026-07-01",
            "benefit_type": "thirteenth_month",
            "gross_amount": "30000.00",
            "source_reference": "Voucher PV-2026-071 reviewed",
        },
        headers=superuser_token_headers,
    )
    assert payment.status_code == 201, payment.text
    original = payment.json()
    assert original["gross_amount"] == "30000.00"
    assert original["correction_of_id"] is None
    duplicate_payment = client.post(
        url,
        json={
            "paid_on": "2026-07-01",
            "benefit_type": "thirteenth_month",
            "gross_amount": "30000.00",
            "source_reference": "Voucher PV-2026-071 reviewed",
        },
        headers=superuser_token_headers,
    )
    assert duplicate_payment.status_code == 409

    invalid_partial_reversal = client.post(
        url,
        json={
            "paid_on": "2026-07-02",
            "benefit_type": "thirteenth_month",
            "gross_amount": "-10000.00",
            "source_reference": "Correction note 1",
            "correction_of_id": original["id"],
            "correction_reason": "Incorrect voucher total",
        },
        headers=superuser_token_headers,
    )
    assert invalid_partial_reversal.status_code == 422

    reversal_payload = {
        "paid_on": "2026-07-02",
        "benefit_type": "thirteenth_month",
        "gross_amount": "-30000.00",
        "source_reference": "Correction note 2",
        "correction_of_id": original["id"],
        "correction_reason": "Original voucher was entered twice",
    }
    reversal = client.post(url, json=reversal_payload, headers=superuser_token_headers)
    assert reversal.status_code == 201, reversal.text
    assert reversal.json()["correction_reason"] == reversal_payload["correction_reason"]
    assert reversal.json()["gross_amount"] == "-30000.00"

    duplicate_reversal = client.post(url, json=reversal_payload, headers=superuser_token_headers)
    assert duplicate_reversal.status_code == 409
    listed = client.get(url, headers=superuser_token_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert sum(Decimal(item["gross_amount"]) for item in listed.json()) == Decimal("0.00")
    assert db.get(EmployeeTaxBenefit, uuid.UUID(original["id"])) is not None


def test_tax_year_benefit_ledger_requires_payroll_approval(
    client: TestClient,
    employee_record: EmployeeRecords,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{API}/employees/{employee_record.id}/tax-year-benefits/2026",
        json={
            "paid_on": "2026-07-01",
            "benefit_type": "other_benefit",
            "gross_amount": "100.00",
            "source_reference": "Voucher PV-26-001",
        },
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_de_minimis_ledger_requires_category_and_conditional_evidence(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-benefits/2026"
    base = {
        "paid_on": "2026-07-01",
        "benefit_type": "de_minimis",
        "gross_amount": "12000.00",
        "source_reference": "Voucher PV-26-071",
    }

    missing_category = client.post(url, json=base, headers=superuser_token_headers)
    assert missing_category.status_code == 422

    missing_evidence = client.post(
        url,
        json={**base, "de_minimis_category": "actual_medical_assistance"},
        headers=superuser_token_headers,
    )
    assert missing_evidence.status_code == 422
    assert "actual_medical_documentation" in missing_evidence.text

    saved = client.post(
        url,
        json={
            **base,
            "de_minimis_category": "actual_medical_assistance",
            "eligibility_evidence": ["actual_medical_documentation"],
        },
        headers=superuser_token_headers,
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["de_minimis_category"] == "actual_medical_assistance"
    assert saved.json()["eligibility_evidence"] == ["actual_medical_documentation"]


def test_unused_vacation_monetization_uses_and_reverses_leave_ledger(
    client: TestClient,
    db: Session,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    policy, enrollment = _vacation_policy_and_balance(
        db, employee_record, Decimal("5.00")
    )
    url = f"{API}/employees/{employee_record.id}/tax-year-benefits/2026"
    payload = {
        "paid_on": "2026-07-01",
        "benefit_type": "de_minimis",
        "de_minimis_category": "monetized_unused_vacation_leave",
        "qualifying_days": 6,
        "vacation_leave_policy_id": str(policy.id),
        "gross_amount": "6000.00",
        "source_reference": "Vacation monetization QA voucher",
    }
    insufficient = client.post(url, json=payload, headers=superuser_token_headers)
    assert insufficient.status_code == 422
    assert "Insufficient unused vacation leave balance" in insufficient.text
    assert not db.exec(
        select(EmployeeTaxBenefit).where(
            EmployeeTaxBenefit.employee_id == employee_record.id
        )
    ).all()

    payload["qualifying_days"] = 4
    created = client.post(url, json=payload, headers=superuser_token_headers)
    assert created.status_code == 201, created.text
    original = created.json()
    assert original["vacation_leave_policy_id"] == str(policy.id)
    assert original["eligibility_snapshot"]["enrollment_id"] == str(enrollment.id)
    assert original["eligibility_snapshot"]["available_days_before"] == "5.00"
    debit = db.exec(
        select(LeaveLedgerEntry).where(
            LeaveLedgerEntry.reference == f"PayrollTaxBenefit:{original['id']}"
        )
    ).one()
    assert debit.amount == Decimal("-4.00")
    duplicate = client.post(url, json=payload, headers=superuser_token_headers)
    assert duplicate.status_code == 409
    assert "source reference is already recorded" in duplicate.text
    assert len(
        db.exec(
            select(LeaveLedgerEntry).where(
                LeaveLedgerEntry.reference == f"PayrollTaxBenefit:{original['id']}"
            )
        ).all()
    ) == 1

    reversal_payload = {
        **payload,
        "paid_on": "2026-07-02",
        "gross_amount": "-6000.00",
        "source_reference": "Vacation monetization QA reversal",
        "correction_of_id": original["id"],
        "correction_reason": "Voucher was voided",
    }
    reversed_response = client.post(
        url, json=reversal_payload, headers=superuser_token_headers
    )
    assert reversed_response.status_code == 201, reversed_response.text
    credit = db.exec(
        select(LeaveLedgerEntry).where(
            LeaveLedgerEntry.reference == f"PayrollTaxBenefitReversal:{original['id']}"
        )
    ).one()
    assert credit.source == LeaveLedgerSource.REVERSAL
    assert credit.amount == Decimal("4.00")


def test_day_based_benefit_api_requires_and_persists_specific_evidence(
    client: TestClient,
    db: Session,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-benefits/2026"
    common = {
        "paid_on": "2026-07-01",
        "benefit_type": "de_minimis",
        "gross_amount": "500.00",
        "source_reference": "Meal voucher QA-001",
        "de_minimis_category": "daily_meal_ot_night",
        "eligibility_evidence": ["approved_overtime_or_night_shift_records"],
        "qualifying_days": 2,
        "qualifying_work_dates": ["2026-06-30", "2026-07-01"],
    }

    missing_wage_order = client.post(
        url,
        json=common,
        headers=superuser_token_headers,
    )
    assert missing_wage_order.status_code == 422

    # Attendance evidence is checked server-side; a client checkbox alone is
    # not sufficient. The first work date is valid but the second is missing.
    db.add(
        DailyTimeRecord(
            employee_id=employee_record.id,
            work_date=date(2026, 6, 30),
            overtime_minutes=60,
            overtime_approved_minutes=30,
        )
    )
    db.commit()
    missing_attendance = client.post(
        url,
        json={
            **common,
            "regional_daily_minimum_wage": "610.00",
            "region_code": "NCR",
            "wage_order_reference": "NCR-WO-QA-01",
            "wage_order_effective_from": "2026-01-01",
        },
        headers=superuser_token_headers,
    )
    assert missing_attendance.status_code == 422
    assert "No active attendance record" in missing_attendance.text

    db.add(
        DailyTimeRecord(
            employee_id=employee_record.id,
            work_date=date(2026, 7, 1),
            overtime_minutes=60,
            overtime_approved_minutes=30,
        )
    )
    db.commit()

    saved = client.post(
        url,
        json={
            **common,
            "regional_daily_minimum_wage": "610.00",
            "region_code": "NCR",
            "wage_order_reference": "NCR-WO-QA-01",
            "wage_order_effective_from": "2026-01-01",
        },
        headers=superuser_token_headers,
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["qualifying_days"] == 2
    assert saved.json()["qualifying_work_dates"] == ["2026-06-30", "2026-07-01"]
    assert saved.json()["regional_daily_minimum_wage"] == "610.00"
    assert saved.json()["region_code"] == "NCR"

    duplicate_dates = client.post(
        url,
        json={
            **common,
            "source_reference": "Duplicate meal voucher QA-002",
            "regional_daily_minimum_wage": "610.00",
            "region_code": "NCR",
            "wage_order_reference": "NCR-WO-QA-01",
            "wage_order_effective_from": "2026-01-01",
        },
        headers=superuser_token_headers,
    )
    assert duplicate_dates.status_code == 409
    assert "already claimed" in duplicate_dates.text


def test_bir_benefit_ledger_applies_reconciled_category_opening_balances(
    db: Session, employee_record: EmployeeRecords
) -> None:
    db.add_all(
        [
            EmployeeTaxBenefit(
                employee_id=employee_record.id,
                tax_year=2026,
                paid_on=date(2026, 10, 20),
                benefit_type="de_minimis",
                de_minimis_category="rice_subsidy",
                gross_amount="1000.00",
                source_reference="Voucher rice October",
            ),
            EmployeeTaxBenefit(
                employee_id=employee_record.id,
                tax_year=2026,
                paid_on=date(2026, 10, 21),
                benefit_type="de_minimis",
                de_minimis_category="uniform_clothing",
                gross_amount="3000.00",
                source_reference="Voucher uniform October",
            ),
        ]
    )
    db.commit()

    rows = _bir_tax_benefit_rows(
        db,
        employee_record.id,
        2026,
        date(2026, 10, 15),
        date(2026, 10, 31),
        {"uniform_clothing": "6000.00"},
        {"rice_subsidy": "2000.00"},
    )

    by_category = {row["de_minimis_category"]: row for row in rows}
    assert by_category["rice_subsidy"]["category_exempt_amount"] == "500.00"
    assert by_category["rice_subsidy"]["category_excess_amount"] == "500.00"
    assert by_category["uniform_clothing"]["category_exempt_amount"] == "2000.00"
    assert by_category["uniform_clothing"]["category_excess_amount"] == "1000.00"


def test_bir_benefit_ledger_applies_day_based_meal_and_vacation_rules(
    db: Session, employee_record: EmployeeRecords
) -> None:
    policy, enrollment = _vacation_policy_and_balance(
        db, employee_record, Decimal("10.00")
    )
    vacation_benefit = EmployeeTaxBenefit(
        employee_id=employee_record.id,
        tax_year=2026,
        paid_on=date(2026, 7, 11),
        benefit_type="de_minimis",
        de_minimis_category="monetized_unused_vacation_leave",
        qualifying_days=4,
        vacation_leave_policy_id=policy.id,
        gross_amount=Decimal("4000.00"),
        source_reference="QA leave monetization voucher",
    )
    leave_reference = f"PayrollTaxBenefit:{vacation_benefit.id}"
    vacation_benefit.eligibility_snapshot = {
        "policy_id": str(policy.id),
        "policy_is_paid": True,
        "policy_tax_exempt_unused_vacation_leave": True,
        "enrollment_id": str(enrollment.id),
        "leave_year": 2026,
        "qualifying_days": 4,
        "ledger_reference": leave_reference,
    }
    db.add_all(
        [
            DailyTimeRecord(
                employee_id=employee_record.id,
                work_date=date(2026, 7, 1),
                overtime_minutes=60,
                overtime_approved_minutes=30,
            ),
            DailyTimeRecord(
                employee_id=employee_record.id,
                work_date=date(2026, 7, 2),
                overtime_minutes=60,
                overtime_approved_minutes=30,
            ),
        ]
    )
    db.add_all(
        [
            EmployeeTaxBenefit(
                employee_id=employee_record.id,
                tax_year=2026,
                paid_on=date(2026, 7, 10),
                benefit_type="de_minimis",
                de_minimis_category="daily_meal_ot_night",
                eligibility_evidence=["approved_overtime_or_night_shift_records"],
                qualifying_days=2,
                qualifying_work_dates=["2026-07-01", "2026-07-02"],
                regional_daily_minimum_wage=Decimal("610.00"),
                region_code="NCR",
                wage_order_reference="NCR-WO-QA-01",
                wage_order_effective_from=date(2026, 1, 1),
                gross_amount=Decimal("500.00"),
                source_reference="QA meal allowance voucher",
            ),
            vacation_benefit,
            LeaveLedgerEntry(
                employee_id=employee_record.id,
                policy_id=policy.id,
                enrollment_id=enrollment.id,
                leave_year=2026,
                source=LeaveLedgerSource.CONSUMED,
                amount=Decimal("-4.00"),
                reference=leave_reference,
            ),
        ]
    )
    db.commit()

    rows = _bir_tax_benefit_rows(
        db,
        employee_record.id,
        2026,
        date(2026, 6, 30),
        date(2026, 7, 31),
        opening_unused_vacation_leave_days_ytd=10,
    )

    by_category = {row["de_minimis_category"]: row for row in rows}
    assert by_category["daily_meal_ot_night"]["category_exempt_amount"] == "366.00"
    assert by_category["daily_meal_ot_night"]["category_excess_amount"] == "134.00"
    assert by_category["daily_meal_ot_night"]["region_code"] == "NCR"
    evidence = by_category["daily_meal_ot_night"]["attendance_evidence"]
    assert len(evidence) == 2
    assert evidence[0]["work_date"] == "2026-07-01"
    assert evidence[0]["overtime_approved_minutes"] == 30
    assert by_category["monetized_unused_vacation_leave"]["category_exempt_amount"] == "2000.00"
    assert by_category["monetized_unused_vacation_leave"]["category_excess_amount"] == "2000.00"


def test_database_rejects_day_based_benefit_with_missing_qualifying_days(
    db: Session, employee_record: EmployeeRecords
) -> None:
    db.add(
        EmployeeTaxBenefit(
            employee_id=employee_record.id,
            tax_year=2026,
            paid_on=date(2026, 7, 10),
            benefit_type="de_minimis",
            de_minimis_category="daily_meal_ot_night",
            qualifying_days=None,
            qualifying_work_dates=["2026-07-01"],
            regional_daily_minimum_wage=Decimal("610.00"),
            region_code="NCR",
            wage_order_reference="NCR-WO-QA-01",
            wage_order_effective_from=date(2026, 1, 1),
            gross_amount=Decimal("250.00"),
            source_reference="QA invalid meal allowance",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_meal_benefit_exemption_fails_closed_after_attendance_changes(
    db: Session, employee_record: EmployeeRecords
) -> None:
    record = DailyTimeRecord(
        employee_id=employee_record.id,
        work_date=date(2026, 7, 1),
        overtime_minutes=60,
        overtime_approved_minutes=30,
    )
    benefit = EmployeeTaxBenefit(
        employee_id=employee_record.id,
        tax_year=2026,
        paid_on=date(2026, 7, 10),
        benefit_type="de_minimis",
        de_minimis_category="daily_meal_ot_night",
        eligibility_evidence=["approved_overtime_or_night_shift_records"],
        qualifying_days=1,
        qualifying_work_dates=["2026-07-01"],
        regional_daily_minimum_wage=Decimal("610.00"),
        region_code="NCR",
        wage_order_reference="NCR-WO-QA-01",
        wage_order_effective_from=date(2026, 1, 1),
        gross_amount=Decimal("250.00"),
        source_reference="QA meal allowance voucher",
    )
    db.add_all([record, benefit])
    db.commit()

    eligible = _bir_tax_benefit_rows(
        db, employee_record.id, 2026, date(2026, 6, 30), date(2026, 7, 31)
    )[0]
    assert eligible["category_exempt_amount"] == "183.00"
    assert eligible["attendance_evidence"][0]["record_id"] == str(record.id)

    record.overtime_approved_minutes = 0
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()

    changed = _bir_tax_benefit_rows(
        db, employee_record.id, 2026, date(2026, 6, 30), date(2026, 7, 31)
    )[0]
    assert changed["category_exempt_amount"] == "0.00"
    assert changed["category_excess_amount"] == "250.00"
    assert changed["calculation_blocker"] == "bir_meal_attendance_evidence_changed_or_unavailable"


def test_unused_vacation_benefit_marks_missing_opening_days_for_payroll_blocker(
    db: Session, employee_record: EmployeeRecords
) -> None:
    policy, enrollment = _vacation_policy_and_balance(
        db, employee_record, Decimal("1.00")
    )
    benefit = EmployeeTaxBenefit(
            employee_id=employee_record.id,
            tax_year=2026,
            paid_on=date(2026, 7, 10),
            benefit_type="de_minimis",
            de_minimis_category="monetized_unused_vacation_leave",
            qualifying_days=1,
            vacation_leave_policy_id=policy.id,
            gross_amount=Decimal("1000.00"),
            source_reference="QA leave monetization voucher missing opening balance",
        )
    leave_reference = f"PayrollTaxBenefit:{benefit.id}"
    benefit.eligibility_snapshot = {
        "policy_id": str(policy.id),
        "policy_is_paid": True,
        "policy_tax_exempt_unused_vacation_leave": True,
        "enrollment_id": str(enrollment.id),
        "leave_year": 2026,
        "qualifying_days": 1,
        "ledger_reference": leave_reference,
    }
    db.add_all(
        [
            benefit,
            LeaveLedgerEntry(
                employee_id=employee_record.id,
                policy_id=policy.id,
                enrollment_id=enrollment.id,
                leave_year=2026,
                source=LeaveLedgerSource.CONSUMED,
                amount=Decimal("-1.00"),
                reference=leave_reference,
            ),
        ]
    )
    db.commit()

    rows = _bir_tax_benefit_rows(
        db,
        employee_record.id,
        2026,
        date(2026, 6, 30),
        date(2026, 7, 31),
    )
    assert rows[0]["calculation_blocker"] == "bir_unused_leave_opening_days_missing"
    assert rows[0]["category_exempt_amount"] == "0.00"
    assert rows[0]["taxable_other_benefit_amount"] == "1000.00"


def test_unused_vacation_exemption_fails_closed_without_matching_ledger_debit(
    db: Session, employee_record: EmployeeRecords
) -> None:
    policy, enrollment = _vacation_policy_and_balance(
        db, employee_record, Decimal("2.00")
    )
    benefit = EmployeeTaxBenefit(
        employee_id=employee_record.id,
        tax_year=2026,
        paid_on=date(2026, 7, 10),
        benefit_type="de_minimis",
        de_minimis_category="monetized_unused_vacation_leave",
        qualifying_days=1,
        vacation_leave_policy_id=policy.id,
        gross_amount=Decimal("1000.00"),
        source_reference="QA leave monetization voucher without matching debit",
        eligibility_snapshot={
            "policy_id": str(policy.id),
            "policy_is_paid": True,
            "policy_tax_exempt_unused_vacation_leave": True,
            "enrollment_id": str(enrollment.id),
            "leave_year": 2026,
            "qualifying_days": 1,
            "ledger_reference": "PayrollTaxBenefit:missing-debit",
        },
    )
    db.add(benefit)
    db.commit()

    rows = _bir_tax_benefit_rows(
        db,
        employee_record.id,
        2026,
        date(2026, 6, 30),
        date(2026, 7, 31),
        opening_unused_vacation_leave_days_ytd=0,
    )
    assert rows[0]["calculation_blocker"] == "bir_unused_vacation_leave_balance_evidence_unavailable"
    assert rows[0]["category_exempt_amount"] == "0.00"
    assert rows[0]["category_excess_amount"] == "1000.00"


def test_previous_employer_requires_explicit_de_minimis_opening_balances(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.put(
        f"{API}/employees/{employee_record.id}/tax-year-declarations/2026",
        json={
            "opening_as_of": "2026-06-30",
            "taxable_compensation_ytd": "100.00",
            "opening_pay_period_count": 6,
            "opening_pay_period_type": "semi_monthly",
            "previous_employer_included": True,
            "opening_benefits_reconciled": True,
            "source_reference": "Reviewed prior payroll records",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 422
    assert "explicit annual and monthly balances" in response.text


def test_tax_year_declaration_requires_approval_permission(
    client: TestClient,
    employee_record: EmployeeRecords,
    normal_user_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-declarations/2026"
    response = client.put(
        url,
        json={"is_verified": True},
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_tax_year_declaration_rejects_invalid_year_and_negative_amounts(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    base = f"{API}/employees/{employee_record.id}/tax-year-declarations"
    assert client.put(f"{base}/1999", json={}, headers=superuser_token_headers).status_code == 422
    assert client.put(
        f"{base}/2026",
        json={"opening_as_of": "2027-01-01", "taxable_compensation_ytd": "-0.01"},
        headers=superuser_token_headers,
    ).status_code == 422


def test_previous_employer_declaration_requires_period_count_and_source_note(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-declarations/2026"
    base = {
        "opening_as_of": "2026-06-30",
        "taxable_compensation_ytd": "180000.00",
        "tax_withheld_ytd": "11000.40",
        "previous_employer_included": True,
        "opening_benefits_reconciled": True,
        "opening_de_minimis_annual_ytd": {
            "uniform_clothing": "0.00",
            "actual_medical_assistance": "0.00",
            "achievement_award": "0.00",
            "christmas_anniversary_gift": "0.00",
            "cba_productivity_incentive": "0.00",
        },
        "opening_de_minimis_monthly_ytd": {
            "medical_cash_dependents": "0.00",
            "rice_subsidy": "0.00",
            "laundry_allowance": "0.00",
        },
    }
    assert client.put(url, json=base, headers=superuser_token_headers).status_code == 422
    response = client.put(
        url,
        json={
            **base,
            "source_reference": "Prior payroll tax records reviewed",
            "opening_pay_period_count": 6,
            "opening_pay_period_type": "semi_monthly",
        },
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text


def test_minimum_wage_earner_classification_requires_wage_order_evidence(
    client: TestClient,
    employee_record: EmployeeRecords,
    superuser_token_headers: dict[str, str],
) -> None:
    url = f"{API}/employees/{employee_record.id}/tax-year-declarations/2026"
    payload = {
        "tax_classification": "minimum_wage_earner",
        "opening_as_of": "2026-01-01",
        "is_verified": True,
    }
    missing_source = client.put(url, json=payload, headers=superuser_token_headers)
    assert missing_source.status_code == 422
    assert "DOLE wage order" in missing_source.text

    with_source = client.put(
        url,
        json={
            **payload,
            "source_reference": "DOLE Wage Order NCR-XX; assigned NCR workplace",
        },
        headers=superuser_token_headers,
    )
    assert with_source.status_code == 200, with_source.text
    assert with_source.json()["tax_classification"] == "minimum_wage_earner"
