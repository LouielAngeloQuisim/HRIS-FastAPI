"""Monthly contribution collection is unique and corrections are reasoned."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from time import sleep

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config.database import engine
from app.config.settings import settings
from app.employee.models import EmployeeRecords, EmployeeStatus
from app.payroll.models import (
    PayrollContributionLedger,
    PayrollEntry,
    PayrollRun,
    PayrollRunStatus,
)
from app.payroll.routes import (
    _stage_monthly_contribution_ledger,
    list_payroll_contribution_ledger,
)
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

    duplicate_correction = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=entry.id,
        scheme="pagibig",
        contribution_month=date(2026, 10, 1),
        sequence=2,
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("10.00"),
        employer_amount=Decimal("0.00"),
        calculation_snapshot={"correction": "duplicate reversal attempt"},
        source_references=["https://www.pagibigfund.gov.ph/"],
        adjustment_reason="Attempt to reverse the same collection twice",
        reverses_id=base.id,
        created_by=actor.id,
    )
    db.add(duplicate_correction)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    wrong_scope_correction = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=entry.id,
        scheme="sss",
        contribution_month=date(2026, 10, 1),
        sequence=1,
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("10.00"),
        employer_amount=Decimal("0.00"),
        calculation_snapshot={"correction": "wrong scheme"},
        source_references=["https://www.sss.gov.ph/sss-contribution-table/"],
        adjustment_reason="Invalid attempt to reverse a different scheme",
        reverses_id=base.id,
        created_by=actor.id,
    )
    db.add(wrong_scope_correction)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

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


def test_contribution_ledger_readback_is_paginated_and_only_shows_finalized_rows(
    db: Session,
) -> None:
    actor = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    employee = EmployeeRecords(
        employee_code=f"LEDGER-READ-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Readback",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    entry = _entry(db, employee.id, actor.id, day=16)
    run = db.get(PayrollRun, entry.payroll_run_id)
    assert run is not None
    run.status = PayrollRunStatus.APPROVED
    run.workflow_status = "finalized"
    base = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=entry.id,
        scheme="sss",
        contribution_month=date(2026, 10, 1),
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("1300.00"),
        employer_amount=Decimal("1950.00"),
        source_references=["https://www.sss.gov.ph/sss-contribution-table/"],
        created_by=actor.id,
    )
    correction = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=entry.id,
        scheme="sss",
        contribution_month=date(2026, 10, 1),
        sequence=1,
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("-100.00"),
        employer_amount=Decimal("0.00"),
        adjustment_reason="Correct an over-collection",
        reverses_id=base.id,
        created_by=actor.id,
    )
    db.add(base)
    db.add(correction)

    draft_entry = _entry(db, employee.id, actor.id, day=1)
    draft = PayrollContributionLedger(
        employee_id=employee.id,
        payroll_entry_id=draft_entry.id,
        scheme="sss",
        contribution_month=date(2026, 11, 1),
        monthly_basis=Decimal("26000.00"),
        employee_amount=Decimal("1300.00"),
        employer_amount=Decimal("1950.00"),
        created_by=actor.id,
    )
    db.add(draft)
    db.commit()

    result = list_payroll_contribution_ledger(
        session=db,
        employee_id=None,
        employee_code=employee.employee_code,
        contribution_month=date(2026, 10, 1),
        scheme="sss",
        skip=0,
        limit=1,
    )
    assert result.count == 2
    assert len(result.data) == 1
    assert result.data[0].employee_code == employee.employee_code
    assert result.data[0].sequence == 0

    second_page = list_payroll_contribution_ledger(
        session=db,
        employee_id=None,
        employee_code=employee.employee_code,
        contribution_month=date(2026, 10, 1),
        scheme="sss",
        skip=1,
        limit=1,
    )
    assert second_page.count == 2
    assert second_page.data[0].sequence == 1
    assert second_page.data[0].reverses_id == base.id
    assert second_page.data[0].adjustment_reason == "Correct an over-collection"


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

    with pytest.raises(HTTPException, match="final eligible payroll period"):
        _stage_monthly_contribution_ledger(
            session=db,
            run=run,
            entries=[entry],
            actor_id=actor.id,
        )
    db.rollback()


def test_separated_employee_collects_monthly_contributions_in_final_pay_period(
    db: Session,
) -> None:
    actor = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    employee = EmployeeRecords(
        employee_code=f"LEDGER-TERM-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Separated Ledger",
        birthdate=date(1990, 1, 1),
        employee_status=EmployeeStatus.RESIGNED,
        date_separated=date(2026, 10, 10),
    )
    db.add(employee)
    db.flush()
    entry = _entry(db, employee.id, actor.id, day=1)
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
                    "source_references": [url],
                }
                for scheme, amount, url in (
                    ("sss", "1000.00", "https://www.sss.gov.ph/sss-contribution-table/"),
                    ("philhealth", "325.00", "https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf"),
                    ("pagibig", "200.00", "https://www.pagibigfund.gov.ph/"),
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
    db.commit()

    rows = db.exec(
        select(PayrollContributionLedger).where(
            PayrollContributionLedger.employee_id == employee.id,
            PayrollContributionLedger.contribution_month == date(2026, 10, 1),
            PayrollContributionLedger.sequence == 0,
        )
    ).all()
    assert {row.scheme for row in rows} == {"sss", "philhealth", "pagibig"}


def test_concurrent_finalization_serializes_monthly_contribution_collection(
    db: Session,
) -> None:
    actor = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    employee = EmployeeRecords(
        employee_code=f"LEDGER-RACE-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Ledger Race",
        birthdate=date(1990, 1, 1),
    )
    db.add(employee)
    db.flush()
    entries = [_entry(db, employee.id, actor.id, day=16) for _ in range(2)]
    for entry in entries:
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
    db.commit()
    entry_ids = [entry.id for entry in entries]
    run_ids = [entry.payroll_run_id for entry in entries]
    staged = Event()
    release_first = Event()
    second_started = Event()

    def first_transaction() -> None:
        with Session(engine) as session:
            run = session.get(PayrollRun, run_ids[0])
            entry = session.get(PayrollEntry, entry_ids[0])
            assert run is not None and entry is not None
            _stage_monthly_contribution_ledger(
                session=session, run=run, entries=[entry], actor_id=actor.id
            )
            staged.set()
            assert release_first.wait(timeout=5)
            session.commit()

    def second_transaction() -> int:
        assert staged.wait(timeout=5)
        second_started.set()
        with Session(engine) as session:
            run = session.get(PayrollRun, run_ids[1])
            entry = session.get(PayrollEntry, entry_ids[1])
            assert run is not None and entry is not None
            with pytest.raises(HTTPException, match="already has"):
                _stage_monthly_contribution_ledger(
                    session=session, run=run, entries=[entry], actor_id=actor.id
                )
            session.rollback()
        return 409

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(first_transaction)
            second = executor.submit(second_transaction)
            assert staged.wait(timeout=5)
            assert second_started.wait(timeout=5)
            sleep(0.1)
            assert not second.done(), "second finalizer bypassed the transaction lock"
            release_first.set()
            first.result(timeout=5)
            assert second.result(timeout=5) == 409
    finally:
        release_first.set()

    rows = db.exec(
        select(PayrollContributionLedger).where(
            PayrollContributionLedger.employee_id == employee.id,
            PayrollContributionLedger.contribution_month == date(2026, 10, 1),
            PayrollContributionLedger.sequence == 0,
        )
    ).all()
    assert len(rows) == 3
