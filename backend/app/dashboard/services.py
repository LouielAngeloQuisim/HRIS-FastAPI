"""Dashboard KPI computation.

Every count is filtered ``WHERE is_deleted = false``. The legacy dashboard
counted archived models and raw DTR log rows (double-counting multi-punch
employees); those bugs are not reproduced here (design §1.6 / Q10).
"""


from sqlmodel import Session, func, select

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

# Counted tables keyed by (model, label) for the shared counter helper.
_COUNTED = [
    (EmployeeRecords, "employee_records"),
    (Division, "divisions"),
    (Department, "departments"),
    (Project, "projects"),
    (Subdivision, "subdivisions"),
    (Owner, "owners"),
    (EmployeeProjects, "employee_projects"),
    (Model, "model_count"),
]


def _count_active(session: Session, model) -> int:
    statement = (
        select(func.count())
        .select_from(model)
        .where(model.is_deleted == False)  # noqa: E712
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
    return stats
