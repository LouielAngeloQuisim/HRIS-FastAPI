"""Dashboard KPI computation.

Every count is filtered ``WHERE is_deleted = false``. The legacy dashboard
counted archived models and raw DTR log rows (double-counting multi-punch
employees); those bugs are not reproduced here (design §1.6 / Q10).
"""


from sqlmodel import Session, col, func, select
from sqlmodel.sql.expression import SelectOfScalar

from app.attendance.adjustment_models import DtrAdjustment
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


def _dtr_records_daily_count(session: Session) -> int:
    """Count distinct employees with >=1 worker log today.

    The worker_logs table is Phase 2 territory and does not exist yet, so this
    returns 0 with a clear note. When the table lands, compute DISTINCT
    employee_id over worker logs within the Asia/Manila day window
    (legacy counted raw log rows across a broken UTC/server-local boundary).
    """
    del session  # unused until Phase 2
    return 0


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
            DtrAdjustment.status == "pending",
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
