"""REST API routes for payroll module.

All payroll endpoints exposed under /api/v1/payroll/* pathway.
Includes government calculators, payroll run lifecycle, loan management, employee salary config, and integration platform.
"""

import calendar
import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from datetime import time as time_of_day
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.attendance.adjustment_models import DtrAdjustment
from app.attendance.models import DailyTimeRecord, EmployeeShiftAssignment, Shift
from app.common.dependencies import CurrentUser, SessionDep
from app.common.schemas import Message
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.leave.models import HolidayConfig, HolidayInstance, LeaveRequest
from app.payroll.annualized_tax import calculate_annualized_compensation_tax
from app.payroll.attendance_calculator import (
    AttendancePayDay,
    CalculationBlocker,
    calculate_attendance_earnings,
)
from app.payroll.calc import (
    StatutoryScheduleUnavailable,
    calculate_all_contributions,
    calculate_bir_tax,
    calculate_pagibig_employee_share,
    calculate_pagibig_employer_share,
    calculate_philhealth_employee_share,
    calculate_philhealth_employer_share,
    calculate_sss_employee_share,
    calculate_sss_employer_share,
)
from app.payroll.fact_tables import (
    BIRBracket,
    PagIBIGBracket,
    PhilHealthBracket,
    SSSBracket,
)
from app.payroll.models import (
    CutoffType,
    EmployeePayGroupAssignment,
    EmployeeSalaryBulkBatch,
    EmployeeTaxYearDeclaration,
    PayrollContributionLedger,
    PayrollDeliveryOutbox,
    PayrollEntry,
    PayrollPayGroup,
    PayrollPolicyVersion,
    PayrollRunStatus,
)
from app.payroll.payroll_tables import (
    EmployeeSalary,
    IntegrationConfig,
    IntegrationMapping,
    Loan,
    LoanAmortization,
    PayrollRun,
)
from app.payroll.schemas import (
    BIRBracketCreate,
    BIRBracketRead,
    EmployeePayGroupAssignmentCreate,
    EmployeePayGroupAssignmentPublic,
    EmployeePayGroupAssignmentUpdate,
    EmployeeSalaryBulkCommit,
    EmployeeSalaryBulkIssue,
    EmployeeSalaryBulkPreflight,
    EmployeeSalaryBulkRequest,
    EmployeeSalaryCreate,
    EmployeeSalaryRead,
    EmployeeSalaryUpdate,
    EmployeeTaxYearDeclarationPublic,
    EmployeeTaxYearDeclarationUpdate,
    FleetIntegrationConfigRead,
    FleetIntegrationMappingRead,
    IntegrationConfigCreate,
    IntegrationConfigUpdate,
    IntegrationMappingCreate,
    IntegrationMappingUpdate,
    LoanAmortizationRead,
    LoanCreate,
    LoanRead,
    PagIBIGBracketCreate,
    PagIBIGBracketRead,
    PayrollAttendanceCalculationEntry,
    PayrollAttendanceCalculationPreview,
    PayrollAttendancePrepareRequest,
    PayrollDeliveryAddressUpdate,
    PayrollDeliveryResendRequest,
    PayrollDeliveryStatusPublic,
    PayrollEntryRead,
    PayrollEntryReviewRequest,
    PayrollGenerateRequest,
    PayrollPayGroupCreate,
    PayrollPayGroupPublic,
    PayrollPayPeriodPublic,
    PayrollPayslipPublic,
    PayrollPolicyVersionCreate,
    PayrollPolicyVersionPublic,
    PayrollPreflightBlocker,
    PayrollPreflightEmployee,
    PayrollPreviewRequest,
    PayrollPreviewResponse,
    PayrollReviewActionResult,
    PayrollRunPreflight,
    PayrollRunRead,
    PayrollSalaryRosterItem,
    PayrollSalaryRosterList,
    PayrunStatusResponse,
    PhilHealthBracketCreate,
    PhilHealthBracketRead,
    SSSBracketCreate,
    SSSBracketRead,
)
from app.payroll.selectors import (
    get_payroll_run_status_counts,
)
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/payroll", tags=["payroll"])


def _payroll_review_counts(session: Session, run_id: uuid.UUID) -> tuple[int, int, int]:
    entries = session.exec(
        select(PayrollEntry).where(
            PayrollEntry.payroll_run_id == run_id,
            col(PayrollEntry.is_deleted).is_(False),
        )
    ).all()
    reviewed = sum(entry.review_state == "reviewed" for entry in entries)
    excluded = sum(entry.review_state == "excluded" for entry in entries)
    unresolved = len(entries) - reviewed - excluded
    return reviewed, excluded, unresolved


def _stage_monthly_contribution_ledger(
    *, session: Session, run: PayrollRun, entries: Sequence[PayrollEntry], actor_id: uuid.UUID
) -> None:
    """Stage the single monthly statutory collection in the final pay period.

    The caller commits this with payroll finalization. Amounts must already be
    present in the reviewed entry and in its frozen monthly contribution input;
    this function never calculates or guesses statutory values.
    """
    if run.date_from is None or run.date_to is None:
        raise HTTPException(status_code=409, detail="Payroll period dates are required")
    if (run.date_from.year, run.date_from.month) != (run.date_to.year, run.date_to.month):
        raise HTTPException(
            status_code=409,
            detail="Monthly statutory collection cannot span calendar months",
        )
    month_end = calendar.monthrange(run.date_to.year, run.date_to.month)[1]
    if run.date_to.day != month_end:
        for entry in entries:
            if entry.review_state == "excluded":
                continue
            for scheme in ("sss", "philhealth", "pagibig"):
                try:
                    amount = Decimal(str(entry.deductions.get(f"{scheme}_employee", "0")))
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Entry {entry.id} has an invalid {scheme} deduction line",
                    ) from exc
                if amount != 0:
                    raise HTTPException(
                        status_code=409,
                        detail=f"{scheme} may be collected only in the final payroll period of the month",
                    )
        return
    month = run.date_to.replace(day=1)
    schemes = ("sss", "philhealth", "pagibig")
    # Finalizing two different runs for the same employee/month at once must
    # serialize before either transaction checks the ledger. The unique index
    # remains the last line of defense for writers outside this workflow.
    for employee_id in sorted(
        {
            entry.employee_id
            for entry in entries
            if entry.review_state != "excluded" and entry.employee_id is not None
        },
        key=lambda value: value.hex,
    ):
        for scheme in schemes:
            lock_key = int.from_bytes(
                hashlib.sha256(
                    f"payroll-contribution:{employee_id}:{scheme}:{month.isoformat()}".encode()
                ).digest()[:8],
                "big",
                signed=True,
            )
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    for entry in entries:
        if entry.review_state == "excluded":
            continue
        monthly = entry.input_snapshot.get("monthly_contributions")
        if not isinstance(monthly, dict) or monthly.get("month") != month.strftime("%Y-%m"):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} lacks a reviewed monthly contribution snapshot",
            )
        amounts = monthly.get("schemes")
        if not isinstance(amounts, dict):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} has no monthly statutory scheme breakdown",
            )
        for scheme in schemes:
            values = amounts.get(scheme)
            if not isinstance(values, dict):
                raise HTTPException(
                    status_code=409,
                    detail=f"Entry {entry.id} is missing {scheme} monthly contribution data",
                )
            try:
                basis = Decimal(str(values["basis"]))
                employee_amount = Decimal(str(values["employee"]))
                employer_amount = Decimal(str(values["employer"]))
            except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"Entry {entry.id} has invalid {scheme} contribution amounts",
                ) from exc
            if (
                not all(value.is_finite() for value in (basis, employee_amount, employer_amount))
                or basis <= 0
                or employee_amount < 0
                or employer_amount < 0
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Entry {entry.id} has invalid {scheme} contribution inputs",
                )
            deduction_key = f"{scheme}_employee"
            try:
                reviewed_employee_amount = Decimal(str(entry.deductions[deduction_key]))
            except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"Entry {entry.id} is missing its reviewed {scheme} deduction line",
                ) from exc
            if reviewed_employee_amount != employee_amount:
                raise HTTPException(
                    status_code=409,
                    detail=f"Entry {entry.id} {scheme} deduction differs from the monthly snapshot",
                )
            source_references = values.get("source_references")
            official_domain = {
                "sss": "sss.gov.ph",
                "philhealth": "philhealth.gov.ph",
                "pagibig": "pagibigfund.gov.ph",
            }[scheme]
            if (
                not isinstance(source_references, list)
                or not source_references
                or any(
                    not isinstance(url, str)
                    or not url.startswith("https://")
                    or not (
                        (hostname := (urlparse(url).hostname or "")) == official_domain
                        or hostname.endswith(f".{official_domain}")
                    )
                    for url in source_references
                )
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Entry {entry.id} has no reviewed source reference for {scheme}",
                )
            prior = session.exec(
                select(PayrollContributionLedger.id).where(
                    PayrollContributionLedger.employee_id == entry.employee_id,
                    PayrollContributionLedger.scheme == scheme,
                    PayrollContributionLedger.contribution_month == month,
                    PayrollContributionLedger.sequence == 0,
                )
            ).first()
            if prior is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Employee {entry.employee_id} already has a {scheme} collection for {month:%Y-%m}",
                )
            session.add(
                PayrollContributionLedger(
                    employee_id=entry.employee_id,
                    payroll_entry_id=entry.id,
                    scheme=scheme,
                    contribution_month=month,
                    monthly_basis=basis,
                    employee_amount=employee_amount,
                    employer_amount=employer_amount,
                    calculation_snapshot={"month": monthly["month"], "values": values},
                    source_references=source_references,
                    created_by=actor_id,
                )
            )


def _monthly_contribution_snapshot(
    *,
    session: Session,
    sss_monthly_compensation: Decimal,
    philhealth_basic_salary: Decimal,
    pagibig_monthly_salary: Decimal,
    contribution_month: date,
    source_urls: Sequence[str],
) -> dict[str, Any]:
    """Calculate the three monthly contribution shares from active schedules."""
    effective_date = contribution_month.replace(day=calendar.monthrange(
        contribution_month.year, contribution_month.month
    )[1])
    sss_employee = calculate_sss_employee_share(
        session, sss_monthly_compensation, effective_date.isoformat()
    )
    sss_employer = calculate_sss_employer_share(
        session, sss_monthly_compensation, effective_date.isoformat()
    )
    philhealth_employee = calculate_philhealth_employee_share(
        session, philhealth_basic_salary, effective_date.isoformat()
    )
    philhealth_employer = calculate_philhealth_employer_share(
        session, philhealth_basic_salary, effective_date.isoformat()
    )
    pagibig_employee = calculate_pagibig_employee_share(
        session, pagibig_monthly_salary, effective_date.isoformat()
    )
    pagibig_employer = calculate_pagibig_employer_share(
        session, pagibig_monthly_salary, effective_date.isoformat()
    )

    def sources(model: type[Any]) -> list[dict[str, str]]:
        rows = session.exec(
            select(model)
            .where(
                model.effective_date <= effective_date,
                col(model.is_active).is_(True),
                col(model.is_deleted).is_(False),
            )
            .order_by(col(model.effective_date).desc())
        ).all()
        if not rows:
            return []
        latest = rows[0].effective_date
        return [
            {"id": str(row.id), "effective_date": row.effective_date.isoformat()}
            for row in rows
            if row.effective_date == latest
        ]

    scheme_models = {
        "sss": SSSBracket,
        "philhealth": PhilHealthBracket,
        "pagibig": PagIBIGBracket,
    }



    schedule_rows = {scheme: sources(model) for scheme, model in scheme_models.items()}
    if any(not rows for rows in schedule_rows.values()):
        raise StatutoryScheduleUnavailable(
            "One or more monthly contribution schedules are unavailable"
        )
    scheme_sources = {
        "sss": "sss.gov.ph",
        "philhealth": "philhealth.gov.ph",
        "pagibig": "pagibigfund.gov.ph",
    }
    official_sources = {
        scheme: [
            url
            for url in source_urls
            if isinstance(url, str)
            if (hostname := (urlparse(url).hostname or "")) == domain
            or hostname.endswith(f".{domain}")
        ]
        for scheme, domain in scheme_sources.items()
    }
    if any(not urls for urls in official_sources.values()):
        raise StatutoryScheduleUnavailable(
            "Confirmed payroll policy is missing an official source for a contribution schedule"
        )
    amount_lines = {
        "sss": (sss_monthly_compensation, sss_employee, sss_employer),
        "philhealth": (philhealth_basic_salary, philhealth_employee, philhealth_employer),
        "pagibig": (pagibig_monthly_salary, pagibig_employee, pagibig_employer),
    }
    return {
        "month": contribution_month.strftime("%Y-%m"),
        "schemes": {
            scheme: {
                "basis": str(basis),
                "employee": str(employee),
                "employer": str(employer),
                "source_references": official_sources[scheme],
                "schedule_rows": schedule_rows[scheme],
            }
            for scheme, (basis, employee, employer) in amount_lines.items()
        },
    }


def _philhealth_monthly_basic_salary_basis(
    *,
    session: Session,
    employee_id: uuid.UUID,
    salaries: Sequence[EmployeeSalary],
    contribution_month: date,
    monthly_divisor: Decimal,
) -> Decimal:
    """Return the contract basic-salary monthly equivalent, independent of attendance.

    PhilHealth's published MBS definition excludes overtime and deductions for
    absences/undertime. For daily/hourly rates this uses the explicitly confirmed
    company monthly divisor and effective shift schedule, not actual worked days.
    A missing effective salary or shift is a blocker rather than a guessed rate.
    """
    days_in_month = calendar.monthrange(
        contribution_month.year, contribution_month.month
    )[1]
    month_end = contribution_month.replace(day=days_in_month)
    assignments = session.exec(
        select(EmployeeShiftAssignment).where(
            EmployeeShiftAssignment.employee_id == employee_id,
            EmployeeShiftAssignment.effective_from <= month_end,
            (col(EmployeeShiftAssignment.effective_to).is_(None))
            | (col(EmployeeShiftAssignment.effective_to) >= contribution_month),
            col(EmployeeShiftAssignment.is_deleted).is_(False),
        )
    ).all()
    shift_ids = {assignment.shift_id for assignment in assignments}
    shifts = (
        {
            shift.id: shift
            for shift in session.exec(
                select(Shift).where(
                    col(Shift.id).in_(shift_ids), col(Shift.is_deleted).is_(False)
                )
            ).all()
        }
        if shift_ids
        else {}
    )
    effective_salaries = [
        salary for salary in salaries if salary.effective_date <= month_end
    ]
    if not effective_salaries:
        raise StatutoryScheduleUnavailable(
            "An effective salary is required for the contribution month"
        )

    if effective_salaries[0].effective_date > contribution_month:
        raise StatutoryScheduleUnavailable(
            "An effective salary is required from the first day of the contribution month"
        )

    monthly_weighted = Decimal("0")
    for index, salary in enumerate(effective_salaries):
        segment_start = max(contribution_month, salary.effective_date)
        next_salary_date = (
            effective_salaries[index + 1].effective_date
            if index + 1 < len(effective_salaries)
            else month_end + timedelta(days=1)
        )
        segment_end = min(month_end, next_salary_date - timedelta(days=1))
        if segment_start > segment_end:
            continue
        segment_days = (segment_end - segment_start).days + 1
        pay_type = str(getattr(salary.pay_type, "value", salary.pay_type))
        if pay_type == "monthly":
            equivalent = salary.basic_rate
        elif pay_type in {"daily", "hourly"}:
            scheduled_minutes: list[Decimal] = []
            cursor = segment_start
            while cursor <= segment_end:
                assignment = next(
                    (
                        row for row in assignments
                        if row.effective_from <= cursor
                        and (row.effective_to is None or row.effective_to >= cursor)
                    ),
                    None,
                )
                shift = shifts.get(assignment.shift_id) if assignment else None
                if shift is None:
                    raise StatutoryScheduleUnavailable(
                        f"An effective shift is required to convert the {pay_type} PhilHealth basic salary on {cursor.isoformat()}"
                    )
                if cursor.isoweekday() in {int(value) for value in shift.days_of_week}:
                    scheduled_minutes.append(Decimal(str(shift.total_hours_minus_lunch)))
                cursor += timedelta(days=1)
            if not scheduled_minutes:
                raise StatutoryScheduleUnavailable(
                    f"No scheduled workdays are available to convert the {pay_type} PhilHealth basic salary from {segment_start.isoformat()}"
                )
            average_minutes = sum(scheduled_minutes, Decimal("0")) / Decimal(
                len(scheduled_minutes)
            )
            daily_equivalent = salary.basic_rate
            if pay_type == "hourly":
                daily_equivalent = salary.basic_rate * average_minutes / Decimal(60)
            equivalent = daily_equivalent * monthly_divisor
        else:
            raise StatutoryScheduleUnavailable(
                f"Unsupported salary basis {pay_type!r} for PhilHealth monthly conversion"
            )
        monthly_weighted += equivalent * Decimal(segment_days) / Decimal(days_in_month)
    return monthly_weighted.quantize(Decimal("0.01"))


def _same_calendar_day(value: date | datetime | str, expected: date) -> bool:
    """Compare date-shaped values consistently across SQLModel serialization."""
    if isinstance(value, str):
        normalized = date.fromisoformat(value[:10])
    else:
        normalized = value.date() if isinstance(value, datetime) else value
    return normalized == expected


def _latest_effective_rows(
    session: Session, model: Any, as_of: date, *, period: str | None = None
) -> list[Any]:
    stmt = select(model).where(
        col(model.effective_date) <= as_of,
        col(model.is_deleted).is_(False),
        col(model.is_active).is_(True),
    )
    if period is not None:
        stmt = stmt.where(model.period == period)
    rows = session.exec(stmt.order_by(col(model.effective_date).desc())).all()
    if not rows:
        return []
    latest_date = rows[0].effective_date
    return [row for row in rows if row.effective_date == latest_date]


def _range_schedule_errors(
    rows: Sequence[Any],
    *,
    minimum_field: str,
    maximum_field: str,
    label: str,
    open_ended_top: bool,
) -> list[str]:
    if not rows:
        return [f"{label} has no active effective schedule"]
    try:
        ordered = sorted(
            rows, key=lambda row: Decimal(str(getattr(row, minimum_field)))
        )
    except (InvalidOperation, TypeError, ValueError):
        return [f"{label} contains a missing or invalid lower bound"]
    errors: list[str] = []
    previous_maximum: Decimal | None = None
    for row in ordered:
        minimum = Decimal(str(getattr(row, minimum_field)))
        maximum_value = getattr(row, maximum_field)
        if minimum_field == "compensation_min" and getattr(row, "monthly_salary_credit", None) is None:
            errors.append(f"{label} contains a row without a monthly salary credit")
        maximum = Decimal(str(maximum_value)) if maximum_value is not None else None
        if not minimum.is_finite() or (maximum is not None and not maximum.is_finite()):
            errors.append(f"{label} contains a non-finite range")
            continue
        if maximum is not None and maximum < minimum:
            errors.append(f"{label} contains a range whose maximum is below its minimum")
        if previous_maximum is None:
            if minimum > Decimal("0.01"):
                errors.append(f"{label} does not cover its lower income range")
        elif minimum <= previous_maximum:
            errors.append(f"{label} contains overlapping income ranges")
        elif minimum != previous_maximum + Decimal("0.01"):
            errors.append(f"{label} contains a gap between income ranges")
        if maximum is None and row is not ordered[-1]:
            errors.append(f"{label} has an open-ended range before its final band")
        previous_maximum = maximum
    if open_ended_top and getattr(ordered[-1], maximum_field) is not None:
        errors.append(f"{label} has no open-ended top band")
    if not open_ended_top and getattr(ordered[-1], maximum_field) is None:
        errors.append(f"{label} unexpectedly has an open-ended top band")
    return errors


