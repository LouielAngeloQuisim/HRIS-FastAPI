"""Read-only query helpers for attendance resources (design §1)."""

import uuid
from datetime import datetime
from typing import Protocol, TypeVar

from sqlmodel import Session, func, select

from app.attendance.models import DailyTimeRecord, Shift
from app.employee.models import EmployeeRecords


class SoftDeletable(Protocol):
    is_deleted: bool


class Timestamped(Protocol):
    created_at: datetime


T = TypeVar("T", bound=SoftDeletable)


def get_list(
    *,
    session: Session,
    model: type[T],
    filter_column=None,
    filter_value=None,
    employee_id_filter: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[T], int]:
    """Return (rows, total) with `is_deleted = false`, optionally filtered by one column
    and/or scoped to a single employee (row-level security for non-HR viewers).
    """
    base = select(model).where(model.is_deleted == False)  # noqa: E712
    if filter_column is not None:
        base = base.where(filter_column == filter_value)
    if employee_id_filter is not None:
        base = base.where(model.employee_id == employee_id_filter)  # type: ignore[attr-defined]

    count_statement = select(func.count()).select_from(model).where(
        model.is_deleted == False  # noqa: E712
    )
    if filter_column is not None:
        count_statement = count_statement.where(filter_column == filter_value)
    if employee_id_filter is not None:
        count_statement = count_statement.where(model.employee_id == employee_id_filter)  # type: ignore[attr-defined]
    count = session.exec(count_statement).one()

    statement = (
        base.order_by(model.created_at.desc())  # type: ignore[attr-defined]
        .offset(skip)
        .limit(limit)
    )
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


def get_employee_id_for_user(*, session: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    """Return the EmployeeRecords.id for a user, or None if no employee record is linked.

    Used by the DTR list route to scope results to the caller's own records
    when the caller is not a superuser/HR admin.
    """
    row = session.exec(
        select(EmployeeRecords).where(
            EmployeeRecords.user_id == user_id,
            EmployeeRecords.is_deleted == False,  # noqa: E712
        )
    ).first()
    return row.id if row is not None else None
