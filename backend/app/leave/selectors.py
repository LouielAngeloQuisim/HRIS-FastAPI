"""Read-only query helpers for the leave domain (design doc §1.5)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from sqlmodel import Session, func, select

from app.leave.models import (
    EmployeeLeaveEnrollment,
    HolidayConfig,
    HolidayInstance,
    LeaveLedgerEntry,
    LeavePolicy,
    LeaveRequest,
    LeaveRequestEvent,
)


class SoftDeletable(Protocol):
    is_deleted: bool


T = Any


def get_active_by_id(*, session: Session, model: type[T], obj_id: uuid.UUID) -> T | None:
    """Fetch a non-deleted row by PK, or None."""
    row = session.get(model, obj_id)
    if row is None or getattr(row, "is_deleted", False):
        return None
    return row


def get_list(
    *,
    session: Session,
    model: type[T],
    skip: int = 0,
    limit: int = 100,
    order_by: Any = None,
) -> tuple[list[T], int]:
    """Return (rows, total) with ``is_deleted = False``."""
    base = select(model).where(model.is_deleted == False)  # noqa: E712

    count_stmt = select(func.count()).select_from(model).where(
        model.is_deleted == False  # noqa: E712
    )
    count = session.exec(count_stmt).one()

    stmt = base.offset(skip).limit(limit)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    rows = session.exec(stmt).all()
    return list(rows), count


# === LeavePolicy =========================================================================


def list_policies(*, session: Session, skip: int = 0, limit: int = 100) -> tuple[list[LeavePolicy], int]:
    return get_list(session=session, model=LeavePolicy, skip=skip, limit=limit)


def get_policy(*, session: Session, policy_id: uuid.UUID) -> LeavePolicy | None:
    return get_active_by_id(session=session, model=LeavePolicy, obj_id=policy_id)


# === EmployeeLeaveEnrollment ============================================================


def list_enrollments(
    *, session: Session, employee_id: uuid.UUID, leave_year: int, skip: int = 0, limit: int = 100
) -> tuple[list[EmployeeLeaveEnrollment], int]:
    base = (
        select(EmployeeLeaveEnrollment)
        .where(EmployeeLeaveEnrollment.is_deleted == False)  # noqa: E712
        .where(EmployeeLeaveEnrollment.employee_id == employee_id)
        .where(EmployeeLeaveEnrollment.leave_year == leave_year)
    )
    count_stmt = select(func.count()).select_from(EmployeeLeaveEnrollment).where(
        EmployeeLeaveEnrollment.is_deleted == False,  # noqa: E712
        EmployeeLeaveEnrollment.employee_id == employee_id,
        EmployeeLeaveEnrollment.leave_year == leave_year,
    )
    count = session.exec(count_stmt).one()
    stmt = base.offset(skip).limit(limit)
    rows = session.exec(stmt).all()
    return list(rows), count


def get_active_enrollment(
    *, session: Session, employee_id: uuid.UUID, policy_id: uuid.UUID, leave_year: int
) -> EmployeeLeaveEnrollment | None:
    return session.exec(
        select(EmployeeLeaveEnrollment).where(
            EmployeeLeaveEnrollment.is_deleted == False,  # noqa: E712
            EmployeeLeaveEnrollment.employee_id == employee_id,
            EmployeeLeaveEnrollment.policy_id == policy_id,
            EmployeeLeaveEnrollment.leave_year == leave_year,
            EmployeeLeaveEnrollment.is_active == True,  # noqa: E712
        )
    ).first()


# === LeaveRequest =======================================================================


def list_leave_requests(
    *,
    session: Session,
    status: str | None = None,
    employee_id: uuid.UUID | None = None,
    leave_year: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[LeaveRequest], int]:
    base = select(LeaveRequest).where(LeaveRequest.is_deleted == False)  # noqa: E712
    if status is not None:
        base = base.where(LeaveRequest.status == status)
    if employee_id is not None:
        base = base.where(LeaveRequest.employee_id == employee_id)
    if leave_year is not None:
        base = base.where(LeaveRequest.leave_year == leave_year)

    count_stmt = select(func.count()).select_from(LeaveRequest).where(
        LeaveRequest.is_deleted == False  # noqa: E712
    )
    if status is not None:
        count_stmt = count_stmt.where(LeaveRequest.status == status)
    if employee_id is not None:
        count_stmt = count_stmt.where(LeaveRequest.employee_id == employee_id)
    if leave_year is not None:
        count_stmt = count_stmt.where(LeaveRequest.leave_year == leave_year)
    count = session.exec(count_stmt).one()

    stmt = base.order_by(LeaveRequest.created_at.desc()).offset(skip).limit(limit)  # type: ignore
    rows = session.exec(stmt).all()
    return list(rows), count


def get_leave_request(*, session: Session, request_id: uuid.UUID) -> LeaveRequest | None:
    return get_active_by_id(session=session, model=LeaveRequest, obj_id=request_id)


def get_request_events(
    *, session: Session, request_id: uuid.UUID
) -> list[LeaveRequestEvent]:
    return list(
        session.exec(
            select(LeaveRequestEvent)
            .where(LeaveRequestEvent.is_deleted == False)  # noqa: E712
            .where(LeaveRequestEvent.request_id == request_id)
            .order_by(LeaveRequestEvent.at.asc())  # type: ignore
        ).all()
    )


def check_overlapping_requests(
    *,
    session: Session,
    employee_id: uuid.UUID,
    date_start: date,
    date_end: date,
    exclude_request_id: uuid.UUID | None = None,
) -> bool:
    """Return True if there is a pending/approved request that overlaps the date range."""
    stmt = (
        select(LeaveRequest)
        .where(
            LeaveRequest.is_deleted == False,  # noqa: E712
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_(["pending", "approved"]),  # type: ignore
            LeaveRequest.date_start <= date_end,
            LeaveRequest.date_end >= date_start,
        )
    )
    if exclude_request_id is not None:
        stmt = stmt.where(LeaveRequest.id != exclude_request_id)
    return session.exec(stmt).first() is not None


# === LeaveLedgerEntry ===================================================================


def get_employee_ledger(
    *, session: Session, employee_id: uuid.UUID, policy_id: uuid.UUID, leave_year: int
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (granted_total, consumed_total, remaining) for an employee's policy/year."""
    rows = session.exec(
        select(LeaveLedgerEntry).where(
            LeaveLedgerEntry.is_deleted == False,  # noqa: E712
            LeaveLedgerEntry.employee_id == employee_id,
            LeaveLedgerEntry.policy_id == policy_id,
            LeaveLedgerEntry.leave_year == leave_year,
        )
    ).all()

    granted_total = Decimal("0.00")
    consumed_total = Decimal("0.00")
    reversal_total = Decimal("0.00")

    for row in rows:
        if row.source in ("grant", "accrual", "carryover_in"):
            granted_total += row.amount
        elif row.source in ("consumed", "carryover_out"):
            consumed_total += abs(row.amount)
        elif row.source == "reversal":
            reversal_total += row.amount
        elif row.source == "manual_adjustment":
            granted_total += row.amount

    net_consumed = consumed_total - abs(reversal_total)
    remaining = granted_total - net_consumed
    return granted_total, net_consumed, remaining


