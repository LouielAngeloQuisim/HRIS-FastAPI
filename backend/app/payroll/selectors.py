"""Selectors for payroll module data reading.

Read helpers with effective-date filtering and permission guards.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from app.payroll.models import (
    EmployeeSalary,
    Loan,
    LoanAmortization,
    PayrollEntry,
    PayrollRun,
)


class SoftDeletable:
    is_deleted: bool


T = Any

PENDING_STATUSES: list[str] = ["draft"]
APPROVED_STATUS = "approved"
PAID_STATUS = "paid"
VOID_STATUS = "void"


# === Effective-date filtering helpers ===


def get_effective_brackets(*, session: Session, model: type[T], as_of: date) -> list[T]:
    stmt = select(model).where(model.effective_date <= as_of, model.is_deleted.is_(False))
    return list(session.exec(stmt).all())


def get_latest_version(*, session: Session, model: type[T], as_of: date) -> T | None:
    stmt = (
        select(model)
        .where(model.effective_date <= as_of, model.is_deleted.is_(False))
        .order_by(model.effective_date.desc())
    )
    return session.exec(stmt).first()


def get_active_bracket_by_type(
    *, session: Session, model: type[T], employee_id: uuid.UUID, as_of: date
) -> T | None:
    stmt = select(model).where(model.is_deleted.is_(False))
    rows = session.exec(stmt).all()
    for row in rows:
        if hasattr(row, "employee_id") and row.employee_id != employee_id:
            continue
        if hasattr(row, "effective_date") and row.effective_date > as_of:
            continue
        return row
    return None


# === Employee salary selectors ===


def get_active_employee_salaries(session: Session, employee_id: uuid.UUID) -> list[Any]:
    stmt = (
        select(EmployeeSalary)
        .where(EmployeeSalary.employee_id == employee_id, EmployeeSalary.is_deleted.is_(False))  # type: ignore[attr-defined]
        .order_by(EmployeeSalary.effective_date.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


# === Payroll run selectors ===


def select_payroll_runs_for_employee(
    session: Session, employee_id: uuid.UUID, include_deleted: bool = False
) -> list[Any]:
    stmt = (
        select(PayrollRun)
        .where(PayrollRun.created_by == employee_id, PayrollRun.is_deleted == include_deleted)
    )
    return list(session.exec(stmt).all())


def select_employee_payroll_runs(
    session: Session, created_by_id: uuid.UUID | None = None, include_deleted: bool = False
) -> list[Any]:
    stmt = select(PayrollRun).where(PayrollRun.is_deleted == include_deleted)
    if created_by_id is not None:
        stmt = stmt.where(PayrollRun.created_by == created_by_id)
    return list(session.exec(stmt).all())


def select_payroll_run_with_entries(
    session: Session, payroll_run_id: uuid.UUID, include_deleted: bool = False
) -> tuple[PayrollRun | None, list[Any]]:
    run = session.get(PayrollRun, payroll_run_id)
    if run is None or (not include_deleted and run.is_deleted):
        return None, []

    entry_stmt = (
        select(PayrollEntry)
        .where(PayrollEntry.payroll_run_id == payroll_run_id)
        .where(PayrollEntry.is_deleted == include_deleted)
        .order_by(PayrollEntry.employee_id, PayrollEntry.id)  # type: ignore[arg-type]
    )
    entries = list(session.exec(entry_stmt).all())
    return run, entries


def get_payroll_run_with_entries(
    session: Session, payroll_run_id: uuid.UUID, include_deleted: bool = False
) -> tuple[Any | None, list[Any]]:
    return select_payroll_run_with_entries(session, payroll_run_id, include_deleted)


def get_existing_singleton_payroll_run_for_determination(
    session: Session, run_id: uuid.UUID, _actor_id: uuid.UUID
) -> PayrollRun:
    run = _fetch_singleton_payroll_run_from_db(session, run_id)
    if run.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payroll run not found or already deleted: {run_id}")
    return run


def get_existing_singleton_payroll_run_for_voiding(
    session: Session, run_id: uuid.UUID, _actor_id: uuid.UUID
) -> PayrollRun:
    run = _fetch_singleton_payroll_run_from_db(session, run_id)
    if run.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payroll run not found or already deleted: {run_id}")
    return run


def _fetch_singleton_payroll_run_from_db(session: Session, payroll_run_id: uuid.UUID) -> PayrollRun:
    run = session.get(PayrollRun, payroll_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payroll run not found: {payroll_run_id}")
    return run


# === Loan selectors ===


def select_employee_loans(
    session: Session, employee_id: uuid.UUID, include_deleted: bool = False
) -> list[Any]:
    stmt = select(Loan).where(Loan.employee_id == employee_id, Loan.is_deleted == include_deleted)
    return list(session.exec(stmt).all())


def select_active_loan_amortizations(session: Session, loan_id: uuid.UUID) -> list[Any]:
    stmt = (
        select(LoanAmortization)
        .where(LoanAmortization.loan_id == loan_id, LoanAmortization.is_paid.is_(False))  # type: ignore[attr-defined]
        .order_by(LoanAmortization.due_date)  # type: ignore[arg-type]
    )
    return list(session.exec(stmt).all())


def select_unsigned_payroll_run_amortizations(session: Session) -> list[Any]:
    stmt = (
        select(LoanAmortization)
        .where(LoanAmortization.is_paid.is_(False))  # type: ignore[attr-defined]
        .join(Loan, LoanAmortization.loan_id == Loan.id)  # type: ignore[arg-type]
        .where(Loan.is_deleted.is_(False))  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def select_payroll_summary_for_user(session: Session, user_id: uuid.UUID) -> dict[str, Any]:
    stmt = (
        select(PayrollRun.status, func.count(), func.sum(PayrollEntry.net_pay))
        .outerjoin(PayrollEntry, PayrollEntry.payroll_run_id == PayrollRun.id)  # type: ignore[arg-type]
        .where(PayrollRun.is_deleted.is_(False), PayrollRun.created_by == user_id)  # type: ignore[attr-defined]
        .group_by(PayrollRun.status)
    )
    results = session.exec(stmt).all()

    status_counts: dict[str, int] = {}
    total_amount = Decimal("0.00")
    for status_val, count, amount in results:
        status_counts[status_val] = count
        if amount is not None:
            total_amount += amount

    return {
        "status_counts": status_counts,
        "total_payroll_runs": sum(status_counts.values()),
        "total_amount": total_amount,
    }


def get_payroll_run_status_counts(
    session: Session, created_by_id: uuid.UUID | None = None
) -> dict[str, int]:
    from sqlalchemy import func

    stmt = select(PayrollRun.status, func.count())
    if created_by_id is not None:
        stmt = stmt.where(PayrollRun.created_by == created_by_id)
    stmt = stmt.where(PayrollRun.is_deleted.is_(False)).group_by(PayrollRun.status)  # type: ignore[attr-defined]

    results = session.exec(stmt).all()
    counts = {"draft": 0, "approved": 0, "paid": 0, "void": 0}
    for status_val, count in results:
        if status_val in counts:
            counts[status_val] = count
    return counts


# === Compliance / notification helpers ===


def select_pending_leave_requests_for_payday(
    session: Session,
    payday_date: date | None = None,
) -> list[Any]:
    # Placeholder: leave selectors are imported lazily to avoid circular imports
    try:
        from app.leave.selectors import select_pending_leaves_for_date_range  # type: ignore[attr-defined]  # isort:skip

        if payday_date:
            return select_pending_leaves_for_date_range(session, payday_date, payday_date)  # type: ignore[no-any-return]
    except Exception:
        pass
    return []