def _statutory_schedule_errors(session: Session, as_of: date) -> list[str]:
    """Require complete, non-overlapping effective tables before policy sign-off."""
    errors: list[str] = []
    sss_rows = _latest_effective_rows(session, SSSBracket, as_of)
    errors.extend(
        _range_schedule_errors(
            sss_rows,
            minimum_field="compensation_min",
            maximum_field="compensation_max",
            label="SSS compensation schedule",
            open_ended_top=True,
        )
    )
    for row in sss_rows:
        if row.monthly_salary_credit is None or row.monthly_salary_credit <= 0:
            errors.append("SSS schedule contains a row without a positive monthly salary credit")
            break
    philhealth_rows = _latest_effective_rows(session, PhilHealthBracket, as_of)
    if len(philhealth_rows) != 1:
        errors.append("PhilHealth requires exactly one active floor/ceiling schedule row")
    elif (
        philhealth_rows[0].salary_min <= 0
        or philhealth_rows[0].salary_max < philhealth_rows[0].salary_min
        or philhealth_rows[0].rate <= 0
    ):
        errors.append("PhilHealth floor, ceiling and rate must be valid positive values")
    pagibig_rows = _latest_effective_rows(session, PagIBIGBracket, as_of)
    errors.extend(
        _range_schedule_errors(
            pagibig_rows,
            minimum_field="salary_min",
            maximum_field="salary_max",
            label="Pag-IBIG schedule",
            open_ended_top=False,
        )
    )
    for period in ("daily", "weekly", "semi_monthly", "monthly"):
        bir_rows = _latest_effective_rows(session, BIRBracket, as_of, period=period)
        errors.extend(
            _range_schedule_errors(
                bir_rows,
                minimum_field="bracket_min",
                maximum_field="bracket_max",
                label=f"BIR {period} tax table",
                open_ended_top=True,
            )
        )
    return errors


def _bir_finalized_history(
    session: Session,
    employee_id: uuid.UUID,
    tax_year: int,
    after: date,
    before: date,
    coverage_start: date,
) -> tuple[list[dict[str, str]], Decimal, Decimal, bool]:
    """Return finalized BIR inputs and prove continuous payroll-period coverage."""
    rows = session.exec(
        select(PayrollEntry, PayrollRun)
        .join(PayrollRun, col(PayrollRun.id) == col(PayrollEntry.payroll_run_id))
        .where(
            PayrollEntry.employee_id == employee_id,
            col(PayrollEntry.review_state).in_(["reviewed", "excluded"]),
            col(PayrollEntry.is_deleted).is_(False),
            PayrollRun.workflow_status == "finalized",
            col(PayrollRun.status).in_([PayrollRunStatus.APPROVED, PayrollRunStatus.PAID]),
            col(PayrollRun.is_deleted).is_(False),
            PayrollRun.date_from > after,
            PayrollRun.date_from >= date(tax_year, 1, 1),
            PayrollRun.date_to < before,
        )
        .order_by(col(PayrollRun.date_from), col(PayrollRun.date_to), col(PayrollEntry.id))
    ).all()
    history: list[dict[str, str]] = []
    taxable_total = Decimal("0.00")
    withheld_total = Decimal("0.00")
    complete = True
    coverage_cursor = coverage_start
    for entry, run in rows:
        coverage_from = max(run.date_from, coverage_start)
        coverage_to = min(run.date_to, before - timedelta(days=1))
        if coverage_from <= coverage_to:
            if coverage_from > coverage_cursor:
                complete = False
            if coverage_to >= coverage_cursor:
                coverage_cursor = coverage_to + timedelta(days=1)
        if entry.review_state == "excluded":
            history.append(
                {
                    "entry_id": str(entry.id),
                    "run_id": str(run.id),
                    "date_from": run.date_from.isoformat(),
                    "date_to": run.date_to.isoformat(),
                    "excluded": "true",
                    "taxable_compensation": "0.00",
                    "tax_withheld": "0.00",
                }
            )
            continue
        calculation = entry.input_snapshot.get("bir_calculation")
        withheld_value = entry.deductions.get("bir_withholding")
        if not isinstance(calculation, dict) or withheld_value is None:
            complete = False
            history.append(
                {
                    "entry_id": str(entry.id),
                    "run_id": str(run.id),
                    "date_from": run.date_from.isoformat(),
                    "date_to": run.date_to.isoformat(),
                    "unavailable": "true",
                }
            )
            continue
        try:
            taxable = Decimal(str(calculation["taxable_compensation"]))
            withheld = Decimal(str(withheld_value))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            complete = False
            history.append(
                {
                    "entry_id": str(entry.id),
                    "run_id": str(run.id),
                    "date_from": run.date_from.isoformat(),
                    "date_to": run.date_to.isoformat(),
                    "unavailable": "true",
                }
            )
            continue
        if not taxable.is_finite() or not withheld.is_finite() or taxable < 0:
            complete = False
            history.append(
                {
                    "entry_id": str(entry.id),
                    "run_id": str(run.id),
                    "date_from": run.date_from.isoformat(),
                    "date_to": run.date_to.isoformat(),
                    "unavailable": "true",
                }
            )
            continue
        taxable_total += taxable
        withheld_total += withheld
        history.append(
            {
                "entry_id": str(entry.id),
                "run_id": str(run.id),
                "date_from": run.date_from.isoformat(),
                "date_to": run.date_to.isoformat(),
                "taxable_compensation": str(taxable),
                "tax_withheld": str(withheld),
            }
        )
    if coverage_cursor < before:
        complete = False
    return history, taxable_total, withheld_total, complete


def _payroll_entry_inputs_are_current(session: Session, entry: PayrollEntry) -> bool:
    snapshot = entry.input_snapshot
    try:
        calculated_fingerprint = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if calculated_fingerprint != entry.input_fingerprint:
            return False
        period = snapshot["period"]
        period_from = date.fromisoformat(str(period["from"]))
        period_to = date.fromisoformat(str(period["to"]))
        if entry.employee_id is None:
            return False
        employee_id = entry.employee_id

        tax_declaration = session.exec(
            select(EmployeeTaxYearDeclaration).where(
                EmployeeTaxYearDeclaration.employee_id == employee_id,
                EmployeeTaxYearDeclaration.tax_year == period_to.year,
            )
        ).first()
        tax_reference = snapshot.get("tax_year_declaration")
        if (tax_declaration is None) != (tax_reference is None):
            return False
        if tax_declaration is not None and tax_reference is not None:
            if (
                str(tax_declaration.id) != tax_reference.get("id")
                or (tax_declaration.updated_at.isoformat() if tax_declaration.updated_at else None)
                != tax_reference.get("updated_at")
                or tax_declaration.is_verified != tax_reference.get("verified")
            ):
                return False

        if "bir_schedule" in snapshot:
            expected_bir_period = CutoffType(
                str(snapshot.get("pay_group_cadence", "monthly"))
            )
            current_bir_rows = session.exec(
                select(BIRBracket).where(
                    BIRBracket.period == expected_bir_period,
                    BIRBracket.effective_date <= period_to,
                    col(BIRBracket.is_active).is_(True),
                    col(BIRBracket.is_deleted).is_(False),
                )
                .order_by(col(BIRBracket.bracket_min))
            ).all()
            if current_bir_rows:
                latest_bir_date = max(row.effective_date for row in current_bir_rows)
                current_bir_snapshot = [
                    {
                        "id": str(row.id),
                        "effective_date": row.effective_date.isoformat(),
                        "bracket_min": str(row.bracket_min),
                        "bracket_max": str(row.bracket_max) if row.bracket_max is not None else None,
                        "base_tax": str(row.base_tax),
                        "excess_rate": str(row.excess_rate),
                        "source_reference": row.source_reference,
                    }
                    for row in current_bir_rows
                    if row.effective_date == latest_bir_date
                ]
            else:
                current_bir_snapshot = []
            if current_bir_snapshot != snapshot.get("bir_schedule", []):
                return False

        if "bir_year_to_date_history" in snapshot:
            history_config = snapshot["bir_year_to_date_history"]
            opening_as_of = date.fromisoformat(str(history_config["opening_as_of"]))
            coverage_start = date.fromisoformat(str(history_config["coverage_start"]))
            current_history, _, _, current_history_complete = _bir_finalized_history(
                session,
                employee_id,
                period_to.year,
                opening_as_of,
                period_from,
                coverage_start,
            )
            recorded_history = history_config.get("finalized_entries", [])
            if (
                current_history != recorded_history
                or current_history_complete
                != history_config.get("complete")
            ):
                return False

        # Compare full scoped identity sets as well as row revisions. This
        # detects newly inserted records that a row-by-row snapshot check alone
        # would miss (for example, a late DTR import or new salary effective in
        # the frozen period).
        salary_ids = set(
            session.exec(
                select(EmployeeSalary.id).where(
                    EmployeeSalary.employee_id == employee_id,
                    EmployeeSalary.effective_date <= period_to,
                    col(EmployeeSalary.is_active).is_(True),
                    col(EmployeeSalary.is_deleted).is_(False),
                )
            ).all()
        )
        if salary_ids != {
            uuid.UUID(str(row["id"])) for row in snapshot["salary_versions"]
        }:
            return False
        attendance_ids = set(
            session.exec(
                select(DailyTimeRecord.id).where(
                    DailyTimeRecord.employee_id == employee_id,
                    col(DailyTimeRecord.work_date).is_not(None),
                    DailyTimeRecord.work_date >= period_from,  # type: ignore[operator]
                    DailyTimeRecord.work_date <= period_to,  # type: ignore[operator]
                    col(DailyTimeRecord.is_deleted).is_(False),
                )
            ).all()
        )
        if attendance_ids != {
            uuid.UUID(str(row["id"])) for row in snapshot["attendance_revisions"]
        }:
            return False
        shift_assignment_ids = set(
            session.exec(
                select(EmployeeShiftAssignment.id).where(
                    EmployeeShiftAssignment.employee_id == employee_id,
                    EmployeeShiftAssignment.effective_from <= period_to,
                    (col(EmployeeShiftAssignment.effective_to).is_(None))
                    | (col(EmployeeShiftAssignment.effective_to) >= period_from),
                    col(EmployeeShiftAssignment.is_deleted).is_(False),
                )
            ).all()
        )
        if shift_assignment_ids != {
            uuid.UUID(str(row["id"])) for row in snapshot["shift_assignments"]
        }:
            return False
        pay_group_assignment_ids = set(
            session.exec(
                select(EmployeePayGroupAssignment.id).where(
                    EmployeePayGroupAssignment.employee_id == employee_id,
                    EmployeePayGroupAssignment.effective_from <= period_to,
                    (col(EmployeePayGroupAssignment.effective_to).is_(None))
                    | (col(EmployeePayGroupAssignment.effective_to) >= period_from),
                )
            ).all()
        )
        if pay_group_assignment_ids != {
            uuid.UUID(str(row["id"])) for row in snapshot["pay_group_assignments"]
        }:
            return False
        leave_ids = set(
            session.exec(
                select(LeaveRequest.id).where(
                    LeaveRequest.employee_id == employee_id,
                    LeaveRequest.date_start <= period_to,
                    LeaveRequest.date_end >= period_from,
                    col(LeaveRequest.is_deleted).is_(False),
                )
            ).all()
        )
        if leave_ids != {
            uuid.UUID(str(row["id"])) for row in snapshot["leave_revisions"]
        }:
            return False
        holiday_ids = set(
            session.exec(
                select(HolidayInstance.id).where(
                    HolidayInstance.observed_date >= period_from,
                    HolidayInstance.observed_date <= period_to,
                    col(HolidayInstance.is_active).is_(True),
                    col(HolidayInstance.is_deleted).is_(False),
                )
            ).all()
        )
        if holiday_ids != {
            uuid.UUID(str(row["id"])) for row in snapshot["holiday_revisions"]
        }:
            return False
        policy_versions = set(
            session.exec(
                select(PayrollPolicyVersion.id).where(
                    PayrollPolicyVersion.effective_from <= period_to,
                    (col(PayrollPolicyVersion.effective_to).is_(None))
                    | (col(PayrollPolicyVersion.effective_to) >= period_from),
                )
            ).all()
        )
        if policy_versions != {
            uuid.UUID(str(row["id"])) for row in snapshot["policy_versions"]
        }:
            return False
        for reference in snapshot.get("attendance_revisions", []):
            dtr = session.get(DailyTimeRecord, uuid.UUID(str(reference["id"])))
            if (
                dtr is None
                or dtr.is_deleted
                or dtr.interval_revision != reference["interval_revision"]
            ):
                return False
            if (dtr.updated_at.isoformat() if dtr.updated_at else None) != reference[
                "updated_at"
            ]:
                return False
            if (
                dtr.overtime_decided_at.isoformat() if dtr.overtime_decided_at else None
            ) != reference.get("overtime_decided_at"):
                return False
        for reference in snapshot.get("salary_versions", []):
            salary = session.get(EmployeeSalary, uuid.UUID(str(reference["id"])))
            if salary is None or salary.is_deleted or not salary.is_active:
                return False
            if (
                salary.updated_at.isoformat() if salary.updated_at else None
            ) != reference["updated_at"] or str(salary.basic_rate) != reference[
                "basic_rate"
            ]:
                return False
        for reference in snapshot.get("shift_assignments", []):
            assignment = session.get(
                EmployeeShiftAssignment, uuid.UUID(str(reference["id"]))
            )
            if assignment is None or assignment.is_deleted:
                return False
            if (
                assignment.updated_at.isoformat() if assignment.updated_at else None
            ) != reference["updated_at"] or str(assignment.shift_id) != reference[
                "shift_id"
            ]:
                return False
        for reference in snapshot.get("pay_group_assignments", []):
            pay_group_assignment = session.get(
                EmployeePayGroupAssignment, uuid.UUID(str(reference["id"]))
            )
            if pay_group_assignment is None:
                return False
            if (
                pay_group_assignment.updated_at.isoformat()
                if pay_group_assignment.updated_at
                else None
            ) != reference["updated_at"]:
                return False
            if str(pay_group_assignment.pay_group_id) != reference["pay_group_id"]:
                return False
        for reference in snapshot.get("leave_revisions", []):
            leave = session.get(LeaveRequest, uuid.UUID(str(reference["id"])))
            if leave is None or leave.is_deleted:
                return False
            if str(getattr(leave.status, "value", leave.status)) != reference["status"]:
                return False
            if (
                leave.updated_at.isoformat() if leave.updated_at else None
            ) != reference["updated_at"]:
                return False
        for reference in snapshot.get("holiday_revisions", []):
            holiday = session.get(HolidayInstance, uuid.UUID(str(reference["id"])))
            if holiday is None or holiday.is_deleted or not holiday.is_active:
                return False
            if (
                holiday.updated_at.isoformat() if holiday.updated_at else None
            ) != reference["updated_at"]:
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


@router.post(
    "/runs/{run_id}/start-review",
    response_model=PayrollReviewActionResult,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def start_payroll_review(
    *, session: SessionDep, run_id: uuid.UUID
) -> PayrollReviewActionResult:
    """Enter review only for runs carrying a fully calculated, versioned snapshot."""
    run = session.exec(
        select(PayrollRun).where(PayrollRun.id == run_id).with_for_update()
    ).first()
    if run is None or run.is_deleted:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.workflow_status == "in_review":
        reviewed, excluded, unresolved = _payroll_review_counts(session, run_id)
        return PayrollReviewActionResult(
            run_id=run_id,
            workflow_status=run.workflow_status,
            reviewed_count=reviewed,
            excluded_count=excluded,
            unresolved_count=unresolved,
        )
    if run.workflow_status != "draft" or run.status != PayrollRunStatus.DRAFT:
        raise HTTPException(
            status_code=409, detail="Only a draft payroll run can enter review"
        )
    if (
        run.is_readonly
        or run.pay_group_id is None
        or run.policy_version_id is None
        or not run.input_fingerprint
    ):
        raise HTTPException(
            status_code=409,
            detail="Legacy or unprepared payroll runs cannot enter the new review workflow",
        )
    policy = session.get(PayrollPolicyVersion, run.policy_version_id)
    if policy is None or not policy.confirmed:
        raise HTTPException(
            status_code=409,
            detail="The payroll policy version is missing or unconfirmed",
        )
    entries = session.exec(
        select(PayrollEntry)
        .where(
            PayrollEntry.payroll_run_id == run_id,
            col(PayrollEntry.is_deleted).is_(False),
        )
        .with_for_update()
    ).all()
    if not entries:
        raise HTTPException(
            status_code=409, detail="A run without employee entries cannot enter review"
        )
    for entry in entries:
        if (
            entry.calculation_version is None
            or not entry.input_fingerprint
            or not entry.input_snapshot
        ):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} has no versioned calculation snapshot",
            )
        if entry.blockers:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Resolve payroll blockers before review",
                    "entry_id": str(entry.id),
                    "blockers": entry.blockers,
                },
            )
        if not _payroll_entry_inputs_are_current(session, entry):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} inputs changed; rebuild the draft before review",
            )
        entry.review_state = "ready"
        entry.reviewed_by = None
        entry.reviewed_at = None
        session.add(entry)
    run.workflow_status = "in_review"
    run.updated_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    reviewed, excluded, unresolved = _payroll_review_counts(session, run_id)
    return PayrollReviewActionResult(
        run_id=run_id,
        workflow_status=run.workflow_status,
        reviewed_count=reviewed,
        excluded_count=excluded,
        unresolved_count=unresolved,
    )


@router.post(
    "/runs/{run_id}/entries/{entry_id}/review",
    response_model=PayrollReviewActionResult,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def review_payroll_entry(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
    entry_id: uuid.UUID,
    current_user: CurrentUser,
    obj_in: PayrollEntryReviewRequest,
) -> PayrollReviewActionResult:
    run = session.exec(
        select(PayrollRun).where(PayrollRun.id == run_id).with_for_update()
    ).first()
    if run is None or run.is_deleted:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.workflow_status != "in_review":
        raise HTTPException(
            status_code=409, detail="Payroll run is not accepting entry reviews"
        )
    entry = session.exec(
        select(PayrollEntry)
        .where(
            PayrollEntry.id == entry_id,
            PayrollEntry.payroll_run_id == run_id,
            col(PayrollEntry.is_deleted).is_(False),
        )
        .with_for_update()
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    if entry.input_fingerprint != obj_in.expected_input_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Payroll inputs changed; recalculate and review this entry again",
        )
    if not _payroll_entry_inputs_are_current(session, entry):
        entry.review_state = "blocked"
        entry.reviewed_by = None
        entry.reviewed_at = None
        entry.review_reason = None
        session.add(entry)
        run.workflow_status = "draft"
        session.add(run)
        session.commit()
        raise HTTPException(
            status_code=409,
            detail="Payroll inputs changed; rebuild the draft before reviewing this entry",
        )
    if entry.blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Resolve payroll blockers before review",
                "blockers": entry.blockers,
            },
        )
    if obj_in.action == "excluded" and not (obj_in.reason or "").strip():
        raise HTTPException(status_code=422, detail="An exclusion reason is required")
    entry.review_state = obj_in.action
    entry.reviewed_by = current_user.id
    entry.reviewed_at = datetime.now(timezone.utc)
    entry.review_reason = (
        (obj_in.reason or "").strip() if obj_in.action == "excluded" else None
    )
    session.add(entry)
    session.flush()
    reviewed, excluded, unresolved = _payroll_review_counts(session, run_id)
    if unresolved == 0:
        run.workflow_status = "ready_for_finalization"
        session.add(run)
    session.commit()
    return PayrollReviewActionResult(
        run_id=run_id,
        entry_id=entry_id,
        workflow_status=run.workflow_status,
        reviewed_count=reviewed,
        excluded_count=excluded,
        unresolved_count=unresolved,
    )


@router.post(
    "/runs/{run_id}/finalize",
    response_model=PayrollReviewActionResult,
    dependencies=[Depends(require_permission("payroll", "approve"))],
)
def finalize_payroll_run(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
    current_user: CurrentUser,
) -> PayrollReviewActionResult:
    if not settings.PAYROLL_FINALIZATION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail=(
                "Payroll finalization is disabled until HR approves the parallel "
                "payroll comparison and enables the finalization setting"
            ),
        )
    run = session.exec(
        select(PayrollRun).where(PayrollRun.id == run_id).with_for_update()
    ).first()
    if run is None or run.is_deleted:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.workflow_status != "ready_for_finalization":
        raise HTTPException(
            status_code=409,
            detail="Every payroll entry must be reviewed or explicitly excluded first",
        )
    if run.created_by is None or run.created_by == current_user.id:
        raise HTTPException(
            status_code=409, detail="The final approver must differ from the preparer"
        )
    entries = session.exec(
        select(PayrollEntry)
        .where(
            PayrollEntry.payroll_run_id == run_id,
            col(PayrollEntry.is_deleted).is_(False),
        )
        .with_for_update()
    ).all()
    if not entries:
        raise HTTPException(status_code=409, detail="Payroll run has no entries")
    for entry in entries:
        if (
            entry.review_state not in {"reviewed", "excluded"}
            or entry.reviewed_by is None
        ):
            raise HTTPException(
                status_code=409, detail=f"Entry {entry.id} has not been dispositioned"
            )
        if entry.reviewed_by == current_user.id:
            raise HTTPException(
                status_code=409,
                detail="Final approver must differ from every employee-entry reviewer",
            )
        if entry.review_state == "reviewed" and entry.net_pay < 0:
            raise HTTPException(
                status_code=409, detail=f"Entry {entry.id} has negative net pay"
            )
        if entry.blockers:
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} still has unresolved blockers",
            )
        required_snapshot_keys = {
            "attendance_revisions",
            "salary_versions",
            "shift_assignments",
            "pay_group_assignments",
            "leave_revisions",
            "holiday_revisions",
        }
        if not required_snapshot_keys.issubset(entry.input_snapshot):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} is missing attendance or salary revision evidence",
            )
        if not entry.input_snapshot["salary_versions"]:
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} has no effective salary version",
            )
        if not _payroll_entry_inputs_are_current(session, entry):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} payroll inputs changed; recalculate and review it again",
            )
        if entry.review_state == "reviewed" and run.adjustment_type == "regular":
            overlap = session.exec(
                select(PayrollEntry.id)
                .join(
                    PayrollRun, col(PayrollRun.id) == col(PayrollEntry.payroll_run_id)
                )
                .where(
                    PayrollEntry.employee_id == entry.employee_id,
                    col(PayrollEntry.is_deleted).is_(False),
                    PayrollRun.id != run.id,
                    col(PayrollRun.is_deleted).is_(False),
                    col(PayrollRun.status).in_(
                        [PayrollRunStatus.APPROVED, PayrollRunStatus.PAID]
                    ),
                    PayrollRun.date_from <= run.date_to,
                    PayrollRun.date_to >= run.date_from,
                )
                .limit(1)
            ).first()
            if overlap is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Employee {entry.employee_id} already has a finalized payroll covering this period",
                )
    policy = (
        session.get(PayrollPolicyVersion, run.policy_version_id)
        if run.policy_version_id
        else None
    )
    if (
        policy is None
        or not policy.confirmed
        or policy.effective_from > run.date_from
        or (policy.effective_to is not None and policy.effective_to < run.date_to)
    ):
        raise HTTPException(
            status_code=409, detail="The effective payroll policy is not confirmed"
        )
    if run.pay_group_id is None:
        raise HTTPException(
            status_code=409, detail="Finalization requires an assigned pay group"
        )
    matching_period = next(
        (
            period
            for period in list_pay_group_periods(
                session=session,
                group_id=run.pay_group_id,
                month=run.date_from.strftime("%Y-%m"),
            )
            if period.date_from == run.date_from and period.date_to == run.date_to
        ),
        None,
    )
    if matching_period is None:
        raise HTTPException(
            status_code=409,
            detail="Payroll range no longer matches a configured pay-group period",
        )
    contribution_policy = policy.policy.get("contribution_collection")
    if not isinstance(contribution_policy, dict) or (
        contribution_policy.get("frequency") != "once_monthly"
        or contribution_policy.get("collection_period") != "last_period"
    ):
        raise HTTPException(
            status_code=409,
            detail="The confirmed policy does not specify once-monthly contribution collection",
        )
    _stage_monthly_contribution_ledger(
        session=session, run=run, entries=entries, actor_id=current_user.id
    )
    try:
        delivery_timezone = ZoneInfo(str(policy.policy["timezone"]))
    except (KeyError, ZoneInfoNotFoundError) as exc:
        raise HTTPException(
            status_code=409,
            detail="The confirmed policy has no valid delivery timezone",
        ) from exc
    delivery_due_at = datetime.combine(
        matching_period.payment_date, time_of_day(9), tzinfo=delivery_timezone
    )

    snapshot_entries: list[dict[str, Any]] = []
    for entry in entries:
        employee = (
            session.get(EmployeeRecords, entry.employee_id)
            if entry.employee_id
            else None
        )
        snapshot_entries.append(
            {
                "id": str(entry.id),
                "employee_id": str(entry.employee_id),
                "employee": {
                    "name": f"{employee.first_name} {employee.last_name}".strip()
                    if employee
                    else "Employee",
                    "code": employee.employee_code if employee else "",
                },
                "review_state": entry.review_state,
                "reviewed_by": str(entry.reviewed_by),
                "reviewed_at": entry.reviewed_at.isoformat()
                if entry.reviewed_at
                else None,
                "review_reason": entry.review_reason,
                "amounts": {
                    "gross": str(entry.gross_pay),
                    "deductions": str(entry.total_deductions),
                    "net": str(entry.net_pay),
                    "earnings": entry.earnings,
                    "deduction_lines": entry.deductions,
                },
                "inputs": entry.input_snapshot,
            }
        )
    snapshot: dict[str, Any] = {
        "run_id": str(run.id),
        "period": {"from": run.date_from.isoformat(), "to": run.date_to.isoformat()},
        "pay_group_id": str(run.pay_group_id),
        "payment_date": matching_period.payment_date.isoformat(),
        "policy_version": policy.version,
        "calculation_version": sorted(
            {
                entry.calculation_version
                for entry in entries
                if entry.calculation_version is not None
            }
        ),
        "entries": snapshot_entries,
    }
    run.frozen_snapshot = snapshot
    run.finalized_by = current_user.id
    run.finalized_at = datetime.now(timezone.utc)
    run.payment_date = matching_period.payment_date
    run.workflow_status = "finalized"
    run.status = PayrollRunStatus.APPROVED
    run.updated_at = run.finalized_at
    session.add(run)
    for entry_index, entry in enumerate(entries):
        if entry.review_state == "excluded":
            continue
        employee = (
            session.get(EmployeeRecords, entry.employee_id)
            if entry.employee_id
            else None
        )
        session.add(
            PayrollDeliveryOutbox(
                payroll_entry_id=entry.id,
                document_version=1,
                recipient_snapshot=employee.email
                if employee and employee.email
                else None,
                content_snapshot={
                    "entry": snapshot["entries"][entry_index],
                    "run": snapshot,
                },
                status="scheduled" if employee and employee.email else "blocked_email",
                next_attempt_at=delivery_due_at.astimezone(timezone.utc),
            )
        )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Payroll finalization conflicted with another run or an existing monthly contribution; refresh and review again.",
        ) from exc
    reviewed, excluded, unresolved = _payroll_review_counts(session, run_id)
    return PayrollReviewActionResult(
        run_id=run_id,
        workflow_status=run.workflow_status,
        reviewed_count=reviewed,
        excluded_count=excluded,
        unresolved_count=unresolved,
    )


@router.get(
    "/runs/{run_id}/delivery-status",
    response_model=list[PayrollDeliveryStatusPublic],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def get_payroll_delivery_status(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[PayrollDeliveryStatusPublic]:
    if session.get(PayrollRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    rows = session.exec(
        select(PayrollDeliveryOutbox)
        .join(
            PayrollEntry,
            col(PayrollEntry.id) == col(PayrollDeliveryOutbox.payroll_entry_id),
        )
        .where(PayrollEntry.payroll_run_id == run_id)
        .order_by(col(PayrollDeliveryOutbox.created_at))
        .offset(skip)
        .limit(limit)
    ).all()
    return [PayrollDeliveryStatusPublic.model_validate(row) for row in rows]


@router.post(
    "/runs/{run_id}/delivery/{job_id}/address",
    response_model=PayrollDeliveryStatusPublic,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def correct_delivery_address(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: CurrentUser,
    obj_in: PayrollDeliveryAddressUpdate,
) -> PayrollDeliveryStatusPublic:
    job = session.exec(
        select(PayrollDeliveryOutbox)
        .join(
            PayrollEntry,
            col(PayrollEntry.id) == col(PayrollDeliveryOutbox.payroll_entry_id),
        )
        .where(
            PayrollDeliveryOutbox.id == job_id, PayrollEntry.payroll_run_id == run_id
        )
        .with_for_update()
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Payslip delivery job not found")
    if job.status not in {"blocked_email", "failed"}:
        raise HTTPException(
            status_code=409,
            detail="Address correction is only allowed for blocked or failed delivery",
        )
    job.recipient_snapshot = str(obj_in.email)
    job.status = "scheduled"
    job.next_attempt_at = datetime.now(timezone.utc)
    job.last_error_code = None
    job.last_action_by = current_user.id
    job.last_action_at = datetime.now(timezone.utc)
    job.last_action_reason = obj_in.reason.strip()
    job.updated_at = job.last_action_at
    session.add(job)
    session.commit()
    session.refresh(job)
    return PayrollDeliveryStatusPublic.model_validate(job)


@router.post(
    "/runs/{run_id}/delivery/{job_id}/resend",
    response_model=PayrollDeliveryStatusPublic,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def request_delivery_resend(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: CurrentUser,
    obj_in: PayrollDeliveryResendRequest,
) -> PayrollDeliveryStatusPublic:
    job = session.exec(
        select(PayrollDeliveryOutbox)
        .join(
            PayrollEntry,
            col(PayrollEntry.id) == col(PayrollDeliveryOutbox.payroll_entry_id),
        )
        .where(
            PayrollDeliveryOutbox.id == job_id, PayrollEntry.payroll_run_id == run_id
        )
        .with_for_update()
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Payslip delivery job not found")
    if job.status == "uncertain" and not obj_in.confirm_duplicate_risk:
        raise HTTPException(
            status_code=422,
            detail="Confirm the possible duplicate email before resending an uncertain delivery",
        )
    if job.status not in {"uncertain", "failed"}:
        raise HTTPException(
            status_code=409, detail="Only failed or uncertain deliveries can be resent"
        )
    if not job.recipient_snapshot:
        raise HTTPException(
            status_code=409,
            detail="Correct the recipient address before retrying delivery",
        )
    job.status = "scheduled"
    job.attempts = 0
    job.next_attempt_at = datetime.now(timezone.utc)
    job.claimed_until = None
    job.last_action_by = current_user.id
    job.last_action_at = datetime.now(timezone.utc)
    job.last_action_reason = obj_in.reason.strip()
    job.last_error_code = None
    job.updated_at = job.last_action_at
    session.add(job)
    session.commit()
    session.refresh(job)
    return PayrollDeliveryStatusPublic.model_validate(job)


@router.get(
    "/pay-groups",
    response_model=list[PayrollPayGroupPublic],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def list_pay_groups(
    *,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[PayrollPayGroupPublic]:
    rows = session.exec(
        select(PayrollPayGroup)
        .where(col(PayrollPayGroup.is_active).is_(True))
        .order_by(col(PayrollPayGroup.code))
        .offset(skip)
        .limit(limit)
    ).all()
    return [PayrollPayGroupPublic.model_validate(row) for row in rows]


@router.post(
    "/pay-groups",
    response_model=PayrollPayGroupPublic,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def create_pay_group(
    *, session: SessionDep, current_user: CurrentUser, obj_in: PayrollPayGroupCreate
) -> PayrollPayGroupPublic:
    if obj_in.cadence.value not in {"daily", "semi_monthly", "monthly"}:
        raise HTTPException(
            status_code=422,
            detail="Pay cadence must be daily, twice-monthly, or monthly",
        )
    if obj_in.cadence.value == "semi_monthly":
        if obj_in.first_period_end_day is None or obj_in.second_period_end_day is None:
            raise HTTPException(
                status_code=422, detail="Twice-monthly groups need both period end days"
            )
        if obj_in.second_period_end_day != 31:
            raise HTTPException(
                status_code=422,
                detail="The second twice-monthly period must end at month-end (31 is the month-end marker)",
            )
    elif (
        obj_in.first_period_end_day is not None
        or obj_in.second_period_end_day is not None
    ):
        raise HTTPException(
            status_code=422,
            detail="Period boundary days apply only to twice-monthly groups",
        )
    row = PayrollPayGroup.model_validate(obj_in, update={"created_by": current_user.id})
    session.add(row)
    session.commit()
    session.refresh(row)
    return PayrollPayGroupPublic.model_validate(row)


@router.get(
    "/pay-groups/{group_id}/periods",
    response_model=list[PayrollPayPeriodPublic],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def list_pay_group_periods(
    *,
    session: SessionDep,
    group_id: uuid.UUID,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
) -> list[PayrollPayPeriodPublic]:
    group = session.get(PayrollPayGroup, group_id)
    if group is None or not group.is_active:
        raise HTTPException(status_code=404, detail="Active pay group not found")
    try:
        year, month_number = (int(part) for part in month.split("-"))
        month_start = date(year, month_number, 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="month must be a valid YYYY-MM value"
        ) from exc
    month_end = date(year, month_number, calendar.monthrange(year, month_number)[1])
    if group.cadence.value == "daily":
        earning_ranges = [(day, day) for day in range(1, month_end.day + 1)]
        periods = [
            (date(year, month_number, start), date(year, month_number, end))
            for start, end in earning_ranges
        ]
    elif group.cadence.value == "semi_monthly":
        if group.first_period_end_day is None:
            raise HTTPException(
                status_code=409,
                detail="Twice-monthly pay group has no first cutoff day",
            )
        if group.first_period_end_day >= month_end.day:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"The configured first twice-monthly cutoff (day {group.first_period_end_day}) "
                    f"does not leave a second period in {month}. Configure a cutoff before day {month_end.day}."
                ),
            )
        first_end = group.first_period_end_day
        periods = [
            (month_start, date(year, month_number, first_end)),
            (date(year, month_number, first_end) + timedelta(days=1), month_end),
        ]
    else:
        periods = [(month_start, month_end)]

    holiday_dates = set(
        session.exec(
            select(col(HolidayInstance.observed_date)).where(
                col(HolidayInstance.observed_date) >= month_start - timedelta(days=31),
                col(HolidayInstance.observed_date) <= month_end + timedelta(days=60),
                col(HolidayInstance.is_active).is_(True),
                col(HolidayInstance.is_deleted).is_(False),
            )
        ).all()
    )

    def shift_business_day(value: date) -> date:
        def business(day: date) -> bool:
            return day.weekday() < 5 and day not in holiday_dates

        if business(value):
            return value
        if group.weekend_rule == "nearest_business_day":
            for distance in range(1, 32):
                backward = value - timedelta(days=distance)
                forward = value + timedelta(days=distance)
                if business(backward):
                    return backward
                if business(forward):
                    return forward
        direction = -1 if group.weekend_rule == "previous_business_day" else 1
        candidate = value
        for _ in range(31):
            candidate += timedelta(days=direction)
            if business(candidate):
                return candidate
        raise HTTPException(
            status_code=409, detail="No business payment date found within 31 days"
        )

    return [
        PayrollPayPeriodPublic(
            pay_group_id=group.id,
            date_from=start,
            date_to=end,
            payment_date=shift_business_day(
                end + timedelta(days=group.payment_offset_days)
            ),
            cadence=group.cadence,
        )
        for start, end in periods
    ]


@router.get(
    "/runs/preflight",
    response_model=PayrollRunPreflight,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def preflight_payroll_run(
    *,
    session: SessionDep,
    pay_group_id: uuid.UUID,
    date_from: date,
    date_to: date,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> PayrollRunPreflight:
    """Return every expected employee in a pay group with explicit blockers.

    This endpoint deliberately does not calculate or persist money. It replaces
    salary-driven roster discovery while the audited calculator/review lifecycle
    is being completed; incomplete configuration is visible rather than omitted.
    """
    if date_from > date_to:
        raise HTTPException(
            status_code=422, detail="date_from must be on or before date_to"
        )
    if (date_to - date_from).days > 62:
        raise HTTPException(
            status_code=422, detail="Payroll preflight is limited to periods of 63 days"
        )
    group = session.get(PayrollPayGroup, pay_group_id)
    if group is None or not group.is_active:
        raise HTTPException(status_code=404, detail="Active pay group not found")

    # A run must use one complete configured earning period. This prevents
    # overlapping ad-hoc ranges from collecting the same deductions twice.
    month = date_from.strftime("%Y-%m")
    configured_periods = list_pay_group_periods(
        session=session, group_id=pay_group_id, month=month
    )
    if not any(
        _same_calendar_day(period.date_from, date_from)
        and _same_calendar_day(period.date_to, date_to)
        for period in configured_periods
    ):
        raise HTTPException(
            status_code=422,
            detail="Date range must match a complete configured pay-group period",
        )

    employees = list(
        session.exec(
            select(EmployeeRecords)
            .where(
                col(EmployeeRecords.is_deleted).is_(False),
                (col(EmployeeRecords.date_hired).is_(None))
                | (col(EmployeeRecords.date_hired) <= date_to),
                (col(EmployeeRecords.date_separated).is_(None))
                | (col(EmployeeRecords.date_separated) >= date_from),
            )
            .order_by(col(EmployeeRecords.employee_code))
        ).all()
    )
    employee_ids = [employee.id for employee in employees]
    if not employee_ids:
        return PayrollRunPreflight(
            pay_group_id=pay_group_id,
            date_from=date_from,
            date_to=date_to,
            entries=[],
            count=0,
            blocked_count=0,
            ready_count=0,
            has_more=False,
        )

    assignments = list(
        session.exec(
            select(EmployeePayGroupAssignment).where(
                col(EmployeePayGroupAssignment.employee_id).in_(employee_ids),
                EmployeePayGroupAssignment.effective_from <= date_to,
                (col(EmployeePayGroupAssignment.effective_to).is_(None))
                | (col(EmployeePayGroupAssignment.effective_to) >= date_from),
            )
        ).all()
    )
    assignments_by_employee: dict[uuid.UUID, list[EmployeePayGroupAssignment]] = {}
    for assignment in assignments:
        assignments_by_employee.setdefault(assignment.employee_id, []).append(
            assignment
        )

    # Only group members and employees with no group assignment belong in this
    # roster. Employees assigned to another group are reviewed in that group.
    expected = [
        employee
        for employee in employees
        if not assignments_by_employee.get(employee.id)
        or any(
            item.pay_group_id == pay_group_id
            for item in assignments_by_employee[employee.id]
        )
    ]
    total = len(expected)
    page = expected[skip : skip + limit]
    page_ids = [employee.id for employee in page]
    if not page:
        return PayrollRunPreflight(
            pay_group_id=pay_group_id,
            date_from=date_from,
            date_to=date_to,
            entries=[],
            count=total,
            blocked_count=0,
            ready_count=0,
            has_more=skip < total,
        )

    shift_assignments = list(
        session.exec(
            select(EmployeeShiftAssignment).where(
                col(EmployeeShiftAssignment.employee_id).in_(page_ids),
                col(EmployeeShiftAssignment.is_deleted).is_(False),
                EmployeeShiftAssignment.effective_from <= date_to,
                (col(EmployeeShiftAssignment.effective_to).is_(None))
                | (col(EmployeeShiftAssignment.effective_to) >= date_from),
            )
        ).all()
    )
    shift_ids = {assignment.shift_id for assignment in shift_assignments}
    shifts = (
        {
            shift.id: shift
            for shift in session.exec(
                select(Shift).where(
                    col(Shift.id).in_(shift_ids), col(Shift.is_deleted).is_(False)
                )
            ).all()
        }
        if shift_ids
        else {}
    )
    shift_assignments_by_employee: dict[uuid.UUID, list[EmployeeShiftAssignment]] = {}
    for shift_assignment in shift_assignments:
        shift_assignments_by_employee.setdefault(
            shift_assignment.employee_id, []
        ).append(shift_assignment)

    salaries = list(
        session.exec(
            select(EmployeeSalary)
            .where(
                col(EmployeeSalary.employee_id).in_(page_ids),
                col(EmployeeSalary.is_active).is_(True),
                col(EmployeeSalary.is_deleted).is_(False),
                EmployeeSalary.effective_date <= date_to,
            )
            .order_by(col(EmployeeSalary.effective_date))
        ).all()
    )
    salaries_by_employee: dict[uuid.UUID, list[EmployeeSalary]] = {}
    for salary in salaries:
        if salary.employee_id is not None:
            salaries_by_employee.setdefault(salary.employee_id, []).append(salary)

    dtrs = list(
        session.exec(
            select(DailyTimeRecord).where(
                col(DailyTimeRecord.employee_id).in_(page_ids),
                col(DailyTimeRecord.is_deleted).is_(False),
                col(DailyTimeRecord.work_date) >= date_from,
                col(DailyTimeRecord.work_date) <= date_to,
            )
        ).all()
    )
    dtrs_by_key: dict[tuple[uuid.UUID, date], list[DailyTimeRecord]] = {}
    for dtr in dtrs:
        if dtr.work_date is not None:
            dtrs_by_key.setdefault((dtr.employee_id, dtr.work_date), []).append(dtr)

    pending_adjustments = session.exec(
        select(DtrAdjustment, col(DailyTimeRecord.work_date))
        .join(
            DailyTimeRecord,
            col(DtrAdjustment.daily_time_record_id) == col(DailyTimeRecord.id),
        )
        .where(
            col(DtrAdjustment.employee_id).in_(page_ids),
            DtrAdjustment.status == "PENDING",
            col(DtrAdjustment.is_deleted).is_(False),
            col(DailyTimeRecord.work_date) >= date_from,
            col(DailyTimeRecord.work_date) <= date_to,
            col(DailyTimeRecord.is_deleted).is_(False),
        )
    ).all()
    adjustments_by_key: dict[tuple[uuid.UUID, date], int] = {}
    for adjustment, adjustment_date in pending_adjustments:
        if adjustment_date is not None:
            key = (adjustment.employee_id, adjustment_date)
            adjustments_by_key[key] = adjustments_by_key.get(key, 0) + 1

    approved_leaves = list(
        session.exec(
            select(LeaveRequest).where(
                col(LeaveRequest.employee_id).in_(page_ids),
                LeaveRequest.status == "approved",
                col(LeaveRequest.is_deleted).is_(False),
                LeaveRequest.date_start <= date_to,
                LeaveRequest.date_end >= date_from,
            )
        ).all()
    )
    leave_days: set[tuple[uuid.UUID, date]] = set()
    for leave in approved_leaves:
        if leave.employee_id is None:
            continue
        start = max(date_from, leave.date_start)
        end = min(date_to, leave.date_end)
        covered_days = (end - start).days + 1
        # A multi-day full-day leave can resolve each scheduled date. Partial
        # hour/day leave still requires its corresponding attendance intervals.
        if leave.requested_hours is not None or leave.total_days_requested < Decimal(
            covered_days
        ):
            continue
        cursor = start
        while cursor <= end:
            leave_days.add((leave.employee_id, cursor))
            cursor += timedelta(days=1)
    holiday_rows = session.exec(
        select(col(HolidayInstance.observed_date), col(HolidayConfig.type))
        .join(HolidayConfig, col(HolidayInstance.config_id) == col(HolidayConfig.id))
        .where(
            HolidayInstance.observed_date >= date_from,
            HolidayInstance.observed_date <= date_to,
            col(HolidayInstance.is_active).is_(True),
            col(HolidayInstance.is_deleted).is_(False),
            col(HolidayConfig.is_active).is_(True),
            col(HolidayConfig.is_deleted).is_(False),
        )
    ).all()
    holiday_days = {
        day
        for day, kind in holiday_rows
        if str(getattr(kind, "value", kind)) != "special_working"
    }
    cursor_dates: list[date] = []
    cursor = date_from
    while cursor <= date_to:
        cursor_dates.append(cursor)
        cursor += timedelta(days=1)
    policies = list(
        session.exec(
            select(PayrollPolicyVersion)
            .where(
                PayrollPolicyVersion.effective_from <= date_to,
                (col(PayrollPolicyVersion.effective_to).is_(None))
                | (col(PayrollPolicyVersion.effective_to) >= date_from),
            )
            .order_by(col(PayrollPolicyVersion.effective_from))
        ).all()
    )
    policy_by_day = {
        day: [
            policy
            for policy in policies
            if policy.effective_from <= day
            and (policy.effective_to is None or policy.effective_to >= day)
        ]
        for day in cursor_dates
    }

    entries: list[PayrollPreflightEmployee] = []
    for employee in page:
        blockers: list[PayrollPreflightBlocker] = []
        warnings: list[str] = []
        employee_groups = assignments_by_employee.get(employee.id, [])
        member_groups = [
            item for item in employee_groups if item.pay_group_id == pay_group_id
        ]
        if not employee_groups:
            blockers.append(
                PayrollPreflightBlocker(
                    code="missing_pay_group",
                    message="Employee has no effective pay-group assignment.",
                )
            )
        elif not member_groups:
            # An assignment exists only in a different group, so it was included
            # only because it overlaps this period; do not expose it as member.
            continue
        elif not any(
            item.effective_from <= date_from
            and (item.effective_to is None or item.effective_to >= date_to)
            for item in member_groups
        ):
            blockers.append(
                PayrollPreflightBlocker(
                    code="pay_group_boundary",
                    message="Pay-group membership changes during this earning period; apply the transfer at the next configured boundary.",
                )
            )

        employee_salaries = salaries_by_employee.get(employee.id, [])
        employed_dates = [
            day
            for day in cursor_dates
            if (employee.date_hired is None or day >= employee.date_hired)
            and (employee.date_separated is None or day <= employee.date_separated)
        ]
        missing_salary_days = [
            day
            for day in employed_dates
            if not any(item.effective_date <= day for item in employee_salaries)
        ]
        if missing_salary_days:
            blockers.append(
                PayrollPreflightBlocker(
                    code="missing_salary",
                    message="No active salary is effective for one or more dates in this period.",
                    work_date=missing_salary_days[0],
                )
            )
        if employee.date_hired is None:
            blockers.append(
                PayrollPreflightBlocker(
                    code="missing_hire_date",
                    message="Employment start date is missing.",
                )
            )
        if employee.email is None or not employee.email.strip():
            warnings.append(
                "No employee email is on file; payslip delivery will need an authorized address correction."
            )

        employee_shift_assignments = shift_assignments_by_employee.get(employee.id, [])
        employee_dtrs = 0
        eligible_ot = 0
        approved_ot = 0
        for work_day in cursor_dates:
            if employee.date_hired is not None and work_day < employee.date_hired:
                continue
            if (
                employee.date_separated is not None
                and work_day > employee.date_separated
            ):
                continue
            day_policies = policy_by_day[work_day]
            if len(day_policies) != 1 or not day_policies[0].confirmed:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="unconfirmed_policy",
                        message="Exactly one confirmed payroll policy must cover this date.",
                        work_date=work_day,
                    )
                )
            day_records = dtrs_by_key.get((employee.id, work_day), [])
            if adjustments_by_key.get((employee.id, work_day), 0):
                blockers.append(
                    PayrollPreflightBlocker(
                        code="attendance_adjustment_pending",
                        message="A DTR correction is awaiting approval for this work date.",
                        work_date=work_day,
                    )
                )
            resolved_nonwork_day = (
                work_day in holiday_days or (employee.id, work_day) in leave_days
            )
            if resolved_nonwork_day and not day_records:
                continue
            effective_shift_assignment = next(
                (
                    item
                    for item in employee_shift_assignments
                    if item.effective_from <= work_day
                    and (item.effective_to is None or item.effective_to >= work_day)
                ),
                None,
            )
            if effective_shift_assignment is None:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="missing_shift",
                        message="No shift is assigned for this work date.",
                        work_date=work_day,
                    )
                )
                continue
            shift = shifts.get(effective_shift_assignment.shift_id)
            if shift is None:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="missing_shift",
                        message="Assigned shift is unavailable or deleted.",
                        work_date=work_day,
                    )
                )
                continue
            try:
                scheduled_days = {int(value) for value in shift.days_of_week}
            except (TypeError, ValueError):
                blockers.append(
                    PayrollPreflightBlocker(
                        code="invalid_shift_schedule",
                        message="Assigned shift has an invalid weekday schedule.",
                        work_date=work_day,
                    )
                )
                continue
            if len(day_records) > 1:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="duplicate_attendance",
                        message="More than one active DTR record exists for this employee and work date; reconcile duplicates before payroll.",
                        work_date=work_day,
                    )
                )
                continue
            if work_day.isoweekday() not in scheduled_days:
                if day_records:
                    dtr = day_records[0]
                    employee_dtrs += 1
                    eligible_ot += dtr.overtime_minutes or 0
                    approved_ot += dtr.overtime_approved_minutes or 0
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="unscheduled_attendance",
                            message="Attendance on a non-scheduled date needs an explicit premium/exception rule before calculation.",
                            work_date=work_day,
                        )
                    )
                continue
            if not day_records:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="missing_attendance_resolution",
                        message="Scheduled work date has no attendance, absence, or approved leave resolution.",
                        work_date=work_day,
                    )
                )
                continue
            dtr = day_records[0]
            employee_dtrs += 1
            if dtr.shift_id != shift.id:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="attendance_shift_mismatch",
                        message="Attendance was calculated against a shift different from the effective assigned shift.",
                        work_date=work_day,
                    )
                )
            if not dtr.is_absent and (
                dtr.login_date is None or dtr.logout_date is None
            ):
                blockers.append(
                    PayrollPreflightBlocker(
                        code="incomplete_attendance",
                        message="Attendance punch is incomplete.",
                        work_date=work_day,
                    )
                )
            if (dtr.overtime_minutes or 0) > 0:
                eligible_ot += dtr.overtime_minutes or 0
                if dtr.overtime_approved is None:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="overtime_pending",
                            message="Overtime requires an authorized decision before payroll review.",
                            work_date=work_day,
                        )
                    )
                elif dtr.overtime_approved:
                    approved_ot += dtr.overtime_approved_minutes or 0

        entries.append(
            PayrollPreflightEmployee(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                employee_name=f"{employee.first_name} {employee.last_name}".strip(),
                email=employee.email,
                blockers=blockers,
                warnings=warnings,
                attendance_records=employee_dtrs,
                eligible_overtime_minutes=eligible_ot,
                approved_overtime_minutes=approved_ot,
            )
        )

    blocked = sum(bool(item.blockers) for item in entries)
    return PayrollRunPreflight(
        pay_group_id=pay_group_id,
        date_from=date_from,
        date_to=date_to,
        policy_versions=sorted(
            {policy.version for policy in policies if policy.confirmed}
        ),
        entries=entries,
        count=total,
        blocked_count=blocked,
        ready_count=len(entries) - blocked,
        has_more=skip + len(page) < total,
    )


