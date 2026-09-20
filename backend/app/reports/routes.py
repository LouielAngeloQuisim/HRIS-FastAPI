"""Phase B5 — Reports module."""

import uuid
from datetime import date
from io import StringIO
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.common.dependencies import SessionDep
from app.leave.models import LeaveLedgerEntry, LeavePolicy
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv_response(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "no data"
    headers = list(rows[0].keys())
    buf = StringIO()
    buf.write(",".join(headers) + "\n")
    for row in rows:
        buf.write(",".join(str(row.get(h, "")) for h in headers) + "\n")
    return buf.getvalue()


@router.get(
    "/leave-balance",
    dependencies=[Depends(require_permission("report", "view"))],
)
def get_leave_balance_report(
    session: SessionDep,
    employee_id: uuid.UUID | None = None,
    policy_id: uuid.UUID | None = None,
    format: str = "json",
) -> Any:
    stmt = select(LeaveLedgerEntry, LeavePolicy).join(
        LeavePolicy, LeaveLedgerEntry.policy_id == LeavePolicy.id  # type: ignore[arg-type]
    )
    if employee_id is not None:
        stmt = stmt.where(LeaveLedgerEntry.employee_id == employee_id)
    if policy_id is not None:
        stmt = stmt.where(LeaveLedgerEntry.policy_id == policy_id)
    results = session.exec(stmt).all()
    rows = []
    for ledger, policy in results:
        rows.append({
            "employee_id": str(ledger.employee_id),
            "policy_code": policy.code,
            "policy_name": policy.name,
            "leave_year": ledger.leave_year,
            "source": ledger.source,
            "amount": float(ledger.amount),
            "note": ledger.note or "",
            "created_at": ledger.created_at.isoformat() if ledger.created_at else None,
        })
    if format == "csv":
        return {"csv": _csv_response(rows)}
    return {"data": rows, "count": len(rows)}


@router.get(
    "/attendance-summary",
    dependencies=[Depends(require_permission("report", "view"))],
)
def get_attendance_summary_report(
    session: SessionDep,
    employee_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    format: str = "json",
) -> Any:
    from app.attendance.models import DailyTimeRecord
    from app.employee.models import EmployeeRecords
    stmt = select(DailyTimeRecord, EmployeeRecords).join(
        EmployeeRecords, DailyTimeRecord.employee_id == EmployeeRecords.id  # type: ignore[arg-type]
    )
    if employee_id is not None:
        stmt = stmt.where(DailyTimeRecord.employee_id == employee_id)
    if date_from is not None:
        stmt = stmt.where(DailyTimeRecord.login_date >= date_from)  # type: ignore[operator]
    if date_to is not None:
        stmt = stmt.where(DailyTimeRecord.login_date <= date_to)  # type: ignore[operator]
    results = session.exec(stmt).all()
    rows = []
    for dtr, emp in results:
        rows.append({
            "employee_id": str(dtr.employee_id),
            "employee_code": emp.employee_code,
            "login_date": dtr.login_date.isoformat() if dtr.login_date else None,
            "rendered_minutes": dtr.rendered_minutes or 0,
            "late_minutes": dtr.late_minutes or 0,
            "undertime_minutes": dtr.undertime_minutes or 0,
            "overtime_minutes": dtr.overtime_minutes or 0,
            "overtime_approved": dtr.overtime_approved,
        })
    if format == "csv":
        return {"csv": _csv_response(rows)}
    return {"data": rows, "count": len(rows)}


@router.get(
    "/payroll-register",
    dependencies=[Depends(require_permission("report", "view"))],
)
def get_payroll_register_report(
    session: SessionDep,
    run_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    format: str = "json",
) -> Any:
    from app.payroll.models import PayrollEntry, PayrollRun
    stmt = select(PayrollEntry, PayrollRun).join(
        PayrollRun, PayrollEntry.payroll_run_id == PayrollRun.id  # type: ignore[arg-type]
    )
    if run_id is not None:
        stmt = stmt.where(PayrollEntry.payroll_run_id == run_id)
    if date_from is not None:
        stmt = stmt.where(PayrollRun.date_from >= date_from)
    if date_to is not None:
        stmt = stmt.where(PayrollRun.date_to <= date_to)
    results = session.exec(stmt).all()
    rows = []
    for entry, run in results:
        rows.append({
            "run_id": str(run.id),
            "run_cutoff_type": run.cutoff_type,
            "run_date_from": run.date_from.isoformat(),
            "run_date_to": run.date_to.isoformat(),
            "run_status": run.status,
            "employee_id": str(entry.employee_id),
            "basic_rate": float(entry.basic_rate),
            "gross_pay": float(entry.gross_pay),
            "total_deductions": float(entry.total_deductions),
            "net_pay": float(entry.net_pay),
            "overtime_pay": float(entry.overtime_pay),
            "thirteenth_month": float(entry.thirteenth_month),
            "non_taxable_income": float(entry.non_taxable_income),
            "taxable_income": float(entry.taxable_income),
        })
    if format == "csv":
        return {"csv": _csv_response(rows)}
    return {"data": rows, "count": len(rows)}


@router.get(
    "/headcount",
    dependencies=[Depends(require_permission("report", "view"))],
)
def get_headcount_report(
    session: SessionDep,
    division_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    format: str = "json",
) -> Any:
    from app.employee.models import EmployeeRecords, EmployeeStatus
    stmt = select(EmployeeRecords).where(
        EmployeeRecords.employee_status == EmployeeStatus.ACTIVE,
        EmployeeRecords.is_deleted == False,  # noqa: E712
    )
    if division_id is not None:
        stmt = stmt.where(EmployeeRecords.division_id == division_id)
    if department_id is not None:
        stmt = stmt.where(EmployeeRecords.department_id == department_id)
    employees = session.exec(stmt).all()
    rows = []
    for emp in employees:
        rows.append({
            "employee_id": str(emp.id),
            "employee_code": emp.employee_code,
            "first_name": emp.first_name,
            "last_name": emp.last_name,
            "division_id": str(emp.division_id) if emp.division_id else None,
            "department_id": str(emp.department_id) if emp.department_id else None,
            "position_id": str(emp.position_id) if emp.position_id else None,
            "employment_type": emp.employment_type,
            "date_hired": emp.date_hired.isoformat() if emp.date_hired else None,
        })
    if format == "csv":
        return {"csv": _csv_response(rows)}
    return {"data": rows, "count": len(rows)}


@router.get(
    "/payroll/summary",
    dependencies=[Depends(require_permission("report", "view"))],
)
def get_payroll_summary_report(
    session: SessionDep,
    run_id: uuid.UUID | None = None,
    format: str = "json",
) -> Any:
    from app.payroll.models import PayrollEntry, PayrollRun
    stmt = select(PayrollEntry, PayrollRun).join(
        PayrollRun, PayrollEntry.payroll_run_id == PayrollRun.id  # type: ignore[arg-type]
    )
    if run_id is not None:
        stmt = stmt.where(PayrollEntry.payroll_run_id == run_id)
    results = session.exec(stmt).all()
    rows = []
    totals = {
        "gross_pay": 0.0,
        "total_deductions": 0.0,
        "net_pay": 0.0,
        "overtime_pay": 0.0,
        "thirteenth_month": 0.0,
        "non_taxable_income": 0.0,
        "taxable_income": 0.0,
    }
    for entry, run in results:
        row = {
            "run_id": str(run.id),
            "run_cutoff_type": run.cutoff_type,
            "run_date_from": run.date_from.isoformat(),
            "run_date_to": run.date_to.isoformat(),
            "run_status": run.status,
            "employee_id": str(entry.employee_id),
            "basic_rate": float(entry.basic_rate),
            "gross_pay": float(entry.gross_pay),
            "total_deductions": float(entry.total_deductions),
            "net_pay": float(entry.net_pay),
            "overtime_pay": float(entry.overtime_pay),
            "thirteenth_month": float(entry.thirteenth_month),
            "non_taxable_income": float(entry.non_taxable_income),
            "taxable_income": float(entry.taxable_income),
        }
        rows.append(row)
        for key in totals:
            totals[key] = round(totals[key] + float(row[key]), 2)  # type: ignore[arg-type]
    if format == "csv":
        return {"csv": _csv_response(rows)}
    return {
        "data": rows,
        "count": len(rows),
        "run_id": str(run_id) if run_id is not None else None,
        "totals": totals,
    }
