"""Dashboard KPI response schemas.

Plain named-count object (no ResponseModel-vs-raw ambiguity). Field names are
the frontend contract and are fixed here.
"""

from sqlmodel import SQLModel


class DashboardStats(SQLModel):
    employee_records: int = 0
    divisions: int = 0
    departments: int = 0
    projects: int = 0
    subdivisions: int = 0
    owners: int = 0
    employee_projects: int = 0
    model_count: int = 0
    dtr_records_daily_count: int = 0
