"""Write operations for the leave domain (design doc §1.4).

All functions take a Session, validate against the rules, write LeaveLedgerEntry rows,
and emit LeaveRequestEvent rows when state changes occur. All ledger mutations are
inside a single SQLAlchemy transaction per request.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.employee.models import EmployeeRecords
from app.employee.selectors import get_active_by_id as get_employee_active_by_id
from app.leave import calc, selectors
from app.leave.models import (
    EmployeeLeaveEnrollment,
    HolidayConfig,
    HolidayInstance,
    LeaveLedgerEntry,
    LeaveLedgerSource,
    LeavePolicy,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveRequestEventType,
    LeaveStatus,
)
from app.user.models import User


def _write_event(
    *, session: Session, request_id: uuid.UUID, event_type: LeaveRequestEventType,
    actor_id: uuid.UUID | None, note: str | None = None, run_id: str | None = None
) -> LeaveRequestEvent:
    evt = LeaveRequestEvent(
        request_id=request_id,
        event=event_type,
        actor_user_id=actor_id,
        note=note,
        run_id=run_id,
    )
    session.add(evt)
    return evt


def _check_eligibility(
    *, employee: EmployeeRecords, policy: LeavePolicy
) -> None:
    """Raise 403 if employee is not eligible for the policy."""
    if policy.gender_scope != "all" and employee.gender is not None:
        if employee.gender.lower() != policy.gender_scope.value:
            raise HTTPException(status_code=403, detail="Employee not eligible for this leave policy")

    if policy.marital_status_scope != "all" and employee.civil_status is not None:
        if employee.civil_status.lower() != policy.marital_status_scope.value:
            raise HTTPException(status_code=403, detail="Employee not eligible for this leave policy")

    if policy.eligible_departments and employee.department_id is not None:
        if employee.department_id not in policy.eligible_departments:
            raise HTTPException(status_code=403, detail="Employee not eligible for this leave policy")


def submit_request(
    *, session: Session, actor: User, payload: dict[str, Any]
) -> LeaveRequest:
    """Submit a new leave request.

    Validates eligibility (department, gender, marital status), checks for date
    overlap with existing pending/approved requests, computes total_days_requested,
    creates the request, and writes a created event. Does NOT write to the ledger.
    """
    from app.leave.schemas import LeaveRequestCreate

    data = LeaveRequestCreate(**payload)

    employee = session.exec(
        select(EmployeeRecords)
        .where(EmployeeRecords.id == data.employee_id, EmployeeRecords.is_deleted == False)  # noqa: E712
        .with_for_update()
    ).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    policy = selectors.get_policy(session=session, policy_id=data.policy_id)
    if policy is None or not policy.is_active:
        raise HTTPException(status_code=404, detail="Leave policy not found or inactive")

    _check_eligibility(employee=employee, policy=policy)

    if selectors.check_overlapping_requests(
        session=session,
        employee_id=data.employee_id,
        date_start=data.date_start,
        date_end=data.date_end,
    ):
        raise HTTPException(status_code=422, detail="Leave request overlaps with an existing pending or approved request")

    if data.date_end < data.date_start:
        raise HTTPException(status_code=422, detail="date_end must be greater than or equal to date_start")

    workday_hours = Decimal("8.0")
    holidays: set[date] = set()
    schedule: set[date] | None = None

    total_days = calc.leave_days_in_range(
        data.date_start,
        data.date_end,
        requested_hours=data.requested_hours,
        workday_hours=workday_hours,
        schedule=schedule,
        holidays=holidays,
    )

    enrollment = selectors.get_active_enrollment(
        session=session,
        employee_id=data.employee_id,
        policy_id=data.policy_id,
        leave_year=data.date_start.year,
    )

    db_obj = LeaveRequest.model_validate(data, update={
        "total_days_requested": total_days,
        "status": LeaveStatus.PENDING,
        "created_by_user": actor.id,
        "enrollment_id": enrollment.id if enrollment else None,
    })

    session.add(db_obj)
    session.flush()

    _write_event(
        session=session,
        request_id=db_obj.id,
        event_type=LeaveRequestEventType.CREATED,
        actor_id=actor.id,
    )

    session.commit()
    session.refresh(db_obj)
    return db_obj


def approve_request(
    *, session: Session, actor: User, request_id: uuid.UUID
) -> LeaveRequest:
    """Approve a leave request.

    Uses pessimistic locking: acquires FOR UPDATE lock on the leave request row
    to prevent concurrent approvals. Validates balance availability, writes a
    consumed ledger entry, transitions to approved. Idempotent: if already
    approved, no second ledger entry is written; writes a noop event.
    """
    db_obj = session.exec(
        select(LeaveRequest)
        .where(LeaveRequest.id == request_id, LeaveRequest.is_deleted == False)  # noqa: E712
        .with_for_update()
    ).first()
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if db_obj.status == LeaveStatus.APPROVED:
        _write_event(
            session=session,
            request_id=db_obj.id,
            event_type=LeaveRequestEventType.NOOP,
            actor_id=actor.id,
            note="Already approved",
        )
        session.commit()
        return db_obj

    calc.validate_state_transition(db_obj.status.value, "approved")

    granted_total, consumed_total, remaining = selectors.get_employee_ledger(
        session=session,
        employee_id=db_obj.employee_id,  # type: ignore
        policy_id=db_obj.policy_id,  # type: ignore
        leave_year=db_obj.date_start.year,
    )

    if remaining < db_obj.total_days_requested:
        raise HTTPException(status_code=422, detail="Insufficient leave balance")

    current_enrollment = selectors.get_active_enrollment(
        session=session,
        employee_id=db_obj.employee_id,  # type: ignore
        policy_id=db_obj.policy_id,  # type: ignore
        leave_year=db_obj.date_start.year,
    )

    ledger_entry = LeaveLedgerEntry(
        employee_id=db_obj.employee_id,
        policy_id=db_obj.policy_id,
        enrollment_id=current_enrollment.id if current_enrollment else None,
        leave_year=db_obj.date_start.year,
        source=LeaveLedgerSource.CONSUMED,
        amount=-db_obj.total_days_requested,
        reference=f"LeaveRequest:{db_obj.id}",
        actor_user_id=actor.id,
    )
    session.add(ledger_entry)

    db_obj.status = LeaveStatus.APPROVED
    db_obj.approved_by_user = actor.id
    db_obj.approved_at = datetime.now(timezone.utc)

    _write_event(
        session=session,
        request_id=db_obj.id,
        event_type=LeaveRequestEventType.APPROVED,
        actor_id=actor.id,
    )

    session.commit()
    session.refresh(db_obj)
    return db_obj


def reject_request(
    *, session: Session, actor: User, request_id: uuid.UUID, note: str | None = None
) -> LeaveRequest:
    """Reject a pending leave request. No ledger change."""
    db_obj = selectors.get_leave_request(session=session, request_id=request_id)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Leave request not found")

    calc.validate_state_transition(db_obj.status.value, "rejected")

    db_obj.status = LeaveStatus.REJECTED
    db_obj.rejected_by_user = actor.id
    db_obj.rejected_at = datetime.now(timezone.utc)
    db_obj.decision_note = note

    _write_event(
        session=session,
        request_id=db_obj.id,
        event_type=LeaveRequestEventType.REJECTED,
        actor_id=actor.id,
        note=note,
    )

    session.commit()
    session.refresh(db_obj)
    return db_obj


def cancel_request(
    *, session: Session, actor: User, request_id: uuid.UUID, note: str | None = None
) -> LeaveRequest:
    """Cancel a leave request.

    If previously approved, writes a reversal ledger entry to the employee's
    current active enrollment year (not the original leave year), with original_year
    recorded.
    """
    db_obj = selectors.get_leave_request(session=session, request_id=request_id)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Leave request not found")

    was_approved = db_obj.status == LeaveStatus.APPROVED

    calc.validate_state_transition(db_obj.status.value, "cancelled")

    if was_approved:
        current_enrollment = selectors.get_active_enrollment(
            session=session,
            employee_id=db_obj.employee_id,  # type: ignore
            policy_id=db_obj.policy_id,  # type: ignore
            leave_year=date.today().year,
        )
        reversal_year = date.today().year

        ledger_entry = LeaveLedgerEntry(
            employee_id=db_obj.employee_id,
            policy_id=db_obj.policy_id,
            enrollment_id=current_enrollment.id if current_enrollment else None,
            leave_year=reversal_year,
            source=LeaveLedgerSource.REVERSAL,
            amount=db_obj.total_days_requested,
            reference=f"LeaveRequest:{db_obj.id}",
            original_year=db_obj.date_start.year,
            note=f"Cancellation of request {db_obj.id}",
            actor_user_id=actor.id,
        )
        session.add(ledger_entry)

    db_obj.status = LeaveStatus.CANCELLED
    db_obj.cancelled_by_user = actor.id
    db_obj.cancelled_at = datetime.now(timezone.utc)
    db_obj.decision_note = note

    _write_event(
        session=session,
        request_id=db_obj.id,
        event_type=LeaveRequestEventType.CANCELLED,
        actor_id=actor.id,
        note=note,
    )

    session.commit()
    session.refresh(db_obj)
    return db_obj


def enroll_employee(
    *, session: Session, actor: User, employee_id: uuid.UUID, policy_id: uuid.UUID, leave_year: int
) -> EmployeeLeaveEnrollment:
    """Enroll an employee in a leave policy for a year.

    Validates eligibility, creates the enrollment, and writes a grant ledger entry.
    Returns 409 if an active enrollment already exists.
    """
    employee = get_employee_active_by_id(session=session, model=EmployeeRecords, obj_id=employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    policy = selectors.get_policy(session=session, policy_id=policy_id)
    if policy is None or not policy.is_active:
        raise HTTPException(status_code=404, detail="Leave policy not found or inactive")

    _check_eligibility(employee=employee, policy=policy)

    existing = selectors.get_active_enrollment(
        session=session, employee_id=employee_id, policy_id=policy_id, leave_year=leave_year
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Active enrollment already exists for this policy and year")

    from app.leave.calc import accrue_for_year
    hire_date = None
    if hasattr(employee, 'date_hired') and employee.date_hired:
        hire_date = employee.date_hired

    granted_days = accrue_for_year(policy, hire_date, leave_year)

    enrollment = EmployeeLeaveEnrollment(
        employee_id=employee_id,
        policy_id=policy_id,
        leave_year=leave_year,
        granted_days=granted_days,
        is_active=True,
    )
    session.add(enrollment)
    session.flush()

    ledger_entry = LeaveLedgerEntry(
        employee_id=employee_id,
        policy_id=policy_id,
        enrollment_id=enrollment.id,
        leave_year=leave_year,
        source=LeaveLedgerSource.GRANT,
        amount=granted_days,
        reference=f"Enrollment:{enrollment.id}",
        actor_user_id=actor.id,
    )
    session.add(ledger_entry)

    session.commit()
    session.refresh(enrollment)
    return enrollment


def run_monthly_accrual(
    *, session: Session, actor: User, leave_year: int, target_year: int, target_month: int
) -> int:
    """Run monthly accrual for all enrolled employees with monthly cadence policies.

    Returns the count of ledger entries written. Requires leave_policy.admin permission.
    """
    if target_year < 1900 or target_month < 1 or target_month > 12:
        raise HTTPException(status_code=422, detail="Invalid target_year or target_month")

    policies = session.exec(
        select(LeavePolicy).where(
            LeavePolicy.is_deleted == False,  # noqa: E712
            LeavePolicy.is_active == True,  # noqa: E712
            LeavePolicy.cadence == "monthly",
        )
    ).all()

    count = 0
    run_id = f"accrual-{target_year}-{target_month:02d}"

    for policy in policies:
        enrollments = session.exec(
            select(EmployeeLeaveEnrollment).where(
                EmployeeLeaveEnrollment.is_deleted == False,  # noqa: E712
                EmployeeLeaveEnrollment.is_active == True,  # noqa: E712
                EmployeeLeaveEnrollment.policy_id == policy.id,
                EmployeeLeaveEnrollment.leave_year == leave_year,
            )
        ).all()

        chunk = calc.monthly_accrual_chunk(policy)

        for enrollment in enrollments:
            existing = session.exec(
                select(LeaveLedgerEntry).where(
                    LeaveLedgerEntry.is_deleted == False,  # noqa: E712
                    LeaveLedgerEntry.enrollment_id == enrollment.id,
                    LeaveLedgerEntry.source == LeaveLedgerSource.ACCRUAL,
                )
            ).all()

            already_accrued = any(
                e.reference == f"accrual-{target_year}-{target_month:02d}"
                for e in existing
            )
            if already_accrued:
                continue

            ledger_entry = LeaveLedgerEntry(
                employee_id=enrollment.employee_id,
                policy_id=policy.id,
                enrollment_id=enrollment.id,
                leave_year=leave_year,
                source=LeaveLedgerSource.ACCRUAL,
                amount=chunk,
                reference=run_id,
                note=f"Monthly accrual {target_year}-{target_month:02d}",
                actor_user_id=actor.id,
            )
            session.add(ledger_entry)
            count += 1

            _write_event(
                session=session,
                request_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                event_type=LeaveRequestEventType.NOOP,
                actor_id=actor.id,
                note=f"Accrual run {run_id}",
                run_id=run_id,
            )

    session.commit()
    return count


def run_year_end_carryover(
    *, session: Session, actor: User, from_year: int, to_year: int,
    target_year_from: int, target_year_to: int
) -> int:
    """Run year-end carryover for all active enrollments.

    Returns the count of carryover entries written. Requires leave_policy.admin permission.
    """
    if target_year_from != from_year or target_year_to != to_year:
        raise HTTPException(status_code=422, detail="target_year_from and target_year_to must match from_year and to_year")

    enrollments = session.exec(
        select(EmployeeLeaveEnrollment).where(
            EmployeeLeaveEnrollment.is_deleted == False,  # noqa: E712
            EmployeeLeaveEnrollment.is_active == True,  # noqa: E712
            EmployeeLeaveEnrollment.leave_year == from_year,
        )
    ).all()

    count = 0
    run_id = f"carryover-{from_year}-{to_year}"

    for enrollment in enrollments:
        granted_total, consumed_total, remaining = selectors.get_employee_ledger(
            session=session,
            employee_id=enrollment.employee_id,  # type: ignore
            policy_id=enrollment.policy_id,  # type: ignore
            leave_year=from_year,
        )

        policy = selectors.get_policy(session=session, policy_id=enrollment.policy_id)  # type: ignore
        if policy is None:
            continue

        carryover_days = calc.carryover_amount(remaining, policy)

        if carryover_days > 0:
            existing_target = selectors.get_active_enrollment(
                session=session,
                employee_id=enrollment.employee_id,  # type: ignore
                policy_id=enrollment.policy_id,  # type: ignore
                leave_year=to_year,
            )
            if existing_target is not None:
                continue

            new_enrollment = EmployeeLeaveEnrollment(
                employee_id=enrollment.employee_id,
                policy_id=enrollment.policy_id,
                leave_year=to_year,
                granted_days=carryover_days,
                is_active=True,
            )
            session.add(new_enrollment)

            carry_out = LeaveLedgerEntry(
                employee_id=enrollment.employee_id,
                policy_id=enrollment.policy_id,
                enrollment_id=enrollment.id,
                leave_year=from_year,
                source=LeaveLedgerSource.CARRYOVER_OUT,
                amount=-carryover_days,
                reference=run_id,
                actor_user_id=actor.id,
            )
            carry_in = LeaveLedgerEntry(
                employee_id=enrollment.employee_id,
                policy_id=enrollment.policy_id,
                enrollment_id=new_enrollment.id,
                leave_year=to_year,
                source=LeaveLedgerSource.CARRYOVER_IN,
                amount=carryover_days,
                reference=run_id,
                original_year=from_year,
                actor_user_id=actor.id,
            )
            session.add(carry_out)
            session.add(carry_in)
            count += 1

            _write_event(
                session=session,
                request_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                event_type=LeaveRequestEventType.NOOP,
                actor_id=actor.id,
                note=f"Carryover run {run_id}",
                run_id=run_id,
            )

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return count

    return count


def apply_manual_adjustment(
    *, session: Session, actor: User,
    employee_id: uuid.UUID, policy_id: uuid.UUID, leave_year: int,
    delta: Decimal, note: str
) -> LeaveLedgerEntry:
    """Apply a manual balance adjustment. Negative balances are allowed.

    Requires leave_policy.admin permission.
    """
    if not note or not note.strip():
        raise HTTPException(status_code=422, detail="Note is required for manual adjustments")

    policy = selectors.get_policy(session=session, policy_id=policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    enrollment = selectors.get_active_enrollment(
        session=session, employee_id=employee_id, policy_id=policy_id, leave_year=leave_year
    )

    ledger_entry = LeaveLedgerEntry(
        employee_id=employee_id,
        policy_id=policy_id,
        enrollment_id=enrollment.id if enrollment else None,
        leave_year=leave_year,
        source=LeaveLedgerSource.MANUAL_ADJUSTMENT,
        amount=delta,
        reference="Manual adjustment",
        note=note,
        actor_user_id=actor.id,
    )
    session.add(ledger_entry)
    session.commit()
    session.refresh(ledger_entry)
    return ledger_entry


def deactivate_policy(
    *, session: Session, _actor: User, policy_id: uuid.UUID
) -> LeavePolicy:
    """Deactivate a leave policy.

    Returns 409 with blocking request IDs if any leave request for this policy
    has status pending or approved. Otherwise soft-deletes (is_active=False).
    """
    from sqlmodel import select

    blocking = session.exec(
        select(LeaveRequest).where(
            LeaveRequest.is_deleted == False,  # noqa: E712
            LeaveRequest.policy_id == policy_id,
            LeaveRequest.status.in_(["pending", "approved"]),  # type: ignore
        )
    ).all()

    if blocking:
        blocking_ids = [str(r.id) for r in blocking]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot deactivate policy with active requests: {', '.join(blocking_ids)}"
        )

    policy = selectors.get_policy(session=session, policy_id=policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    policy.is_active = False
    policy.is_deleted = True
    policy.deleted_at = datetime.now(timezone.utc)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def create_policy(*, session: Session, data: dict[str, Any]) -> LeavePolicy:
    """Create a new leave policy."""
    db_obj = LeavePolicy.model_validate(data)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_policy(
    *, session: Session, policy_id: uuid.UUID, data: dict[str, Any]
) -> LeavePolicy:
    """Update an existing leave policy."""
    policy = selectors.get_policy(session=session, policy_id=policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Leave policy not found")
    policy.sqlmodel_update(data)
    policy.updated_at = datetime.now(timezone.utc)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def create_holiday_config(*, session: Session, data: dict[str, Any]) -> HolidayConfig:
    """Create a new holiday config."""
    db_obj = HolidayConfig.model_validate(data)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_holiday_config(
    *, session: Session, config_id: uuid.UUID, data: dict[str, Any]
) -> HolidayConfig:
    """Update an existing holiday config."""
    cfg = selectors.get_holiday_config(session=session, config_id=config_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Holiday config not found")
    cfg.sqlmodel_update(data)
    cfg.updated_at = datetime.now(timezone.utc)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


def create_holiday_instance(
    *, session: Session, config_id: uuid.UUID, date_val: date,
    raw_date_val: date | None, leave_year: int
) -> HolidayInstance:
    """Create a holiday instance for a year."""
    cfg = selectors.get_holiday_config(session=session, config_id=config_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Holiday config not found")

    db_obj = HolidayInstance(
        config_id=config_id,
        observed_date=date_val,
        raw_date=raw_date_val,
        leave_year=leave_year,
        is_active=True,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj
