"""Notification routers (Phase B5)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.common.dependencies import CurrentUser, SessionDep
from app.common.schemas import Message
from app.notification import models as m
from app.notification import schemas as s
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "/",
    response_model=s.NotificationList,
    dependencies=[Depends(require_permission("notification", "view"))],
)
def list_notifications(session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> Any:
    stmt = (
        select(m.Notification)
        .where(
            m.Notification.user_id == current_user.id,
            m.Notification.is_deleted == False,  # noqa: E712
        )
        .order_by(m.Notification.created_at.desc())  # type: ignore[union-attr]
    )
    count = len(session.exec(stmt).all())
    rows = session.exec(stmt.offset(skip).limit(limit)).all()
    return s.NotificationList(data=[s.NotificationPublic.model_validate(r) for r in rows], count=count)


@router.post(
    "/",
    response_model=s.NotificationPublic,
    dependencies=[Depends(require_permission("notification", "add"))],
    status_code=201,
)
def create_notification(session: SessionDep, current_user: CurrentUser, payload: s.NotificationCreate) -> Any:
    payload_dict = payload.model_dump()
    payload_dict["user_id"] = current_user.id
    db_obj = m.Notification.model_validate(payload_dict)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return s.NotificationPublic.model_validate(db_obj)


@router.post(
    "/mark-all-read",
    response_model=Message,
    dependencies=[Depends(require_permission("notification", "edit"))],
)
def mark_all_notifications_read(session: SessionDep, current_user: CurrentUser) -> Any:
    stmt = (
        select(m.Notification)
        .where(
            m.Notification.user_id == current_user.id,
            m.Notification.is_deleted == False,  # noqa: E712
            m.Notification.read_at is None,  # noqa: E712
        )
    )
    notifications = session.exec(stmt).all()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for notification in notifications:
        notification.read_at = now
        session.add(notification)
    session.commit()
    return Message(message="All notifications marked as read")


@router.get(
    "/unread-count",
    dependencies=[Depends(require_permission("notification", "view"))],
)
def get_unread_count(session: SessionDep, current_user: CurrentUser) -> Any:
    stmt = (
        select(m.Notification)
        .where(
            m.Notification.user_id == current_user.id,
            m.Notification.is_deleted == False,  # noqa: E712
            m.Notification.read_at is None,  # noqa: E712
        )
    )
    count = len(session.exec(stmt).all())
    return {"unread_count": count}


@router.get(
    "/{notification_id}",
    response_model=s.NotificationPublic,
    dependencies=[Depends(require_permission("notification", "view"))],
)
def get_notification(session: SessionDep, current_user: CurrentUser, notification_id: uuid.UUID) -> Any:
    db_obj = session.exec(
        select(m.Notification).where(
            m.Notification.id == notification_id,
            m.Notification.user_id == current_user.id,
            m.Notification.is_deleted == False,  # noqa: E712
        )
    ).first()
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return s.NotificationPublic.model_validate(db_obj)


@router.post(
    "/{notification_id}/read",
    response_model=s.NotificationPublic,
    dependencies=[Depends(require_permission("notification", "edit"))],
)
def mark_notification_read(session: SessionDep, notification_id: uuid.UUID, current_user: CurrentUser) -> Any:
    db_obj = session.exec(
        select(m.Notification).where(
            m.Notification.id == notification_id,
            m.Notification.user_id == current_user.id,
            m.Notification.is_deleted == False,  # noqa: E712
        )
    ).first()
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    from datetime import datetime, timezone
    db_obj.read_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return s.NotificationPublic.model_validate(db_obj)


@router.post(
    "/pre-payday-check",
    dependencies=[Depends(require_permission("notification", "add"))],
    status_code=202,
)
def run_pre_payday_check_route(session: SessionDep, days_before: int = 3) -> Any:
    """Run the pre-payday compliance sweep.

    Notifies *all* users holding payroll view permission (not just the caller)
    using the dedicated ``pre_payday_check`` notification type, and honours the
    ``days_before`` window.
    """
    from app.notification.services import run_pre_payday_check

    return run_pre_payday_check(session=session, days_before=days_before)
