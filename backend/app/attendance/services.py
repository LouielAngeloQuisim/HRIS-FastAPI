"""Write operations for attendance resources (design §3).

Follows the Phase 0-1 service shape (keyword-only args, ``session`` first,
``model_validate``/``sqlmodel_update``, add/commit/refresh). The calc core
(calc.compute_dtr) runs server-side on every punch create/update so stored
values are always consistent; actor fields are set from CurrentUser, never from
the request body.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.attendance import calc
from app.attendance.models import (
    DailyTimeRecord,
    DtrAttendanceInterval,
    DtrOvertimeDecision,
    Shift,
)
from app.attendance.schemas import DailyTimeRecordCreate, DailyTimeRecordUpdate
from app.attendance.selectors import get_active_by_id
from app.common.types import ModelT
from app.employee.models import EmployeeRecords


def resolve_attendance_work_date(*, session: Session, employee_id: uuid.UUID, login_date: datetime) -> date:
    """Anchor a punch to the effective shift's starting Manila work date."""
    from app.attendance.selectors import get_employee_shift_assignment

    login_at = login_date
    if login_at.tzinfo is None:
        login_at = login_at.replace(tzinfo=timezone.utc)
    local_login = login_at.astimezone(ZoneInfo("Asia/Manila"))
    work_date = local_login.date()
    prior_assignment = get_employee_shift_assignment(
        session=session, employee_id=employee_id, work_date=work_date - timedelta(days=1)
    )
    if prior_assignment is not None:
        prior_shift = get_active_by_id(session=session, model=Shift, obj_id=prior_assignment.shift_id)
        if prior_shift is not None:
            prior_start = calc.parse_time_to_minutes(prior_shift.start_time)
            prior_end = calc.parse_time_to_minutes(prior_shift.end_time)
            login_minute = local_login.hour * 60 + local_login.minute
            if prior_start > prior_end and login_minute < prior_end:
                work_date -= timedelta(days=1)
    return work_date


def _build_shift_params(shift: Shift) -> calc.ShiftParams:
    """Build calculation inputs from the employee's effective assigned shift."""
    return calc.ShiftParams(
        start_minutes=calc.parse_time_to_minutes(shift.start_time),
        end_minutes=calc.parse_time_to_minutes(shift.end_time),
        lunch_minutes=shift.lunch_break_duration,
        shift_minutes=shift.total_hours_minus_lunch,
        days_of_week=tuple(int(d) for d in shift.days_of_week),
    )


