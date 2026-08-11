"""Read-only query helpers for Phase 1 resources.

Phase 0 declares one selector file per resource with explicit functions; Phase 1
has 16+ resources with an identical shape, so these are generic helpers keyed by
model. All list queries filter ``is_deleted = false`` and return
``(list[X], count)`` to match the ``{data, count}`` route shape.
"""

import uuid
from typing import TypeVar

from sqlmodel import Session, func, select
from sqlmodel.main import SQLModel as SQLModelBase

from app.employee.models import EmployeeAdditionalRecords, EmployeeAttachments

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
    base = (
        select(model).where(model.is_deleted == False)  # noqa: E712
    )
    if filter_column is not None:
        base = base.where(filter_column == filter_value)

    count_statement = select(func.count()).select_from(model).where(
        model.is_deleted == False  # noqa: E712
    )
    if filter_column is not None:
        count_statement = count_statement.where(filter_column == filter_value)
    count = session.exec(count_statement).one()

    statement = (
        base.order_by(model.created_at.desc()).offset(skip).limit(limit)
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


def get_by_unique(*, session: Session, model: type[T], column, value) -> T | None:
    return session.exec(select(model).where(column == value)).first()


def get_additional_records_for_employee(
    *, session: Session, employee_id: uuid.UUID
) -> EmployeeAdditionalRecords | None:
    return session.exec(
        select(EmployeeAdditionalRecords).where(
            EmployeeAdditionalRecords.employee_id == employee_id
        )
    ).first()


def get_attachments_for_employee(
    *, session: Session, employee_id: uuid.UUID
) -> tuple[list[EmployeeAttachments], int]:
    statement = select(EmployeeAttachments).where(
        EmployeeAttachments.employee_id == employee_id,
        EmployeeAttachments.is_deleted == False,  # noqa: E712
    )
    rows = session.exec(statement.order_by(EmployeeAttachments.date_uploaded.desc())).all()
    return list(rows), len(rows)


def get_attachment_by_id(
    *, session: Session, attachment_id: uuid.UUID
) -> EmployeeAttachments | None:
    row = session.get(EmployeeAttachments, attachment_id)
    if row is None or row.is_deleted:
        return None
    return row


def count_active_categories_referencing(
    *, session: Session, blocks_id: uuid.UUID | None = None, lot_id: uuid.UUID | None = None
) -> int:
    """Count ACTIVE (non-deleted) Category rows referencing a Blocks/Lots row.

    Implements the §7 delete-guard predicate: the count only considers
    ``is_deleted = false`` Categories, so a Block/Lot referenced solely by a
    soft-deleted Category is not blocked.
    """
    from app.employee.models import Category

    statement = select(func.count()).select_from(Category).where(
        Category.is_deleted == False  # noqa: E712
    )
    if blocks_id is not None:
        statement = statement.where(Category.blocks_id == blocks_id)
    if lot_id is not None:
        statement = statement.where(Category.lot_id == lot_id)
    return session.exec(statement).one()
