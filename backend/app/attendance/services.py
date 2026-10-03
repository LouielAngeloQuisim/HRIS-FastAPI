"""Write operations for attendance resources (design §3).

Follows the Phase 0-1 service shape (keyword-only args, ``session`` first,
``model_validate``/``sqlmodel_update``, add/commit/refresh). The calc core
(calc.compute_dtr) runs server-side on every punch create/update so stored
values are always consistent; actor fields are set from CurrentUser, never from
the request body.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.attendance import calc
from app.attendance.models import DailyTimeRecord, Shift
from app.attendance.schemas import DailyTimeRecordCreate, DailyTimeRecordUpdate
from app.attendance.selectors import get_active_by_id
from app.common.types import ModelT


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
        get_employee_by_id,
        get_shift_by_code,
    )

    if data.source_ref is not None and not data.source_ref.strip():
        raise HTTPException(status_code=400, detail="source_ref must not be blank")

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
        session.commit()
        session.refresh(db_obj)
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
    *, existing: DailyTimeRecord, data: DailyTimeRecordCreate, shift_id: uuid.UUID | None
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
