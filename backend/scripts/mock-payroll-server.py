"""F7 mock payroll server for sandbox/CI gate execution."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel


class PayrollRun(BaseModel):
    id: str
    status: str
    cutoff_type: str
    period_start: str
    period_end: str


class DashboardStats(BaseModel):
    payroll_total_gross: float
    payroll_total_net: float
    employee_count: int


app = FastAPI(title="F7 Mock Payroll Server")


@app.get("/api/v1/payroll/runs", response_model=list[PayrollRun])
def list_payroll_runs() -> list[PayrollRun]:
    return [
        PayrollRun(
            id="MOCK-1",
            status="posted",
            cutoff_type="monthly",
            period_start="2026-08-01",
            period_end="2026-08-31",
        )
    ]


@app.get("/api/v1/dashboard/stats", response_model=DashboardStats)
def dashboard_stats() -> DashboardStats:
    return DashboardStats(
        payroll_total_gross=100_000.0,
        payroll_total_net=85_000.0,
        employee_count=42,
    )
