"""Dashboard KPI computation.

Every count is filtered ``WHERE is_deleted = false``. The legacy dashboard
counted archived models and raw DTR log rows (double-counting multi-punch
employees); those bugs are not reproduced here (design §1.6 / Q10).
"""


from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, func, select
from sqlmodel.sql.expression import SelectOfScalar

from app.attendance.adjustment_models import DtrAdjustment
from app.attendance.models import DailyTimeRecord
from app.common.types import AuditedSQLModel
from app.dashboard.schemas import DashboardStats
from app.employee.models import (
    Department,
    Division,
    EmployeeProjects,
    EmployeeRecords,
    Model,
    Owner,
    Project,
    Subdivision,
)
from app.leave.models import LeaveRequest
from app.payroll.models import PayrollEntry, PayrollRun

MANILA = ZoneInfo("Asia/Manila")

# Counted tables keyed by (model, label) for the shared counter helper.
_COUNTED: list[tuple[type[AuditedSQLModel], str]] = [
    (EmployeeRecords, "employee_records"),
    (Division, "divisions"),
    (Department, "departments"),
    (Project, "projects"),
    (Subdivision, "subdivisions"),
    (Owner, "owners"),
    (EmployeeProjects, "employee_projects"),
    (Model, "model_count"),
]


def _count_active(session: Session, model: type[AuditedSQLModel]) -> int:
    statement: SelectOfScalar[int] = (
        select(func.count())
        .select_from(model)
        .where(col(model.is_deleted) == False)  # noqa: E712
    )
    return session.exec(statement).one()


def manila_day_window(now: datetime) -> tuple[datetime, datetime]:
    """[start, end) UTC instants covering the Asia/Manila calendar day containing `now`.

    Pure and explicit so the midnight boundary is unit-testable without a
    clock: the legacy bug counted raw rows across a broken UTC/server-local
    boundary (design §1.6 / Q10), so the window is anchored to Manila
    midnight (UTC+08:00, no DST) and converted to UTC — never server-local.
    """
    local = now.astimezone(MANILA)
    start_local = datetime(local.year, local.month, local.day, tzinfo=MANILA)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def count_daily_attendance(session: Session, now: datetime) -> int:
    """Distinct employees with >=1 real punch (login) in the Manila day containing `now`.

    DISTINCT employee_id fixes the legacy double-count of multi-punch
    employees; only active rows count (deleted punches removed — QA-08),
    absence placeholders (no login) are excluded.
    """
    start, end = manila_day_window(now)
    statement: SelectOfScalar[int] = (
        select(func.count(func.distinct(DailyTimeRecord.employee_id)))
        .select_from(DailyTimeRecord)
        .where(
            col(DailyTimeRecord.is_deleted) == False,  # noqa: E712
            col(DailyTimeRecord.is_absent) == False,  # noqa: E712
            col(DailyTimeRecord.login_date).is_not(None),
            col(DailyTimeRecord.login_date) >= start,
            col(DailyTimeRecord.login_date) < end,
        )
    )
    return session.exec(statement).one()


def _dtr_records_daily_count(session: Session) -> int:
    """KPI: employees present today (Asia/Manila), counted server-side."""
    return count_daily_attendance(session, datetime.now(timezone.utc))


def build_dashboard_stats(*, session: Session) -> DashboardStats:
    stats = DashboardStats()
    for model, label in _COUNTED:
        setattr(stats, label, _count_active(session, model))
    stats.dtr_records_daily_count = _dtr_records_daily_count(session)
    stats.payroll_runs_count = _count_active(session, PayrollRun)
    stats.pending_leave_requests = session.exec(
        select(func.count()).select_from(LeaveRequest).where(
            LeaveRequest.is_deleted == False,  # noqa: E712
            LeaveRequest.status == "pending",
        )
    ).one()
    stats.pending_dtr_adjustments = session.exec(
        select(func.count()).select_from(DtrAdjustment).where(
            DtrAdjustment.is_deleted == False,  # noqa: E712
            # DTR adjustment statuses are UPPERCASE (PENDING/APPROVED/REJECTED)
            # in the backend state machine — unlike leave statuses, which are
            # lowercase. Comparing against "pending" always returned 0 (QA-03).
            DtrAdjustment.status == "PENDING",
        )
    ).one()

    payroll_totals = session.exec(
        select(
            func.coalesce(func.sum(PayrollEntry.gross_pay), 0),
            func.coalesce(func.sum(PayrollEntry.net_pay), 0),
        )
        .select_from(PayrollEntry)
        .where(PayrollEntry.is_deleted == False)  # noqa: E712
    ).one()
    stats.payroll_total_gross = float(payroll_totals[0])
    stats.payroll_total_net = float(payroll_totals[1])
    return stats