@router.get(
    "/runs/attendance-calculation-preview",
    response_model=PayrollAttendanceCalculationPreview,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def attendance_calculation_preview(
    *,
    session: SessionDep,
    pay_group_id: uuid.UUID,
    date_from: date,
    date_to: date,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> PayrollAttendanceCalculationPreview:
    """Return provisional regular/overtime earnings with blockers and source refs.

    Statutory withholding, monthly contribution reconciliation, finalization,
    and delivery are deliberately excluded from this preview.
    """
    roster = preflight_payroll_run(
        session=session,
        pay_group_id=pay_group_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    employee_ids = [entry.employee_id for entry in roster.entries]
    if not employee_ids:
        return PayrollAttendanceCalculationPreview(
            pay_group_id=pay_group_id,
            date_from=date_from,
            date_to=date_to,
            entries=[],
            count=roster.count,
            has_more=roster.has_more,
        )

    employees = {
        employee.id: employee
        for employee in session.exec(
            select(EmployeeRecords).where(col(EmployeeRecords.id).in_(employee_ids))
        ).all()
    }
    salaries = session.exec(
        select(EmployeeSalary)
        .where(
            col(EmployeeSalary.employee_id).in_(employee_ids),
            EmployeeSalary.effective_date <= date_to,
            col(EmployeeSalary.is_active).is_(True),
            col(EmployeeSalary.is_deleted).is_(False),
        )
        .order_by(col(EmployeeSalary.effective_date))
    ).all()
    salaries_by_employee: dict[uuid.UUID, list[EmployeeSalary]] = {}
    for salary in salaries:
        if salary.employee_id:
            salaries_by_employee.setdefault(salary.employee_id, []).append(salary)

    assignments = session.exec(
        select(EmployeeShiftAssignment).where(
            col(EmployeeShiftAssignment.employee_id).in_(employee_ids),
            col(EmployeeShiftAssignment.is_deleted).is_(False),
            EmployeeShiftAssignment.effective_from <= date_to,
            (col(EmployeeShiftAssignment.effective_to).is_(None))
            | (col(EmployeeShiftAssignment.effective_to) >= date_from),
        )
    ).all()
    assignments_by_employee: dict[uuid.UUID, list[EmployeeShiftAssignment]] = {}
    for assignment in assignments:
        assignments_by_employee.setdefault(assignment.employee_id, []).append(
            assignment
        )
    shift_ids = {assignment.shift_id for assignment in assignments}
    shifts = (
        {
            shift.id: shift
            for shift in session.exec(
                select(Shift).where(
                    col(Shift.id).in_(shift_ids), col(Shift.is_deleted).is_(False)
                )
            ).all()
        }
        if shift_ids
        else {}
    )
    dtrs = session.exec(
        select(DailyTimeRecord).where(
            col(DailyTimeRecord.employee_id).in_(employee_ids),
            col(DailyTimeRecord.work_date) >= date_from,
            col(DailyTimeRecord.work_date) <= date_to,
            col(DailyTimeRecord.is_deleted).is_(False),
        )
    ).all()
    dtrs_by_key = {
        (dtr.employee_id, dtr.work_date): dtr for dtr in dtrs if dtr.work_date
    }
    policies = session.exec(
        select(PayrollPolicyVersion).where(
            PayrollPolicyVersion.effective_from <= date_to,
            (col(PayrollPolicyVersion.effective_to).is_(None))
            | (col(PayrollPolicyVersion.effective_to) >= date_from),
            col(PayrollPolicyVersion.confirmed).is_(True),
        )
    ).all()
    leave_rows = session.exec(
        select(LeaveRequest).where(
            col(LeaveRequest.employee_id).in_(employee_ids),
            LeaveRequest.status == "approved",
            col(LeaveRequest.is_deleted).is_(False),
            LeaveRequest.date_start <= date_to,
            LeaveRequest.date_end >= date_from,
            col(LeaveRequest.requested_hours).is_(None),
        )
    ).all()
    paid_leave_days: set[tuple[uuid.UUID, date]] = set()
    for leave in leave_rows:
        if leave.employee_id is None:
            continue
        cursor = max(date_from, leave.date_start)
        end = min(date_to, leave.date_end)
        while cursor <= end:
            paid_leave_days.add((leave.employee_id, cursor))
            cursor += timedelta(days=1)
    holiday_rows = session.exec(
        select(col(HolidayInstance.observed_date), col(HolidayConfig.type))
        .join(HolidayConfig, col(HolidayInstance.config_id) == col(HolidayConfig.id))
        .where(
            HolidayInstance.observed_date >= date_from,
            HolidayInstance.observed_date <= date_to,
            col(HolidayInstance.is_active).is_(True),
            col(HolidayInstance.is_deleted).is_(False),
            col(HolidayConfig.is_active).is_(True),
            col(HolidayConfig.is_deleted).is_(False),
        )
    ).all()
    holiday_days = {
        holiday_day
        for holiday_day, kind in holiday_rows
        if str(getattr(kind, "value", kind)) != "special_working"
    }

    previews: list[PayrollAttendanceCalculationEntry] = []
    for employee_entry in roster.entries:
        blockers = list(employee_entry.blockers)
        formulas: list[str] = []
        refs: list[str] = []
        calculation_groups: dict[
            tuple[Decimal, str, Decimal, str], list[AttendancePayDay]
        ] = {}
        results = []
        employee = employees.get(employee_entry.employee_id)
        employee_salaries = salaries_by_employee.get(employee_entry.employee_id, [])
        if employee is None:
            blockers.append(
                PayrollPreflightBlocker(
                    code="employee_missing", message="Employee record is unavailable."
                )
            )
        if employee is not None and employee.date_hired is None:
            blockers.append(
                PayrollPreflightBlocker(
                    code="missing_hire_date",
                    message="Employment start date is required for payroll calculation.",
                )
            )

        cursor = date_from
        while cursor <= date_to and not blockers:
            if employee and (
                cursor < (employee.date_hired or date.min)
                or (employee.date_separated and cursor > employee.date_separated)
            ):
                cursor += timedelta(days=1)
                continue
            effective_salary = next(
                (
                    item
                    for item in reversed(employee_salaries)
                    if item.effective_date <= cursor
                ),
                None,
            )
            if effective_salary is None:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="missing_salary",
                        message="No salary is effective for this work date.",
                        work_date=cursor,
                    )
                )
                break
            effective_assignment = next(
                (
                    item
                    for item in assignments_by_employee.get(
                        employee_entry.employee_id, []
                    )
                    if item.effective_from <= cursor
                    and (item.effective_to is None or item.effective_to >= cursor)
                ),
                None,
            )
            if (
                effective_assignment is None
                or effective_assignment.shift_id not in shifts
            ):
                blockers.append(
                    PayrollPreflightBlocker(
                        code="missing_shift",
                        message="No effective shift is available for this work date.",
                        work_date=cursor,
                    )
                )
                break
            shift = shifts[effective_assignment.shift_id]
            if cursor.isoweekday() not in {int(value) for value in shift.days_of_week}:
                cursor += timedelta(days=1)
                continue
            day_policies = [
                policy
                for policy in policies
                if policy.effective_from <= cursor
                and (policy.effective_to is None or policy.effective_to >= cursor)
            ]
            if len(day_policies) != 1:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="unconfirmed_policy",
                        message="Exactly one confirmed policy is required for calculation.",
                        work_date=cursor,
                    )
                )
                break
            policy = day_policies[0]
            dtr = dtrs_by_key.get((employee_entry.employee_id, cursor))
            paid_leave_record = (employee_entry.employee_id, cursor) in paid_leave_days
            paid_leave = paid_leave_record and bool(policy.policy.get("paid_leave"))
            holiday = cursor in holiday_days
            paid_holiday = holiday and bool(policy.policy.get("paid_holidays"))
            resolved_no_punch_day = paid_leave_record or holiday
            if dtr is None and not resolved_no_punch_day:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="missing_attendance_resolution",
                        message="Attendance is not resolved for this scheduled work date.",
                        work_date=cursor,
                    )
                )
                break
            if dtr is not None and dtr.rendered_minutes is None and not dtr.is_absent:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="uncomputed_attendance",
                        message="Attendance duration must be recomputed before payroll calculation.",
                        work_date=cursor,
                    )
                )
                break
            overtime_rule = policy.policy.get("overtime_rule")
            multiplier_value = (
                overtime_rule.get("multiplier")
                if isinstance(overtime_rule, dict)
                else None
            )
            if multiplier_value is None:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="overtime_policy_incomplete",
                        message="A numeric overtime multiplier is required by the confirmed policy.",
                        work_date=cursor,
                    )
                )
                break
            try:
                monthly_divisor = Decimal(str(policy.policy["monthly_divisor"]))
                multiplier = Decimal(str(multiplier_value))
                partial_rule = str(policy.policy["daily_partial_work"])
                worked_minutes = (
                    0
                    if dtr is None or dtr.is_absent
                    else int(dtr.rendered_minutes or 0)
                )
                eligible_ot = int(dtr.overtime_minutes or 0) if dtr else 0
                approved_ot = (
                    int(dtr.overtime_approved_minutes or 0)
                    if dtr and dtr.overtime_approved
                    else 0
                )
                rounding = str(policy.policy["rounding_mode"])
                calculation_groups.setdefault(
                    (monthly_divisor, partial_rule, multiplier, rounding), []
                ).append(
                    AttendancePayDay(
                        work_date=cursor,
                        pay_type=str(
                            getattr(
                                effective_salary.pay_type,
                                "value",
                                effective_salary.pay_type,
                            )
                        ),  # type: ignore[arg-type]
                        basic_rate=effective_salary.basic_rate,
                        overtime_rate=effective_salary.overtime_rate,
                        # Despite the legacy column name, this field stores
                        # minutes (normally 480), as documented in the HRIS
                        # data model. Do not convert it from hours again.
                        scheduled_minutes=shift.total_hours_minus_lunch,
                        worked_minutes=worked_minutes,
                        overtime_eligible_minutes=eligible_ot,
                        overtime_approved_minutes=approved_ot,
                        paid_absence=(paid_leave or paid_holiday) and dtr is None,
                        absence=bool(
                            (dtr and dtr.is_absent)
                            or (
                                dtr is None
                                and resolved_no_punch_day
                                and not (paid_leave or paid_holiday)
                            )
                        ),
                    )
                )
            except (
                CalculationBlocker,
                KeyError,
                InvalidOperation,
                TypeError,
                ValueError,
            ) as exc:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="calculation_input_invalid",
                        message=str(exc),
                        work_date=cursor,
                    )
                )
                break
            if dtr:
                refs.append(f"attendance:{dtr.id}:revision:{dtr.interval_revision}")
            refs.append(
                f"salary:{effective_salary.id}:effective:{effective_salary.effective_date}"
            )
            refs.append(f"shift-assignment:{effective_assignment.id}")
            refs.append(f"policy:{policy.id}:v{policy.version}")
            formulas.append(
                f"{cursor}: {effective_salary.pay_type.value} basis; {worked_minutes} worked minutes; {approved_ot} of {eligible_ot} overtime minutes approved"
            )
            cursor += timedelta(days=1)

        for (monthly_divisor, partial_rule, multiplier, rounding), days in (
            calculation_groups.items()
        ):
            if blockers:
                break
            try:
                results.append(
                    calculate_attendance_earnings(
                        days,
                        monthly_divisor=monthly_divisor,
                        daily_partial_work=partial_rule,  # type: ignore[arg-type]
                        overtime_multiplier=multiplier,
                        rounding=rounding,
                    )
                )
            except CalculationBlocker as exc:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="calculation_input_invalid",
                        message=str(exc),
                    )
                )

        regular = sum((result.regular for result in results), Decimal("0.00"))
        overtime = sum((result.overtime for result in results), Decimal("0.00"))
        attendance_deduction = sum(
            (result.attendance_deduction for result in results), Decimal("0.00")
        )
        previews.append(
            PayrollAttendanceCalculationEntry(
                employee_id=employee_entry.employee_id,
                employee_code=employee_entry.employee_code,
                employee_name=employee_entry.employee_name,
                regular_earnings=regular if not blockers else None,
                approved_overtime=overtime if not blockers else None,
                attendance_deduction=attendance_deduction if not blockers else None,
                gross_before_statutory=regular + overtime if not blockers else None,
                blockers=blockers,
                formula=formulas,
                source_references=sorted(set(refs)),
            )
        )
    return PayrollAttendanceCalculationPreview(
        pay_group_id=pay_group_id,
        date_from=date_from,
        date_to=date_to,
        entries=previews,
        count=roster.count,
        has_more=roster.has_more,
    )