def _compute_and_apply(*, db_obj: DailyTimeRecord, shift: Shift | None) -> None:
    """Run the calc core and write the computed minutes onto the row."""
    # Any recalculation changes the evidence behind an overtime decision.
    db_obj.overtime_approved = None
    db_obj.overtime_approved_minutes = None
    db_obj.overtime_decision_reason = None
    db_obj.overtime_decided_by = None
    db_obj.overtime_decided_at = None
    if db_obj.login_date is None:
        db_obj.work_date = None
        db_obj.rendered_minutes = None
        db_obj.late_minutes = None
        db_obj.undertime_minutes = None
        db_obj.overtime_minutes = None
        db_obj.is_time_calculated = False
        return
    if shift is None:
        raise HTTPException(
            status_code=422,
            detail="An effective shift assignment is required to calculate attendance.",
        )
    login_at = db_obj.login_date
    if login_at.tzinfo is None:
        login_at = login_at.replace(tzinfo=timezone.utc)
    local_login = login_at.astimezone(ZoneInfo("Asia/Manila"))
    work_date = local_login.date()
    if shift is not None:
        shift_start = calc.parse_time_to_minutes(shift.start_time)
        shift_end = calc.parse_time_to_minutes(shift.end_time)
        login_minute = local_login.hour * 60 + local_login.minute
        if shift_start > shift_end and login_minute < shift_end:
            work_date -= timedelta(days=1)
    db_obj.work_date = work_date
    if db_obj.logout_date is None:
        db_obj.rendered_minutes = None
        db_obj.late_minutes = None
        db_obj.undertime_minutes = None
        db_obj.overtime_minutes = None
        db_obj.is_time_calculated = False
        return
    zone = ZoneInfo("Asia/Manila")
    local_logout = db_obj.logout_date
    if local_logout.tzinfo is None:
        local_logout = local_logout.replace(tzinfo=timezone.utc)
    local_logout = local_logout.astimezone(zone)
    scheduled_start = datetime.combine(
        work_date,
        datetime.strptime(shift.start_time, "%H:%M").time(),
        tzinfo=zone,
    )
    gross_minutes = int((local_logout - local_login).total_seconds() // 60)
    rendered_minutes = max(0, gross_minutes - shift.lunch_break_duration)
    db_obj.rendered_minutes = rendered_minutes
    db_obj.late_minutes = max(0, int((local_login - scheduled_start).total_seconds() // 60))
    db_obj.undertime_minutes = max(0, shift.total_hours_minus_lunch - rendered_minutes)
    db_obj.overtime_minutes = max(0, rendered_minutes - shift.total_hours_minus_lunch)
    db_obj.is_time_calculated = True


def create_obj(*, session: Session, model: type[ModelT], data: BaseModel) -> ModelT:
    db_obj = model.model_validate(data)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_obj(*, session: Session, db_obj: ModelT, data: BaseModel) -> ModelT:
    update_dict = data.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_dict)
    db_obj.updated_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def soft_delete_obj(*, session: Session, db_obj: ModelT) -> ModelT:
    db_obj.is_deleted = True
    db_obj.deleted_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def create_dtr(
    *,
    session: Session,
    data: DailyTimeRecordCreate,
    actor_id: uuid.UUID,
    commit: bool = True,
) -> tuple[DailyTimeRecord, bool]:
    """Create a punch record: resolve codes, validate, run the calc core, set actor.

    ``employee_code``/``shift_code`` resolve server-side to their UUIDs (design §3.2
    column mapping). ``source`` is forced to ``'manual'`` server-side; computed and
    actor fields on the request body are ignored (server-authoritative).

    QA-01 import idempotency: when ``source_ref`` (an opaque per-import-row key) is
    supplied, the same (employee, key) with identical meaningful input returns the
    already-committed row instead of inserting a duplicate — returns
    ``(existing, replayed=True)`` so the route can answer 200 instead of 201.
    Same key with a *different* payload is a conflict (409), never a silent swap.
    A key whose active row was soft-deleted is also 409: an automatic retry must
    not resurrect a deliberately deleted punch; a fresh explicit import gets a
    fresh key. Concurrency is settled by the partial unique index
    ``uq_daily_time_record_source_ref_active`` — the INSERT runs in a SAVEPOINT; a
    losing concurrent inserter rolls back to the savepoint, re-reads the committed
    winner and replays it (or 409s on a payload change). Keyless creates are
    unchanged and always return ``(row, False)`` with 201.
    """
    from app.attendance.models import Shift
    from app.attendance.selectors import (
        get_deleted_dtr_by_employee_and_source_ref,
        get_dtr_by_employee_and_source_ref,
        get_employee_by_code,
        get_employee_shift_assignment,
        get_shift_by_code,
    )

    if data.source_ref is not None and not data.source_ref.strip():
        raise HTTPException(status_code=400, detail="source_ref must not be blank")

    # --- resolve employee_code -> employee_id ---
    employee_id = data.employee_id
    if employee_id is None:
        if data.employee_code is None:
            raise HTTPException(
                status_code=400,
                detail="Either employee_id or employee_code is required",
            )
        emp = get_employee_by_code(session=session, code=data.employee_code)
        if emp is None:
            raise HTTPException(
                status_code=404, detail=f"Employee not found: {data.employee_code}"
            )
        employee_id = emp.id

    # The employee must exist whether resolved by id or by code.
    emp = session.exec(
        select(EmployeeRecords)
        .where(
            EmployeeRecords.id == employee_id,
            EmployeeRecords.is_deleted == False,  # noqa: E712
        )
        .with_for_update()
    ).first()
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.login_date >= data.logout_date:
        raise HTTPException(
            status_code=400, detail="login_date must be before logout_date"
        )

    # --- resolve shift_code -> shift_id ---
    shift_id = data.shift_id
    shift = None
    if shift_id is None and data.shift_code is not None:
        shift = get_shift_by_code(session=session, code=data.shift_code)
        if shift is None:
            raise HTTPException(
                status_code=404, detail=f"Shift not found: {data.shift_code}"
            )
        shift_id = shift.id
    elif shift_id is not None:
        shift = get_active_by_id(session=session, model=Shift, obj_id=shift_id)
        if shift is None:
            raise HTTPException(status_code=404, detail="Shift not found")

    # Assignment dates use the company calendar; timestamps remain UTC.
    work_date = resolve_attendance_work_date(
        session=session, employee_id=employee_id, login_date=data.login_date
    )
    assignment = get_employee_shift_assignment(
        session=session, employee_id=employee_id, work_date=work_date
    )
    if assignment is None:
        raise HTTPException(
            status_code=422,
            detail=f"No shift is assigned to employee {emp.employee_code} on {work_date}; assign a shift before recording attendance.",
        )
    if shift_id is None:
        shift_id = assignment.shift_id
        shift = get_active_by_id(session=session, model=Shift, obj_id=shift_id)
    elif shift_id != assignment.shift_id:
        raise HTTPException(
            status_code=409,
            detail=f"Submitted shift does not match the employee's assigned shift on {work_date}.",
        )

    # --- idempotent replay check (only when this request carries a key) ---
    if data.source_ref is not None:
        existing = get_dtr_by_employee_and_source_ref(
            session=session, employee_id=employee_id, source_ref=data.source_ref
        )
        if existing is not None:
            if _same_punch_payload(existing=existing, data=data, shift_id=shift_id):
                return existing, True
            raise HTTPException(
                status_code=409,
                detail=(
                    "Import row changed since the first attempt with the same "
                    f"identity ({data.source_ref}) - reconcile manually; the "
                    "original punch was left untouched."
                ),
            )
        if get_deleted_dtr_by_employee_and_source_ref(
            session=session, employee_id=employee_id, source_ref=data.source_ref
        ) is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The punch previously committed under this import identity "
                    f"({data.source_ref}) has been deleted. An automatic retry "
                    "will not resurrect it - start a fresh import to re-record "
                    "the punch."
                ),
            )

    existing_workday = session.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee_id,
            DailyTimeRecord.work_date == work_date,
            col(DailyTimeRecord.is_deleted).is_(False),
        )
    ).first()
    if existing_workday is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Attendance already exists for employee {emp.employee_code} "
                f"and work date {work_date}; use the correction/interval workflow."
            ),
        )
    db_obj = DailyTimeRecord.model_validate(
        data,
        update={
            "employee_id": employee_id,
            "shift_id": shift_id,
            "source": "manual",
            "created_by": actor_id,
            "updated_by": actor_id,
        },
    )
    _compute_and_apply(db_obj=db_obj, shift=shift)

    if data.source_ref is None:
        # Keyless manual create: unchanged behavior, cannot conflict on the
        # import index (NULL source_ref rows are excluded from it).
        session.add(db_obj)
        if commit:
            session.commit()
            session.refresh(db_obj)
        else:
            session.flush()
        return db_obj, False

    try:
        with session.begin_nested():
            session.add(db_obj)
            session.flush()
    except IntegrityError:
        # Lost the concurrent race: the winner has now committed (PostgreSQL
        # blocks the second inserter on the unique index until the first
        # transaction resolves), so re-read it under READ COMMITTED.
        session.expire_all()
        winner = get_dtr_by_employee_and_source_ref(
            session=session, employee_id=employee_id, source_ref=data.source_ref
        )
        if winner is None:
            same_day = session.exec(
                select(DailyTimeRecord).where(
                    DailyTimeRecord.employee_id == employee_id,
                    DailyTimeRecord.work_date == work_date,
                    col(DailyTimeRecord.is_deleted).is_(False),
                )
            ).first()
            if same_day is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Attendance already exists for this employee and work date; use the correction/interval workflow.",
                )
            raise
        if not _same_punch_payload(existing=winner, data=data, shift_id=shift_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "A different punch was committed under this import identity "
                    f"({data.source_ref}) concurrently - reconcile manually."
                ),
            )
        return winner, True

    if commit:
        session.commit()
        session.refresh(db_obj)
    return db_obj, False


