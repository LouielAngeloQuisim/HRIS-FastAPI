"""Write operations for DTR adjustments (design §2B).

State machine: PENDING -> APPROVED | REJECTED.
- APPROVED applies the adjusted times to the underlying DailyTimeRecord and
  recomputes it via the calc core (analysis §7: adjustment OT then counts in pay).
- REJECTED leaves the DTR unchanged.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from app.attendance.adjustment_models import DtrAdjustment
from app.attendance.models import DailyTimeRecord
from app.attendance.services import get_active_by_id


def get_adjustment(*, session: Session, adjustment_id: uuid.UUID) -> DtrAdjustment | None:
    """Fetch a non-deleted adjustment by PK, or None."""
    row = session.get(DtrAdjustment, adjustment_id)
    if row is None or row.is_deleted:
        return None
    return row


def create_adjustment(
    *,
    session: Session,
    data,
    dtr: DailyTimeRecord,
    actor_id: uuid.UUID,
) -> DtrAdjustment:
    """Propose a correction. Starts in PENDING; snapshots the current times."""
    now = datetime.now(timezone.utc)
    db_obj = DtrAdjustment(
        daily_time_record_id=dtr.id,
        employee_id=dtr.employee_id,
        original_login_date=dtr.login_date,
        original_logout_date=dtr.logout_date,
        adjusted_login_date=data.adjusted_login_date,
        adjusted_logout_date=data.adjusted_logout_date,
        reason=data.reason,
        adjusted_date=data.adjusted_date,
        status="PENDING",
        created_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def _apply_adjustment(*, session: Session, adjustment: DtrAdjustment) -> None:
    """Apply the adjusted times to the DTR and recompute (server-authoritative)."""
    dtr = get_active_by_id(session=session, model=DailyTimeRecord, obj_id=adjustment.daily_time_record_id)
    if dtr is None:
        raise HTTPException(status_code=404, detail="DailyTimeRecord not found")
    dtr.login_date = adjustment.adjusted_login_date
    dtr.logout_date = adjustment.adjusted_logout_date
    dtr.updated_at = datetime.now(timezone.utc)
    session.add(dtr)
    session.flush()
    from app.attendance.services import recompute_dtr

    recompute_dtr(session=session, dtr=dtr)


def approve_adjustment(
    *, session: Session, adjustment: DtrAdjustment, actor_id: uuid.UUID
) -> DtrAdjustment:
    """PENDING -> APPROVED: apply the correction and recompute the DTR."""
    if adjustment.status != "PENDING":
        raise HTTPException(
            status_code=409, detail=f"Cannot approve an adjustment with status {adjustment.status}"
        )
    _apply_adjustment(session=session, adjustment=adjustment)
    adjustment.status = "APPROVED"
    adjustment.approved_by = actor_id
    adjustment.updated_at = datetime.now(timezone.utc)
    session.add(adjustment)
    session.commit()
    session.refresh(adjustment)
    return adjustment


def reject_adjustment(
    *, session: Session, adjustment: DtrAdjustment, actor_id: uuid.UUID
) -> DtrAdjustment:
    """PENDING -> REJECTED: DTR is left unchanged."""
    if adjustment.status != "PENDING":
        raise HTTPException(
            status_code=409, detail=f"Cannot reject an adjustment with status {adjustment.status}"
        )
    adjustment.status = "REJECTED"
    adjustment.approved_by = actor_id
    adjustment.updated_at = datetime.now(timezone.utc)
    session.add(adjustment)
    session.commit()
    session.refresh(adjustment)
    return adjustment
