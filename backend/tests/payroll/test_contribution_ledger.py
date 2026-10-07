"""Monthly contribution collection is unique and corrections are reasoned."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.payroll.models import (
    PayrollContributionLedger,
    PayrollEntry,
    PayrollRun,
)
from app.payroll.routes import _stage_monthly_contribution_ledger
from app.user.models import User


def _entry(
    db: Session, employee_id: uuid.UUID, actor_id: uuid.UUID, *, day: int
) -> PayrollEntry:
    run = PayrollRun(
        cutoff_type="semi_monthly",
        date_from=date(2026, 10, day),
        date_to=date(2026, 10, 15 if day == 1 else 31),
        created_by=actor_id,
    )
    db.add(run)
    db.flush()
    entry = PayrollEntry(
        payroll_run_id=run.id,
        employee_id=employee_id,
        basic_rate=Decimal("26000.00"),
        rate_date_from=run.date_from,
        rate_date_to=run.date_to,
        gross_pay=Decimal("13000.00"),
        total_deductions=Decimal("0.00"),
        net_pay=Decimal("13000.00"),
        taxable_income=Decimal("13000.00"),
    )
    db.add(entry)
    db.flush()
    return entry


def test_monthly_collection_rejects_duplicate_and_keeps_reasoned_correction(
    db: Session,
) -> None:
    actor = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    employee = EmployeeRecords(
        employee_code=f"LEDGER-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Ledger",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    entry = _entry(db, employee.id, actor.id, day=1)
    base = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=entry.id,
        scheme="pagibig",
        contribution_month=date(2026, 10, 1),
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("200.00"),
        employer_amount=Decimal("200.00"),
        calculation_snapshot={"employee_rate": "2", "employer_rate": "2"},
        source_references=["https://www.pagibigfund.gov.ph/"],
        created_by=actor.id,
    )
    db.add(base)
    db.commit()
    db.refresh(base)

    correction = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=entry.id,
        scheme="pagibig",
        contribution_month=date(2026, 10, 1),
        sequence=1,
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("-10.00"),
        employer_amount=Decimal("0.00"),
        calculation_snapshot={"correction": "employee deduction over-collected"},
        source_references=["https://www.pagibigfund.gov.ph/"],
        adjustment_reason="Reverse an approved over-deduction",
        reverses_id=base.id,
        created_by=actor.id,
    )
    db.add(correction)
    db.commit()

    duplicate_entry = _entry(db, employee.id, actor.id, day=16)
    duplicate = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=duplicate_entry.id,
        scheme="pagibig",
        contribution_month=date(2026, 10, 1),
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("200.00"),
        employer_amount=Decimal("200.00"),
        calculation_snapshot={"employee_rate": "2", "employer_rate": "2"},
        source_references=["https://www.pagibigfund.gov.ph/"],
        created_by=actor.id,
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    rows = db.exec(
        select(PayrollContributionLedger).where(
            PayrollContributionLedger.employee_id == employee.id,
            PayrollContributionLedger.scheme == "pagibig",
            PayrollContributionLedger.contribution_month == date(2026, 10, 1),
        )
    ).all()
    assert {(row.sequence, row.employee_amount) for row in rows} == {
        (0, Decimal("200.00")),
        (1, Decimal("-10.00")),
    }


def test_final_period_stages_exactly_one_monthly_collection_per_scheme(
    db: Session,
) -> None:
    actor = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    employee = EmployeeRecords(
        employee_code=f"LEDGER-FINAL-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Final Ledger",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    entry = _entry(db, employee.id, actor.id, day=16)
    entry.deductions = {
        "sss_employee": "1000.00",
        "philhealth_employee": "325.00",
        "pagibig_employee": "200.00",
    }
    entry.input_snapshot = {
        "monthly_contributions": {
            "month": "2026-10",
            "schemes": {
                scheme: {
                    "basis": "26000.00",
                    "employee": amount,
                    "employer": amount,
                    "source_references": [
                        {
                            "sss": "https://www.sss.gov.ph/sss-contribution-table/",
                            "philhealth": "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf",
                            "pagibig": "https://www.pagibigfund.gov.ph/",
                        }[scheme]
                    ],
                }
                for scheme, amount in (
                    ("sss", "1000.00"),
                    ("philhealth", "325.00"),
                    ("pagibig", "200.00"),
                )
            },
        }
    }
    db.add(entry)
    db.flush()

    run = db.get(PayrollRun, entry.payroll_run_id)
    assert run is not None
    _stage_monthly_contribution_ledger(
        session=db, run=run, entries=[entry], actor_id=actor.id
    )
    rows = db.exec(
        select(PayrollContributionLedger).where(
            PayrollContributionLedger.employee_id == employee.id,
            PayrollContributionLedger.contribution_month == date(2026, 10, 1),
        )
    ).all()
    assert {row.scheme for row in rows} == {"sss", "philhealth", "pagibig"}

    with pytest.raises(HTTPException, match="already has"):
        _stage_monthly_contribution_ledger(
            session=db,
            run=run,
            entries=[entry],
            actor_id=actor.id,
        )
    db.rollback()


def test_first_period_cannot_withhold_monthly_contributions(db: Session) -> None:
    actor = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    employee = EmployeeRecords(
        employee_code=f"LEDGER-EARLY-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Early Ledger",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    entry = _entry(db, employee.id, actor.id, day=1)
    entry.deductions = {"sss_employee": "1.00"}
    db.add(entry)
    db.flush()
    run = db.get(PayrollRun, entry.payroll_run_id)
    assert run is not None

    with pytest.raises(HTTPException, match="only in the final payroll period"):
        _stage_monthly_contribution_ledger(
            session=db,
            run=run,
            entries=[entry],
            actor_id=actor.id,
        )
    db.rollback()
