"""Write operations for attendance resources (design §3).

Follows the Phase 0-1 service shape (keyword-only args, ``session`` first,
``model_validate``/``sqlmodel_update``, add/commit/refresh). The calc core
(calc.compute_dtr) runs server-side on every punch create/update so stored
values are always consistent; actor fields are set from CurrentUser, never from
the request body.
"""

import uuid
from datetime import datetime, timezone
from typing import TypeVar

from fastapi import HTTPException
from sqlmodel import Session

from app.attendance import calc
from app.attendance.models import DailyTimeRecord, Shift
from app.attendance.selectors import get_active_by_id

T = TypeVar("T")


def _build_shift_params(shift: Shift | None) -> calc.ShiftParams:
    """Build the decoupled calc input from a Shift row, or DEFAULT_SHIFT."""
    if shift is None:
        return calc.DEFAULT_SHIFT
    return calc.ShiftParams(
        start_minutes=calc.parse_time_to_minutes(shift.start_time),
        end_minutes=calc.parse_time_to_minutes(shift.end_time),
        lunch_minutes=shift.lunch_break_duration,
        shift_minutes=shift.total_hours_minus_lunch,
        days_of_week=tuple(int(d) for d in shift.days_of_week),
    )


def _compute_and_apply(
    *, db_obj: DailyTimeRecord, shift: Shift | None
) -> None:
    """Run the calc core and write the computed minutes onto the row."""
    if db_obj.login_date is None or db_obj.logout_date is None:
        return
    params = _build_shift_params(shift)
    result = calc.compute_dtr(db_obj.login_date, db_obj.logout_date, params)
    db_obj.rendered_minutes = result.rendered_minutes
    db_obj.late_minutes = result.late_minutes
    db_obj.undertime_minutes = result.undertime_minutes
    db_obj.overtime_minutes = result.overtime_minutes
    db_obj.is_time_calculated = True


def create_obj(*, session: Session, model: type[T], data) -> T:
    db_obj = model.model_validate(data)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_obj(*, session: Session, db_obj: T, data) -> T:
    update_dict = data.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_dict)
    db_obj.updated_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def soft_delete_obj(*, session: Session, db_obj: T) -> T:
    db_obj.is_deleted = True
    db_obj.deleted_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def create_dtr(
    *,
    session: Session,
    data,
    actor_id: uuid.UUID,
) -> DailyTimeRecord:
    """Create a punch record: resolve codes, validate, run the calc core, set actor.

    ``employee_code``/``shift_code`` resolve server-side to their UUIDs (design §3.2
    column mapping). ``source`` is forced to ``'manual'`` server-side; computed and
    actor fields on the request body are ignored (server-authoritative).
    """
    from app.attendance.models import Shift
    from app.attendance.selectors import (
        get_employee_by_code,
        get_employee_by_id,
        get_shift_by_code,
    )

    # --- resolve employee_code -> employee_id ---
    employee_id = data.employee_id
    if employee_id is None:
        if data.employee_code is None:
            raise HTTPException(
                status_code=400, detail="Either employee_id or employee_code is required"
            )
        emp = get_employee_by_code(session=session, code=data.employee_code)
        if emp is None:
            raise HTTPException(
                status_code=404, detail=f"Employee not found: {data.employee_code}"
            )
        employee_id = emp.id

    # The employee must exist whether resolved by id or by code.
    emp = get_employee_by_id(session=session, employee_id=employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")

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

    if data.login_date >= data.logout_date:
        raise HTTPException(
            status_code=400, detail="login_date must be before logout_date"
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

    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


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
    data,
    shift: Shift | None,
    actor_id: uuid.UUID,
) -> DailyTimeRecord:
    """Recompute via the calc core if login/logout/shift change; set actor."""
    update_dict = data.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_dict)
    db_obj.updated_at = datetime.now(timezone.utc)
    db_obj.updated_by = actor_id

    if db_obj.login_date and db_obj.logout_date and db_obj.login_date >= db_obj.logout_date:
        raise HTTPException(
            status_code=400, detail="login_date must be before logout_date"
        )

    _compute_and_apply(db_obj=db_obj, shift=shift)

    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def set_overtime_approved(
    *, session: Session, db_obj: DailyTimeRecord, approved: bool, actor_id: uuid.UUID
) -> DailyTimeRecord:
    """Phase 2B: flip overtime_approved (paid only when True)."""
    db_obj.overtime_approved = approved
    db_obj.updated_at = datetime.now(timezone.utc)
    db_obj.updated_by = actor_id
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj
