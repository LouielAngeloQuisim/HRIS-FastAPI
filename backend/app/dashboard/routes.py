"""Dashboard KPI endpoint."""

from typing import Any

from fastapi import APIRouter, Depends

from app.common.dependencies import SessionDep
from app.dashboard.schemas import DashboardStats
from app.dashboard.services import build_dashboard_stats
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/",
    response_model=DashboardStats,
    dependencies=[Depends(require_permission("emp_list", "view"))],
)
def read_dashboard(session: SessionDep) -> Any:
    """Aggregate headcount / org / project KPIs.

    Gated by ``emp_list``/``view``: any authenticated user with basic
    employee-view access can read the dashboard, matching the legacy
    open-to-any-authenticated-user behaviour while staying behind auth + RBAC.
    """
    return build_dashboard_stats(session=session)
