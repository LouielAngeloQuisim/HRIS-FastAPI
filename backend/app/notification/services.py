"""Phase B5 — notification service.

Provides the in-app notification writer plus optional email delivery, payroll
run event notifications, and the pre-payday compliance check.

Design constraints:
- No hardcoded recipients: every notification is addressed to a resolved
  ``user_id`` (or the set of users holding a given RBAC permission).
- Email is only attempted when ``settings.emails_enabled`` is true; otherwise
  the in-app notification is still written.
- Deep-links are placed in ``Notification.data["link"]`` for the frontend.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Any

from sqlmodel import Session, or_, select

from app.config.settings import settings
from app.notification import models as m
from app.rbac.models import Module, Role, RolePermission
from app.user.models import User

logger = logging.getLogger(__name__)


def create_notification(
    session: Session,
    *,
    user_id: uuid.UUID | None,
    type: m.NotificationType,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> m.Notification:
    """Persist a single in-app notification."""
    notification = m.Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        data=data,
    )
    session.add(notification)
    session.flush()
    return notification


def send_email_notification(
    *, email_to: str | None, subject: str, html_content: str
) -> bool:
    """Best-effort email delivery. Returns True when actually sent."""
    if not email_to or not settings.emails_enabled:
        return False
    try:
        from app.utils import send_email

        send_email(email_to=email_to, subject=subject, html_content=html_content)
        return True
    except Exception:  # pragma: no cover - email must never break a request
        logger.exception("Failed to send notification email to %s", email_to)
        return False


def _users_with_permission(session: Session, *, module_code: str, permission: str = "view") -> list[User]:
    """Resolve all active users with ``module_code`` + ``permission`` via RBAC.

    Superusers are always included — they bypass route RBAC and must not be
    silently excluded from operational notifications.
    """
    col = {
        "view": RolePermission.can_view,
        "add": RolePermission.can_add,
        "edit": RolePermission.can_edit,
        "delete": RolePermission.can_delete,
    }.get(permission)
    if col is None:
        return []

    role_users = session.exec(
        select(User)
        .join(Role, User.role_id == Role.id)  # type: ignore[arg-type]
        .join(RolePermission, RolePermission.role_id == Role.id)  # type: ignore[arg-type]
        .join(Module, Module.id == RolePermission.module_id)  # type: ignore[arg-type]
        .where(
            Module.code == module_code,
            col == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
        )
    ).all()
    supers = session.exec(
        select(User).where(
            User.is_superuser == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
        )
    ).all()

    seen: set[uuid.UUID] = set()
    recipients: list[User] = []
    for user in [*role_users, *supers]:
        if user.id not in seen:
            seen.add(user.id)
            recipients.append(user)
    return recipients


def notify_permission_holders(
    session: Session,
    *,
    module_code: str,
    type: m.NotificationType,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    email_html: str | None = None,
) -> list[m.Notification]:
    """Notify every active user holding ``module_code`` view permission."""
    recipients = _users_with_permission(session, module_code=module_code, permission="view")
    created: list[m.Notification] = []
    for user in recipients:
        created.append(
            create_notification(
                session,
                user_id=user.id,
                type=type,
                title=title,
                body=body,
                data=data,
            )
        )
        if email_html:
            send_email_notification(
                email_to=user.email,
                subject=title,
                html_content=email_html,
            )
    return created


# --- Payroll run events ----------------------------------------------------------


def _payroll_run_summary(session: Session, run: Any) -> dict[str, Any]:
    from sqlmodel import func

    from app.payroll.models import PayrollEntry

    stmt = select(
        func.count(),
        func.coalesce(func.sum(PayrollEntry.gross_pay), 0),
        func.coalesce(func.sum(PayrollEntry.net_pay), 0),
    ).where(
        PayrollEntry.payroll_run_id == run.id,
        PayrollEntry.is_deleted == False,  # noqa: E712
    )
    count, total_gross, total_net = session.exec(stmt).one()
    return {
        "employee_count": int(count or 0),
        "total_gross_pay": str(total_gross),
        "total_net_pay": str(total_net),
    }


def notify_payroll_run_event(session: Session, *, run: Any, event: str) -> list[m.Notification]:
    """Emit an in-app notification for a payroll run lifecycle event."""
    type_map = {
        "generated": m.NotificationType.PAYROLL_RUN_GENERATED,
        "approved": m.NotificationType.PAYROLL_RUN_APPROVED,
        "voided": m.NotificationType.PAYROLL_RUN_VOIDED,
    }
    notification_type = type_map.get(event)
    if notification_type is None:
        return []

    summary = _payroll_run_summary(session, run)
    title = f"Payroll run {event}: {run.date_from} to {run.date_to}"
    body = (
        f"Cutoff: {run.cutoff_type}. Employees: {summary['employee_count']}. "
        f"Total gross: PHP {summary['total_gross_pay']}. Total net: PHP {summary['total_net_pay']}."
    )
    data = {
        "run_id": str(run.id),
        "event": event,
        "date_from": run.date_from.isoformat(),
        "date_to": run.date_to.isoformat(),
        "status": str(run.status),
        "link": f"/payroll-runs/{run.id}",
        **summary,
    }
    created = notify_permission_holders(
        session,
        module_code="payroll",
        type=notification_type,
        title=title,
        body=body,
        data=data,
    )
    session.commit()
    return created


# --- Pre-payday compliance check --------------------------------------------------


def _day_bounds(date_from: date, date_to: date) -> tuple[Any, Any]:
    """Half-open UTC bounds so same-day punches on the final date are included."""
    from datetime import datetime, time, timezone

    start = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
    return start, end


def _pending_overtime_count(session: Session, employee_id: uuid.UUID, date_from: date, date_to: date) -> int:
    from sqlmodel import func

    from app.attendance.models import DailyTimeRecord

    start_dt, end_dt = _day_bounds(date_from, date_to)
    stmt = select(func.count()).where(
        DailyTimeRecord.employee_id == employee_id,
        DailyTimeRecord.login_date >= start_dt,
        DailyTimeRecord.login_date < end_dt,
        DailyTimeRecord.is_deleted == False,  # noqa: E712
        DailyTimeRecord.overtime_minutes > 0,  # type: ignore[operator]
        or_(
            DailyTimeRecord.overtime_approved == False,  # noqa: E712
            DailyTimeRecord.overtime_approved.is_(None),  # type: ignore[union-attr]
        ),
    )
    return int(session.exec(stmt).one() or 0)


def _missing_dtr_count(session: Session, employee_id: uuid.UUID, date_from: date, date_to: date) -> int:
    from sqlmodel import func

    from app.attendance.models import DailyTimeRecord

    start_dt, end_dt = _day_bounds(date_from, date_to)
    present = session.exec(
        select(func.count(func.distinct(DailyTimeRecord.login_date)))
        .where(
            DailyTimeRecord.employee_id == employee_id,
            DailyTimeRecord.login_date >= start_dt,
            DailyTimeRecord.login_date < end_dt,
            DailyTimeRecord.is_deleted == False,  # noqa: E712
        )
    ).one()
    scheduled = 0
    cur = date_from
    while cur <= date_to:
        if cur.isoweekday() <= 5:
            scheduled += 1
        cur += timedelta(days=1)
    return max(0, scheduled - int(present or 0))


def run_pre_payday_check(
    session: Session, *, days_before: int = 3, today: date | None = None
) -> dict[str, Any]:
    """Run the pre-payday compliance sweep and notify payroll viewers.

    A run is "upcoming" when it is a draft whose ``date_from`` falls within the
    next ``days_before`` days (inclusive of today). Previously the window was
    collapsed to a single day, so it never matched.
    """
    from app.attendance.adjustment_models import DtrAdjustment
    from app.employee.models import EmployeeRecords, EmployeeStatus
    from app.leave.models import LeaveRequest
    from app.payroll.models import EmployeeSalary, PayrollRun, PayrollRunStatus

    checked_date = today or date.today()
    window_start = checked_date
    window_end = checked_date + timedelta(days=max(0, days_before))

    upcoming_runs = list(
        session.exec(
            select(PayrollRun).where(
                PayrollRun.is_deleted == False,  # noqa: E712
                PayrollRun.status == PayrollRunStatus.DRAFT,
                PayrollRun.date_from >= window_start,
                PayrollRun.date_from <= window_end,
            )
        ).all()
    )

    active_employees = list(
        session.exec(
            select(EmployeeRecords).where(
                EmployeeRecords.employee_status == EmployeeStatus.ACTIVE,
                EmployeeRecords.is_deleted == False,  # noqa: E712
            )
        ).all()
    )

    flags: list[dict[str, Any]] = []
    for run in upcoming_runs:
        for emp in active_employees:
            has_salary = session.exec(
                select(EmployeeSalary).where(
                    EmployeeSalary.employee_id == emp.id,
                    EmployeeSalary.is_active == True,  # noqa: E712
                    EmployeeSalary.is_deleted == False,  # noqa: E712
                )
            ).first() is not None
            pending_leaves = len(
                session.exec(
                    select(LeaveRequest).where(
                        LeaveRequest.employee_id == emp.id,
                        LeaveRequest.is_deleted == False,  # noqa: E712
                        LeaveRequest.status == "pending",
                        LeaveRequest.date_start <= run.date_to,
                        LeaveRequest.date_end >= run.date_from,
                    )
                ).all()
            )
            pending_dtr = len(
                session.exec(
                    select(DtrAdjustment).where(
                        DtrAdjustment.employee_id == emp.id,
                        DtrAdjustment.is_deleted == False,  # noqa: E712
                        DtrAdjustment.status.in_(("PENDING", "pending")),  # type: ignore[attr-defined]
                    )
                ).all()
            )
            pending_ot = _pending_overtime_count(session, emp.id, run.date_from, run.date_to)
            missing_dtr = _missing_dtr_count(session, emp.id, run.date_from, run.date_to)

            if not has_salary or pending_leaves or pending_dtr or pending_ot or missing_dtr:
                flags.append(
                    {
                        "employee_id": str(emp.id),
                        "employee_code": emp.employee_code,
                        "employee_name": f"{emp.first_name} {emp.last_name}",
                        "run_id": str(run.id),
                        "missing_salary": not has_salary,
                        "pending_leaves": pending_leaves,
                        "pending_dtr_adjustments": pending_dtr,
                        "pending_overtime": pending_ot,
                        "missing_dtr_days": missing_dtr,
                        "link": f"/payroll-runs/{run.id}",
                    }
                )

    employee_count = len(active_employees)
    from sqlmodel import func

    estimated_total_payroll_cost = session.exec(
        select(func.coalesce(func.sum(EmployeeSalary.basic_rate), 0)).where(
            EmployeeSalary.employee_id.in_([e.id for e in active_employees]),  # type: ignore[union-attr]
            EmployeeSalary.is_active == True,  # noqa: E712
            EmployeeSalary.is_deleted == False,  # noqa: E712
        )
    ).one()
    estimated_total_payroll_cost = float(estimated_total_payroll_cost or 0)

    if upcoming_runs:
        title = f"Pre-payday check: {len(upcoming_runs)} upcoming payroll run(s)"
        body = f"{len(flags)} compliance flag(s) found for payroll periods starting {window_start} to {window_end}."
        notify_permission_holders(
            session,
            module_code="payroll",
            type=m.NotificationType.PRE_PAYDAY_CHECK,
            title=title,
            body=body,
            data={
                "days_before": days_before,
                "checked_date": checked_date.isoformat(),
                "employee_count": employee_count,
                "estimated_total_payroll_cost": estimated_total_payroll_cost,
                "flags": flags,
                "link": "/payroll",
            },
        )
        session.commit()

    return {
        "status": "completed" if upcoming_runs else "no_upcoming_runs",
        "checked_date": checked_date.isoformat(),
        "days_before": days_before,
        "upcoming_runs": len(upcoming_runs),
        "employee_count": employee_count,
        "estimated_total_payroll_cost": estimated_total_payroll_cost,
        "flags": flags,
    }