def get_employee_ledger_events(
    *, session: Session, employee_id: uuid.UUID, policy_id: uuid.UUID, leave_year: int,
    skip: int = 0, limit: int = 20
) -> tuple[list[LeaveLedgerEntry], int, Decimal, Decimal, Decimal]:
    """Return (events, total_count, granted_total, consumed_total, remaining).

    Summary totals are computed with SUM FILTER in a single query alongside paginated events.
    """
    base = (
        select(LeaveLedgerEntry)
        .where(
            LeaveLedgerEntry.is_deleted == False,  # noqa: E712
            LeaveLedgerEntry.employee_id == employee_id,
            LeaveLedgerEntry.policy_id == policy_id,
            LeaveLedgerEntry.leave_year == leave_year,
        )
        .order_by(LeaveLedgerEntry.created_at.desc())  # type: ignore
    )

    count_stmt = select(func.count()).select_from(LeaveLedgerEntry).where(
        LeaveLedgerEntry.is_deleted == False,  # noqa: E712
        LeaveLedgerEntry.employee_id == employee_id,
        LeaveLedgerEntry.policy_id == policy_id,
        LeaveLedgerEntry.leave_year == leave_year,
    )
    total_count = session.exec(count_stmt).one()

    consumed_total = session.exec(
        select(func.sum(func.abs(LeaveLedgerEntry.amount))).where(
            LeaveLedgerEntry.is_deleted == False,  # noqa: E712
            LeaveLedgerEntry.employee_id == employee_id,
            LeaveLedgerEntry.policy_id == policy_id,
            LeaveLedgerEntry.leave_year == leave_year,
            LeaveLedgerEntry.source.in_(["consumed", "carryover_out"]),  # type: ignore
        )
    ).one() or Decimal("0.00")

    reversal_total = session.exec(
        select(func.sum(LeaveLedgerEntry.amount)).where(
            LeaveLedgerEntry.is_deleted == False,  # noqa: E712
            LeaveLedgerEntry.employee_id == employee_id,
            LeaveLedgerEntry.policy_id == policy_id,
            LeaveLedgerEntry.leave_year == leave_year,
            LeaveLedgerEntry.source == "reversal",
        )
    ).one() or Decimal("0.00")

    granted_total = session.exec(
        select(func.sum(LeaveLedgerEntry.amount)).where(
            LeaveLedgerEntry.is_deleted == False,  # noqa: E712
            LeaveLedgerEntry.employee_id == employee_id,
            LeaveLedgerEntry.policy_id == policy_id,
            LeaveLedgerEntry.leave_year == leave_year,
            LeaveLedgerEntry.source.in_(["grant", "accrual", "carryover_in", "manual_adjustment"]),  # type: ignore
        )
    ).one() or Decimal("0.00")

    net_consumed = consumed_total - abs(reversal_total)
    remaining = granted_total - net_consumed

    events = list(session.exec(base.offset(skip).limit(limit)).all())
    return events, total_count, granted_total, net_consumed, remaining


