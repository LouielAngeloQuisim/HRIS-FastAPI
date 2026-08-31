"""Read-only query helpers for attendance resources (design §1)."""

import uuid
from datetime import datetime
from typing import TypeVar

from sqlmodel import Session, func, select
from sqlmodel.main import SQLModel as SQLModelBase

from app.attendance.models import DailyTimeRecord, Shift
from app.employee.models import EmployeeRecords

T = TypeVar("T", bound=SQLModelBase)


def get_list(
    *,
    session: Session,
    model: type[T],
    filter_column=None,
    filter_value=None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[T], int]:
    """Return (rows, total) with `is_deleted = false`, optionally filtered by one column."""
    base = select(model).where(model.is_deleted == False)  # noqa: E712
    if filter_column is not None:
        base = base.where(filter_column == filter_value)

    count_statement = select(func.count()).select_from(model).where(
        model.is_deleted == False  # noqa: E712
    )
    if filter_column is not None:
        count_statement = count_statement.where(filter_column == filter_value)
    count = session.exec(count_statement).one()

    statement = base.order_by(model.created_at.desc()).offset(skip).limit(limit)
    rows = session.exec(statement).all()
    return list(rows), count


def get_by_id(*, session: Session, model: type[T], obj_id: uuid.UUID) -> T | None:
    return session.get(model, obj_id)


def get_active_by_id(*, session: Session, model: type[T], obj_id: uuid.UUID) -> T | None:
    """Fetch a non-deleted row by PK, or None."""
    row = session.get(model, obj_id)
    if row is None or getattr(row, "is_deleted", False):
        return None
    return row


def get_dtr_by_employee_and_login(
    *, session: Session, employee_id: uuid.UUID, login_date: datetime
) -> DailyTimeRecord | None:
    """Dedupe key for a punch: one non-deleted record per employee per login timestamp."""
    return session.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee_id,
            DailyTimeRecord.login_date == login_date,
            DailyTimeRecord.is_deleted == False,  # noqa: E712
        )
    ).first()


def get_shift_by_code(*, session: Session, code: str) -> Shift | None:
    return session.exec(
        select(Shift).where(Shift.code == code, Shift.is_deleted == False)  # noqa: E712
    ).first()


def get_employee_by_id(*, session: Session, employee_id: uuid.UUID) -> EmployeeRecords | None:
    """Fetch a non-deleted employee by PK, or None."""
    row = session.get(EmployeeRecords, employee_id)
    if row is None or getattr(row, "is_deleted", False):
        return None
    return row


def get_employee_by_code(*, session: Session, code: str) -> EmployeeRecords | None:
    """Resolve an employee_code to its record (ingestion-time lookup)."""
    return session.exec(
        select(EmployeeRecords).where(
            EmployeeRecords.employee_code == code,
            EmployeeRecords.is_deleted == False,  # noqa: E712
        )
    ).first()
