"""Services for payroll module business logic.

Core computation pipeline, preview/generation consistency guarantee, and rate-change logic.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.employee.models import EmployeeRecords
from app.payroll.calc import calculate_all_contributions
from app.payroll.models import PayrollRunStatus
from app.payroll.payroll_tables import (
    EmployeeSalary,
    Loan,
    LoanAmortization,
    PayrollEntry,
    PayrollRun,
)
from app.payroll.schemas import PayrollGenerateRequest, PayrollPreviewRequest
from app.payroll.selectors import (
    get_active_employee_salaries,
    select_active_loan_amortizations,
    select_employee_loans,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Core computation helpers
# --------------------------------------------------------------------------- #


def _get_effective_salary(session: Session, employee_id: uuid.UUID, as_of: date) -> EmployeeSalary | None:
    salaries = get_active_employee_salaries(session, employee_id)
    if not salaries:
        return None
    applicable = None
    for s in salaries:
        if s.effective_date <= as_of:
            applicable = s
    return applicable


def _pro_rate_basic_rate(basic_rate: Decimal, pay_type: str, days_in_period: int, days_worked: int) -> Decimal:
    if pay_type == "monthly":
        return (basic_rate / Decimal(days_in_period) * Decimal(days_worked)).quantize(Decimal("0.01"))
    if pay_type == "daily":
        return (basic_rate * Decimal(days_worked)).quantize(Decimal("0.01"))
    if pay_type == "hourly":
        # For hourly, days_worked here actually means hours worked
        return (basic_rate * Decimal(days_worked)).quantize(Decimal("0.01"))
    return basic_rate


def _compute_employee_entry(
    session: Session,
    employee_id: uuid.UUID,
    payroll_run: PayrollRun,
    review_overrides: Any | None = None,
) -> PayrollEntry:
    as_of = payroll_run.date_from
    salaries = get_active_employee_salaries(session, employee_id)
    if not salaries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Employee {employee_id} has no active salary record",
        )

    # Sort by effective_date for mid-period rate change handling
    salaries_sorted = sorted(salaries, key=lambda s: s.effective_date)
    primary_salary = next((s for s in salaries_sorted if s.effective_date <= as_of), salaries_sorted[0])

    # Determine days in period and worked days
    days_in_period = (payroll_run.date_to - payroll_run.date_from).days + 1

    # Attendance adjustments from DTR records
    overtime_pay = Decimal("0.00")
    attendance_deduction = Decimal("0.00")
    absence_days = 0

    try:
        from app.attendance.calc import compute_dtr, is_scheduled_workday, ShiftParams  # isort:skip
        from app.attendance.models import DailyTimeRecord  # isort:skip
        from app.attendance.selectors import get_list as get_attendance_list  # isort:skip

        default_shift = ShiftParams(
            start_minutes=480,
            end_minutes=1020,
            lunch_minutes=60,
            shift_minutes=480,
            grace_minutes=0,
            days_of_week=(1, 2, 3, 4, 5),
        )

        dtr_rows, _ = get_attendance_list(
            session=session,
            model=DailyTimeRecord,
            skip=0,
            limit=1000,
        )
        employee_dtrs = [
            dtr for dtr in dtr_rows
            if dtr.employee_id == employee_id and not dtr.is_deleted
        ]

        current_date = payroll_run.date_from
        while current_date <= payroll_run.date_to:
            if is_scheduled_workday(current_date, default_shift):
                day_dtrs = [
                    dtr for dtr in employee_dtrs
                    if dtr.login_date and dtr.login_date.date() == current_date
                ]
                if day_dtrs:
                    dtr = day_dtrs[0]
                    if dtr.login_date and dtr.logout_date:
                        result = compute_dtr(dtr.login_date, dtr.logout_date, default_shift)
                        if result.overtime_minutes > 0 and dtr.overtime_approved:
                            overtime_pay += (
                                Decimal(result.overtime_minutes) / Decimal(60) * primary_salary.overtime_rate
                            ).quantize(Decimal("0.01"))
                    elif dtr.is_absent:
                        absence_days += 1
            current_date += timedelta(days=1)

        if absence_days > 0:
            if primary_salary.pay_type.value == "monthly":
                daily_rate = primary_salary.basic_rate / Decimal(days_in_period)
            else:
                daily_rate = primary_salary.basic_rate
            attendance_deduction = (daily_rate * Decimal(absence_days)).quantize(Decimal("0.01"))

    except Exception:
        pass

    # Pro-rate basic pay, handling mid-period rate changes
    days_worked = days_in_period - absence_days
    if len(salaries_sorted) == 1 or all(s.effective_date == salaries_sorted[0].effective_date for s in salaries_sorted):
        basic_pay = _pro_rate_basic_rate(primary_salary.basic_rate, primary_salary.pay_type.value, days_in_period, days_worked)
    else:
        basic_pay = Decimal("0.00")
        current_date = payroll_run.date_from
        while current_date <= payroll_run.date_to:
            applicable = primary_salary
            for s in salaries_sorted:
                if s.effective_date <= current_date:
                    applicable = s
            if primary_salary.pay_type.value == "monthly":
                daily_rate = applicable.basic_rate / Decimal(days_in_period)
            else:
                daily_rate = applicable.basic_rate
            basic_pay += daily_rate
            current_date += timedelta(days=1)
        basic_pay = basic_pay.quantize(Decimal("0.01"))

    if review_overrides:
        if review_overrides.overtime_pay is not None:
            overtime_pay = review_overrides.overtime_pay
        if review_overrides.attendance_deduction_override is not None:
            attendance_deduction = review_overrides.attendance_deduction_override

    # Gross pay before contributions
    other_allowances = primary_salary.non_taxable_allowance
    if review_overrides and review_overrides.allowances is not None:
        other_allowances = review_overrides.allowances

    gross_pay = basic_pay + overtime_pay + other_allowances - attendance_deduction
    if gross_pay < 0:
        gross_pay = Decimal("0.00")

    # Government contributions
    contributions = calculate_all_contributions(session, gross_pay, str(payroll_run.cutoff_type))
    sss_employee = contributions["sss_employee"]
    philhealth_employee = contributions["philhealth_employee"]
    pagibig_employee = contributions["pagibig_employee"]
    taxable_income = contributions["taxable_income"]

    # BIR tax
    bir_tax = contributions["bir"]

    # Loan amortizations
    loan_amortization_total = Decimal("0.00")
    active_loans = select_employee_loans(session, employee_id)
    for loan in active_loans:
        if loan.balance > 0:
            amortizations = select_active_loan_amortizations(session, loan.id)
            for amort in amortizations:
                if amort.due_date <= payroll_run.date_to:
                    loan_amortization_total += amort.amount

    if review_overrides and review_overrides.loan_amortizations:
        for la in review_overrides.loan_amortizations:
            if la.amount:
                loan_amortization_total += la.amount

    # Non-taxable income
    non_taxable_income = primary_salary.non_taxable_allowance
    # 13th-month pay: basic_monthly / 12
    thirteenth_month = (primary_salary.basic_rate / Decimal("12.0")).quantize(Decimal("0.01"))
    if thirteenth_month > primary_salary.thirteenth_month_exempt_portion:
        thirteenth_month = primary_salary.thirteenth_month_exempt_portion
    if review_overrides and review_overrides.non_taxable_income is not None:
        non_taxable_income += review_overrides.non_taxable_income

    total_deductions = sss_employee + philhealth_employee + pagibig_employee + bir_tax + loan_amortization_total
    net_pay = taxable_income - bir_tax - loan_amortization_total
    if net_pay < 0:
        net_pay = Decimal("0.00")

    # Actual take-home includes non-taxable income added back
    take_home = net_pay + non_taxable_income

    # Determine rate window for audit
    if len(salaries_sorted) == 1 or all(s.effective_date == salaries_sorted[0].effective_date for s in salaries_sorted):
        rate_date_from = primary_salary.effective_date
        rate_date_to = primary_salary.effective_date
    else:
        rate_date_from = salaries_sorted[0].effective_date
        rate_date_to = salaries_sorted[-1].effective_date

    entry = PayrollEntry(
        payroll_run_id=payroll_run.id,
        employee_id=employee_id,
        basic_rate=basic_pay,
        rate_date_from=rate_date_from,
        rate_date_to=rate_date_to,
        earnings={
            "overtime_pay": str(overtime_pay),
            "other_allowances": str(other_allowances),
            "thirteenth_month": str(thirteenth_month),
        },
        deductions={
            "sss_employee": str(sss_employee),
            "philhealth_employee": str(philhealth_employee),
            "pagibig_employee": str(pagibig_employee),
            "bir": str(bir_tax),
            "loan_amortization": str(loan_amortization_total),
            "attendance_deduction": str(attendance_deduction),
        },
        gross_pay=gross_pay,
        total_deductions=total_deductions,
        net_pay=take_home,
        overtime_pay=overtime_pay,
        thirteenth_month=thirteenth_month,
        non_taxable_income=non_taxable_income,
        taxable_income=taxable_income,
    )
    return entry


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def preview_payroll(
    session: Session,
    request: PayrollPreviewRequest,
    _created_by_id: uuid.UUID | None = None,
) -> PayrollRun:
    """Preview payroll entries without persisting them.

    Computes exact entries for a payroll cutoff based on effective dates, government rates, and employee salary config.
    Returns PayrollRun with draft status (no DB persistence yet).
    """
    if request.cutoff_type not in ["daily", "weekly", "semi_monthly", "monthly"]:
        raise HTTPException(status_code=400, detail="Invalid cutoff_type")

    draft_run = PayrollRun(
        cutoff_type=request.cutoff_type,
        date_from=request.date_from,
        date_to=request.date_to,
        status=PayrollRunStatus.DRAFT,
        adjustment_type=request.adjustment_type,
        created_by=None,
    )
    session.add(draft_run)
    session.flush()

    # Select employees
    if request.department_id:
        stmt = (
            select(EmployeeSalary)
            .join(EmployeeRecords, EmployeeSalary.employee_id == EmployeeRecords.id)  # type: ignore[arg-type]
            .where(EmployeeRecords.department_id == request.department_id, EmployeeSalary.is_deleted.is_(False))  # type: ignore[attr-defined]
        )
    elif request.employee_ids:
        stmt = select(EmployeeSalary).where(EmployeeSalary.employee_id.in_(request.employee_ids), EmployeeSalary.is_deleted.is_(False))  # type: ignore[union-attr,attr-defined]
    else:
        stmt = select(EmployeeSalary).where(EmployeeSalary.is_deleted.is_(False))  # type: ignore[attr-defined]

    salaries = session.exec(stmt).all()

    # Deduplicate by employee_id: use the most recent effective salary for each employee
    seen_employees: set[uuid.UUID] = set()
    unique_salaries: list[EmployeeSalary] = []
    for salary in sorted(salaries, key=lambda s: s.effective_date, reverse=True):
        if salary.employee_id is not None and salary.employee_id not in seen_employees:
            seen_employees.add(salary.employee_id)
            unique_salaries.append(salary)

    override_map: dict[uuid.UUID, Any] = {}
    if request.entries:
        override_map = {ov.employee_id: ov for ov in request.entries}

    for salary in unique_salaries:
        if salary.employee_id is None:
            continue
        try:
            override = override_map.get(salary.employee_id)
            entry = _compute_employee_entry(session, salary.employee_id, draft_run, override)
            entry.payroll_run_id = draft_run.id
            session.add(entry)
        except HTTPException:
            raise

    if not unique_salaries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No employees with active salary records found for the given criteria",
        )

    session.commit()
    return draft_run


def generate_payroll(
    session: Session,
    request: PayrollGenerateRequest,
    created_by_id: uuid.UUID,
) -> PayrollRun:
    """Generate payroll run with persisted entries (status=draft)."""
    preview_run = preview_payroll(session, PayrollPreviewRequest(**request.model_dump()), created_by_id)

    preview_run.created_by = created_by_id
    session.add(preview_run)
    session.commit()
    session.refresh(preview_run)
    return preview_run


def create_or_complete_loan_amortization_schedule(
    session: Session, loan_id: uuid.UUID, start_date: str
) -> list[LoanAmortization]:
    """Create amortization schedule for a loan."""
    loan = session.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    monthly_payment = (loan.balance / Decimal(loan.terms_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amortizations: list[LoanAmortization] = []
    balance = loan.balance
    start = date.fromisoformat(start_date)

    for i in range(loan.terms_months):
        due = date(start.year, start.month, start.day) + timedelta(days=i * 30)
        amount = monthly_payment if balance > monthly_payment else balance
        amort = LoanAmortization(
            loan_id=loan_id,
            due_date=due,
            amount=amount,
            remaining_balance=balance - amount,
            is_paid=False,
        )
        amortizations.append(amort)
        balance -= amount
        if balance <= 0:
            break

    for amort in amortizations:
        session.add(amort)
    session.commit()
    return amortizations