@router.post(
    "/runs/prepare-attendance-draft",
    response_model=PayrollRunRead,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def prepare_attendance_payroll_draft(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    obj_in: PayrollAttendancePrepareRequest,
    response: Response,
) -> PayrollRunRead:
    """Persist a bounded, traceable draft; statutory blockers prevent approval.

    Earnings and deductions remain provisional until the employer completes
    statutory and HR acceptance. Finalization is separately disabled by a
    default-off setting while that acceptance is outstanding.
    """
    if obj_in.date_from > obj_in.date_to:
        raise HTTPException(
            status_code=422, detail="date_from must be on or before date_to"
        )
    # Serialize preparation for the same pay-group period even when no run row
    # exists yet; the unique run identity is enforced inside the transaction.
    lock_key = int.from_bytes(
        hashlib.sha256(
            f"{obj_in.pay_group_id}:{obj_in.date_from}:{obj_in.date_to}:regular".encode()
        ).digest()[:8],
        "big",
        signed=True,
    )
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    existing = session.exec(
        select(PayrollRun)
        .where(
            PayrollRun.pay_group_id == obj_in.pay_group_id,
            PayrollRun.date_from == obj_in.date_from,
            PayrollRun.date_to == obj_in.date_to,
            PayrollRun.adjustment_type == "regular",
            col(PayrollRun.is_deleted).is_(False),
            col(PayrollRun.status) != PayrollRunStatus.VOID,
        )
        .with_for_update()
    ).first()
    if existing is not None:
        response.status_code = 200
        entries = session.exec(
            select(PayrollEntry).where(
                PayrollEntry.payroll_run_id == existing.id,
                col(PayrollEntry.is_deleted).is_(False),
            )
        ).all()
        return PayrollRunRead.model_validate(
            existing,
            update={
                "entries": [PayrollEntryRead.model_validate(entry) for entry in entries]
            },
        )

    roster = preflight_payroll_run(
        session=session,
        pay_group_id=obj_in.pay_group_id,
        date_from=obj_in.date_from,
        date_to=obj_in.date_to,
        skip=0,
        limit=200,
    )
    if roster.has_more or roster.count > 200:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "This period exceeds the 200-employee atomic preparation limit; split the pay group or use a supported batch workflow.",
                "expected_employees": roster.count,
            },
        )
    if roster.count == 0:
        raise HTTPException(
            status_code=409,
            detail="No employees are expected in this pay group and period",
        )
    previews = attendance_calculation_preview(
        session=session,
        pay_group_id=obj_in.pay_group_id,
        date_from=obj_in.date_from,
        date_to=obj_in.date_to,
        skip=0,
        limit=200,
    )
    group = session.get(PayrollPayGroup, obj_in.pay_group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Pay group not found")
    policies = session.exec(
        select(PayrollPolicyVersion)
        .where(
            PayrollPolicyVersion.effective_from <= obj_in.date_to,
            (col(PayrollPolicyVersion.effective_to).is_(None))
            | (col(PayrollPolicyVersion.effective_to) >= obj_in.date_from),
        )
        .order_by(col(PayrollPolicyVersion.effective_from))
    ).all()
    if len(policies) != 1 or not policies[0].confirmed:
        raise HTTPException(
            status_code=409,
            detail="Exactly one confirmed payroll policy must cover the prepared period",
        )
    policy = policies[0]
    configured_periods = list_pay_group_periods(
        session=session,
        group_id=obj_in.pay_group_id,
        month=obj_in.date_from.strftime("%Y-%m"),
    )

    period = next(
        (
            candidate
            for candidate in configured_periods
            if _same_calendar_day(candidate.date_from, obj_in.date_from)
            and _same_calendar_day(candidate.date_to, obj_in.date_to)
        ),
        None,
    )
    if period is None:
        raise HTTPException(
            status_code=422,
            detail="Date range must match a complete configured pay-group period",
        )

    month_start = obj_in.date_to.replace(day=1)
    month_end = month_start.replace(
        day=calendar.monthrange(month_start.year, month_start.month)[1]
    )
    full_month_previews: dict[uuid.UUID, PayrollAttendanceCalculationEntry] = {}
    if obj_in.date_to == month_end:
        # The preview endpoint accepts only complete configured earning
        # periods. Build the statutory monthly basis from those slices instead
        # of asking it to evaluate an invalid all-month range for a split-pay
        # group.
        for configured_period in configured_periods:
            slice_preview = attendance_calculation_preview(
                session=session,
                pay_group_id=obj_in.pay_group_id,
                date_from=date.fromisoformat(str(configured_period.date_from)[:10]),
                date_to=date.fromisoformat(str(configured_period.date_to)[:10]),
                skip=0,
                limit=200,
            )
            for entry in slice_preview.entries:
                previous = full_month_previews.get(entry.employee_id)
                if previous is None:
                    full_month_previews[entry.employee_id] = entry
                    continue
                full_month_previews[entry.employee_id] = PayrollAttendanceCalculationEntry(
                    employee_id=entry.employee_id,
                    employee_code=entry.employee_code,
                    employee_name=entry.employee_name,
                    regular_earnings=(
                        previous.regular_earnings + entry.regular_earnings
                        if previous.regular_earnings is not None
                        and entry.regular_earnings is not None
                        else None
                    ),
                    approved_overtime=(
                        previous.approved_overtime + entry.approved_overtime
                        if previous.approved_overtime is not None
                        and entry.approved_overtime is not None
                        else None
                    ),
                    attendance_deduction=(
                        previous.attendance_deduction + entry.attendance_deduction
                        if previous.attendance_deduction is not None
                        and entry.attendance_deduction is not None
                        else None
                    ),
                    gross_before_statutory=(
                        previous.gross_before_statutory + entry.gross_before_statutory
                        if previous.gross_before_statutory is not None
                        and entry.gross_before_statutory is not None
                        else None
                    ),
                    blockers=[*previous.blockers, *entry.blockers],
                    formula=[*previous.formula, *entry.formula],
                    source_references=sorted(
                        set(previous.source_references + entry.source_references)
                    ),
                )

    now = datetime.now(timezone.utc)
    run = PayrollRun(
        cutoff_type={
            "daily": CutoffType.DAILY,
            "semi_monthly": CutoffType.SEMI_MONTHLY,
            "monthly": CutoffType.MONTHLY,
        }[group.cadence.value],
        date_from=obj_in.date_from,
        date_to=obj_in.date_to,
        created_by=current_user.id,
        pay_group_id=group.id,
        policy_version_id=policy.id,
        workflow_status="draft",
        generation_fingerprint=hashlib.sha256(
            f"attendance-v1:{group.id}:{obj_in.date_from}:{obj_in.date_to}".encode()
        ).hexdigest(),
        updated_at=now,
    )
    session.add(run)
    session.flush()
    preview_by_employee = {entry.employee_id: entry for entry in previews.entries}
    for roster_entry in roster.entries:
        preview = preview_by_employee.get(roster_entry.employee_id)
        blockers = list(roster_entry.blockers)
        if preview is None:
            blockers.append(
                PayrollPreflightBlocker(
                    code="calculation_missing",
                    message="Attendance calculation did not return this expected employee.",
                )
            )
        else:
            blockers.extend(preview.blockers)
        employee_salaries = session.exec(
            select(EmployeeSalary)
            .where(
                EmployeeSalary.employee_id == roster_entry.employee_id,
                EmployeeSalary.effective_date <= obj_in.date_to,
                col(EmployeeSalary.is_active).is_(True),
                col(EmployeeSalary.is_deleted).is_(False),
            )
            .order_by(col(EmployeeSalary.effective_date))
        ).all()
        if not employee_salaries:
            blockers.append(
                PayrollPreflightBlocker(
                    code="salary_missing",
                    message="An effective salary is required to calculate this employee's payroll.",
                )
            )
        else:
            effective_salary_for_period = employee_salaries[-1]
            if effective_salary_for_period.non_taxable_allowance or effective_salary_for_period.de_minimis_monthly:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="allowance_tax_treatment_unavailable",
                        message="Allowance and de minimis tax treatment must be configured before this employee can be calculated.",
                    )
                )
        salary_refs = [
            {
                "id": str(salary.id),
                "updated_at": salary.updated_at.isoformat()
                if salary.updated_at
                else None,
                "basic_rate": str(salary.basic_rate),
            }
            for salary in employee_salaries
        ]
        monthly_contributions: dict[str, Any] | None = None
        final_period_of_month = obj_in.date_to.day == calendar.monthrange(
            obj_in.date_to.year, obj_in.date_to.month
        )[1]
        if final_period_of_month:
            month_start = obj_in.date_to.replace(day=1)
            effective_salary = employee_salaries[-1] if employee_salaries else None
            if effective_salary is None:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="monthly_contribution_salary_missing",
                        message="A monthly salary is required to calculate this employee's once-monthly statutory contributions.",
                    )
                )
            else:
                try:
                    full_month = full_month_previews.get(roster_entry.employee_id)
                    if full_month is None:
                        raise StatutoryScheduleUnavailable(
                            "Full-month attendance calculation did not return this employee"
                        )
                    if full_month.blockers:
                        raise StatutoryScheduleUnavailable(
                            "Resolve the full month's attendance and overtime blockers before assessing SSS compensation"
                        )
                    if effective_salary.non_taxable_allowance or effective_salary.de_minimis_monthly:
                        raise StatutoryScheduleUnavailable(
                            "Additional allowances need an approved scheme-specific contribution treatment"
                        )
                    sss_basis = (
                        full_month.regular_earnings
                        + full_month.approved_overtime
                        if full_month.regular_earnings is not None
                        and full_month.approved_overtime is not None
                        else None
                    )
                    if sss_basis is None or sss_basis <= 0:
                        raise StatutoryScheduleUnavailable(
                            "Full-month regular and approved overtime earnings are required for the SSS compensation basis"
                        )
                    pagibig_basis = sss_basis
                    policy_sources = policy.policy.get("statutory_sources_reviewed", [])
                    if not isinstance(policy_sources, list):
                        raise StatutoryScheduleUnavailable(
                            "Confirmed payroll policy has no reviewed statutory source list"
                        )
                    month_policy_rows = session.exec(
                        select(PayrollPolicyVersion).where(
                            PayrollPolicyVersion.effective_from <= obj_in.date_to,
                            (col(PayrollPolicyVersion.effective_to).is_(None))
                            | (col(PayrollPolicyVersion.effective_to) >= month_start),
                            col(PayrollPolicyVersion.confirmed).is_(True),
                        )
                    ).all()
                    divisors = {
                        Decimal(str(row.policy["monthly_divisor"]))
                        for row in month_policy_rows
                        if row.policy.get("monthly_divisor") is not None
                    }
                    if len(divisors) != 1:
                        raise StatutoryScheduleUnavailable(
                            "One confirmed monthly divisor must apply throughout the contribution month for daily/hourly PhilHealth conversion"
                        )
                    philhealth_basis = _philhealth_monthly_basic_salary_basis(
                        session=session,
                        employee_id=roster_entry.employee_id,
                        salaries=employee_salaries,
                        contribution_month=month_start,
                        monthly_divisor=next(iter(divisors)),
                    )
                    if philhealth_basis <= 0:
                        raise StatutoryScheduleUnavailable(
                            "A positive contractual monthly basic-salary equivalent is required for PhilHealth"
                        )
                    monthly_contributions = _monthly_contribution_snapshot(
                        session=session,
                        sss_monthly_compensation=sss_basis,
                        philhealth_basic_salary=philhealth_basis,
                        pagibig_monthly_salary=pagibig_basis,
                        contribution_month=month_start,
                        source_urls=policy_sources,
                    )
                    monthly_contributions["basis_method"] = {
                        "sss": "actual full-month regular earnings plus approved overtime; indexed by the effective SSS schedule",
                        "philhealth": (
                            "contractual fixed-basic monthly equivalent; monthly salary is weighted by calendar days, while daily/hourly rates use the confirmed monthly divisor and effective scheduled shift minutes; overtime and absence deductions excluded"
                        ),
                        "pagibig": "full-month regular earnings plus approved overtime; allowances remain blocked until their fund-salary treatment is configured",
                    }
                except StatutoryScheduleUnavailable as exc:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="statutory_schedule_unavailable",
                            message=str(exc),
                        )
                    )
        tax_declaration = session.exec(
            select(EmployeeTaxYearDeclaration).where(
                EmployeeTaxYearDeclaration.employee_id == roster_entry.employee_id,
                EmployeeTaxYearDeclaration.tax_year == obj_in.date_to.year,
            )
        ).first()
        if tax_declaration is None:
            blockers.append(
                PayrollPreflightBlocker(
                    code="bir_ytd_unavailable",
                    message="Enter and verify this employee's tax classification and opening year-to-date amounts before payroll review.",
                )
            )
        elif not tax_declaration.is_verified:
            blockers.append(
                PayrollPreflightBlocker(
                    code="bir_ytd_unverified",
                    message="A payroll approver must verify this employee's tax-year declaration before calculation.",
                )
            )
        elif tax_declaration.tax_classification != "ordinary":
            blockers.append(
                PayrollPreflightBlocker(
                    code="bir_tax_classification_unsupported",
                    message="Minimum-wage-earner tax treatment requires verified eligibility and compensation-limit rules before calculation.",
                )
            )
        dtr_rows = session.exec(
            select(DailyTimeRecord)
            .where(
                DailyTimeRecord.employee_id == roster_entry.employee_id,
                col(DailyTimeRecord.is_deleted).is_(False),
                col(DailyTimeRecord.work_date).is_not(None),
                DailyTimeRecord.work_date >= obj_in.date_from,  # type: ignore[operator]
                DailyTimeRecord.work_date <= obj_in.date_to,  # type: ignore[operator]
            )
            .order_by(col(DailyTimeRecord.work_date))
        ).all()
        attendance_refs = [
            {
                "id": str(row.id),
                "interval_revision": row.interval_revision,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "overtime_decided_at": row.overtime_decided_at.isoformat()
                if row.overtime_decided_at
                else None,
            }
            for row in dtr_rows
        ]
        shift_rows = session.exec(
            select(EmployeeShiftAssignment).where(
                EmployeeShiftAssignment.employee_id == roster_entry.employee_id,
                col(EmployeeShiftAssignment.is_deleted).is_(False),
                EmployeeShiftAssignment.effective_from <= obj_in.date_to,
                (col(EmployeeShiftAssignment.effective_to).is_(None))
                | (col(EmployeeShiftAssignment.effective_to) >= obj_in.date_from),
            )
        ).all()
        shift_refs = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "shift_id": str(row.shift_id),
            }
            for row in shift_rows
        ]
        group_rows = session.exec(
            select(EmployeePayGroupAssignment).where(
                EmployeePayGroupAssignment.employee_id == roster_entry.employee_id,
                EmployeePayGroupAssignment.effective_from <= obj_in.date_to,
                (col(EmployeePayGroupAssignment.effective_to).is_(None))
                | (col(EmployeePayGroupAssignment.effective_to) >= obj_in.date_from),
            )
        ).all()
        group_refs = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "pay_group_id": str(row.pay_group_id),
            }
            for row in group_rows
        ]
        leave_rows = session.exec(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == roster_entry.employee_id,
                LeaveRequest.date_start <= obj_in.date_to,
                LeaveRequest.date_end >= obj_in.date_from,
                col(LeaveRequest.is_deleted).is_(False),
            )
        ).all()
        leave_refs = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "status": str(getattr(row.status, "value", row.status)),
            }
            for row in leave_rows
        ]
        holiday_rows = session.exec(
            select(HolidayInstance).where(
                HolidayInstance.observed_date >= obj_in.date_from,
                HolidayInstance.observed_date <= obj_in.date_to,
                col(HolidayInstance.is_active).is_(True),
                col(HolidayInstance.is_deleted).is_(False),
            )
        ).all()
        holiday_refs = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in holiday_rows
        ]
        snapshot: dict[str, Any] = {
            "attendance_revisions": attendance_refs,
            "salary_versions": salary_refs,
            "shift_assignments": shift_refs,
            "pay_group_assignments": group_refs,
            "leave_revisions": leave_refs,
            "holiday_revisions": holiday_refs,
            "policy_versions": [{"id": str(policy.id), "version": policy.version}],
            "employee_id": str(roster_entry.employee_id),
            "pay_group_id": str(group.id),
            "pay_group_cadence": group.cadence.value,
            "period": {
                "from": obj_in.date_from.isoformat(),
                "to": obj_in.date_to.isoformat(),
            },
        }
        if monthly_contributions is not None:
            snapshot["monthly_contributions"] = monthly_contributions
        if tax_declaration is not None:
            snapshot["tax_year_declaration"] = {
                "id": str(tax_declaration.id),
                "updated_at": tax_declaration.updated_at.isoformat()
                if tax_declaration.updated_at
                else None,
                "tax_classification": tax_declaration.tax_classification,
                "taxable_compensation_ytd": str(tax_declaration.taxable_compensation_ytd),
                "tax_withheld_ytd": str(tax_declaration.tax_withheld_ytd),
                "previous_employer_included": tax_declaration.previous_employer_included,
                "verified": tax_declaration.is_verified,
            }
        bir_period = group.cadence
        effective_bir_rows = session.exec(
            select(BIRBracket).where(
                BIRBracket.period == bir_period,
                BIRBracket.effective_date <= obj_in.date_to,
                col(BIRBracket.is_active).is_(True),
                col(BIRBracket.is_deleted).is_(False),
            ).order_by(col(BIRBracket.bracket_min))
        ).all()
        if effective_bir_rows:
            latest_bir_date = max(row.effective_date for row in effective_bir_rows)
            snapshot["bir_schedule"] = [
                {
                    "id": str(row.id),
                    "effective_date": row.effective_date.isoformat(),
                    "bracket_min": str(row.bracket_min),
                    "bracket_max": str(row.bracket_max) if row.bracket_max is not None else None,
                    "base_tax": str(row.base_tax),
                    "excess_rate": str(row.excess_rate),
                    "source_reference": row.source_reference,
                }
                for row in effective_bir_rows
                if row.effective_date == latest_bir_date
            ]
        regular = (
            preview.regular_earnings
            if preview and preview.regular_earnings is not None
            else Decimal("0.00")
        )
        overtime = (
            preview.approved_overtime
            if preview and preview.approved_overtime is not None
            else Decimal("0.00")
        )
        attendance_deduction = (
            preview.attendance_deduction
            if preview and preview.attendance_deduction is not None
            else Decimal("0.00")
        )
        gross = regular + overtime
        employee_statutory = {
            scheme: Decimal(str(values["employee"]))
            for scheme, values in monthly_contributions["schemes"].items()
        } if monthly_contributions is not None else {}
        employer_statutory = {
            scheme: Decimal(str(values["employer"]))
            for scheme, values in monthly_contributions["schemes"].items()
        } if monthly_contributions is not None else {}
        deductions: dict[str, Any] = {
            "attendance": str(attendance_deduction),
            "statutory": {key: str(value) for key, value in employee_statutory.items()},
            "employer_contributions": {key: str(value) for key, value in employer_statutory.items()},
        }
        deductions.update({f"{scheme}_employee": str(amount) for scheme, amount in employee_statutory.items()})
        total_deductions = attendance_deduction + sum(employee_statutory.values(), Decimal("0.00"))
        taxable_pay = (
            gross
            - attendance_deduction
            - sum(employee_statutory.values(), Decimal("0.00"))
        )
        bir_withholding = Decimal("0.00")
        if tax_declaration is not None and tax_declaration.is_verified and tax_declaration.tax_classification == "ordinary":
            if taxable_pay < 0:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="bir_taxable_compensation_negative",
                        message="Employee-side mandatory contributions exceed this period's gross earnings; BIR taxable compensation requires correction.",
                    )
                )
            else:
                try:
                    is_year_end = obj_in.date_to == date(
                        obj_in.date_to.year,
                        12,
                        calendar.monthrange(obj_in.date_to.year, 12)[1],
                    )
                    if is_year_end:
                        opening_as_of = tax_declaration.opening_as_of
                        employee_row = session.get(EmployeeRecords, roster_entry.employee_id)
                        if (
                            opening_as_of is None
                            or opening_as_of.year != obj_in.date_to.year
                            or opening_as_of >= obj_in.date_from
                        ):
                            blockers.append(
                                PayrollPreflightBlocker(
                                    code="bir_ytd_opening_date_invalid",
                                    message="Set a verified opening-balance date in this tax year, before the final payroll period.",
                                )
                            )
                            history_rows: list[dict[str, str]] = []
                            history_taxable = Decimal("0.00")
                            history_withheld = Decimal("0.00")
                            history_complete = False
                        else:
                            coverage_start = max(
                                opening_as_of + timedelta(days=1),
                                date(obj_in.date_to.year, 1, 1),
                                employee_row.date_hired
                                if employee_row and employee_row.date_hired
                                else date(obj_in.date_to.year, 1, 1),
                            )
                            (
                                history_rows,
                                history_taxable,
                                history_withheld,
                                history_complete,
                            ) = _bir_finalized_history(
                                session,
                                roster_entry.employee_id,
                                obj_in.date_to.year,
                                opening_as_of,
                                obj_in.date_from,
                                coverage_start,
                            )
                        if opening_as_of is not None and not history_complete:
                            blockers.append(
                                PayrollPreflightBlocker(
                                    code="bir_ytd_history_unavailable",
                                    message="Finalized payroll does not provide a complete tax-year history after the opening-balance date; reconcile the missing periods before the annual adjustment.",
                                )
                            )
                        elif opening_as_of is not None:
                            assert tax_declaration is not None
                            prior_taxable = (
                                tax_declaration.taxable_compensation_ytd
                                + history_taxable
                            )
                            prior_withheld = (
                                tax_declaration.tax_withheld_ytd + history_withheld
                            )
                            annual_taxable = prior_taxable + taxable_pay
                            annual_tax_due = calculate_annualized_compensation_tax(
                                annual_taxable
                            )
                            bir_withholding = annual_tax_due - prior_withheld
                            snapshot["bir_year_to_date_history"] = {
                                "opening_taxable_compensation": str(
                                    tax_declaration.taxable_compensation_ytd
                                ),
                                "opening_tax_withheld": str(
                                    tax_declaration.tax_withheld_ytd
                                ),
                                "opening_as_of": opening_as_of.isoformat(),
                                "coverage_start": coverage_start.isoformat(),
                                "finalized_entries": history_rows,
                                "finalized_taxable_compensation": str(history_taxable),
                                "finalized_tax_withheld": str(history_withheld),
                                "complete": history_complete,
                            }
                            snapshot["bir_calculation"] = {
                                "method": "annualized_rr_11_2018_2023_onward",
                                "taxable_compensation": str(taxable_pay),
                                "annual_taxable_compensation": str(annual_taxable),
                                "annual_tax_due": str(annual_tax_due),
                                "prior_tax_withheld": str(prior_withheld),
                                "withholding": str(bir_withholding),
                                "schedule_reference": "https://bir-cdn.bir.gov.ph/local/pdf/RR%20No.%2011-2018.pdf",
                                "year_end_adjustment_pending": False,
                            }
                    else:
                        bir_withholding = calculate_bir_tax(
                            session,
                            taxable_pay,
                            group.cadence.value,
                            obj_in.date_to.isoformat(),
                        )
                        snapshot["bir_calculation"] = {
                            "method": "periodic_annex_e",
                            "period_type": group.cadence.value,
                            "taxable_compensation": str(taxable_pay),
                            "withholding": str(bir_withholding),
                            "schedule_effective_date": obj_in.date_to.isoformat(),
                            "year_end_adjustment_pending": False,
                        }
                except StatutoryScheduleUnavailable as exc:
                    blockers.append(
                        PayrollPreflightBlocker(code="bir_schedule_unavailable", message=str(exc))
                    )
        if "bir_calculation" in snapshot:
            deductions["bir_withholding"] = str(bir_withholding)
            total_deductions += bir_withholding
        net_pay = gross - total_deductions
        if monthly_contributions is None:
            # The monthly deduction is collected in the final period only.
            # A non-final period has no contribution snapshot by design.
            deductions.update(
                {f"{scheme}_employee": "0.00" for scheme in ("sss", "philhealth", "pagibig")}
            )
        if net_pay < 0:
            blockers.append(
                PayrollPreflightBlocker(
                    code="negative_net_pay",
                    message="Calculated deductions exceed earnings; an authorized correction is required before review.",
                )
            )
        fingerprint = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        session.add(
            PayrollEntry(
                payroll_run_id=run.id,
                employee_id=roster_entry.employee_id,
                basic_rate=(
                    employee_salaries[-1].basic_rate
                    if employee_salaries
                    else Decimal("0.00")
                ),
                rate_date_from=obj_in.date_from,
                rate_date_to=obj_in.date_to,
                earnings={
                    "regular": str(regular),
                    "approved_overtime": str(overtime),
                    "provisional": True,
                },
                deductions=deductions,
                gross_pay=gross,
                total_deductions=total_deductions,
                net_pay=net_pay,
                overtime_pay=overtime,
                thirteenth_month=Decimal("0.00"),
                non_taxable_income=Decimal("0.00"),
                taxable_income=taxable_pay,
                review_state="blocked",
                calculation_version="attendance-v1-provisional",
                input_snapshot=snapshot,
                input_fingerprint=fingerprint,
                blockers=[
                    item.model_dump(mode="json", exclude_none=True) for item in blockers
                ],
                created_at=now,
                updated_at=now,
            )
        )
    run_sources = []
    for roster_entry in roster.entries:
        calculation = preview_by_employee.get(roster_entry.employee_id)
        run_sources.append(
            (
                roster_entry.employee_id.hex,
                calculation.source_references if calculation else [],
            )
        )
    run.input_fingerprint = hashlib.sha256(
        json.dumps(
            sorted(run_sources),
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    session.add(run)
    session.commit()
    session.refresh(run)
    entries = session.exec(
        select(PayrollEntry)
        .where(
            PayrollEntry.payroll_run_id == run.id,
            col(PayrollEntry.is_deleted).is_(False),
        )
        .order_by(col(PayrollEntry.employee_id))
    ).all()
    return PayrollRunRead.model_validate(
        run,
        update={
            "entries": [PayrollEntryRead.model_validate(entry) for entry in entries]
        },
    )


@router.get(
    "/pay-group-assignments",
    response_model=list[EmployeePayGroupAssignmentPublic],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def list_pay_group_assignments(
    *,
    session: SessionDep,
    employee_id: uuid.UUID | None = None,
    as_of: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[EmployeePayGroupAssignmentPublic]:
    stmt = select(EmployeePayGroupAssignment)
    if employee_id is not None:
        stmt = stmt.where(EmployeePayGroupAssignment.employee_id == employee_id)
    if as_of is not None:
        stmt = stmt.where(
            EmployeePayGroupAssignment.effective_from <= as_of,
            (col(EmployeePayGroupAssignment.effective_to).is_(None))
            | (col(EmployeePayGroupAssignment.effective_to) >= as_of),
        )
    rows = session.exec(
        stmt.order_by(col(EmployeePayGroupAssignment.effective_from).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [EmployeePayGroupAssignmentPublic.model_validate(row) for row in rows]


@router.post(
    "/pay-group-assignments",
    response_model=EmployeePayGroupAssignmentPublic,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def create_pay_group_assignment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    obj_in: EmployeePayGroupAssignmentCreate,
) -> EmployeePayGroupAssignmentPublic:
    if obj_in.effective_to is not None and obj_in.effective_to < obj_in.effective_from:
        raise HTTPException(
            status_code=422, detail="effective_to must be on or after effective_from"
        )
    employee = session.exec(
        select(EmployeeRecords)
        .where(
            EmployeeRecords.id == obj_in.employee_id,
            col(EmployeeRecords.is_deleted).is_(False),
        )
        .with_for_update()
    ).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    group = session.get(PayrollPayGroup, obj_in.pay_group_id)
    if group is None or not group.is_active:
        raise HTTPException(status_code=404, detail="Active pay group not found")
    assignments = session.exec(
        select(EmployeePayGroupAssignment).where(
            EmployeePayGroupAssignment.employee_id == obj_in.employee_id
        )
    ).all()
    new_end = obj_in.effective_to or date.max
    for existing in assignments:
        old_end = existing.effective_to or date.max
        if obj_in.effective_from <= old_end and existing.effective_from <= new_end:
            raise HTTPException(
                status_code=409,
                detail=f"Pay group assignment overlaps existing assignment {existing.id}",
            )
    row = EmployeePayGroupAssignment.model_validate(
        obj_in, update={"assigned_by": current_user.id}
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return EmployeePayGroupAssignmentPublic.model_validate(row)


@router.patch(
    "/pay-group-assignments/{assignment_id}",
    response_model=EmployeePayGroupAssignmentPublic,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def close_pay_group_assignment(
    *,
    session: SessionDep,
    assignment_id: uuid.UUID,
    obj_in: EmployeePayGroupAssignmentUpdate,
) -> EmployeePayGroupAssignmentPublic:
    existing = session.get(EmployeePayGroupAssignment, assignment_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Pay group assignment not found")
    employee = session.exec(
        select(EmployeeRecords)
        .where(EmployeeRecords.id == existing.employee_id)
        .with_for_update()
    ).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    row = session.exec(
        select(EmployeePayGroupAssignment)
        .where(EmployeePayGroupAssignment.id == assignment_id)
        .with_for_update()
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Pay group assignment not found")
    if obj_in.effective_to < row.effective_from:
        raise HTTPException(
            status_code=422, detail="effective_to must not precede the assignment start"
        )
    later = session.exec(
        select(EmployeePayGroupAssignment)
        .where(
            EmployeePayGroupAssignment.employee_id == row.employee_id,
            EmployeePayGroupAssignment.effective_from > row.effective_from,
        )
        .order_by(col(EmployeePayGroupAssignment.effective_from))
        .limit(1)
    ).first()
    if later is not None and obj_in.effective_to >= later.effective_from:
        raise HTTPException(
            status_code=409, detail="effective_to overlaps the next assignment"
        )
    row.effective_to = obj_in.effective_to
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return EmployeePayGroupAssignmentPublic.model_validate(row)


@router.get(
    "/policies",
    response_model=list[PayrollPolicyVersionPublic],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def list_payroll_policies(
    *,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[PayrollPolicyVersionPublic]:
    rows = session.exec(
        select(PayrollPolicyVersion)
        .order_by(col(PayrollPolicyVersion.version).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [PayrollPolicyVersionPublic.model_validate(row) for row in rows]


@router.post(
    "/policies",
    response_model=PayrollPolicyVersionPublic,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def create_payroll_policy(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    obj_in: PayrollPolicyVersionCreate,
) -> PayrollPolicyVersionPublic:
    # Serialize version allocation across concurrent admins; locking the latest
    # row alone does not protect the empty-table case.
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 684219731})
    latest = session.exec(
        select(PayrollPolicyVersion)
        .order_by(col(PayrollPolicyVersion.version).desc())
        .limit(1)
        .with_for_update()
    ).first()
    version = 1 if latest is None else latest.version + 1
    if latest is not None:
        if obj_in.effective_from <= latest.effective_from:
            raise HTTPException(
                status_code=409,
                detail="Policy effective dates must advance; historical versions are not rewritten",
            )
        latest.effective_to = obj_in.effective_from - timedelta(days=1)
        session.add(latest)
    row = PayrollPolicyVersion(
        version=version,
        effective_from=obj_in.effective_from,
        policy=obj_in.policy,
        confirmed=False,
        created_by=current_user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return PayrollPolicyVersionPublic.model_validate(row)


@router.post(
    "/policies/{policy_id}/confirm",
    response_model=PayrollPolicyVersionPublic,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def confirm_payroll_policy(
    *, session: SessionDep, policy_id: uuid.UUID, current_user: CurrentUser
) -> PayrollPolicyVersionPublic:
    required = {
        "timezone",
        "monthly_divisor",
        "daily_partial_work",
        "paid_leave",
        "paid_holidays",
        "break_minutes",
        "grace_minutes",
        "overtime_rule",
        "premium_rules",
        "allowance_tax_treatment",
        "rounding_mode",
        "contribution_collection",
        "statutory_sources_reviewed",
    }
    row = session.exec(
        select(PayrollPolicyVersion)
        .where(PayrollPolicyVersion.id == policy_id)
        .with_for_update()
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Payroll policy not found")
    if row.confirmed:
        return PayrollPolicyVersionPublic.model_validate(row)
    missing = sorted(
        key for key in required if key not in row.policy or row.policy[key] is None
    )
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"message": "Policy is incomplete", "missing": missing},
        )
    sources = row.policy["statutory_sources_reviewed"]
    if (
        not isinstance(sources, list)
        or not sources
        or any(
            not isinstance(item, str) or not item.startswith("https://")
            for item in sources
        )
    ):
        raise HTTPException(
            status_code=422,
            detail="Confirmation requires HTTPS references to statutory sources reviewed",
        )
    try:
        ZoneInfo(str(row.policy["timezone"]))
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=422, detail="Policy timezone must be a valid IANA timezone"
        ) from exc
    try:
        divisor = Decimal(str(row.policy["monthly_divisor"]))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422, detail="monthly_divisor must be a positive number"
        ) from exc
    if divisor <= 0:
        raise HTTPException(
            status_code=422, detail="monthly_divisor must be a positive number"
        )
    for key in ("break_minutes", "grace_minutes"):
        if (
            not isinstance(row.policy[key], int)
            or isinstance(row.policy[key], bool)
            or row.policy[key] < 0
        ):
            raise HTTPException(
                status_code=422, detail=f"{key} must be a non-negative whole number"
            )
    for key in ("paid_leave", "paid_holidays"):
        if not isinstance(row.policy[key], bool):
            raise HTTPException(
                status_code=422, detail=f"{key} must be explicitly true or false"
            )
    if row.policy["daily_partial_work"] not in {"full_day", "pro_rated", "hours_based"}:
        raise HTTPException(
            status_code=422,
            detail="daily_partial_work must be full_day, pro_rated, or hours_based",
        )
    if row.policy["rounding_mode"] not in {"half_up", "half_even", "down"}:
        raise HTTPException(
            status_code=422, detail="rounding_mode must be half_up, half_even, or down"
        )
    for key in (
        "overtime_rule",
        "premium_rules",
        "allowance_tax_treatment",
        "contribution_collection",
    ):
        if not isinstance(row.policy[key], dict) or not row.policy[key]:
            raise HTTPException(
                status_code=422, detail=f"{key} must be a non-empty policy object"
            )
    # The selected company rule is one statutory collection per calendar
    # month. An explicit final-period trigger prevents a twice-monthly run
    # from withholding a full monthly amount twice.
    contribution_collection = row.policy["contribution_collection"]
    if (
        contribution_collection.get("frequency") != "once_monthly"
        or contribution_collection.get("collection_period") != "last_period"
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Contribution collection must be configured once per calendar month on the final pay period.",
                "required": {
                    "frequency": "once_monthly",
                    "collection_period": "last_period",
                },
            },
        )
    official_hosts = (
        "bir.gov.ph",
        "sss.gov.ph",
        "philhealth.gov.ph",
        "pagibigfund.gov.ph",
    )
    referenced_hosts = {urlparse(url).hostname or "" for url in sources}
    if any(
        not any(
            host == official or host.endswith(f".{official}")
            for host in referenced_hosts
        )
        for official in official_hosts
    ):
        raise HTTPException(
            status_code=422,
            detail="Include reviewed official sources for BIR, SSS, PhilHealth and Pag-IBIG",
        )
    schedule_errors = _statutory_schedule_errors(session, row.effective_from)
    if schedule_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Statutory schedules must be complete for the policy effective date.",
                "schedule_errors": schedule_errors,
            },
        )
    row.confirmed = True
    row.confirmed_by = current_user.id
    row.confirmed_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return PayrollPolicyVersionPublic.model_validate(row)


# --------------------------------------------------------------------------- #
# Government Contribution Calculator Endpoints (B4A.1)
# --------------------------------------------------------------------------- #


@router.get(
    "/sss-brackets/",
    response_model=list[SSSBracketRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_sss_brackets(
    *,
    session: SessionDep,
    effective_date: str | None = Query(
        default=None, description="Filter by effective date (ISO format)"
    ),
    include_deleted: bool = Query(default=False),
) -> list[SSSBracketRead]:
    """List all SSS brackets with optional effective-date filtering."""
    stmt = (
        select(SSSBracket)
        .where(SSSBracket.is_deleted == include_deleted)
        .order_by(SSSBracket.effective_date, SSSBracket.msc_max)  # type: ignore[arg-type]
    )
    if effective_date:
        eff = datetime.fromisoformat(effective_date).date()
        stmt = (
            select(SSSBracket)
            .where(
                SSSBracket.effective_date <= eff,
                SSSBracket.is_deleted == include_deleted,
            )
            .order_by(SSSBracket.effective_date, SSSBracket.msc_max)  # type: ignore[arg-type]
        )
    brackets = session.exec(stmt).all()
    return [SSSBracketRead.model_validate(b) for b in brackets]


@router.post(
    "/sss-brackets/",
    response_model=SSSBracketRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_sss_bracket(
    *,
    session: SessionDep,
    bracket: SSSBracketCreate,
) -> SSSBracketRead:
    """Create SSS contribution bracket."""
    db_bracket = SSSBracket.model_validate(bracket)
    session.add(db_bracket)
    session.commit()
    session.refresh(db_bracket)
    return SSSBracketRead.model_validate(db_bracket)


@router.get(
    "/sss-brackets/{bracket_id}",
    response_model=SSSBracketRead,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def get_sss_bracket(
    *,
    session: SessionDep,
    bracket_id: uuid.UUID,
) -> SSSBracketRead:
    """Get specific SSS bracket."""
    db_bracket = session.get(SSSBracket, bracket_id)
    if not db_bracket:
        raise HTTPException(status_code=404, detail="SSS bracket not found")
    return SSSBracketRead.model_validate(db_bracket)


@router.patch(
    "/sss-brackets/{bracket_id}",
    response_model=SSSBracketRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def update_sss_bracket(
    *,
    session: SessionDep,
    bracket_id: uuid.UUID,
    bracket: SSSBracketCreate,
) -> SSSBracketRead:
    """Update SSS bracket."""
    db_bracket = session.get(SSSBracket, bracket_id)
    if not db_bracket:
        raise HTTPException(status_code=404, detail="SSS bracket not found")

    for key, value in bracket.model_dump(exclude_unset=True).items():
        setattr(db_bracket, key, value)

    db_bracket.updated_at = datetime.now(timezone.utc)
    session.add(db_bracket)
    session.commit()
    session.refresh(db_bracket)
    return SSSBracketRead.model_validate(db_bracket)


@router.delete(
    "/sss-brackets/{bracket_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_sss_bracket(
    *,
    session: SessionDep,
    bracket_id: uuid.UUID,
) -> Message:
    """Delete SSS bracket (soft delete)."""
    db_bracket = session.get(SSSBracket, bracket_id)
    if not db_bracket:
        raise HTTPException(status_code=404, detail="SSS bracket not found")

    db_bracket.is_deleted = True
    db_bracket.deleted_at = datetime.now(timezone.utc)
    session.add(db_bracket)
    session.commit()

    return Message(message="SSS bracket deleted successfully")


# --- PhilHealth ---------------------------------------------------------------


@router.get(
    "/philhealth-brackets/",
    response_model=list[PhilHealthBracketRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_philhealth_brackets(
    *,
    session: SessionDep,
    _effective_date: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[PhilHealthBracketRead]:
    """List all PhilHealth brackets."""
    stmt = (
        select(PhilHealthBracket)
        .where(PhilHealthBracket.is_deleted == include_deleted)
        .order_by(PhilHealthBracket.effective_date, PhilHealthBracket.salary_max)  # type: ignore[arg-type]
    )
    brackets = session.exec(stmt).all()
    return [PhilHealthBracketRead.model_validate(b) for b in brackets]


@router.post(
    "/philhealth-brackets/",
    response_model=PhilHealthBracketRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_philhealth_bracket(
    *,
    session: SessionDep,
    bracket: PhilHealthBracketCreate,
) -> PhilHealthBracketRead:
    """Create PhilHealth bracket."""
    db_bracket = PhilHealthBracket.model_validate(bracket)
    session.add(db_bracket)
    session.commit()
    session.refresh(db_bracket)
    return PhilHealthBracketRead.model_validate(db_bracket)


# --- Pag-IBIG -----------------------------------------------------------------


@router.get(
    "/pagibig-brackets/",
    response_model=list[PagIBIGBracketRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_pagibig_brackets(
    *,
    session: SessionDep,
    _effective_date: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[PagIBIGBracketRead]:
    """List all Pag-IBIG brackets."""
    stmt = (
        select(PagIBIGBracket)
        .where(PagIBIGBracket.is_deleted == include_deleted)
        .order_by(PagIBIGBracket.effective_date, PagIBIGBracket.salary_max)  # type: ignore[arg-type]
    )
    brackets = session.exec(stmt).all()
    return [PagIBIGBracketRead.model_validate(b) for b in brackets]


@router.post(
    "/pagibig-brackets/",
    response_model=PagIBIGBracketRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_pagibig_bracket(
    *,
    session: SessionDep,
    bracket: PagIBIGBracketCreate,
) -> PagIBIGBracketRead:
    """Create Pag-IBIG bracket."""
    db_bracket = PagIBIGBracket.model_validate(bracket)
    session.add(db_bracket)
    session.commit()
    session.refresh(db_bracket)
    return PagIBIGBracketRead.model_validate(db_bracket)


# --- BIR -----------------------------------------------------------------------


@router.get(
    "/bir-brackets/",
    response_model=list[BIRBracketRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_bir_brackets(
    *,
    session: SessionDep,
    period_type: str = Query(
        default="monthly",
        description="Filter by payment period type (daily/weekly/semi_monthly/monthly)",
    ),
    effective_date: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[BIRBracketRead]:
    """List all BIR brackets with period type filtering."""
    stmt = (
        select(BIRBracket)
        .where(BIRBracket.is_deleted == include_deleted)
        .order_by(BIRBracket.effective_date, BIRBracket.bracket_min)  # type: ignore[arg-type]
    )
    if period_type:
        stmt = stmt.where(BIRBracket.period == period_type)
    if effective_date:
        eff = datetime.fromisoformat(effective_date).date()
        stmt = stmt.where(BIRBracket.effective_date <= eff)
    brackets = session.exec(stmt).all()
    return [BIRBracketRead.model_validate(b) for b in brackets]


@router.post(
    "/bir-brackets/",
    response_model=BIRBracketRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_bir_bracket(
    *,
    session: SessionDep,
    bracket: BIRBracketCreate,
) -> BIRBracketRead:
    """Create BIR bracket."""
    db_bracket = BIRBracket.model_validate(bracket)
    session.add(db_bracket)
    session.commit()
    session.refresh(db_bracket)
    return BIRBracketRead.model_validate(db_bracket)


# --------------------------------------------------------------------------- #
# Batch Contribution Calculation Endpoint
# --------------------------------------------------------------------------- #


@router.post("/calculate-contributions/")
async def calculate_contributions_endpoint(
    *,
    gross_pay: Decimal = Query(..., gt=0, description="Gross pay amount"),
    period_type: str = Query(
        default="monthly",
        description="Pay period type (daily/weekly/semi_monthly/monthly)",
    ),
    effective_date: str | None = Query(
        default=None, description="Optional effective date for rate lookup"
    ),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate all government contributions for a given gross pay amount."""
    try:
        result = calculate_all_contributions(
            session, gross_pay, period_type, effective_date
        )
    except StatutoryScheduleUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"contributions": {k: float(v) for k, v in result.items()}}


@router.post("/sss/calculate")
async def calculate_sss(
    *,
    monthly_compensation: Decimal | None = Query(default=None, gt=0),
    msc: Decimal | None = Query(
        default=None, gt=0, deprecated=True,
        description="Deprecated alias; this value is monthly compensation, not MSC",
    ),
    effective_date: str | None = Query(default=None),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate total SSS contribution from monthly compensation mapping."""
    if (monthly_compensation is None) == (msc is None):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of monthly_compensation or deprecated msc",
        )
    compensation = monthly_compensation if monthly_compensation is not None else msc
    assert compensation is not None
    try:
        employee = calculate_sss_employee_share(session, compensation, effective_date)
        employer = calculate_sss_employer_share(session, compensation, effective_date)
    except StatutoryScheduleUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "employee_share": float(employee),
        "employer_share": float(employer),
        "total": float(employee + employer),
    }


@router.post("/philhealth/calculate")
async def calculate_philhealth(
    *,
    salary: Decimal = Query(..., gt=0, description="Basic salary"),
    effective_date: str | None = Query(default=None),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate PhilHealth contribution (employee + employer)."""
    try:
        employee = calculate_philhealth_employee_share(session, salary, effective_date)
        employer = calculate_philhealth_employer_share(session, salary, effective_date)
    except StatutoryScheduleUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "employee_share": float(employee),
        "employer_share": float(employer),
        "total": float(employee + employer),
    }


@router.post("/pagibig/calculate")
async def calculate_pagibig(
    *,
    salary: Decimal = Query(..., gt=0, description="Basic salary"),
    effective_date: str | None = Query(default=None),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate Pag-IBIG contribution (employee + employer)."""
    try:
        employee = calculate_pagibig_employee_share(session, salary, effective_date)
        employer = calculate_pagibig_employer_share(session, salary, effective_date)
    except StatutoryScheduleUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "employee_share": float(employee),
        "employer_share": float(employer),
        "total": float(employee + employer),
    }


@router.post("/bir/calculate")
async def calculate_bir(
    *,
    taxable_income: Decimal = Query(..., gt=0, description="Taxable income"),
    period_type: str = Query(
        default="monthly", description="Pay period type for BIR bracket lookup"
    ),
    effective_date: date | None = Query(default=None),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate BIR withholding tax."""
    try:
        tax = calculate_bir_tax(
            session,
            taxable_income,
            period_type,
            effective_date.isoformat() if effective_date else None,
        )
    except StatutoryScheduleUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"tax_amount": float(tax)}


# --------------------------------------------------------------------------- #
# Payroll Run Management Endpoints (B4B.2)
# --------------------------------------------------------------------------- #


@router.post(
    "/runs/preview",
    response_model=PayrollPreviewResponse,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def preview_payroll_endpoint(
    *,
    _session: SessionDep,
    _request: PayrollPreviewRequest,
) -> PayrollPreviewResponse:
    """Reject the legacy calculator until the attendance-driven calculator is ready.

    The old implementation uses default shifts, capped DTR loading and broad
    exception suppression; returning amounts from it would be misleading.
    """
    raise HTTPException(
        status_code=409,
        detail="Payroll amount preview is unavailable while the legacy calculator is retired. Use the pay-group preflight to resolve blockers; amounts remain disabled until the attendance-driven calculator passes parallel review.",
    )


@router.post(
    "/runs/generate",
    response_model=PayrollRun,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def generate_payroll_endpoint(
    *,
    _session: SessionDep,
    _request: PayrollGenerateRequest,
    _current_user: CurrentUser,
) -> PayrollRun:
    """Do not persist amounts from the retired legacy calculator."""
    raise HTTPException(
        status_code=409,
        detail="Payroll generation is unavailable while the legacy calculator is retired. Resolve preflight blockers and wait for the attendance-driven calculator and independent review workflow.",
    )


@router.get(
    "/runs",
    response_model=list[PayrollRunRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_payroll_runs(
    *,
    session: SessionDep,
    created_by_id: uuid.UUID | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[PayrollRunRead]:
    """List all payroll runs with optional employee filtering."""
    from app.payroll.selectors import select_employee_payroll_runs

    runs = select_employee_payroll_runs(session, created_by_id, include_deleted)
    return [PayrollRunRead.model_validate(r) for r in runs]


@router.get(
    "/runs/{run_id}",
    response_model=PayrollRunRead,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def get_payroll_run(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
) -> PayrollRunRead:
    """Get specific payroll run with entries."""
    from app.payroll.selectors import select_payroll_run_with_entries

    run, entries = select_payroll_run_with_entries(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")

    entry_list = [PayrollEntryRead.model_validate(e) for e in entries]
    return PayrollRunRead.model_validate(run, update={"entries": entry_list})


@router.post(
    "/runs/{run_id}/approve",
    response_model=PayrollRunRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def approve_payroll_run(
    *,
    _session: SessionDep,
    run_id: uuid.UUID,
    _current_user: CurrentUser,
) -> PayrollRunRead:
    """Legacy approval is disabled until the attendance-driven review flow ships.

    Existing draft runs remain readable, but this endpoint cannot turn a preview
    into an approved/payable run. The replacement flow must verify policy
    versions, attendance, independent reviews and finalization snapshots first.
    """
    raise HTTPException(
        status_code=409,
        detail=(
            f"Payroll approval for run {run_id} is temporarily disabled. Use read-only preview; "
            "finalization will be enabled after attendance, policy and review "
            "controls are available."
        ),
    )


@router.post(
    "/runs/{run_id}/void",
    response_model=PayrollRunRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def void_payroll_run(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
    current_user: CurrentUser,
) -> PayrollRunRead:
    """Void payroll run (draft or approved only)."""
    from app.payroll.selectors import get_existing_singleton_payroll_run_for_voiding

    run = get_existing_singleton_payroll_run_for_voiding(
        session, run_id, current_user.id
    )

    if run.status not in [PayrollRunStatus.DRAFT, PayrollRunStatus.APPROVED]:
        raise HTTPException(
            status_code=400, detail="Only draft or approved payroll runs can be voided"
        )

    run.status = PayrollRunStatus.VOID
    run.updated_at = datetime.now(timezone.utc)
    run.deleted_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    session.refresh(run)

    return PayrollRunRead.model_validate(run)


@router.get(
    "/runs/status",
    response_model=PayrunStatusResponse,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def get_payroll_status_counts(
    *,
    session: SessionDep,
    created_by_id: uuid.UUID | None = Query(default=None),
) -> PayrunStatusResponse:
    """Get payroll status summary for dashboard."""
    counts = get_payroll_run_status_counts(session, created_by_id)
    return PayrunStatusResponse(**counts)


# --------------------------------------------------------------------------- #
# Employee Salary Management Endpoints
# --------------------------------------------------------------------------- #


@router.get(
    "/employees/{employee_id}/tax-year-declarations/{tax_year}",
    response_model=EmployeeTaxYearDeclarationPublic,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def get_employee_tax_year_declaration(
    *, session: SessionDep, employee_id: uuid.UUID, tax_year: int
) -> EmployeeTaxYearDeclarationPublic:
    if tax_year < 2000 or tax_year > 2200:
        raise HTTPException(status_code=422, detail="tax_year must be between 2000 and 2200")
    row = session.exec(
        select(EmployeeTaxYearDeclaration).where(
            EmployeeTaxYearDeclaration.employee_id == employee_id,
            EmployeeTaxYearDeclaration.tax_year == tax_year,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Tax-year declaration not found")
    return EmployeeTaxYearDeclarationPublic.model_validate(row)


@router.put(
    "/employees/{employee_id}/tax-year-declarations/{tax_year}",
    response_model=EmployeeTaxYearDeclarationPublic,
    dependencies=[Depends(require_permission("payroll", "approve"))],
)
def upsert_employee_tax_year_declaration(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    employee_id: uuid.UUID,
    tax_year: int,
    obj_in: EmployeeTaxYearDeclarationUpdate,
) -> EmployeeTaxYearDeclarationPublic:
    """Record reviewed tax classification and opening year-to-date totals."""
    if tax_year < 2000 or tax_year > 2200:
        raise HTTPException(status_code=422, detail="tax_year must be between 2000 and 2200")
    if obj_in.opening_as_of.year != tax_year or obj_in.opening_as_of > date.today():
        raise HTTPException(
            status_code=422,
            detail="opening_as_of must be a date in the declared tax year that is not in the future",
        )
    employee = session.exec(
        select(EmployeeRecords)
        .where(
            EmployeeRecords.id == employee_id,
            col(EmployeeRecords.is_deleted).is_(False),
        )
        .with_for_update()
    ).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    row = session.exec(
        select(EmployeeTaxYearDeclaration)
        .where(
            EmployeeTaxYearDeclaration.employee_id == employee_id,
            EmployeeTaxYearDeclaration.tax_year == tax_year,
        )
        .with_for_update()
    ).first()
    now = datetime.now(timezone.utc)
    if row is None:
        row = EmployeeTaxYearDeclaration(employee_id=employee_id, tax_year=tax_year)
    finalized = session.exec(
        select(PayrollRun.id)
        .where(
            col(PayrollEntry.payroll_run_id) == col(PayrollRun.id),
            PayrollEntry.employee_id == employee_id,
            PayrollRun.date_to >= date(tax_year, 1, 1),
            PayrollRun.date_to < date(tax_year + 1, 1, 1),
            PayrollRun.workflow_status == "finalized",
            col(PayrollRun.is_deleted).is_(False),
            col(PayrollEntry.is_deleted).is_(False),
        )
    ).first()
    if finalized:
        raise HTTPException(
            status_code=409,
            detail="Tax-year opening inputs are locked after payroll finalization; use the reasoned tax correction workflow.",
        )
    for key, value in obj_in.model_dump(exclude={"is_verified"}).items():
        setattr(row, key, value)
    row.is_verified = obj_in.is_verified
    row.verified_by = current_user.id if obj_in.is_verified else None
    row.verified_at = now if obj_in.is_verified else None
    row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    return EmployeeTaxYearDeclarationPublic.model_validate(row)


@router.get(
    "/employees/{employee_id}/salary",
    response_model=list[EmployeeSalaryRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_employee_salaries(
    employee_id: uuid.UUID,
    *,
    session: SessionDep,
    _effective_date: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[EmployeeSalaryRead]:
    """List all salary records for an employee with optional effective-date filtering."""
    stmt = select(EmployeeSalary).where(
        EmployeeSalary.employee_id == employee_id,
        EmployeeSalary.is_deleted == include_deleted,
    )
    if _effective_date:
        eff = datetime.fromisoformat(_effective_date).date()
        stmt = stmt.where(EmployeeSalary.effective_date <= eff)
    salaries = session.exec(stmt).all()
    return [EmployeeSalaryRead.model_validate(s) for s in salaries]


@router.get(
    "/salary-roster",
    response_model=PayrollSalaryRosterList,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def list_salary_roster(
    *,
    session: SessionDep,
    as_of: date | None = Query(default=None),
    missing_salary: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> PayrollSalaryRosterList:
    if as_of is None:
        as_of = datetime.now(ZoneInfo("Asia/Manila")).date()
    has_salary = (
        select(EmployeeSalary.id)
        .where(
            EmployeeSalary.employee_id == EmployeeRecords.id,
            EmployeeSalary.effective_date <= as_of,
            col(EmployeeSalary.is_active).is_(True),
            col(EmployeeSalary.is_deleted).is_(False),
        )
        .exists()
    )
    base = select(EmployeeRecords).where(
        col(EmployeeRecords.is_deleted).is_(False),
        EmployeeRecords.employee_status == "Active",
    )
    if missing_salary:
        base = base.where(~has_salary)
    statement = select(EmployeeRecords, has_salary.label("has_effective_salary")).where(
        col(EmployeeRecords.is_deleted).is_(False),
        EmployeeRecords.employee_status == "Active",
    )
    if missing_salary:
        statement = statement.where(~has_salary)
    rows = session.exec(
        statement.order_by(col(EmployeeRecords.employee_code)).offset(skip).limit(limit)
    ).all()
    count = session.exec(select(func.count()).select_from(base.subquery())).one()
    return PayrollSalaryRosterList(
        data=[
            PayrollSalaryRosterItem(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                first_name=employee.first_name,
                last_name=employee.last_name,
                employee_status=str(employee.employee_status.value),
                has_effective_salary=bool(has_salary_result),
            )
            for employee, has_salary_result in rows
        ],
        count=count,
    )


def _salary_bulk_fingerprint(request: EmployeeSalaryBulkRequest) -> str:
    body = request.model_dump(mode="json", exclude={"batch_id"})
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _salary_bulk_preflight(
    *, session: Session, request: EmployeeSalaryBulkRequest, actor_id: uuid.UUID
) -> EmployeeSalaryBulkPreflight:
    issues: list[EmployeeSalaryBulkIssue] = []
    seen: set[uuid.UUID] = set()
    ids = sorted({row.employee_id for row in request.rows}, key=str)
    employees = session.exec(
        select(EmployeeRecords)
        .where(
            col(EmployeeRecords.id).in_(ids),
            col(EmployeeRecords.is_deleted).is_(False),
            EmployeeRecords.employee_status == "Active",
        )
        .order_by(col(EmployeeRecords.id))
        .with_for_update()
    ).all()
    employee_by_id = {employee.id: employee for employee in employees}
    for index, row in enumerate(request.rows):
        if row.employee_id in seen:
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=row.employee_id,
                    code="duplicate_employee",
                    message="Select each employee only once in a salary batch.",
                )
            )
            continue
        seen.add(row.employee_id)
        if row.employee_id not in employee_by_id:
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=row.employee_id,
                    code="employee_unavailable",
                    message="Employee is missing, inactive, or unavailable.",
                )
            )
            continue
        existing = session.exec(
            select(EmployeeSalary.id).where(
                EmployeeSalary.employee_id == row.employee_id,
                EmployeeSalary.effective_date == request.effective_date,
                col(EmployeeSalary.is_deleted).is_(False),
            )
        ).first()
        if existing is not None:
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=row.employee_id,
                    code="effective_date_conflict",
                    message="A salary record already exists for this employee on the selected effective date.",
                )
            )
    fingerprint = _salary_bulk_fingerprint(request)
    batch = session.get(EmployeeSalaryBulkBatch, request.batch_id)
    if batch is not None and (
        batch.created_by != actor_id or batch.payload_fingerprint != fingerprint
    ):
        issues.append(
            EmployeeSalaryBulkIssue(
                row_index=0,
                employee_id=request.rows[0].employee_id,
                code="batch_identity_conflict",
                message="This batch identity was used by another request; start a new batch.",
            )
        )
    return EmployeeSalaryBulkPreflight(
        batch_id=request.batch_id,
        valid=not issues,
        requested=len(request.rows),
        issues=issues,
    )


@router.post(
    "/salaries/bulk/preflight",
    response_model=EmployeeSalaryBulkPreflight,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def preflight_salary_bulk(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: EmployeeSalaryBulkRequest,
) -> EmployeeSalaryBulkPreflight:
    return _salary_bulk_preflight(
        session=session, request=request, actor_id=current_user.id
    )


@router.post(
    "/salaries/bulk/commit",
    response_model=EmployeeSalaryBulkCommit,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def commit_salary_bulk(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: EmployeeSalaryBulkRequest,
) -> EmployeeSalaryBulkCommit:
    fingerprint = _salary_bulk_fingerprint(request)
    lock_key = int.from_bytes(request.batch_id.bytes[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    existing_batch = session.get(EmployeeSalaryBulkBatch, request.batch_id)
    if existing_batch is not None:
        if (
            existing_batch.created_by != current_user.id
            or existing_batch.payload_fingerprint != fingerprint
        ):
            raise HTTPException(
                status_code=409,
                detail="Salary batch identity is unavailable or was used with different data",
            )
        ids = [uuid.UUID(value) for value in existing_batch.result_salary_ids]
        rows = list(
            session.exec(
                select(EmployeeSalary).where(col(EmployeeSalary.id).in_(ids))
            ).all()
        )
        return EmployeeSalaryBulkCommit(
            batch_id=request.batch_id,
            replayed=True,
            salaries=[EmployeeSalaryRead.model_validate(row) for row in rows],
        )
    preflight = _salary_bulk_preflight(
        session=session, request=request, actor_id=current_user.id
    )
    if not preflight.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Salary batch has conflicts; no salaries were saved.",
                "issues": [issue.model_dump(mode="json") for issue in preflight.issues],
            },
        )
    rows = [
        EmployeeSalary(
            employee_id=item.employee_id,
            basic_rate=item.basic_rate,
            pay_type=item.pay_type,
            effective_date=request.effective_date,
            overtime_rate=item.overtime_rate,
            non_taxable_allowance=item.non_taxable_allowance,
            currency="PHP",
            is_active=True,
        )
        for item in request.rows
    ]
    session.add_all(rows)
    session.flush()
    batch = EmployeeSalaryBulkBatch(
        id=request.batch_id,
        payload_fingerprint=fingerprint,
        created_by=current_user.id,
        result_salary_ids=[str(row.id) for row in rows],
    )
    session.add(batch)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A salary changed while this batch was being saved; preflight again. No partial salaries were saved.",
        ) from exc
    return EmployeeSalaryBulkCommit(
        batch_id=request.batch_id,
        replayed=False,
        salaries=[EmployeeSalaryRead.model_validate(row) for row in rows],
    )


@router.get(
    "/salaries/{salary_id}",
    response_model=EmployeeSalaryRead,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def get_employee_salary(
    *,
    session: SessionDep,
    salary_id: uuid.UUID,
) -> EmployeeSalaryRead:
    """Get specific employee salary record."""
    salary = session.get(EmployeeSalary, salary_id)
    if not salary:
        raise HTTPException(status_code=404, detail="Employee salary not found")
    return EmployeeSalaryRead.model_validate(salary)


@router.post(
    "/employees/{employee_id}/salary",
    response_model=EmployeeSalaryRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_employee_salary(
    employee_id: uuid.UUID,
    *,
    session: SessionDep,
    salary: EmployeeSalaryCreate,
) -> EmployeeSalaryRead:
    """Create salary record for employee."""
    db_salary = EmployeeSalary.model_validate(salary)
    db_salary.employee_id = employee_id
    session.add(db_salary)
    session.commit()
    session.refresh(db_salary)
    return EmployeeSalaryRead.model_validate(db_salary)


@router.patch(
    "/salaries/{salary_id}",
    response_model=EmployeeSalaryRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def update_employee_salary(
    *,
    session: SessionDep,
    salary_id: uuid.UUID,
    salary: EmployeeSalaryUpdate,
) -> EmployeeSalaryRead:
    """Update employee salary record (sparse delta; untouched fields preserved)."""
    db_salary = session.get(EmployeeSalary, salary_id)
    if not db_salary:
        raise HTTPException(status_code=404, detail="Employee salary not found")

    for key, value in salary.model_dump(exclude_unset=True).items():
        setattr(db_salary, key, value)

    db_salary.updated_at = datetime.now(timezone.utc)
    session.add(db_salary)
    session.commit()
    session.refresh(db_salary)
    return EmployeeSalaryRead.model_validate(db_salary)


@router.delete(
    "/salaries/{salary_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_employee_salary(
    *,
    session: SessionDep,
    salary_id: uuid.UUID,
) -> Message:
    """Soft-delete an employee salary record. The employee remains intact;
    history is preserved via ``is_deleted`` / ``deleted_at``."""
    db_salary = session.get(EmployeeSalary, salary_id)
    if db_salary is None or db_salary.is_deleted:
        raise HTTPException(status_code=404, detail="Employee salary not found")

    db_salary.is_deleted = True
    db_salary.deleted_at = datetime.now(timezone.utc)
    session.add(db_salary)
    session.commit()
    return Message(message="Employee salary archived")


# --------------------------------------------------------------------------- #
# Loan Management Endpoints
# --------------------------------------------------------------------------- #


@router.post(
    "/loans/",
    response_model=LoanRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_loan(
    *,
    session: SessionDep,
    loan: LoanCreate,
) -> LoanRead:
    """Create employee loan."""
    db_loan = Loan.model_validate(loan)
    session.add(db_loan)
    session.commit()
    session.refresh(db_loan)
    return LoanRead.model_validate(db_loan)


@router.get(
    "/employees/{employee_id}/loans",
    response_model=list[LoanRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_employees_loans(
    employee_id: uuid.UUID,
    *,
    session: SessionDep,
    include_deleted: bool = Query(default=False),
) -> list[LoanRead]:
    """List loans for an employee."""
    stmt = select(Loan).where(
        Loan.employee_id == employee_id, Loan.is_deleted == include_deleted
    )
    loans = session.exec(stmt).all()
    return [LoanRead.model_validate(loan) for loan in loans]


@router.get(
    "/loans/{loan_id}",
    response_model=LoanRead,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def get_loan(
    *,
    session: SessionDep,
    loan_id: uuid.UUID,
) -> LoanRead:
    """Get specific loan."""
    loan = session.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return LoanRead.model_validate(loan)


@router.delete(
    "/loans/{loan_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_loan(
    *,
    session: SessionDep,
    loan_id: uuid.UUID,
) -> Message:
    """Delete loan (soft delete)."""
    loan = session.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    loan.is_deleted = True
    loan.deleted_at = datetime.now(timezone.utc)
    session.add(loan)
    session.commit()

    return Message(message="SSS bracket deleted successfully")


# --------------------------------------------------------------------------- #
# Loan Amortization Endpoints
# --------------------------------------------------------------------------- #


@router.post(
    "/loans/{loan_id}/amortizations",
    response_model=list[LoanAmortizationRead],
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_amortization_schedule(
    loan_id: uuid.UUID,
    start_date: str = Query(..., description="Loan start date (ISO format)"),
    *,
    session: SessionDep,
    _current_user: CurrentUser,
) -> list[LoanAmortizationRead]:
    """Create amortization schedule for a loan."""
    from app.payroll.services import create_or_complete_loan_amortization_schedule

    amortization_records = create_or_complete_loan_amortization_schedule(
        session, loan_id, start_date
    )
    return [LoanAmortizationRead.model_validate(a) for a in amortization_records]


@router.get(
    "/loans/{loan_id}/amortizations",
    response_model=list[LoanAmortizationRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_amortizations(
    loan_id: uuid.UUID,
    *,
    session: SessionDep,
    include_paid: bool = Query(default=False),
) -> list[LoanAmortizationRead]:
    """List amortizations for a loan."""
    stmt = select(LoanAmortization).where(LoanAmortization.loan_id == loan_id)
    if not include_paid:
        stmt = stmt.where(LoanAmortization.is_paid.is_(False))  # type: ignore[attr-defined]
    stmt = stmt.order_by(LoanAmortization.due_date)  # type: ignore[arg-type]
    amortizations = session.exec(stmt).all()
    return [LoanAmortizationRead.model_validate(a) for a in amortizations]


@router.post(
    "/amortizations/{amortization_id}/pay",
    response_model=LoanAmortizationRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def pay_amortization(
    *,
    session: SessionDep,
    amortization_id: uuid.UUID,
) -> LoanAmortizationRead:
    """Mark amortization as paid."""
    amortization = session.get(LoanAmortization, amortization_id)
    if not amortization:
        raise HTTPException(status_code=404, detail="Amortization not found")
    if amortization.is_paid:
        raise HTTPException(status_code=400, detail="Amortization already paid")

    amortization.is_paid = True
    amortization.paid_date = datetime.now(timezone.utc).date()
    session.add(amortization)
    session.commit()
    session.refresh(amortization)
    return LoanAmortizationRead.model_validate(amortization)


# --------------------------------------------------------------------------- #
# Integration Platform Endpoints (B4A.2)
# --------------------------------------------------------------------------- #


@router.get(
    "/integrations",
    response_model=list[FleetIntegrationConfigRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_integrations(
    *,
    session: SessionDep,
    include_deleted: bool = Query(default=False),
) -> list[FleetIntegrationConfigRead]:
    """List all integration configs."""
    stmt = (
        select(IntegrationConfig)
        .where(IntegrationConfig.is_deleted == include_deleted)
        .order_by(IntegrationConfig.name)
    )
    configs = session.exec(stmt).all()
    return [FleetIntegrationConfigRead.model_validate(c) for c in configs]


@router.get(
    "/integrations/{config_id}",
    response_model=FleetIntegrationConfigRead,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def get_integration(
    *,
    session: SessionDep,
    config_id: uuid.UUID,
) -> FleetIntegrationConfigRead:
    """Get specific integration config."""
    config = session.get(IntegrationConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Integration not found")
    return FleetIntegrationConfigRead.model_validate(config)


@router.post(
    "/integrations",
    response_model=FleetIntegrationConfigRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_integration(
    *,
    session: SessionDep,
    config: IntegrationConfigCreate,
) -> FleetIntegrationConfigRead:
    """Create integration config."""
    db_config = IntegrationConfig.model_validate(config)
    session.add(db_config)
    session.commit()
    session.refresh(db_config)
    return FleetIntegrationConfigRead.model_validate(db_config)


@router.patch(
    "/integrations/{config_id}",
    response_model=FleetIntegrationConfigRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def update_integration(
    *,
    session: SessionDep,
    config_id: uuid.UUID,
    config: IntegrationConfigUpdate,
) -> FleetIntegrationConfigRead:
    """Update integration config."""
    db_config = session.get(IntegrationConfig, config_id)
    if not db_config:
        raise HTTPException(status_code=404, detail="Integration not found")

    for key, value in config.model_dump(exclude_unset=True).items():
        setattr(db_config, key, value)

    db_config.updated_at = datetime.now(timezone.utc)
    session.add(db_config)
    session.commit()
    session.refresh(db_config)
    return FleetIntegrationConfigRead.model_validate(db_config)


@router.delete(
    "/integrations/{config_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_integration(
    *,
    session: SessionDep,
    config_id: uuid.UUID,
) -> Message:
    """Delete integration config (soft delete)."""
    db_config = session.get(IntegrationConfig, config_id)
    if not db_config:
        raise HTTPException(status_code=404, detail="Integration not found")

    db_config.is_deleted = True
    db_config.deleted_at = datetime.now(timezone.utc)
    session.add(db_config)
    session.commit()
    return Message(message="SSS bracket deleted successfully")


# --- Integration mappings ------------------------------------------------------


@router.get(
    "/integrations/{config_id}/mappings",
    response_model=list[FleetIntegrationMappingRead],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_integration_mappings(
    config_id: uuid.UUID,
    *,
    session: SessionDep,
    include_deleted: bool = Query(default=False),
) -> list[FleetIntegrationMappingRead]:
    """List field mappings for an integration config."""
    stmt = select(IntegrationMapping).where(
        IntegrationMapping.integration_config_id == config_id,
        IntegrationMapping.is_deleted == include_deleted,
    )
    mappings = session.exec(stmt).all()
    return [FleetIntegrationMappingRead.model_validate(m) for m in mappings]


@router.post(
    "/integrations/{config_id}/mappings",
    response_model=FleetIntegrationMappingRead,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
async def create_integration_mapping(
    config_id: uuid.UUID,
    *,
    session: SessionDep,
    mapping: IntegrationMappingCreate,
) -> FleetIntegrationMappingRead:
    """Create field mapping for an integration config."""
    db_mapping = IntegrationMapping.model_validate(mapping)
    db_mapping.integration_config_id = config_id
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    return FleetIntegrationMappingRead.model_validate(db_mapping)


@router.patch(
    "/integrations/mappings/{mapping_id}",
    response_model=FleetIntegrationMappingRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def update_integration_mapping(
    *,
    session: SessionDep,
    mapping_id: uuid.UUID,
    mapping: IntegrationMappingUpdate,
) -> FleetIntegrationMappingRead:
    """Update field mapping."""
    db_mapping = session.get(IntegrationMapping, mapping_id)
    if not db_mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    for key, value in mapping.model_dump(exclude_unset=True).items():
        setattr(db_mapping, key, value)

    db_mapping.updated_at = datetime.now(timezone.utc)
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    return FleetIntegrationMappingRead.model_validate(db_mapping)


@router.delete(
    "/integrations/mappings/{mapping_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_integration_mapping(
    *,
    session: SessionDep,
    mapping_id: uuid.UUID,
) -> Message:
    """Delete field mapping (soft delete)."""
    db_mapping = session.get(IntegrationMapping, mapping_id)
    if not db_mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    db_mapping.is_deleted = True
    db_mapping.deleted_at = datetime.now(timezone.utc)
    session.add(db_mapping)
    session.commit()
    return Message(message="SSS bracket deleted successfully")


# --------------------------------------------------------------------------- #
# Payslip Endpoints (B4B.2f)
# --------------------------------------------------------------------------- #


@router.get(
    "/runs/{run_id}/payslips",
    response_model=list[PayrollPayslipPublic],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def list_payslips_for_run(
    *,
    session: SessionDep,
    run_id: uuid.UUID,
) -> list[PayrollPayslipPublic]:
    """Generate payslip data for all employees in a payroll run."""
    from app.payroll.selectors import select_payroll_run_with_entries

    run, entries = select_payroll_run_with_entries(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")

    payslips: list[PayrollPayslipPublic] = []
    for entry in entries:
        employee_name = None
        if entry.employee_id:
            emp = session.get(EmployeeRecords, entry.employee_id)
            if emp:
                employee_name = f"{emp.first_name} {emp.last_name}"

        payslips.append(
            PayrollPayslipPublic(
                run_id=run.id,
                employee_id=entry.employee_id,
                employee_name=employee_name,
                cutoff_type=run.cutoff_type.value,
                date_from=run.date_from,
                date_to=run.date_to,
                basic_rate=entry.basic_rate,
                rate_date_from=entry.rate_date_from,
                rate_date_to=entry.rate_date_to,
                earnings=entry.earnings,
                deductions=entry.deductions,
                gross_pay=entry.gross_pay,
                total_deductions=entry.total_deductions,
                net_pay=entry.net_pay,
                overtime_pay=entry.overtime_pay,
                thirteenth_month=entry.thirteenth_month,
                non_taxable_income=entry.non_taxable_income,
                taxable_income=entry.taxable_income,
                status=run.status.value,
            )
        )
    return payslips


@router.get(
    "/employees/{employee_id}/payslip",
    response_model=PayrollPayslipPublic | None,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
async def get_employee_payslip_for_latest_run(
    *,
    session: SessionDep,
    employee_id: uuid.UUID,
) -> PayrollPayslipPublic | None:
    from app.payroll.selectors import (  # isort:skip
        select_employee_payroll_runs,
        select_payroll_run_with_entries,
    )

    runs = select_employee_payroll_runs(session, include_deleted=False)
    runs = [
        run for run in runs
        if run.workflow_status == "finalized"
        or run.status in {PayrollRunStatus.APPROVED, PayrollRunStatus.PAID}
    ]
    matching_runs = []
    for run in runs:
        _, entries = select_payroll_run_with_entries(
            session, run.id, include_deleted=False
        )
        if any(e.employee_id == employee_id for e in entries):
            matching_runs.append(run)

    if not matching_runs:
        return None

    latest_run = max(matching_runs, key=lambda r: r.created_at or datetime.min)
    _, entries = select_payroll_run_with_entries(
        session, latest_run.id, include_deleted=False
    )
    entry = next((e for e in entries if e.employee_id == employee_id), None)
    if not entry:
        return None

    employee_name = None
    emp = session.get(EmployeeRecords, employee_id)
    if emp:
        employee_name = f"{emp.first_name} {emp.last_name}"

    return PayrollPayslipPublic(
        run_id=latest_run.id,
        employee_id=employee_id,
        employee_name=employee_name,
        cutoff_type=latest_run.cutoff_type.value,
        date_from=latest_run.date_from,
        date_to=latest_run.date_to,
        basic_rate=entry.basic_rate,
        rate_date_from=entry.rate_date_from,
        rate_date_to=entry.rate_date_to,
        earnings=entry.earnings,
        deductions=entry.deductions,
        gross_pay=entry.gross_pay,
        total_deductions=entry.total_deductions,
        net_pay=entry.net_pay,
        overtime_pay=entry.overtime_pay,
        thirteenth_month=entry.thirteenth_month,
        non_taxable_income=entry.non_taxable_income,
        taxable_income=entry.taxable_income,
        status=latest_run.status.value,
    )


# --------------------------------------------------------------------------- #
# Routes Integration
# --------------------------------------------------------------------------- #

routers = [router]


@router.patch(
    "/philhealth-brackets/{bracket_id}",
    response_model=PhilHealthBracketRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def update_philhealth_bracket(
    *, session: SessionDep, bracket_id: uuid.UUID, bracket: PhilHealthBracketCreate
) -> PhilHealthBracketRead:
    """Update configuration; previously generated payroll snapshots remain intact."""
    row = session.get(PhilHealthBracket, bracket_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="PhilHealth bracket not found")
    for key, value in bracket.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return PhilHealthBracketRead.model_validate(row)


@router.delete(
    "/philhealth-brackets/{bracket_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_philhealth_bracket(
    *, session: SessionDep, bracket_id: uuid.UUID
) -> Message:
    """Deactivate configuration without deleting its historical row."""
    row = session.get(PhilHealthBracket, bracket_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="PhilHealth bracket not found")
    row.is_deleted = True
    row.is_active = False
    row.deleted_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    return Message(message="PhilHealth bracket deactivated")


@router.patch(
    "/pagibig-brackets/{bracket_id}",
    response_model=PagIBIGBracketRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def update_pagibig_bracket(
    *, session: SessionDep, bracket_id: uuid.UUID, bracket: PagIBIGBracketCreate
) -> PagIBIGBracketRead:
    """Update configuration; previously generated payroll snapshots remain intact."""
    row = session.get(PagIBIGBracket, bracket_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="Pag-IBIG bracket not found")
    for key, value in bracket.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return PagIBIGBracketRead.model_validate(row)


@router.delete(
    "/pagibig-brackets/{bracket_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_pagibig_bracket(
    *, session: SessionDep, bracket_id: uuid.UUID
) -> Message:
    """Deactivate configuration without deleting its historical row."""
    row = session.get(PagIBIGBracket, bracket_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="Pag-IBIG bracket not found")
    row.is_deleted = True
    row.is_active = False
    row.deleted_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    return Message(message="Pag-IBIG bracket deactivated")


@router.patch(
    "/bir-brackets/{bracket_id}",
    response_model=BIRBracketRead,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
async def update_bir_bracket(
    *, session: SessionDep, bracket_id: uuid.UUID, bracket: BIRBracketCreate
) -> BIRBracketRead:
    """Update configuration; previously generated payroll snapshots remain intact."""
    row = session.get(BIRBracket, bracket_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="BIR bracket not found")
    for key, value in bracket.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return BIRBracketRead.model_validate(row)


@router.delete(
    "/bir-brackets/{bracket_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("payroll", "delete"))],
)
async def delete_bir_bracket(*, session: SessionDep, bracket_id: uuid.UUID) -> Message:
    """Deactivate configuration without deleting its historical row."""
    row = session.get(BIRBracket, bracket_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="BIR bracket not found")
    row.is_deleted = True
    row.is_active = False
    row.deleted_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    return Message(message="BIR bracket deactivated")