# === Holiday =============================================================================


def is_holiday(*, session: Session, check_date: date) -> HolidayInstance | None:
    """Check if ``check_date`` is a holiday instance (observed date)."""
    return session.exec(
        select(HolidayInstance).where(
            HolidayInstance.is_deleted == False,  # noqa: E712
            HolidayInstance.is_active == True,  # noqa: E712
            HolidayInstance.observed_date == check_date,
        )
    ).first()


def list_holiday_configs(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[HolidayConfig], int]:
    return get_list(session=session, model=HolidayConfig, skip=skip, limit=limit)


def get_holiday_config(*, session: Session, config_id: uuid.UUID) -> HolidayConfig | None:
    return get_active_by_id(session=session, model=HolidayConfig, obj_id=config_id)


def list_holiday_instances(
    *, session: Session, leave_year: int, skip: int = 0, limit: int = 100
) -> tuple[list[HolidayInstance], int]:
    base = (
        select(HolidayInstance)
        .where(HolidayInstance.is_deleted == False)  # noqa: E712
        .where(HolidayInstance.leave_year == leave_year)
    )
    count_stmt = select(func.count()).select_from(HolidayInstance).where(
        HolidayInstance.is_deleted == False,  # noqa: E712
        HolidayInstance.leave_year == leave_year,
    )
    count = session.exec(count_stmt).one()
    stmt = base.offset(skip).limit(limit)
    rows = session.exec(stmt).all()
    return list(rows), count


def get_holiday_instances_for_year(
    *, session: Session, leave_year: int
) -> list[HolidayInstance]:
    return list(
        session.exec(
            select(HolidayInstance)
            .where(
                HolidayInstance.is_deleted == False,  # noqa: E712
                HolidayInstance.leave_year == leave_year,
                HolidayInstance.is_active == True,  # noqa: E712
            )
            .order_by(HolidayInstance.observed_date.asc())  # type: ignore
        ).all()
    )


# === Calendar ============================================================================


def get_employee_leave_calendar(
    *, session: Session, employee_id: uuid.UUID, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    """Return calendar events (requests + holidays) for the date range."""

    requests = session.exec(
        select(LeaveRequest)
        .where(
            LeaveRequest.is_deleted == False,  # noqa: E712
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.date_start <= to_date,
            LeaveRequest.date_end >= from_date,
        )
        .order_by(LeaveRequest.date_start.asc())  # type: ignore
    ).all()

    holidays = session.exec(
        select(HolidayInstance)
        .where(
            HolidayInstance.is_deleted == False,  # noqa: E712
            HolidayInstance.is_active == True,  # noqa: E712
            HolidayInstance.observed_date >= from_date,
            HolidayInstance.observed_date <= to_date,
        )
        .order_by(HolidayInstance.observed_date.asc())  # type: ignore
    ).all()

    events: list[dict[str, Any]] = []

    for req in requests:
        policy = get_active_by_id(session=session, model=LeavePolicy, obj_id=req.policy_id)  # type: ignore
        events.append({
            "id": req.id,
            "observed_date": req.date_start,
            "title": policy.name if policy else "Leave",
            "status": req.status,
            "color": policy.calendar_color if policy else "#3B82F6",
            "type": "request",
        })

    for hi in holidays:
        cfg = get_active_by_id(session=session, model=HolidayConfig, obj_id=hi.config_id)
        events.append({
            "id": hi.id,
            "observed_date": hi.observed_date,
            "title": cfg.name if cfg else "Holiday",
            "status": None,
            "color": "#EF4444",
            "type": "holiday",
        })

    return events