def _as_utc(dt: datetime | None) -> datetime | None:
    """Normalize for replay comparison: naive request timestamps are UTC by
    convention (the wizard and API clients send explicit offsets); DB values
    come back tz-aware. Compares instants, not string formats."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _same_punch_payload(
    *,
    existing: DailyTimeRecord,
    data: DailyTimeRecordCreate,
    shift_id: uuid.UUID | None,
) -> bool:
    """Replay guard: identical meaningful punch input only.

    Actor/computed/source fields are server-authoritative and excluded; a key
    replay must never silently return a row created with different times/shift.
    """
    return (
        _as_utc(existing.login_date) == _as_utc(data.login_date)
        and _as_utc(existing.logout_date) == _as_utc(data.logout_date)
        and existing.shift_id == shift_id
    )


def recompute_dtr(*, session: Session, dtr: DailyTimeRecord) -> None:
    """Resolve the DTR's shift and recompute its minutes via the calc core."""
    shift = None
    if dtr.shift_id is not None:
        shift = get_active_by_id(session=session, model=Shift, obj_id=dtr.shift_id)
    _compute_and_apply(db_obj=dtr, shift=shift)


def update_dtr(
    *,
    session: Session,
    db_obj: DailyTimeRecord,
    data: DailyTimeRecordUpdate,
    shift: Shift | None,
    actor_id: uuid.UUID,
) -> DailyTimeRecord:
    """Recompute via the calc core if login/logout/shift change; set actor."""
    update_dict = data.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_dict)
    db_obj.updated_at = datetime.now(timezone.utc)
    db_obj.updated_by = actor_id

    if (
        db_obj.login_date
        and db_obj.logout_date
        and db_obj.login_date >= db_obj.logout_date
    ):
        raise HTTPException(
            status_code=400, detail="login_date must be before logout_date"
        )

    _compute_and_apply(db_obj=db_obj, shift=shift)

    if db_obj.work_date is not None:
        employee = session.exec(
            select(EmployeeRecords)
            .where(EmployeeRecords.id == db_obj.employee_id)
            .with_for_update()
        ).first()
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found")
        from app.attendance.selectors import get_employee_shift_assignment

        assignment = get_employee_shift_assignment(
            session=session, employee_id=db_obj.employee_id, work_date=db_obj.work_date
        )
        if assignment is None:
            raise HTTPException(status_code=422, detail="An effective shift assignment is required for the attendance work date")
        if assignment.shift_id != db_obj.shift_id:
            raise HTTPException(status_code=409, detail="Attendance shift does not match the effective employee assignment")
        existing = session.exec(
            select(DailyTimeRecord).where(
                DailyTimeRecord.employee_id == db_obj.employee_id,
                DailyTimeRecord.work_date == db_obj.work_date,
                DailyTimeRecord.id != db_obj.id,
                col(DailyTimeRecord.is_deleted).is_(False),
            )
        ).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Attendance already exists for this employee and work date")

    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def set_overtime_approved(
    *,
    session: Session,
    db_obj: DailyTimeRecord,
    approved: bool,
    actor_id: uuid.UUID,
    approved_minutes: int | None = None,
    reason: str | None = None,
) -> DailyTimeRecord:
    """Record an explicit overtime decision, bounded by calculated eligible time."""
    if db_obj.overtime_minutes is None or db_obj.overtime_minutes <= 0:
        raise HTTPException(status_code=409, detail="This record has no eligible overtime")
    if not reason or not reason.strip():
        raise HTTPException(status_code=422, detail="A decision reason is required")
    if approved:
        minutes = db_obj.overtime_minutes if approved_minutes is None else approved_minutes
        if minutes <= 0 or minutes > db_obj.overtime_minutes:
            raise HTTPException(
                status_code=422,
                detail=f"Approved overtime must be between 1 and {db_obj.overtime_minutes} minutes.",
            )
        db_obj.overtime_approved_minutes = minutes
    else:
        if approved_minutes not in (None, 0):
            raise HTTPException(status_code=422, detail="Rejected overtime cannot approve minutes")
        db_obj.overtime_approved_minutes = 0
    db_obj.overtime_approved = approved
    db_obj.overtime_decision_reason = reason.strip()
    db_obj.overtime_decided_by = actor_id
    db_obj.overtime_decided_at = datetime.now(timezone.utc)
    session.add(
        DtrOvertimeDecision(
            daily_time_record_id=db_obj.id,
            status="approved" if approved else "rejected",
            eligible_minutes=db_obj.overtime_minutes,
            approved_minutes=db_obj.overtime_approved_minutes or 0,
            reason=reason.strip(),
            decided_by=actor_id,
        )
    )
    db_obj.updated_at = datetime.now(timezone.utc)
    db_obj.updated_by = actor_id
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def replace_dtr_intervals(
    *,
    session: Session,
    dtr: DailyTimeRecord,
    intervals: list[Any],
    actor_id: uuid.UUID,
    commit: bool = True,
) -> list[DtrAttendanceInterval]:
    """Append a complete interval revision and recompute the daily record atomically."""
    locked_dtr = session.exec(
        select(DailyTimeRecord)
        .where(DailyTimeRecord.id == dtr.id, col(DailyTimeRecord.is_deleted).is_(False))
        .with_for_update()
    ).first()
    if locked_dtr is None:
        raise HTTPException(status_code=404, detail="DailyTimeRecord not found")
    dtr = locked_dtr
    if not dtr.work_date or not dtr.shift_id:
        raise HTTPException(status_code=409, detail="Work date and assigned shift are required before editing intervals")
    shift = get_active_by_id(session=session, model=Shift, obj_id=dtr.shift_id)
    if shift is None:
        raise HTTPException(status_code=409, detail="The assigned shift is unavailable")
    from app.attendance.selectors import get_employee_shift_assignment

    assignment = get_employee_shift_assignment(
        session=session, employee_id=dtr.employee_id, work_date=dtr.work_date
    )
    if assignment is None or assignment.shift_id != shift.id:
        raise HTTPException(status_code=409, detail="Effective shift assignment changed; reconcile this attendance before editing")

    zone = ZoneInfo("Asia/Manila")
    normalized: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for index, interval in enumerate(intervals):
        start = _as_utc(interval.start_at)
        end = _as_utc(interval.end_at)
        if start is None or end is None or end <= start:
            raise HTTPException(status_code=422, detail=f"Interval {index + 1} must end after it starts")
        if end - start > timedelta(hours=24):
            raise HTTPException(status_code=422, detail=f"Interval {index + 1} cannot exceed 24 hours")
        local_start = start.astimezone(zone).date()
        local_end = end.astimezone(zone).date()
        if local_start < dtr.work_date or local_start > dtr.work_date + timedelta(days=1):
            raise HTTPException(status_code=422, detail=f"Interval {index + 1} is outside the assigned work date")
        if local_end > dtr.work_date + timedelta(days=1):
            raise HTTPException(status_code=422, detail=f"Interval {index + 1} ends beyond the next local calendar day")
        normalized.append((start, end, dict(interval.original_row)))
    normalized.sort(key=lambda item: item[0])
    for previous, current in zip(normalized, normalized[1:], strict=False):
        if current[0] < previous[1]:
            raise HTTPException(status_code=422, detail="Attendance intervals overlap")

    revision = dtr.interval_revision + 1
    rows = [
        DtrAttendanceInterval(
            daily_time_record_id=dtr.id,
            revision=revision,
            sequence=index,
            start_at=start,
            end_at=end,
            original_row=source or {"start_at": start.isoformat(), "end_at": end.isoformat()},
            created_by=actor_id,
        )
        for index, (start, end, source) in enumerate(normalized)
    ]
    total_minutes = sum(int((end - start).total_seconds() // 60) for start, end, _ in normalized)
    local_starts = [start.astimezone(zone) for start, _, _ in normalized]
    scheduled_start = datetime.combine(
        dtr.work_date,
        datetime.strptime(shift.start_time, "%H:%M").time(),
        tzinfo=zone,
    )
    actual_start = min(local_starts)
    dtr.login_date = normalized[0][0]
    dtr.logout_date = max(item[1] for item in normalized)
    # A single continuous punch still needs the scheduled break deducted.
    # Multiple explicit work intervals already exclude unpaid gaps such as
    # lunch; deducting the break again would understate hours worked.
    rendered_minutes = max(
        0, total_minutes - (shift.lunch_break_duration if len(normalized) == 1 else 0)
    )
    dtr.rendered_minutes = rendered_minutes
    dtr.late_minutes = max(0, int((actual_start - scheduled_start).total_seconds() // 60))
    dtr.undertime_minutes = max(0, shift.total_hours_minus_lunch - rendered_minutes)
    dtr.overtime_minutes = max(0, rendered_minutes - shift.total_hours_minus_lunch)
    dtr.overtime_approved = None
    dtr.overtime_approved_minutes = None
    dtr.overtime_decision_reason = None
    dtr.overtime_decided_by = None
    dtr.overtime_decided_at = None
    dtr.interval_revision = revision
    dtr.updated_by = actor_id
    dtr.updated_at = datetime.now(timezone.utc)
    session.add(dtr)
    session.add_all(rows)
    if commit:
        session.commit()
    else:
        session.flush()
    return rows
