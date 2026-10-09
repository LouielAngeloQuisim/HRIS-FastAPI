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
from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
)
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.attendance.adjustment_models import DtrAdjustment
from app.attendance.models import (
    DailyTimeRecord,
    DtrAttendanceInterval,
    EmployeeShiftAssignment,
    Shift,
)
from app.audit.models import AuditLog
from app.common.dependencies import CurrentUser, SessionDep
from app.common.schemas import Message
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.leave.models import (
    EmployeeLeaveEnrollment,
    HolidayConfig,
    HolidayInstance,
    LeaveLedgerEntry,
    LeaveLedgerSource,
    LeavePolicy,
    LeaveRequest,
)
from app.payroll.annualized_tax import (
    calculate_annualized_compensation_tax,
    cumulative_average_required,
    cumulative_average_withholding,
)
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
from app.payroll.holiday_rates import HolidayRateError, resolve_holiday_factors
from app.payroll.models import (
    CutoffType,
    EmployeePayGroupAssignment,
    EmployeePayGroupBulkBatch,
    EmployeeSalaryBulkBatch,
    EmployeeTaxBenefit,
    EmployeeTaxYearDeclaration,
    PayrollContributionLedger,
    PayrollDeliveryOutbox,
    PayrollEntry,
    PayrollPayGroup,
    PayrollPolicyVersion,
    PayrollRunStatus,
    PayType,
)
from app.payroll.night_differential import (
    NightDifferentialInputError,
    allocate_night_work_minutes,
)
from app.payroll.payroll_tables import (
    EmployeeSalary,
    IntegrationConfig,
    IntegrationMapping,
    Loan,
    LoanAmortization,
    PayrollRun,
)
from app.payroll.roster_lock import lock_payroll_roster
from app.payroll.schemas import (
    BIRBracketCreate,
    BIRBracketRead,
    EmployeePayGroupAssignmentCreate,
    EmployeePayGroupAssignmentPublic,
    EmployeePayGroupAssignmentUpdate,
    EmployeePayGroupBulkCommit,
    EmployeePayGroupBulkIssue,
    EmployeePayGroupBulkPreflight,
    EmployeePayGroupBulkRequest,
    EmployeeSalaryBulkCommit,
    EmployeeSalaryBulkIssue,
    EmployeeSalaryBulkPreflight,
    EmployeeSalaryBulkRequest,
    EmployeeSalaryCreate,
    EmployeeSalaryIncrementRequest,
    EmployeeSalaryIncrementResult,
    EmployeeSalaryRead,
    EmployeeSalaryUpdate,
    EmployeeTaxBenefitCreate,
    EmployeeTaxBenefitPublic,
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
    PayrollContributionCorrectionCreate,
    PayrollContributionCorrectionTarget,
    PayrollContributionLedgerList,
    PayrollContributionLedgerPublic,
    PayrollDeliveryAddressUpdate,
    PayrollDeliveryResendRequest,
    PayrollDeliveryStatusPublic,
    PayrollDraftRebuildRequest,
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

# RR 11-2018 §2.78.1(B)(11); taxable excess is included at annualization.
BIR_13TH_MONTH_AND_OTHER_BENEFITS_EXEMPTION_CAP = Decimal("90000.00")


@router.get(
    "/contribution-ledger",
    response_model=PayrollContributionLedgerList,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def list_payroll_contribution_ledger(
    *,
    session: SessionDep,
    employee_id: uuid.UUID | None = Query(default=None),
    employee_code: str | None = Query(default=None, min_length=1, max_length=64),
    contribution_month: date | None = Query(default=None),
    scheme: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> PayrollContributionLedgerList:
    """Read finalized statutory collections and linked immutable corrections."""
    if contribution_month is not None and contribution_month.day != 1:
        raise HTTPException(
            status_code=422, detail="contribution_month must be the first day of a month"
        )
    if scheme is not None and scheme not in {"sss", "philhealth", "pagibig"}:
        raise HTTPException(status_code=422, detail="Unsupported contribution scheme")

    base = (
        select(PayrollContributionLedger.id)
        .join(
            PayrollEntry,
            col(PayrollEntry.id) == col(PayrollContributionLedger.payroll_entry_id),
        )
        .join(PayrollRun, col(PayrollRun.id) == col(PayrollEntry.payroll_run_id))
        .join(
            EmployeeRecords,
            col(EmployeeRecords.id) == col(PayrollContributionLedger.employee_id),
        )
        .where(
            PayrollRun.workflow_status == "finalized",
            col(PayrollRun.status).in_([PayrollRunStatus.APPROVED, PayrollRunStatus.PAID]),
            col(PayrollRun.is_deleted).is_(False),
            col(PayrollEntry.is_deleted).is_(False),
        )
    )
    if employee_id is not None:
        base = base.where(PayrollContributionLedger.employee_id == employee_id)
    if employee_code is not None:
        base = base.where(EmployeeRecords.employee_code == employee_code.strip())
    if contribution_month is not None:
        base = base.where(PayrollContributionLedger.contribution_month == contribution_month)
    if scheme is not None:
        base = base.where(PayrollContributionLedger.scheme == scheme)
    count = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = session.exec(
        select(PayrollContributionLedger, EmployeeRecords)
        .join(
            EmployeeRecords,
            col(EmployeeRecords.id) == col(PayrollContributionLedger.employee_id),
        )
        .join(
            PayrollEntry,
            col(PayrollEntry.id) == col(PayrollContributionLedger.payroll_entry_id),
        )
        .join(PayrollRun, col(PayrollRun.id) == col(PayrollEntry.payroll_run_id))
        .where(
            PayrollRun.workflow_status == "finalized",
            col(PayrollRun.status).in_([PayrollRunStatus.APPROVED, PayrollRunStatus.PAID]),
            col(PayrollRun.is_deleted).is_(False),
            col(PayrollEntry.is_deleted).is_(False),
            *(
                [PayrollContributionLedger.employee_id == employee_id]
                if employee_id is not None
                else []
            ),
            *(
                [EmployeeRecords.employee_code == employee_code.strip()]
                if employee_code is not None
                else []
            ),
            *(
                [PayrollContributionLedger.contribution_month == contribution_month]
                if contribution_month is not None
                else []
            ),
            *([PayrollContributionLedger.scheme == scheme] if scheme is not None else []),
        )
        .order_by(
            col(PayrollContributionLedger.contribution_month).desc(),
            col(EmployeeRecords.employee_code),
            col(PayrollContributionLedger.scheme),
            col(PayrollContributionLedger.sequence),
        )
        .offset(skip)
        .limit(limit)
    ).all()
    data = [
        PayrollContributionLedgerPublic.model_validate(
            ledger,
            update={
                "employee_code": employee.employee_code,
                "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
            },
        )
        for ledger, employee in rows
    ]
    return PayrollContributionLedgerList(data=data, count=count)


@router.get(
    "/contribution-ledger/{ledger_id}/correction-targets",
    response_model=list[PayrollContributionCorrectionTarget],
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def list_contribution_correction_targets(
    *, session: SessionDep, ledger_id: uuid.UUID
) -> list[PayrollContributionCorrectionTarget]:
    """List bounded later drafts eligible to receive this employee's correction."""
    source = session.get(PayrollContributionLedger, ledger_id)
    if source is None or source.sequence != 0:
        raise HTTPException(status_code=404, detail="Original contribution not found")
    original_entry = session.get(PayrollEntry, source.payroll_entry_id)
    original_run = (
        session.get(PayrollRun, original_entry.payroll_run_id)
        if original_entry is not None and original_entry.payroll_run_id
        else None
    )
    if (
        original_entry is None
        or original_run is None
        or original_run.workflow_status != "finalized"
        or original_run.status not in {PayrollRunStatus.APPROVED, PayrollRunStatus.PAID}
        or source.employee_id != original_entry.employee_id
    ):
        raise HTTPException(status_code=409, detail="Source collection is not finalized")
    if session.exec(
        select(PayrollContributionLedger.id).where(
            PayrollContributionLedger.reverses_id == source.id
        )
    ).first() is not None:
        raise HTTPException(status_code=409, detail="This contribution already has a correction")
    month_end = source.contribution_month.replace(
        day=calendar.monthrange(
            source.contribution_month.year, source.contribution_month.month
        )[1]
    )
    rows = session.exec(
        select(PayrollEntry, PayrollRun)
        .join(PayrollRun, col(PayrollRun.id) == col(PayrollEntry.payroll_run_id))
        .where(
            PayrollEntry.employee_id == source.employee_id,
            col(PayrollEntry.is_deleted).is_(False),
            col(PayrollEntry.review_state).in_(["blocked", "ready"]),
            PayrollRun.workflow_status == "draft",
            PayrollRun.status == PayrollRunStatus.DRAFT,
            col(PayrollRun.is_deleted).is_(False),
            PayrollRun.date_from > month_end,
        )
        .order_by(col(PayrollRun.date_from), col(PayrollRun.id))
        .limit(200)
    ).all()
    return [
        PayrollContributionCorrectionTarget(
            entry_id=entry.id,
            run_id=run.id,
            date_from=run.date_from,
            date_to=run.date_to,
            review_state=entry.review_state,
            net_pay=entry.net_pay,
        )
        for entry, run in rows
    ]


@router.post(
    "/contribution-ledger/corrections",
    response_model=PayrollContributionLedgerPublic,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def create_payroll_contribution_correction(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    obj_in: PayrollContributionCorrectionCreate,
) -> PayrollContributionLedgerPublic:
    """Apply a linked contribution delta to a later, still-unreviewed payroll.

    Finalized runs are immutable. The correction changes only the target draft's
    deduction and net-pay preview, invalidates its input fingerprint, and must
    be reviewed again before finalization.
    """
    source = session.exec(
        select(PayrollContributionLedger)
        .where(PayrollContributionLedger.id == obj_in.source_ledger_id)
        .with_for_update()
    ).first()
    if source is None or source.sequence != 0:
        raise HTTPException(
            status_code=404,
            detail="Original finalized contribution collection was not found",
        )
    original_entry = session.get(PayrollEntry, source.payroll_entry_id)
    original_run = (
        session.get(PayrollRun, original_entry.payroll_run_id)
        if original_entry is not None and original_entry.payroll_run_id
        else None
    )
    if (
        original_entry is None
        or original_run is None
        or original_run.workflow_status != "finalized"
        or original_run.status not in {PayrollRunStatus.APPROVED, PayrollRunStatus.PAID}
        or original_entry.employee_id != source.employee_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Contribution corrections require an original finalized payroll collection",
        )

    target = session.exec(
        select(PayrollEntry)
        .where(PayrollEntry.id == obj_in.target_entry_id)
        .with_for_update()
    ).first()
    target_run = (
        session.get(PayrollRun, target.payroll_run_id)
        if target is not None and target.payroll_run_id
        else None
    )
    source_month_end = source.contribution_month.replace(
        day=calendar.monthrange(
            source.contribution_month.year, source.contribution_month.month
        )[1]
    )
    if (
        target is None
        or target_run is None
        or target.employee_id != source.employee_id
        or target_run.workflow_status != "draft"
        or target_run.status != PayrollRunStatus.DRAFT
        or target_run.is_deleted
        or target.is_deleted
        or target.review_state not in {"blocked", "ready"}
        or target_run.date_from <= source_month_end
    ):
        raise HTTPException(
            status_code=409,
            detail="Choose this employee's unreviewed draft in a later pay period",
        )

    for field, original in (
        ("employee_amount", source.employee_amount),
        ("employer_amount", source.employer_amount),
    ):
        delta = getattr(obj_in, field)
        if not original and delta != 0:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot change a zero original collection",
            )
        if original and (original + delta) * original < 0:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot reverse the original collection past zero",
            )

    if obj_in.employee_amount != 0:
        if target_run.date_to.year != source.contribution_month.year:
            raise HTTPException(
                status_code=409,
                detail="Employee contribution corrections must be settled in the same tax year; use the year-end tax correction workflow otherwise",
            )
        if "bir_withholding" not in target.deductions:
            raise HTTPException(
                status_code=409,
                detail="The target draft has no calculated BIR withholding line for the reviewed tax correction",
            )

    prior = session.exec(
        select(PayrollContributionLedger).where(
            PayrollContributionLedger.reverses_id == source.id
        )
    ).first()
    if prior is not None:
        raise HTTPException(
            status_code=409,
            detail="This finalized contribution already has a correction; use a separate reviewed adjustment for any further correction",
        )

    deduction_key = f"{source.scheme}_correction"
    try:
        existing_adjustment = Decimal(str(target.deductions.get(deduction_key, "0.00")))
        current_bir_withholding = Decimal(
            str(target.deductions.get("bir_withholding", "0.00"))
        )
        total_deductions = (
            Decimal(str(target.total_deductions))
            + obj_in.employee_amount
            + obj_in.bir_withholding_delta
        )
        gross = Decimal(str(target.gross_pay))
        taxable_income = Decimal(str(target.taxable_income)) - obj_in.employee_amount
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=409, detail="Target payroll has invalid deduction amounts"
        ) from exc
    net_pay = gross - total_deductions
    corrected_bir_withholding = current_bir_withholding + obj_in.bir_withholding_delta
    if net_pay < 0 or corrected_bir_withholding < 0 or taxable_income < 0:
        raise HTTPException(
            status_code=409,
            detail="Correction cannot produce negative net pay, BIR withholding, or taxable compensation",
        )

    next_sequence = (
        session.exec(
            select(func.max(PayrollContributionLedger.sequence)).where(
                PayrollContributionLedger.employee_id == source.employee_id,
                PayrollContributionLedger.scheme == source.scheme,
                PayrollContributionLedger.contribution_month == source.contribution_month,
            )
        ).one()
        or 0
    ) + 1
    correction = PayrollContributionLedger(
        employee_id=source.employee_id,
        payroll_entry_id=target.id,
        scheme=source.scheme,
        contribution_month=source.contribution_month,
        sequence=next_sequence,
        monthly_basis=source.monthly_basis,
        employee_amount=obj_in.employee_amount,
        employer_amount=obj_in.employer_amount,
        calculation_snapshot={
            "source_ledger_id": str(source.id),
            "target_payroll_entry_id": str(target.id),
            "original_basis": str(source.monthly_basis),
            "employee_delta": str(obj_in.employee_amount),
            "employer_delta": str(obj_in.employer_amount),
            "bir_withholding_delta": str(obj_in.bir_withholding_delta),
            "tax_review_reference": obj_in.tax_review_reference,
        },
        source_references=[obj_in.source_reference.strip()],
        adjustment_reason=obj_in.reason.strip(),
        reverses_id=source.id,
        created_by=current_user.id,
    )
    target.deductions = {
        **target.deductions,
        deduction_key: str(existing_adjustment + obj_in.employee_amount),
        **(
            {"bir_withholding": str(corrected_bir_withholding)}
            if obj_in.bir_withholding_delta != 0
            else {}
        ),
    }
    target.total_deductions = total_deductions
    target.net_pay = net_pay
    target.taxable_income = taxable_income
    target.input_snapshot = {
        **target.input_snapshot,
        "contribution_corrections": [
            *target.input_snapshot.get("contribution_corrections", []),
            {
                "source_ledger_id": str(source.id),
                "correction_id": str(correction.id),
                "scheme": source.scheme,
                "contribution_month": source.contribution_month.isoformat(),
                "employee_amount": str(obj_in.employee_amount),
                "employer_amount": str(obj_in.employer_amount),
                "bir_withholding_delta": str(obj_in.bir_withholding_delta),
                "tax_review_reference": obj_in.tax_review_reference,
                "reason": obj_in.reason.strip(),
                "source_reference": obj_in.source_reference.strip(),
            },
        ],
    }
    target.input_fingerprint = hashlib.sha256(
        json.dumps(target.input_snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    target.updated_at = datetime.now(timezone.utc)
    audit = AuditLog(
        method="POST",
        path="/api/v1/payroll/contribution-ledger/corrections",
        status_code=201,
        user_id=current_user.id,
        module="payroll",
        action="contribution_correction",
        extra={
            "source_ledger_id": str(source.id),
            "target_payroll_entry_id": str(target.id),
            "scheme": source.scheme,
            "employee_amount": str(obj_in.employee_amount),
            "employer_amount": str(obj_in.employer_amount),
            "bir_withholding_delta": str(obj_in.bir_withholding_delta),
            "tax_review_reference": obj_in.tax_review_reference,
            "reason": obj_in.reason.strip(),
        },
    )
    session.add(correction)
    session.add(target)
    session.add(audit)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="The contribution was already corrected or the target payroll changed; reload before retrying",
        ) from exc
    session.refresh(correction)
    employee = session.get(EmployeeRecords, correction.employee_id)
    if employee is None:
        raise HTTPException(status_code=409, detail="Correction employee was removed")
    return PayrollContributionLedgerPublic.model_validate(
        correction,
        update={
            "employee_code": employee.employee_code,
            "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
        },
    )


def _confirmed_rest_day_factors(policy: dict[str, Any]) -> tuple[Decimal, Decimal]:
    """Read employer-confirmed ordinary rest-day total-pay factors."""
    premium_rules = policy.get("premium_rules")
    if not isinstance(premium_rules, dict):
        raise ValueError("premium_rules must configure ordinary rest-day factors")
    try:
        regular = Decimal(str(premium_rules["rest_day_regular_multiplier"]))
        overtime = Decimal(str(premium_rules["rest_day_overtime_multiplier"]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(
            "Configure rest_day_regular_multiplier and rest_day_overtime_multiplier"
        ) from exc
    if (
        not regular.is_finite()
        or not overtime.is_finite()
        or regular < Decimal("1.30")
        or overtime < Decimal("1.69")
    ):
        raise ValueError(
            "Ordinary rest-day factors must be at least 1.30 regular and 1.69 overtime"
        )
    return regular, overtime


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
    """Stage one monthly collection in the final eligible employee pay period.

    The caller commits this with payroll finalization. Amounts must already be
    present in the reviewed entry and in its frozen monthly contribution input;
    this function never calculates or guesses statutory values. An employee
    separated during the month collects in the final-pay period covering their
    separation date; active employees collect in the calendar month's last run.
    """
    if run.date_from is None or run.date_to is None:
        raise HTTPException(status_code=409, detail="Payroll period dates are required")
    if (run.date_from.year, run.date_from.month) != (run.date_to.year, run.date_to.month):
        raise HTTPException(
            status_code=409,
            detail="Monthly statutory collection cannot span calendar months",
        )
    month_end = calendar.monthrange(run.date_to.year, run.date_to.month)[1]
    month = run.date_to.replace(day=1)
    schemes = ("sss", "philhealth", "pagibig")
    collection_entries: list[PayrollEntry] = []
    for entry in entries:
        if entry.review_state == "excluded":
            continue
        employee = session.get(EmployeeRecords, entry.employee_id) if entry.employee_id else None
        is_separation_final_pay = bool(
            employee is not None
            and str(getattr(employee.employee_status, "value", employee.employee_status))
            in {"Resigned", "Terminated"}
            and employee.date_separated is not None
            and run.date_from <= employee.date_separated <= run.date_to
        )
        if run.date_to.day == month_end or is_separation_final_pay:
            collection_entries.append(entry)
            continue
        for scheme in schemes:
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
                    detail=f"{scheme} may be collected only in the final eligible payroll period of the month",
                )
    if not collection_entries:
        return
    # Finalizing two different runs for the same employee/month at once must
    # serialize before either transaction checks the ledger. The unique index
    # remains the last line of defense for writers outside this workflow.
    for employee_id in sorted(
        {
            entry.employee_id
            for entry in collection_entries
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
    for entry in collection_entries:
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

    schedule_fields = {
        "sss": (
            "msc_min", "msc_max", "compensation_min", "compensation_max",
            "monthly_salary_credit", "employer_ss", "employer_ec",
            "employer_mpf", "employee_ss", "employee_mpf",
        ),
        "philhealth": (
            "salary_min", "salary_max", "rate", "employer_share", "employee_share",
        ),
        "pagibig": ("salary_min", "salary_max", "employee_rate", "employer_rate"),
    }

    def sources(model: type[Any], fields: Sequence[str]) -> list[dict[str, Any]]:
        rows = session.exec(
            select(model)
            .where(
                model.effective_date <= effective_date,
                col(model.is_active).is_(True),
                col(model.is_deleted).is_(False),
            )
            .order_by(col(model.effective_date).desc(), col(model.id))
        ).all()
        if not rows:
            return []
        latest = rows[0].effective_date
        if model is PhilHealthBracket and latest.year != effective_date.year:
            return []
        snapshots: list[dict[str, Any]] = []
        for row in rows:
            if row.effective_date != latest:
                continue
            snapshots.append({
                "id": str(row.id),
                "effective_date": row.effective_date.isoformat(),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "values": {
                    field: str(getattr(row, field))
                    if getattr(row, field) is not None else None
                    for field in fields
                },
            })
        return snapshots

    scheme_models = {
        "sss": SSSBracket,
        "philhealth": PhilHealthBracket,
        "pagibig": PagIBIGBracket,
    }



    schedule_rows = {
        scheme: sources(model, schedule_fields[scheme])
        for scheme, model in scheme_models.items()
    }
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
    policies: Sequence[PayrollPolicyVersion],
) -> Decimal:
    """Return the contract basic-salary monthly equivalent, independent of attendance.

    PhilHealth's published MBS definition excludes overtime and deductions for
    absences/undertime. For daily/hourly rates this uses each effective policy's
    confirmed monthly divisor and effective shift schedule, not actual worked days.
    A missing effective salary or shift is a blocker rather than a guessed rate.
    """
    days_in_month = calendar.monthrange(
        contribution_month.year, contribution_month.month
    )[1]
    month_end = contribution_month.replace(day=days_in_month)
    employee = session.get(EmployeeRecords, employee_id)
    separation_date = employee.date_separated if employee else None
    if separation_date is not None and separation_date < contribution_month:
        raise StatutoryScheduleUnavailable(
            "The employee's separation date precedes the contribution month"
        )
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
    effective_salaries = sorted(
        (salary for salary in salaries if salary.effective_date <= month_end),
        key=lambda row: row.effective_date,
    )
    if not effective_salaries or effective_salaries[0].effective_date > contribution_month:
        raise StatutoryScheduleUnavailable(
            "An effective salary is required from the first day of the contribution month"
        )

    # Split the statutory monthly equivalent whenever either salary or policy
    # changes. Daily/hourly conversion uses the divisor and scheduled minutes
    # effective for that segment, then calendar-weights the result.
    segments: list[
        tuple[
            date,
            date,
            EmployeeSalary,
            PayrollPolicyVersion,
            Decimal,
            EmployeeShiftAssignment | None,
        ]
    ] = []
    cursor = contribution_month
    while cursor <= month_end:
        effective_cursor = (
            min(cursor, separation_date)
            if separation_date is not None
            else cursor
        )
        salary_rows = [
            row for row in effective_salaries if row.effective_date <= effective_cursor
        ]
        policy_rows = [
            row for row in policies
            if row.confirmed
            and row.effective_from <= effective_cursor
            and (row.effective_to is None or row.effective_to >= effective_cursor)
        ]
        if not salary_rows:
            raise StatutoryScheduleUnavailable(
                f"An effective salary is required on {effective_cursor.isoformat()}"
            )
        if len(policy_rows) != 1:
            raise StatutoryScheduleUnavailable(
                f"Exactly one confirmed payroll policy is required on {effective_cursor.isoformat()} for PhilHealth conversion"
            )
        salary, policy = salary_rows[-1], policy_rows[0]
        try:
            divisor = Decimal(str(policy.policy.get("monthly_divisor", "0")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise StatutoryScheduleUnavailable(
                f"A positive monthly divisor is required on {effective_cursor.isoformat()} for PhilHealth conversion"
            ) from exc
        if divisor <= 0:
            raise StatutoryScheduleUnavailable(
                f"A positive monthly divisor is required on {effective_cursor.isoformat()} for PhilHealth conversion"
            )
        pay_type = str(getattr(salary.pay_type, "value", salary.pay_type))
        assignment = next(
            (
                row for row in assignments
                if row.effective_from <= effective_cursor
                and (row.effective_to is None or row.effective_to >= effective_cursor)
            ),
            None,
        ) if pay_type in {"daily", "hourly"} else None
        if pay_type in {"daily", "hourly"} and (
            assignment is None or assignment.shift_id not in shifts
        ):
            raise StatutoryScheduleUnavailable(
                f"An effective shift is required to convert the {pay_type} PhilHealth basic salary on {cursor.isoformat()}"
            )
        segment_end = cursor
        while segment_end < month_end:
            next_date = segment_end + timedelta(days=1)
            next_effective_date = (
                min(next_date, separation_date)
                if separation_date is not None
                else next_date
            )
            next_salary = [
                row
                for row in effective_salaries
                if row.effective_date <= next_effective_date
            ]
            next_policy = [
                row for row in policies
                if row.confirmed
                and row.effective_from <= next_effective_date
                and (row.effective_to is None or row.effective_to >= next_effective_date)
            ]
            next_assignment = next(
                (
                    row for row in assignments
                    if row.effective_from <= next_effective_date
                    and (row.effective_to is None or row.effective_to >= next_effective_date)
                ),
                None,
            ) if pay_type in {"daily", "hourly"} else None
            if (
                not next_salary
                or len(next_policy) != 1
                or next_salary[-1].id != salary.id
                or next_policy[0].id != policy.id
                or (
                    pay_type in {"daily", "hourly"}
                    and (
                        next_assignment is None
                        or assignment is None
                        or next_assignment.id != assignment.id
                    )
                )
            ):
                break
            segment_end = next_date
        segments.append((cursor, segment_end, salary, policy, divisor, assignment))
        cursor = segment_end + timedelta(days=1)

    monthly_weighted = Decimal("0")
    for segment_start, segment_end, salary, _policy, divisor, assignment in segments:
        segment_days = (segment_end - segment_start).days + 1
        pay_type = str(getattr(salary.pay_type, "value", salary.pay_type))
        if pay_type == "monthly":
            equivalent = salary.basic_rate
        elif pay_type in {"daily", "hourly"}:
            if assignment is None:
                raise StatutoryScheduleUnavailable(
                    f"An effective shift is required to convert the {pay_type} PhilHealth basic salary from {segment_start.isoformat()}"
                )
            shift = shifts.get(assignment.shift_id)
            if shift is None:
                raise StatutoryScheduleUnavailable(
                    f"An effective shift is required to convert the {pay_type} PhilHealth basic salary from {segment_start.isoformat()}"
                )
            scheduled_minutes: list[Decimal] = []
            for work_day in (
                segment_start + timedelta(days=offset)
                for offset in range(segment_days)
            ):
                if work_day.isoweekday() in {int(value) for value in shift.days_of_week}:
                    scheduled_minutes.append(Decimal(str(shift.total_hours_minus_lunch)))
            if not scheduled_minutes:
                raise StatutoryScheduleUnavailable(
                    f"No scheduled workdays are available to convert the {pay_type} PhilHealth basic salary from {segment_start.isoformat()}"
                )
            average_minutes = sum(scheduled_minutes, Decimal("0")) / Decimal(len(scheduled_minutes))
            daily_equivalent = salary.basic_rate
            if pay_type == "hourly":
                daily_equivalent = salary.basic_rate * average_minutes / Decimal(60)
            equivalent = daily_equivalent * divisor
        else:
            raise StatutoryScheduleUnavailable(
                f"Unsupported salary basis {pay_type!r} for PhilHealth monthly conversion"
            )
        monthly_weighted += equivalent * Decimal(segment_days) / Decimal(days_in_month)
    return monthly_weighted.quantize(Decimal("0.01"))


def _fixed_recurring_allowance_for_period(
    *,
    salaries: Sequence[EmployeeSalary],
    employee: EmployeeRecords | None,
    date_from: date,
    date_to: date,
    policies: Sequence[PayrollPolicyVersion],
) -> Decimal:
    """Calculate the supported taxable fixed monthly cash allowance.

    The legacy salary column does not establish a tax exemption. This rule
    applies only with explicit taxable/calendar-day/no-attendance-deduction
    policy settings. Category-specific de minimis benefits stay in their
    separate ledger.
    """
    if date_from > date_to:
        raise StatutoryScheduleUnavailable("Allowance period start must not follow its end")
    effective_salaries = sorted(salaries, key=lambda row: row.effective_date)
    # Keep an unrounded subtotal per calendar month and effective policy. This
    # lets a policy change take effect on its effective date without applying
    # the period's last rounding rule retroactively to earlier dates.
    subtotals: dict[tuple[int, int, str], tuple[Decimal, str]] = {}
    policy_rows = list(policies)
    cursor = date_from
    while cursor <= date_to:
        if employee is not None and employee.date_hired and cursor < employee.date_hired:
            cursor += timedelta(days=1)
            continue
        if employee is not None and employee.date_separated and cursor > employee.date_separated:
            cursor += timedelta(days=1)
            continue
        salary = next(
            (row for row in reversed(effective_salaries) if row.effective_date <= cursor),
            None,
        )
        if salary is None:
            raise StatutoryScheduleUnavailable(
                f"An effective salary is required to determine the fixed allowance on {cursor.isoformat()}"
            )
        if salary.de_minimis_monthly:
            raise StatutoryScheduleUnavailable(
                "De minimis benefits require category, eligibility, ceiling, and paid-benefit ledger reconciliation"
            )
        monthly_amount = Decimal(str(salary.non_taxable_allowance or 0))
        if monthly_amount < 0:
            raise StatutoryScheduleUnavailable("Fixed recurring allowance cannot be negative")
        if monthly_amount:
            applicable = [
                row
                for row in policy_rows
                if row.confirmed
                and row.effective_from <= cursor
                and (row.effective_to is None or row.effective_to >= cursor)
            ]
            if len(applicable) != 1:
                raise StatutoryScheduleUnavailable(
                    f"Exactly one confirmed payroll policy is required for fixed allowance calculation on {cursor.isoformat()}"
                )
            policy = applicable[0].policy
            policy_id = str(applicable[0].id)
            treatment = policy.get("allowance_tax_treatment")
            if not isinstance(treatment, dict) or any(
                treatment.get(key) != expected
                for key, expected in (
                    ("fixed_recurring", "taxable"),
                    ("proration", "calendar_days"),
                    ("absence", "not_deducted"),
                )
            ):
                raise StatutoryScheduleUnavailable(
                    "Configure fixed recurring allowances as taxable, prorated by employed calendar days, and not reduced for attendance before payroll preparation"
                )
            rounding_mode_name = str(policy.get("rounding_mode"))
            if rounding_mode_name not in {"half_up", "half_even", "down"}:
                raise StatutoryScheduleUnavailable(
                    "A supported company rounding mode is required to calculate the fixed allowance"
                )
            month_days = calendar.monthrange(cursor.year, cursor.month)[1]
            key = (cursor.year, cursor.month, policy_id)
            prior_amount, _ = subtotals.get(key, (Decimal("0"), rounding_mode_name))
            subtotals[key] = (
                prior_amount + monthly_amount / Decimal(month_days),
                rounding_mode_name,
            )
        cursor += timedelta(days=1)
    rounding_modes = {
        "half_up": ROUND_HALF_UP,
        "half_even": ROUND_HALF_EVEN,
        "down": ROUND_DOWN,
    }
    return sum(
        (
            amount.quantize(Decimal("0.01"), rounding=rounding_modes[rounding_name])
            for amount, rounding_name in subtotals.values()
        ),
        Decimal("0.00"),
    )


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
    if model is PhilHealthBracket and latest_date.year != as_of.year:
        return []
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
        errors.append(
            f"PhilHealth requires one active floor/ceiling schedule effective in {as_of.year}"
        )
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
    group_ids = {run.pay_group_id for _, run in rows if run.pay_group_id is not None}
    period_types = {
        group.id: group.cadence.value
        for group in session.exec(
            select(PayrollPayGroup).where(col(PayrollPayGroup.id).in_(group_ids))
        ).all()
    } if group_ids else {}
    history: list[dict[str, str]] = []
    taxable_total = Decimal("0.00")
    withheld_total = Decimal("0.00")
    complete = True
    coverage_cursor = coverage_start
    for entry, run in rows:
        period_type = (
            period_types.get(run.pay_group_id, "unknown")
            if run.pay_group_id is not None
            else "unknown"
        )
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
                    "pay_period_type": period_type,
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
                    "pay_period_type": period_type,
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
                "pay_period_type": period_type,
            }
        )
    if coverage_cursor < before:
        complete = False
    return history, taxable_total, withheld_total, complete


def _bir_cumulative_average_was_used(
    session: Session, employee_id: uuid.UUID, tax_year: int, before: date
) -> bool:
    """Keep RR 11-2018 cumulative-average withholding for the rest of the year."""
    snapshots = session.exec(
        select(PayrollEntry.input_snapshot)
        .join(PayrollRun, col(PayrollRun.id) == col(PayrollEntry.payroll_run_id))
        .where(
            PayrollEntry.employee_id == employee_id,
            col(PayrollEntry.review_state) == "reviewed",
            col(PayrollEntry.is_deleted).is_(False),
            PayrollRun.workflow_status == "finalized",
            col(PayrollRun.status).in_([PayrollRunStatus.APPROVED, PayrollRunStatus.PAID]),
            col(PayrollRun.is_deleted).is_(False),
            PayrollRun.date_from >= date(tax_year, 1, 1),
            PayrollRun.date_to < before,
        )
    ).all()
    return any(
        isinstance(snapshot, dict)
        and isinstance(calculation := snapshot.get("bir_calculation"), dict)
        and calculation.get("method") == "cumulative_average_rr_11_2018"
        for snapshot in snapshots
    )


class _MealAttendanceEvidenceInvalid(ValueError):
    """Fail-closed marker for attendance that no longer proves a BIR exemption."""


def _verify_daily_meal_allowance_attendance(
    *,
    session: Session,
    employee_id: uuid.UUID,
    work_dates: list[date],
) -> list[dict[str, Any]]:
    """Require each claimed meal-allowance date to show approved OT or night work."""
    records = session.exec(
        select(DailyTimeRecord).where(
            DailyTimeRecord.employee_id == employee_id,
            col(DailyTimeRecord.work_date).in_(work_dates),
            col(DailyTimeRecord.is_deleted).is_(False),
        )
    ).all()
    by_date = {record.work_date: record for record in records}
    zone = ZoneInfo("Asia/Manila")
    evidence: list[dict[str, Any]] = []

    for work_date in work_dates:
        record = by_date.get(work_date)
        if record is None:
            raise HTTPException(
                status_code=422,
                detail=f"No active attendance record exists for qualifying meal-allowance date {work_date}.",
            )
        shift = session.get(Shift, record.shift_id) if record.shift_id else None
        stored_intervals = session.exec(
            select(DtrAttendanceInterval)
            .where(
                DtrAttendanceInterval.daily_time_record_id == record.id,
                DtrAttendanceInterval.revision == record.interval_revision,
            )
            .order_by(col(DtrAttendanceInterval.sequence))
        ).all()
        evidence.append(
            {
                "record_id": str(record.id),
                "work_date": work_date.isoformat(),
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                "interval_revision": record.interval_revision,
                "rendered_minutes": record.rendered_minutes,
                "overtime_minutes": record.overtime_minutes,
                "overtime_approved_minutes": record.overtime_approved_minutes,
                "login_at": record.login_date.isoformat() if record.login_date else None,
                "logout_at": record.logout_date.isoformat() if record.logout_date else None,
                "shift_id": str(record.shift_id) if record.shift_id else None,
                "shift": (
                    {
                        "id": str(shift.id),
                        "updated_at": shift.updated_at.isoformat() if shift.updated_at else None,
                        "start_time": shift.start_time,
                        "end_time": shift.end_time,
                        "scheduled_minutes": shift.total_hours_minus_lunch,
                        "unpaid_break_minutes": shift.lunch_break_duration,
                        "days_of_week": shift.days_of_week,
                        "is_deleted": shift.is_deleted,
                    }
                    if shift
                    else None
                ),
                "intervals": [
                    {
                        "id": str(item.id),
                        "revision": item.revision,
                        "sequence": item.sequence,
                        "start_at": item.start_at.isoformat(),
                        "end_at": item.end_at.isoformat(),
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                    }
                    for item in stored_intervals
                ],
            }
        )
        if (record.overtime_approved_minutes or 0) > 0:
            continue
        if record.shift_id is None or record.rendered_minutes is None:
            raise HTTPException(
                status_code=422,
                detail=f"Attendance on {work_date} needs an assigned shift and calculated minutes to verify night work.",
            )
        if shift is None:
            raise HTTPException(
                status_code=422,
                detail=f"The assigned shift for {work_date} is unavailable; night work cannot be verified.",
            )
        if stored_intervals:
            intervals = [(item.start_at, item.end_at) for item in stored_intervals]
        elif record.interval_revision > 0:
            raise HTTPException(
                status_code=422,
                detail=f"Attendance interval history for {work_date} is incomplete; night work cannot be verified.",
            )
        elif record.login_date is not None and record.logout_date is not None:
            intervals = [(record.login_date, record.logout_date)]
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Attendance punches for {work_date} do not prove night work.",
            )
        try:
            night_regular, night_overtime = allocate_night_work_minutes(
                intervals,
                scheduled_minutes=int(shift.total_hours_minus_lunch),
                expected_worked_minutes=int(record.rendered_minutes),
                approved_overtime_minutes=int(record.overtime_approved_minutes or 0),
                unpaid_break_minutes=int(shift.lunch_break_duration),
                zone=zone,
            )
        except (NightDifferentialInputError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Attendance for {work_date} cannot verify qualifying night work: {exc}",
            ) from exc
        if night_regular + night_overtime <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Attendance for {work_date} shows neither approved overtime nor work between 22:00 and 06:00.",
            )
    return evidence


def _bir_tax_benefit_rows(
    session: Session,
    employee_id: uuid.UUID,
    tax_year: int,
    opening_as_of: date | None,
    through: date,
    opening_de_minimis_annual_ytd: dict[str, str] | None = None,
    opening_de_minimis_monthly_ytd: dict[str, str] | None = None,
    opening_unused_vacation_leave_days_ytd: int | None = None,
    opening_benefit_history_present: bool = False,
) -> list[dict[str, Any]]:
    start = opening_as_of or date(tax_year, 1, 1) - timedelta(days=1)
    rows = session.exec(
        select(EmployeeTaxBenefit)
        .where(
            EmployeeTaxBenefit.employee_id == employee_id,
            EmployeeTaxBenefit.tax_year == tax_year,
            EmployeeTaxBenefit.paid_on > start,
            EmployeeTaxBenefit.paid_on <= through,
        )
        .order_by(
            col(EmployeeTaxBenefit.paid_on),
            col(EmployeeTaxBenefit.created_at),
            col(EmployeeTaxBenefit.id),
        )
    ).all()
    reversed_ids = {
        row.correction_of_id for row in rows if row.correction_of_id is not None
    }
    active_rows = [
        row
        for row in rows
        if row.correction_of_id is None and row.id not in reversed_ids
    ]
    monthly_paid: dict[tuple[int, int, str], Decimal] = {
        (opening_as_of.year, opening_as_of.month, category): Decimal(amount)
        for category, amount in (opening_de_minimis_monthly_ytd or {}).items()
        if opening_as_of is not None
    }
    annual_paid: dict[str, Decimal] = {
        category: Decimal(amount)
        for category, amount in (opening_de_minimis_annual_ytd or {}).items()
    }
    result: list[dict[str, Any]] = []
    from app.payroll.de_minimis import (
        calculate_daily_meal_exemption,
        calculate_de_minimis_allocation,
        calculate_unused_vacation_leave_exemption,
    )

    unused_vacation_days_used = opening_unused_vacation_leave_days_ytd or 0

    for row in active_rows:
        gross = Decimal(row.gross_amount)
        category_excess = Decimal("0.00")
        category_exempt = Decimal("0.00")
        calculation_blocker = ""
        calculation_blocker_message = ""
        attendance_evidence: list[dict[str, Any]] = []
        vacation_leave_evidence: dict[str, Any] | None = None
        taxable_other_benefit = (
            gross if row.benefit_type in {"thirteenth_month", "other_benefit"}
            else Decimal("0.00")
        )
        wage_order_dates_verified = False
        if row.wage_order_effective_from is not None and row.qualifying_work_dates:
            try:
                wage_order_dates = [
                    date.fromisoformat(day) for day in row.qualifying_work_dates
                ]
                wage_order_dates_verified = (
                    len(wage_order_dates) == row.qualifying_days
                    and len(set(wage_order_dates)) == len(wage_order_dates)
                    and all(
                        row.wage_order_effective_from <= work_date
                        and (
                            row.wage_order_effective_to is None
                            or work_date <= row.wage_order_effective_to
                        )
                        for work_date in wage_order_dates
                    )
                )
            except (TypeError, ValueError):
                wage_order_dates_verified = False
        if row.benefit_type == "de_minimis":
            category = row.de_minimis_category
            if category is None:
                raise ValueError("A de minimis record is missing its category")
            month_key = (row.paid_on.year, row.paid_on.month, category)
            try:
                if category == "daily_meal_ot_night":
                    if row.regional_daily_minimum_wage is None:
                        raise ValueError("Regional daily minimum wage is missing")
                    try:
                        attendance_evidence = _verify_daily_meal_allowance_attendance(
                            session=session,
                            employee_id=employee_id,
                            work_dates=[
                                date.fromisoformat(day)
                                for day in row.qualifying_work_dates or []
                            ],
                        )
                    except HTTPException as exc:
                        category_excess = gross
                        calculation_blocker = "bir_meal_attendance_evidence_changed_or_unavailable"
                        calculation_blocker_message = str(exc.detail)
                        attendance_evidence = []
                        raise _MealAttendanceEvidenceInvalid from exc
                    allocation = calculate_daily_meal_exemption(
                        gross_amount=gross,
                        regional_daily_minimum_wage=row.regional_daily_minimum_wage,
                        qualifying_days=int(row.qualifying_days or 0),
                        evidence_verified=(
                            "approved_overtime_or_night_shift_records"
                            in (row.eligibility_evidence or [])
                            and bool(row.region_code)
                            and bool(row.wage_order_reference)
                            and wage_order_dates_verified
                        ),
                    )
                    category_excess = allocation.category_excess
                    category_exempt = allocation.eligible_exempt
                elif category == "monetized_unused_vacation_leave":
                    if (
                        (opening_as_of is not None or opening_benefit_history_present)
                        and opening_unused_vacation_leave_days_ytd is None
                    ):
                        category_excess = gross
                        calculation_blocker = "bir_unused_leave_opening_days_missing"
                        calculation_blocker_message = (
                            "Reconcile opening-year exempt monetized vacation-leave days before allocating the exemption."
                        )
                    else:
                        ledger_reference = f"PayrollTaxBenefit:{row.id}"
                        leave_debit = session.exec(
                            select(LeaveLedgerEntry).where(
                                LeaveLedgerEntry.employee_id == employee_id,
                                LeaveLedgerEntry.policy_id == row.vacation_leave_policy_id,
                                LeaveLedgerEntry.leave_year == row.tax_year,
                                LeaveLedgerEntry.source == LeaveLedgerSource.CONSUMED,
                                LeaveLedgerEntry.reference == ledger_reference,
                                col(LeaveLedgerEntry.is_deleted).is_(False),
                            )
                        ).first()
                        saved_evidence = row.eligibility_snapshot
                        evidence_verified = bool(
                            isinstance(saved_evidence, dict)
                            and saved_evidence.get("policy_id")
                            == str(row.vacation_leave_policy_id)
                            and saved_evidence.get("policy_is_paid") is True
                            and saved_evidence.get(
                                "policy_tax_exempt_unused_vacation_leave"
                            ) is True
                            and saved_evidence.get("leave_year") == row.tax_year
                            and saved_evidence.get("qualifying_days")
                            == int(row.qualifying_days or 0)
                            and saved_evidence.get("ledger_reference") == ledger_reference
                            and leave_debit is not None
                            and leave_debit.amount == -Decimal(row.qualifying_days or 0)
                            and saved_evidence.get("enrollment_id")
                            == str(leave_debit.enrollment_id)
                        )
                        vacation_leave_evidence = {
                            "verified": evidence_verified,
                            "snapshot": saved_evidence,
                            "ledger_entry": (
                                {
                                    "id": str(leave_debit.id),
                                    "source": str(getattr(leave_debit.source, "value", leave_debit.source)),
                                    "amount": str(leave_debit.amount),
                                    "reference": leave_debit.reference,
                                    "updated_at": leave_debit.updated_at.isoformat()
                                    if leave_debit.updated_at
                                    else None,
                                }
                                if leave_debit is not None
                                else None
                            ),
                        }
                        if not evidence_verified:
                            category_excess = gross
                            calculation_blocker = "bir_unused_vacation_leave_balance_evidence_unavailable"
                            calculation_blocker_message = (
                                "A matching server-recorded leave-ledger deduction and verified vacation-policy snapshot are required before this exemption can be applied."
                            )
                        else:
                            allocation = calculate_unused_vacation_leave_exemption(
                                gross_amount=gross,
                                qualifying_days=int(row.qualifying_days or 0),
                                prior_exempt_days=unused_vacation_days_used,
                                evidence_verified=True,
                            )
                            category_excess = allocation.category_excess
                            category_exempt = allocation.eligible_exempt
                            unused_vacation_days_used += allocation.exempt_days
                else:
                    category_allocation = calculate_de_minimis_allocation(
                        current_paid={category: gross},
                        month_to_date_paid={
                            category: monthly_paid.get(month_key, Decimal("0.00"))
                        },
                        year_to_date_paid={
                            category: annual_paid.get(category, Decimal("0.00"))
                        },
                        other_benefits_exempt_remaining=Decimal("90000.00"),
                        evidence=set(row.eligibility_evidence or []),
                    )
                    category_excess = category_allocation.category_excess[category]
                    category_exempt = category_allocation.eligible_exempt[category]
            except (TypeError, ValueError, InvalidOperation) as exc:
                category_excess = gross
                if not calculation_blocker:
                    calculation_blocker = "bir_de_minimis_evidence_invalid"
                    calculation_blocker_message = str(exc)
            taxable_other_benefit = category_excess
            if category not in {"daily_meal_ot_night", "monetized_unused_vacation_leave"}:
                monthly_paid[month_key] = monthly_paid.get(
                    month_key, Decimal("0.00")
                ) + gross
                annual_paid[category] = annual_paid.get(category, Decimal("0.00")) + gross
        result.append(
            {
                "id": str(row.id),
                "paid_on": row.paid_on.isoformat(),
                "benefit_type": row.benefit_type,
                "de_minimis_category": row.de_minimis_category or "",
                "eligibility_evidence": ",".join(sorted(row.eligibility_evidence or [])),
                "qualifying_days": str(row.qualifying_days or ""),
                "qualifying_work_dates": ",".join(row.qualifying_work_dates or []),
                "regional_daily_minimum_wage": str(row.regional_daily_minimum_wage or ""),
                "region_code": row.region_code or "",
                "wage_order_reference": row.wage_order_reference or "",
                "wage_order_effective_from": row.wage_order_effective_from.isoformat()
                if row.wage_order_effective_from
                else "",
                "wage_order_effective_to": row.wage_order_effective_to.isoformat()
                if row.wage_order_effective_to
                else "",
                "calculation_blocker": calculation_blocker,
                "calculation_blocker_message": calculation_blocker_message,
                "attendance_evidence": attendance_evidence,
                "vacation_leave_evidence": vacation_leave_evidence,
                "gross_amount": str(gross),
                "category_exempt_amount": str(category_exempt),
                "category_excess_amount": str(category_excess),
                "taxable_other_benefit_amount": str(taxable_other_benefit),
                "source_reference": row.source_reference,
            }
        )
    return result


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
        employee_record = session.get(EmployeeRecords, employee_id)
        employee_reference = snapshot.get("employee_record")
        if employee_record is None or employee_record.is_deleted or not isinstance(
            employee_reference, dict
        ):
            return False
        current_employee_reference = {
            "id": str(employee_record.id),
            "employee_code": employee_record.employee_code,
            "first_name": employee_record.first_name,
            "last_name": employee_record.last_name,
            "email": employee_record.email,
            "is_deleted": employee_record.is_deleted,
            "employee_status": str(
                getattr(employee_record.employee_status, "value", employee_record.employee_status)
            ),
            "date_hired": employee_record.date_hired.isoformat()
            if employee_record.date_hired
            else None,
            "date_separated": employee_record.date_separated.isoformat()
            if employee_record.date_separated
            else None,
        }
        if current_employee_reference != employee_reference:
            return False

        pay_group_id = uuid.UUID(str(snapshot["pay_group_id"]))
        pay_group = session.get(PayrollPayGroup, pay_group_id)
        pay_group_reference = snapshot.get("pay_group")
        if pay_group is None or not isinstance(pay_group_reference, dict):
            return False
        current_pay_group_reference = {
            "id": str(pay_group.id),
            "code": pay_group.code,
            "name": pay_group.name,
            "cadence": str(getattr(pay_group.cadence, "value", pay_group.cadence)),
            "first_period_end_day": pay_group.first_period_end_day,
            "second_period_end_day": pay_group.second_period_end_day,
            "payment_offset_days": pay_group.payment_offset_days,
            "weekend_rule": pay_group.weekend_rule,
            "is_active": pay_group.is_active,
            "updated_at": pay_group.updated_at.isoformat()
            if pay_group.updated_at
            else None,
        }
        if current_pay_group_reference != pay_group_reference:
            return False

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
            current_tax_reference = {
                "id": str(tax_declaration.id),
                "updated_at": tax_declaration.updated_at.isoformat()
                if tax_declaration.updated_at
                else None,
                "tax_classification": tax_declaration.tax_classification,
                "taxable_compensation_ytd": str(
                    tax_declaration.taxable_compensation_ytd
                ),
                "tax_withheld_ytd": str(tax_declaration.tax_withheld_ytd),
                "opening_pay_period_count": tax_declaration.opening_pay_period_count,
                "opening_pay_period_type": tax_declaration.opening_pay_period_type,
                "previous_employer_included": tax_declaration.previous_employer_included,
                "source_reference": tax_declaration.source_reference,
                "opening_benefits_exempt_ytd": str(
                    tax_declaration.opening_benefits_exempt_ytd
                ),
                "opening_benefits_reconciled": tax_declaration.opening_benefits_reconciled,
                "opening_de_minimis_annual_ytd": tax_declaration.opening_de_minimis_annual_ytd,
                "opening_de_minimis_monthly_ytd": tax_declaration.opening_de_minimis_monthly_ytd,
                "opening_unused_vacation_leave_days_ytd": tax_declaration.opening_unused_vacation_leave_days_ytd,
                "opening_as_of": tax_declaration.opening_as_of.isoformat()
                if tax_declaration.opening_as_of
                else None,
                "verified": tax_declaration.is_verified,
            }
            if current_tax_reference != tax_reference:
                return False

        benefit_reference = snapshot.get("bir_tax_benefit_ledger")
        if isinstance(benefit_reference, list):
            current_benefits = _bir_tax_benefit_rows(
                session,
                employee_id,
                period_to.year,
                tax_declaration.opening_as_of if tax_declaration else None,
                period_to,
                tax_declaration.opening_de_minimis_annual_ytd
                if tax_declaration
                else None,
                tax_declaration.opening_de_minimis_monthly_ytd
                if tax_declaration
                else None,
                tax_declaration.opening_unused_vacation_leave_days_ytd
                if tax_declaration
                else None,
                bool(
                    tax_declaration
                    and (
                        tax_declaration.opening_benefits_reconciled
                        or tax_declaration.previous_employer_included
                    )
                ),
            )
            if current_benefits != benefit_reference:
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

        monthly_snapshot = snapshot.get("monthly_contributions")
        if monthly_snapshot is not None:
            month = date.fromisoformat(f"{monthly_snapshot['month']}-01")
            month_end = month.replace(day=calendar.monthrange(month.year, month.month)[1])
            statutory_models: dict[str, tuple[type[Any], tuple[str, ...]]] = {
                "sss": (
                    SSSBracket,
                    (
                        "msc_min", "msc_max", "compensation_min", "compensation_max",
                        "monthly_salary_credit", "employer_ss", "employer_ec",
                        "employer_mpf", "employee_ss", "employee_mpf",
                    ),
                ),
                "philhealth": (
                    PhilHealthBracket,
                    ("salary_min", "salary_max", "rate", "employer_share", "employee_share"),
                ),
                "pagibig": (
                    PagIBIGBracket,
                    ("salary_min", "salary_max", "employee_rate", "employer_rate"),
                ),
            }
            recorded_schemes = monthly_snapshot.get("schemes", {})
            for scheme, (model, fields) in statutory_models.items():
                rows = session.exec(
                    select(model)
                    .where(
                        model.effective_date <= month_end,
                        col(model.is_active).is_(True),
                        col(model.is_deleted).is_(False),
                    )
                    .order_by(col(model.effective_date).desc(), col(model.id))
                ).all()
                latest_date = rows[0].effective_date if rows else None
                current_rows = [
                    {
                        "id": str(row.id),
                        "effective_date": row.effective_date.isoformat(),
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                        "values": {
                            field: str(getattr(row, field))
                            if getattr(row, field) is not None else None
                            for field in fields
                        },
                    }
                    for row in rows
                    if row.effective_date == latest_date
                ]
                if current_rows != recorded_schemes.get(scheme, {}).get("schedule_rows", []):
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
        expected_shift_ids = {
            uuid.UUID(str(row["shift_id"])) for row in snapshot["shift_assignments"]
        }
        current_shifts = session.exec(
            select(Shift).where(col(Shift.id).in_(expected_shift_ids))
        ).all()
        current_shift_revisions = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "code": row.code,
                "name": row.name,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "lunch_break_duration": row.lunch_break_duration,
                "total_hours_minus_lunch": row.total_hours_minus_lunch,
                "days_of_week": list(row.days_of_week),
                "is_deleted": row.is_deleted,
            }
            for row in sorted(current_shifts, key=lambda item: str(item.id))
        ]
        if current_shift_revisions != snapshot.get("shift_revisions"):
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
        leave_policy_ids = {
            uuid.UUID(str(reference["id"]))
            for reference in snapshot.get("leave_policy_revisions", [])
        }
        current_leave_policies = (
            session.exec(
                select(LeavePolicy).where(col(LeavePolicy.id).in_(leave_policy_ids))
            ).all()
            if leave_policy_ids
            else []
        )
        current_leave_policy_revisions = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "is_paid": row.is_paid,
                "is_active": row.is_active,
                "is_deleted": row.is_deleted,
            }
            for row in sorted(current_leave_policies, key=lambda item: str(item.id))
        ]
        if current_leave_policy_revisions != snapshot.get(
            "leave_policy_revisions", []
        ):
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
        holiday_config_rows = session.exec(
            select(HolidayConfig).join(
                HolidayInstance,
                col(HolidayInstance.config_id) == col(HolidayConfig.id),
            ).where(
                HolidayInstance.observed_date >= period_from,
                HolidayInstance.observed_date <= period_to,
                col(HolidayInstance.is_active).is_(True),
                col(HolidayInstance.is_deleted).is_(False),
                col(HolidayConfig.is_active).is_(True),
                col(HolidayConfig.is_deleted).is_(False),
            )
        ).all()
        if {row.id for row in holiday_config_rows} != {
            uuid.UUID(str(row["id"]))
            for row in snapshot.get("holiday_config_revisions", [])
        }:
            return False
        for reference in snapshot.get("holiday_config_revisions", []):
            holiday_config = session.get(
                HolidayConfig, uuid.UUID(str(reference["id"]))
            )
            if holiday_config is None or not holiday_config.is_active or holiday_config.is_deleted:
                return False
            if (
                str(getattr(holiday_config.type, "value", holiday_config.type))
                != reference["type"]
                or str(holiday_config.multiplier_regular)
                != reference["multiplier_regular"]
                or str(holiday_config.multiplier_overtime)
                != reference["multiplier_overtime"]
                or str(holiday_config.multiplier_regular_rest_day)
                != reference.get("multiplier_regular_rest_day")
                or str(holiday_config.multiplier_overtime_rest_day)
                != reference.get("multiplier_overtime_rest_day")
                or holiday_config.region_code != reference["region_code"]
                or (
                    holiday_config.updated_at.isoformat()
                    if holiday_config.updated_at
                    else None
                )
                != reference["updated_at"]
            ):
                return False
        policy_rows = session.exec(
            select(PayrollPolicyVersion).where(
                PayrollPolicyVersion.effective_from <= period_to,
                (col(PayrollPolicyVersion.effective_to).is_(None))
                | (col(PayrollPolicyVersion.effective_to) >= period_from),
            )
        ).all()
        current_policy_revisions = [
            {
                "id": str(row.id),
                "version": row.version,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat()
                if row.effective_to
                else None,
                "policy": row.policy,
                "confirmed": row.confirmed,
                "confirmed_by": str(row.confirmed_by) if row.confirmed_by else None,
                "confirmed_at": row.confirmed_at.isoformat()
                if row.confirmed_at
                else None,
            }
            for row in sorted(policy_rows, key=lambda item: str(item.id))
        ]
        if current_policy_revisions != snapshot["policy_versions"]:
            return False
        for reference in snapshot.get("attendance_revisions", []):
            dtr = session.get(DailyTimeRecord, uuid.UUID(str(reference["id"])))
            if dtr is None or dtr.is_deleted:
                return False
            current_attendance_reference = {
                "id": str(dtr.id),
                "interval_revision": dtr.interval_revision,
                "updated_at": dtr.updated_at.isoformat() if dtr.updated_at else None,
                "overtime_decided_at": dtr.overtime_decided_at.isoformat()
                if dtr.overtime_decided_at
                else None,
                "work_date": dtr.work_date.isoformat() if dtr.work_date else None,
                "shift_id": str(dtr.shift_id) if dtr.shift_id else None,
                "login_date": dtr.login_date.isoformat() if dtr.login_date else None,
                "logout_date": dtr.logout_date.isoformat() if dtr.logout_date else None,
                "rendered_minutes": dtr.rendered_minutes,
                "late_minutes": dtr.late_minutes,
                "undertime_minutes": dtr.undertime_minutes,
                "overtime_minutes": dtr.overtime_minutes,
                "overtime_approved": dtr.overtime_approved,
                "overtime_approved_minutes": dtr.overtime_approved_minutes,
                "overtime_decision_reason": dtr.overtime_decision_reason,
                "overtime_decided_by": str(dtr.overtime_decided_by)
                if dtr.overtime_decided_by
                else None,
                "is_absent": dtr.is_absent,
            }
            if current_attendance_reference != reference:
                return False
        for reference in snapshot.get("salary_versions", []):
            salary = session.get(EmployeeSalary, uuid.UUID(str(reference["id"])))
            if salary is None or salary.is_deleted or not salary.is_active:
                return False
            current_salary_reference = {
                "id": str(salary.id),
                "updated_at": salary.updated_at.isoformat() if salary.updated_at else None,
                "basic_rate": str(salary.basic_rate),
                "currency": salary.currency,
                "effective_date": salary.effective_date.isoformat(),
                "pay_type": str(getattr(salary.pay_type, "value", salary.pay_type)),
                "overtime_rate": str(salary.overtime_rate),
                "absent_penalty_rate": str(salary.absent_penalty_rate),
                "non_taxable_allowance": str(salary.non_taxable_allowance),
                "de_minimis_monthly": salary.de_minimis_monthly,
                "thirteenth_month_exempt_portion": str(
                    salary.thirteenth_month_exempt_portion
                ),
                "is_active": salary.is_active,
            }
            if current_salary_reference != reference:
                return False
        for reference in snapshot.get("shift_assignments", []):
            assignment = session.get(
                EmployeeShiftAssignment, uuid.UUID(str(reference["id"]))
            )
            if assignment is None or assignment.is_deleted:
                return False
            current_shift_assignment_reference = {
                "id": str(assignment.id),
                "updated_at": assignment.updated_at.isoformat()
                if assignment.updated_at
                else None,
                "employee_id": str(assignment.employee_id),
                "shift_id": str(assignment.shift_id),
                "effective_from": assignment.effective_from.isoformat(),
                "effective_to": assignment.effective_to.isoformat()
                if assignment.effective_to
                else None,
                "is_deleted": assignment.is_deleted,
            }
            if current_shift_assignment_reference != reference:
                return False
        for reference in snapshot.get("pay_group_assignments", []):
            pay_group_assignment = session.get(
                EmployeePayGroupAssignment, uuid.UUID(str(reference["id"]))
            )
            if pay_group_assignment is None:
                return False
            current_pay_group_reference = {
                "id": str(pay_group_assignment.id),
                "updated_at": pay_group_assignment.updated_at.isoformat()
                if pay_group_assignment.updated_at
                else None,
                "employee_id": str(pay_group_assignment.employee_id),
                "pay_group_id": str(pay_group_assignment.pay_group_id),
                "effective_from": pay_group_assignment.effective_from.isoformat(),
                "effective_to": pay_group_assignment.effective_to.isoformat()
                if pay_group_assignment.effective_to
                else None,
            }
            if current_pay_group_reference != reference:
                return False
        for reference in snapshot.get("leave_revisions", []):
            leave = session.get(LeaveRequest, uuid.UUID(str(reference["id"])))
            if leave is None or leave.is_deleted:
                return False
            current_leave_reference = {
                "id": str(leave.id),
                "updated_at": leave.updated_at.isoformat() if leave.updated_at else None,
                "employee_id": str(leave.employee_id) if leave.employee_id else None,
                "policy_id": str(leave.policy_id) if leave.policy_id else None,
                "date_start": leave.date_start.isoformat(),
                "date_end": leave.date_end.isoformat(),
                "requested_hours": str(leave.requested_hours)
                if leave.requested_hours is not None
                else None,
                "total_days_requested": str(leave.total_days_requested),
                "status": str(getattr(leave.status, "value", leave.status)),
            }
            if current_leave_reference != reference:
                return False
        for reference in snapshot.get("holiday_revisions", []):
            holiday = session.get(HolidayInstance, uuid.UUID(str(reference["id"])))
            if holiday is None or holiday.is_deleted or not holiday.is_active:
                return False
            current_holiday_reference = {
                "id": str(holiday.id),
                "updated_at": holiday.updated_at.isoformat()
                if holiday.updated_at
                else None,
                "config_id": str(holiday.config_id),
                "observed_date": holiday.observed_date.isoformat(),
                "raw_date": holiday.raw_date.isoformat() if holiday.raw_date else None,
                "is_active": holiday.is_active,
                "is_deleted": holiday.is_deleted,
            }
            if current_holiday_reference != reference:
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def _run_roster_matches_current_membership(
    *, session: Session, run: PayrollRun, entries: Sequence[PayrollEntry]
) -> bool:
    if run.pay_group_id is None:
        return False
    roster = preflight_payroll_run(
        session=session,
        pay_group_id=run.pay_group_id,
        date_from=run.date_from,
        date_to=run.date_to,
        skip=0,
        limit=201,
    )
    if roster.has_more or roster.count > 200:
        return False
    prepared_ids = {entry.employee_id for entry in entries}
    expected_ids = {row.employee_id for row in roster.entries}
    return len(entries) == roster.count and prepared_ids == expected_ids


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
        if not _payroll_entry_inputs_are_current(session, entry):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} inputs changed; rebuild the draft before review",
            )
        entry.review_state = "blocked" if entry.blockers else "ready"
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
    if entry.blockers and obj_in.action != "excluded":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Resolve payroll blockers before review or exclude with a reason",
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
    if run.pay_group_id is None:
        raise HTTPException(status_code=409, detail="Payroll run has no pay group")
    lock_payroll_roster(session)
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
    if not _run_roster_matches_current_membership(
        session=session, run=run, entries=entries
    ):
        raise HTTPException(
            status_code=409,
            detail="Expected pay-group employee roster changed; rebuild and review the draft again",
        )
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
        if entry.review_state == "reviewed" and entry.blockers:
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} still has unresolved blockers",
            )
        if entry.review_state == "reviewed" and (
            (
                entry.calculation_version is not None
                and entry.calculation_version.endswith("-provisional")
            )
            or entry.earnings.get("provisional") is True
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Entry {entry.id} uses provisional attendance earnings; "
                    "complete and approve the payroll calculation before finalization"
                ),
            )
        required_snapshot_keys = {
            "attendance_revisions",
            "salary_versions",
            "shift_assignments",
            "shift_revisions",
            "pay_group_assignments",
            "leave_revisions",
            "holiday_revisions",
        }
        if entry.review_state == "reviewed" and not required_snapshot_keys.issubset(entry.input_snapshot):
            raise HTTPException(
                status_code=409,
                detail=f"Entry {entry.id} is missing attendance or salary revision evidence",
            )
        if entry.review_state == "reviewed" and not entry.input_snapshot["salary_versions"]:
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
        select(col(HolidayInstance.observed_date), HolidayConfig)
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
    holiday_configs_by_day: dict[date, list[HolidayConfig]] = {}
    for day, holiday_config in holiday_rows:
        if str(getattr(holiday_config.type, "value", holiday_config.type)) != "special_working":
            holiday_configs_by_day.setdefault(day, []).append(holiday_config)
    holiday_days = set(holiday_configs_by_day)
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
        employee_status = str(getattr(employee.employee_status, "value", employee.employee_status))
        if employee_status in {"Resigned", "Terminated"} and employee.date_separated is None:
            blockers.append(
                PayrollPreflightBlocker(
                    code="employment_end_date_missing",
                    message="A resigned or terminated employee needs an effective separation date before payroll can be calculated.",
                )
            )
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
                    dtr_worked = (
                        not dtr.is_absent and int(dtr.rendered_minutes or 0) > 0
                    )
                    day_holidays = holiday_configs_by_day.get(work_day, [])
                    if dtr_worked and not day_holidays:
                        try:
                            if len(day_policies) != 1 or not day_policies[0].confirmed:
                                raise ValueError("A confirmed policy is required")
                            _confirmed_rest_day_factors(day_policies[0].policy)
                        except ValueError as exc:
                            blockers.append(
                                PayrollPreflightBlocker(
                                    code="rest_day_policy_unconfirmed",
                                    message=f"Ordinary rest-day work cannot be calculated: {exc}.",
                                    work_date=work_day,
                                )
                            )
                    elif dtr_worked and len(day_holidays) > 1 and not (
                        len(day_holidays) == 2
                        and str(getattr(day_holidays[0].type, "value", day_holidays[0].type))
                        in {"regular", "special_non_working"}
                        and all(
                            str(getattr(item.type, "value", item.type))
                            == str(getattr(day_holidays[0].type, "value", day_holidays[0].type))
                            for item in day_holidays
                        )
                    ):
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="holiday_configuration_ambiguous",
                                message="Mixed or unsupported overlapping holidays apply to this rest day; resolve the holiday configuration before payroll.",
                                work_date=work_day,
                            )
                        )
                    elif dtr_worked and (
                        day_holidays[0].multiplier_regular_rest_day is None
                        or day_holidays[0].multiplier_overtime_rest_day is None
                    ):
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="holiday_multiplier_incomplete",
                                message="Worked holiday on a rest day needs configured regular and overtime total factors.",
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
    pay_group = session.get(PayrollPayGroup, pay_group_id)
    if pay_group is None:
        raise HTTPException(status_code=404, detail="Active pay group not found")
    monthly_period_fraction = {
        CutoffType.MONTHLY: Decimal("1"),
        CutoffType.SEMI_MONTHLY: Decimal("0.5"),
    }.get(pay_group.cadence)
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

    eligibility_start = date_from - timedelta(days=min(7, (date_from - date.min).days))
    assignments = session.exec(
        select(EmployeeShiftAssignment).where(
            col(EmployeeShiftAssignment.employee_id).in_(employee_ids),
            col(EmployeeShiftAssignment.is_deleted).is_(False),
            EmployeeShiftAssignment.effective_from <= date_to,
            (col(EmployeeShiftAssignment.effective_to).is_(None))
            | (col(EmployeeShiftAssignment.effective_to) >= eligibility_start),
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
    dtr_ids = [dtr.id for dtr in dtrs]
    interval_rows = (
        session.exec(
            select(DtrAttendanceInterval)
            .where(col(DtrAttendanceInterval.daily_time_record_id).in_(dtr_ids))
            .order_by(
                col(DtrAttendanceInterval.daily_time_record_id),
                col(DtrAttendanceInterval.sequence),
            )
        ).all()
        if dtr_ids
        else []
    )
    dtr_intervals: dict[uuid.UUID, list[DtrAttendanceInterval]] = {}
    dtr_by_id = {dtr.id: dtr for dtr in dtrs}
    for interval in interval_rows:
        dtr = dtr_by_id.get(interval.daily_time_record_id)
        if dtr is not None and interval.revision == dtr.interval_revision:
            dtr_intervals.setdefault(interval.daily_time_record_id, []).append(interval)
    previous_dtrs = session.exec(
        select(DailyTimeRecord).where(
            col(DailyTimeRecord.employee_id).in_(employee_ids),
            col(DailyTimeRecord.work_date) >= eligibility_start,
            col(DailyTimeRecord.work_date) < date_from,
            col(DailyTimeRecord.is_deleted).is_(False),
        )
    ).all()
    previous_dtrs_by_key: dict[tuple[uuid.UUID, date], list[DailyTimeRecord]] = {}
    for prior_dtr in previous_dtrs:
        if prior_dtr.work_date is not None:
            previous_dtrs_by_key.setdefault(
                (prior_dtr.employee_id, prior_dtr.work_date), []
            ).append(prior_dtr)
    policies = session.exec(
        select(PayrollPolicyVersion).where(
            PayrollPolicyVersion.effective_from <= date_to,
            (col(PayrollPolicyVersion.effective_to).is_(None))
            | (col(PayrollPolicyVersion.effective_to) >= eligibility_start),
            col(PayrollPolicyVersion.confirmed).is_(True),
        )
    ).all()
    leave_rows = session.exec(
        select(LeaveRequest).where(
            col(LeaveRequest.employee_id).in_(employee_ids),
            LeaveRequest.status == "approved",
            col(LeaveRequest.is_deleted).is_(False),
            LeaveRequest.date_start <= date_to,
            LeaveRequest.date_end >= eligibility_start,
        )
    ).all()
    leave_policy_ids = {
        leave.policy_id for leave in leave_rows if leave.policy_id is not None
    }
    leave_policy_rows = (
        session.exec(
            select(LeavePolicy).where(col(LeavePolicy.id).in_(leave_policy_ids))
        ).all()
        if leave_policy_ids
        else []
    )
    leave_policies_by_id = {row.id: row for row in leave_policy_rows}
    approved_leave_days: set[tuple[uuid.UUID, date]] = set()
    paid_leave_days: set[tuple[uuid.UUID, date]] = set()
    unclassified_leave_days: set[tuple[uuid.UUID, date]] = set()
    partial_leave_by_day: dict[
        tuple[uuid.UUID, date], list[tuple[Decimal, uuid.UUID | None, uuid.UUID]]
    ] = {}
    for leave in leave_rows:
        if leave.employee_id is None:
            continue
        cursor = max(eligibility_start, leave.date_start)
        end = min(date_to, leave.date_end)
        leave_policy = (
            leave_policies_by_id.get(leave.policy_id)
            if leave.policy_id is not None
            else None
        )
        while cursor <= end:
            key = (leave.employee_id, cursor)
            if leave.requested_hours is not None:
                partial_leave_by_day.setdefault(key, []).append(
                    (leave.requested_hours, leave.policy_id, leave.id)
                )
            else:
                approved_leave_days.add(key)
                if leave_policy is None:
                    unclassified_leave_days.add(key)
                elif leave_policy.is_paid:
                    paid_leave_days.add(key)
            cursor += timedelta(days=1)
    holiday_rows = session.exec(
        select(HolidayInstance, HolidayConfig)
        .join(HolidayConfig, col(HolidayInstance.config_id) == col(HolidayConfig.id))
        .where(
            HolidayInstance.observed_date >= eligibility_start,
            HolidayInstance.observed_date <= date_to,
            col(HolidayInstance.is_active).is_(True),
            col(HolidayInstance.is_deleted).is_(False),
            col(HolidayConfig.is_active).is_(True),
            col(HolidayConfig.is_deleted).is_(False),
        )
    ).all()
    holidays_by_day: dict[
        date,
        list[
            tuple[
                str,
                Decimal | None,
                Decimal | None,
                Decimal | None,
                Decimal | None,
                str | None,
                uuid.UUID,
            ]
        ],
    ] = {}
    for holiday_instance, holiday_config in holiday_rows:
        holiday_day = holiday_instance.observed_date
        kind = holiday_config.type
        if str(getattr(kind, "value", kind)) == "special_working":
            continue
        holidays_by_day.setdefault(holiday_day, []).append(
            (
                str(getattr(kind, "value", kind)),
                holiday_config.multiplier_regular,
                holiday_config.multiplier_overtime,
                holiday_config.multiplier_regular_rest_day,
                holiday_config.multiplier_overtime_rest_day,
                holiday_config.region_code,
                holiday_config.id,
            )
        )
    previews: list[PayrollAttendanceCalculationEntry] = []
    for employee_entry in roster.entries:
        blockers = list(employee_entry.blockers)
        formulas: list[str] = []
        refs: list[str] = []
        calculation_groups: dict[
            tuple[Decimal, str, Decimal, str, str | None, int], list[AttendancePayDay]
        ] = {}
        results = []
        employee = employees.get(employee_entry.employee_id)
        employee_salaries = salaries_by_employee.get(employee_entry.employee_id, [])
        employee_assignments = assignments_by_employee.get(employee_entry.employee_id, [])

        # The divisor is based on the full configured pay period, not merely
        # the dates an employee happened to work. For a mid-period hire or
        # separation, use the nearest effective shift to define the schedule
        # outside active employment; those dates contribute to the denominator
        # but never to the employee's payable numerator.
        monthly_period_scheduled_days = 0
        period_day = date_from
        while period_day <= date_to:
            assignment_for_denominator = next(
                (
                    item
                    for item in employee_assignments
                    if item.effective_from <= period_day
                    and (item.effective_to is None or item.effective_to >= period_day)
                ),
                None,
            )
            if assignment_for_denominator is None and employee_assignments:
                assignment_for_denominator = min(
                    employee_assignments,
                    key=lambda item: (
                        abs((item.effective_from - period_day).days),
                        item.effective_from,
                        str(item.id),
                    ),
                )
            denominator_shift = (
                shifts.get(assignment_for_denominator.shift_id)
                if assignment_for_denominator is not None
                else None
            )
            if denominator_shift is not None:
                try:
                    denominator_weekdays = {
                        int(value) for value in denominator_shift.days_of_week
                    }
                except (TypeError, ValueError):
                    denominator_weekdays = set()
                if period_day.isoweekday() in denominator_weekdays:
                    monthly_period_scheduled_days += 1
            period_day += timedelta(days=1)
        def preceding_workday_eligibility(
            holiday_date: date, employee_record: EmployeeRecords | None,
        ) -> tuple[bool, str | None, DailyTimeRecord | None]:
            if employee_record is None:
                return False, "Employee record is unavailable for holiday eligibility.", None
            if employee_record.date_hired is not None and employee_record.date_hired >= holiday_date:
                return False, None, None
            if (
                employee_record.date_separated is not None
                and employee_record.date_separated < holiday_date
            ):
                return False, None, None
            candidate = holiday_date - timedelta(days=1)
            for _ in range(7):
                if employee_record.date_hired is not None and candidate < employee_record.date_hired:
                    return False, None, None
                assignment = next(
                    (
                        item
                        for item in assignments_by_employee.get(employee_record.id, [])
                        if item.effective_from <= candidate
                        and (item.effective_to is None or item.effective_to >= candidate)
                    ),
                    None,
                )
                if assignment is None:
                    return False, "Prior scheduled workday cannot be determined because no effective shift is recorded.", None
                prior_shift = shifts.get(assignment.shift_id)
                if prior_shift is None:
                    return False, "Prior scheduled workday cannot be determined because its shift is unavailable.", None
                try:
                    prior_scheduled_days = {int(value) for value in prior_shift.days_of_week}
                except (TypeError, ValueError):
                    return False, "Prior shift has an invalid weekday schedule.", None
                if candidate.isoweekday() not in prior_scheduled_days:
                    candidate -= timedelta(days=1)
                    continue

                prior_leave = (employee_record.id, candidate) in paid_leave_days
                if prior_leave:
                    leave_policies = [
                        row
                        for row in policies
                        if row.effective_from <= candidate
                        and (row.effective_to is None or row.effective_to >= candidate)
                    ]
                    if len(leave_policies) != 1 or not leave_policies[0].confirmed:
                        return False, "Prior approved leave has no single confirmed policy for paid-leave eligibility.", None
                    if bool(leave_policies[0].policy.get("paid_leave")):
                        return True, None, None
                    if candidate in holidays_by_day:
                        candidate -= timedelta(days=1)
                        continue
                    return False, None, None

                prior_records = previous_dtrs_by_key.get((employee_record.id, candidate), [])
                if candidate >= date_from:
                    current_record = dtrs_by_key.get((employee_record.id, candidate))
                    if current_record is not None:
                        prior_records = [current_record]
                if len(prior_records) > 1:
                    return False, "Prior scheduled workday has duplicate attendance records.", None
                if prior_records:
                    prior_dtr = prior_records[0]
                    if prior_dtr.is_absent:
                        if candidate in holidays_by_day:
                            candidate -= timedelta(days=1)
                            continue
                        return False, None, prior_dtr
                    if (
                        prior_dtr.login_date is None
                        or prior_dtr.logout_date is None
                        or prior_dtr.rendered_minutes is None
                    ):
                        return False, "Prior scheduled workday attendance is incomplete.", prior_dtr
                    if prior_dtr.rendered_minutes > 0:
                        return True, None, prior_dtr
                    if candidate in holidays_by_day:
                        candidate -= timedelta(days=1)
                        continue
                    return False, None, prior_dtr

                if candidate in holidays_by_day:
                    candidate -= timedelta(days=1)
                    continue
                return False, "Prior scheduled workday has no attendance or approved leave resolution.", None
            return False, "Could not identify a prior scheduled workday within seven days.", None

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
            leave_key = (employee_entry.employee_id, cursor)
            if leave_key in unclassified_leave_days:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="leave_policy_unavailable",
                        message="Approved leave has no available leave policy, so paid versus unpaid treatment cannot be verified.",
                        work_date=cursor,
                    )
                )
                break
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
            scheduled_weekdays = {int(value) for value in shift.days_of_week}
            is_rest_day = cursor.isoweekday() not in scheduled_weekdays
            dtr = dtrs_by_key.get((employee_entry.employee_id, cursor))
            holiday_configs = holidays_by_day.get(cursor, [])
            worked_on_rest_day = bool(
                is_rest_day
                and dtr is not None
                and not dtr.is_absent
                and int(dtr.rendered_minutes or 0) > 0
            )
            if is_rest_day and not holiday_configs and not worked_on_rest_day:
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
            paid_leave_record = (employee_entry.employee_id, cursor) in paid_leave_days
            paid_leave = paid_leave_record and bool(policy.policy.get("paid_leave"))
            approved_leave_record = (employee_entry.employee_id, cursor) in approved_leave_days
            partial_leaves = partial_leave_by_day.get(leave_key, [])
            partial_leave_minutes = 0
            paid_partial_leave_minutes = 0
            unpaid_partial_leave_minutes = 0
            if len(partial_leaves) > 1:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="multiple_partial_leave_requests_unresolved",
                        message="Multiple approved hourly leave requests exist for this employee and work date; resolve them into one authorized request before payroll calculation.",
                        work_date=cursor,
                    )
                )
                break
            if partial_leaves and leave_key in approved_leave_days:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="partial_and_full_day_leave_conflict",
                        message="Approved hourly and full-day leave overlap on this work date; resolve the conflicting leave records before payroll calculation.",
                        work_date=cursor,
                    )
                )
                break
            if partial_leaves:
                partial_leave = partial_leaves[0]
                leave_hours, leave_policy_id, leave_id = partial_leave
                partial_minutes_decimal = leave_hours * Decimal(60)
                leave_policy = (
                    leave_policies_by_id.get(leave_policy_id)
                    if leave_policy_id is not None
                    else None
                )
                if partial_minutes_decimal != partial_minutes_decimal.to_integral_value():
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="partial_leave_minute_precision_invalid",
                            message="Approved hourly leave must resolve to a whole number of minutes.",
                            work_date=cursor,
                        )
                    )
                    break
                if leave_policy is None:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="leave_policy_unavailable",
                            message="Approved hourly leave has no available leave policy, so paid versus unpaid treatment cannot be verified.",
                            work_date=cursor,
                        )
                    )
                    break
                partial_leave_minutes = int(partial_minutes_decimal)
                if partial_leave_minutes <= 0 or partial_leave_minutes > shift.total_hours_minus_lunch:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="partial_leave_duration_invalid",
                            message="Approved hourly leave must be greater than zero and no longer than the effective shift.",
                            work_date=cursor,
                        )
                    )
                    break
                if holiday_configs:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="partial_leave_holiday_unresolved",
                            message="Hourly leave on a holiday requires a confirmed holiday-and-leave stacking rule.",
                            work_date=cursor,
                        )
                    )
                    break
                if dtr is not None and dtr.is_absent:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="partial_leave_attendance_conflict",
                            message="Hourly leave conflicts with a full-day absence disposition; correct the attendance disposition.",
                            work_date=cursor,
                        )
                    )
                    break
                worked_for_leave = (
                    0 if dtr is None or dtr.is_absent else int(dtr.rendered_minutes or 0)
                )
                if worked_for_leave + partial_leave_minutes > shift.total_hours_minus_lunch:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="partial_leave_attendance_overlap",
                            message="Worked minutes plus approved hourly leave exceed the effective shift; resolve the overlapping attendance or leave record.",
                            work_date=cursor,
                        )
                    )
                    break
                if dtr is None and partial_leave_minutes < shift.total_hours_minus_lunch:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="partial_leave_attendance_unresolved",
                            message="Partial hourly leave does not resolve the remaining scheduled work time; provide attendance or an authorized absence disposition.",
                            work_date=cursor,
                        )
                    )
                    break
                if partial_leave_minutes == shift.total_hours_minus_lunch:
                    paid_leave = bool(leave_policy.is_paid) and bool(
                        policy.policy.get("paid_leave")
                    )
                    approved_leave_record = True
                    partial_leave_minutes = 0
                else:
                    if bool(leave_policy.is_paid) and bool(policy.policy.get("paid_leave")):
                        paid_partial_leave_minutes = partial_leave_minutes
                    else:
                        unpaid_partial_leave_minutes = partial_leave_minutes
                refs.append(f"leave:{leave_id}:approved-hours:{leave_hours}")
                formulas.append(
                    f"{cursor}: {partial_leave_minutes or int(partial_minutes_decimal)} approved hourly leave minutes; "
                    f"{'paid' if paid_leave or paid_partial_leave_minutes else 'unpaid'} treatment"
                )
            holiday_kind_for_date = holiday_configs[0][0] if holiday_configs else None
            if len(holiday_configs) > 1 and not (
                len(holiday_configs) == 2
                and holiday_kind_for_date in {"regular", "special_non_working"}
                and all(item[0] == holiday_kind_for_date for item in holiday_configs)
            ):
                blockers.append(
                    PayrollPreflightBlocker(
                        code="holiday_configuration_ambiguous",
                        message="Mixed or unsupported overlapping holidays apply to this work date; resolve the holiday configuration before payroll.",
                        work_date=cursor,
                    )
                )
                break
            holiday = bool(holiday_configs)
            holiday_regular_multiplier: Decimal | None = None
            holiday_overtime_multiplier: Decimal | None = None
            holiday_regular_base: Decimal | None = None
            paid_holiday = False
            if holiday:
                holiday_kind = holiday_configs[0][0]
                if any(item[5] for item in holiday_configs):
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="holiday_region_unresolved",
                            message="This regional holiday cannot be applied until the employee work location is mapped to the holiday region.",
                            work_date=cursor,
                        )
                    )
                    break
                if holiday_kind == "regular" and (dtr is None or dtr.is_absent):
                    paid_holiday, eligibility_error, eligibility_dtr = preceding_workday_eligibility(cursor, employee)
                    if eligibility_error:
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="regular_holiday_eligibility_unresolved",
                                message=eligibility_error,
                                work_date=cursor,
                            )
                        )
                        break
                    if eligibility_dtr is not None:
                        refs.append(
                            f"attendance:{eligibility_dtr.id}:revision:{eligibility_dtr.interval_revision}"
                        )
                    formulas.append(
                        f"{cursor}: unworked regular holiday; prior scheduled workday eligibility {'met' if paid_holiday else 'not met'}"
                    )
                elif holiday_kind != "regular":
                    paid_holiday = bool(policy.policy.get("paid_holidays"))
                holiday_worked = bool(
                    dtr is not None
                    and not dtr.is_absent
                    and int(dtr.rendered_minutes or 0) > 0
                )
                if len(holiday_configs) == 2 and paid_holiday and not holiday_worked:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="double_holiday_unworked_unresolved",
                            message="Paid unworked double-holiday treatment is not configured; confirm the applicable monthly/daily entitlement before calculation.",
                            work_date=cursor,
                        )
                    )
                    break
                refs.extend(
                    f"holiday:{item[6]}:{item[0]}:{cursor}" for item in holiday_configs
                )
                if dtr is not None and not dtr.is_absent and int(dtr.rendered_minutes or 0) > 0:
                    configured_regular = [
                        item[3] if is_rest_day else item[1] for item in holiday_configs
                    ]
                    configured_overtime = [
                        item[4] if is_rest_day else item[2] for item in holiday_configs
                    ]
                    try:
                        if any(item[0] != holiday_kind for item in holiday_configs):
                            raise HolidayRateError(
                                "Mixed holiday types on the same date require an explicitly reviewed stacking rule."
                            )
                        applicable_regular_factor, applicable_overtime_factor = (
                            resolve_holiday_factors(
                                holiday_kind,
                                len(holiday_configs),
                                rest_day=is_rest_day,
                                configured_regular=configured_regular,
                                configured_overtime=configured_overtime,
                            )
                        )
                    except HolidayRateError as exc:
                        error_message = str(exc)
                        blockers.append(
                            PayrollPreflightBlocker(
                                code=(
                                    "holiday_multiplier_incomplete"
                                    if "configuration is incomplete" in error_message
                                    else "holiday_rate_unresolved"
                                ),
                                message=error_message,
                                work_date=cursor,
                            )
                        )
                        break
                    holiday_regular_multiplier = applicable_regular_factor
                    holiday_overtime_multiplier = applicable_overtime_factor
                    if effective_salary.pay_type == PayType.MONTHLY:
                        try:
                            holiday_divisor = Decimal(
                                str(policy.policy["monthly_holiday_pay_divisor"])
                            )
                        except (KeyError, InvalidOperation, TypeError, ValueError):
                            holiday_divisor = Decimal("0")
                        if holiday_divisor <= 0:
                            blockers.append(
                                PayrollPreflightBlocker(
                                    code="monthly_holiday_basis_unconfirmed",
                                    message="Confirm a positive monthly_holiday_pay_divisor before calculating a worked holiday premium for monthly-paid employees.",
                                    work_date=cursor,
                                )
                            )
                            break
                        holiday_regular_base = (
                            effective_salary.basic_rate / holiday_divisor
                        )
                    formulas.append(
                        f"{cursor}: {len(holiday_configs)} {holiday_kind} holiday(s), statutory-safe premium"
                        f"{' on rest day' if is_rest_day else ''}; regular factor {applicable_regular_factor}; "
                        f"overtime factor {applicable_overtime_factor}"
                    )
            rest_day_regular_multiplier: Decimal | None = None
            rest_day_overtime_multiplier: Decimal | None = None
            rest_day_regular_base: Decimal | None = None
            if is_rest_day and not holiday and worked_on_rest_day:
                try:
                    (
                        rest_day_regular_multiplier,
                        rest_day_overtime_multiplier,
                    ) = _confirmed_rest_day_factors(policy.policy)
                    if effective_salary.pay_type == PayType.MONTHLY:
                        rest_day_divisor = Decimal(
                            str(policy.policy["monthly_divisor"])
                        )
                        if rest_day_divisor <= 0:
                            raise ValueError("monthly_divisor must be positive")
                        rest_day_regular_base = (
                            effective_salary.basic_rate
                            / rest_day_divisor
                            * Decimal(
                                min(
                                    int(dtr.rendered_minutes or 0)
                                    if dtr is not None
                                    else 0,
                                    shift.total_hours_minus_lunch,
                                )
                            )
                            / Decimal(shift.total_hours_minus_lunch)
                        )
                except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code="rest_day_policy_unconfirmed",
                            message=f"Ordinary rest-day work cannot be calculated: {exc}.",
                            work_date=cursor,
                        )
                    )
                    break
                formulas.append(
                    f"{cursor}: ordinary rest-day work; total factors "
                    f"{rest_day_regular_multiplier} regular and "
                    f"{rest_day_overtime_multiplier} overtime"
                )
            if (
                is_rest_day
                and effective_salary.pay_type == PayType.MONTHLY
                and not worked_on_rest_day
            ):
                # A monthly-paid employee's ordinary monthly base already
                # includes unworked rest days and holidays; do not add a
                # scheduled-day fraction for an unscheduled date.
                cursor += timedelta(days=1)
                continue
            resolved_no_punch_day = approved_leave_record or holiday
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
                night_regular_minutes = 0
                night_overtime_minutes = 0
                if dtr is not None and worked_minutes > 0:
                    interval_records = dtr_intervals.get(dtr.id, [])
                    if interval_records:
                        actual_intervals = [
                            (item.start_at, item.end_at) for item in interval_records
                        ]
                    elif dtr.interval_revision > 0:
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="night_differential_interval_history_missing",
                                message="Current attendance interval revision is missing; repair attendance history before calculating night work.",
                                work_date=cursor,
                            )
                        )
                        break
                    elif dtr.login_date is not None and dtr.logout_date is not None:
                        actual_intervals = [(dtr.login_date, dtr.logout_date)]
                    else:
                        actual_intervals = []
                    if actual_intervals:
                        try:
                            night_regular_minutes, night_overtime_minutes = (
                                allocate_night_work_minutes(
                                    actual_intervals,
                                    scheduled_minutes=shift.total_hours_minus_lunch,
                                    expected_worked_minutes=worked_minutes,
                                    approved_overtime_minutes=approved_ot,
                                    unpaid_break_minutes=(
                                        shift.lunch_break_duration
                                        if len(actual_intervals) == 1
                                        else 0
                                    ),
                                    zone=ZoneInfo(
                                        str(policy.policy.get("timezone", "Asia/Manila"))
                                    ),
                                )
                            )
                        except (NightDifferentialInputError, ZoneInfoNotFoundError) as exc:
                            blockers.append(
                                PayrollPreflightBlocker(
                                    code="night_differential_attendance_unresolved",
                                    message=str(exc),
                                    work_date=cursor,
                                )
                            )
                            break
                night_differential_rate: Decimal | None = None
                if night_regular_minutes or night_overtime_minutes:
                    premium_rules = policy.policy.get("premium_rules")
                    configured_night_rate = (
                        premium_rules.get("night_differential_rate")
                        if isinstance(premium_rules, dict)
                        else None
                    )
                    try:
                        night_differential_rate = Decimal(str(configured_night_rate))
                    except (InvalidOperation, TypeError, ValueError):
                        night_differential_rate = None
                    if (
                        night_differential_rate is None
                        or night_differential_rate < Decimal("0.10")
                    ):
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="night_differential_policy_unconfirmed",
                                message="Confirmed payroll policy must set premium_rules.night_differential_rate to at least 0.10 for work between 22:00 and 06:00.",
                                work_date=cursor,
                            )
                        )
                        break
                rounding = str(policy.policy["rounding_mode"])
                monthly_partial_rule = policy.policy.get("monthly_partial_work")
                if monthly_partial_rule is not None:
                    monthly_partial_rule = str(monthly_partial_rule)
                if effective_salary.pay_type == PayType.MONTHLY:
                    monthly_proration = policy.policy.get("monthly_salary_proration")
                    if monthly_proration not in {
                        "scheduled_workday_fraction",
                        "monthly_divisor_per_workday",
                    }:
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="monthly_salary_proration_unconfirmed",
                                message="Confirm monthly salary proration as a fixed pay-period fraction or monthly-divisor amount per scheduled workday.",
                                work_date=cursor,
                            )
                        )
                        break
                    if (
                        monthly_proration == "scheduled_workday_fraction"
                        and monthly_period_fraction is None
                    ):
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="monthly_salary_group_incompatible",
                                message="Monthly-paid employees must use a monthly or twice-monthly pay group.",
                                work_date=cursor,
                            )
                        )
                        break
                    if (
                        monthly_proration == "scheduled_workday_fraction"
                        and monthly_period_scheduled_days <= 0
                    ):
                        blockers.append(
                            PayrollPreflightBlocker(
                                code="monthly_salary_schedule_unavailable",
                                message="The full pay-period shift schedule is unavailable for monthly salary proration.",
                                work_date=cursor,
                            )
                        )
                        break
                grace_minutes = int(policy.policy["grace_minutes"])
                raw_late_minutes = 0
                if dtr is not None and dtr.login_date is not None:
                    local_login = dtr.login_date.astimezone(
                        ZoneInfo(str(policy.policy["timezone"]))
                    )
                    if local_login.date() != cursor:
                        raise CalculationBlocker(
                            f"Attendance login is outside its assigned shift work date on {cursor}"
                        )
                    start = time_of_day.fromisoformat(shift.start_time)
                    raw_late_minutes = max(
                        0,
                        local_login.hour * 60
                        + local_login.minute
                        - start.hour * 60
                        - start.minute,
                    )
                calculation_groups.setdefault(
                    (
                        monthly_divisor,
                        partial_rule,
                        multiplier,
                        rounding,
                        monthly_partial_rule,
                        grace_minutes,
                    ),
                    [],
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
                        holiday_regular_multiplier=holiday_regular_multiplier,
                        holiday_overtime_multiplier=holiday_overtime_multiplier,
                        holiday_regular_base=holiday_regular_base,
                        rest_day_regular_multiplier=rest_day_regular_multiplier,
                        rest_day_overtime_multiplier=rest_day_overtime_multiplier,
                        rest_day_regular_base=rest_day_regular_base,
                        night_regular_minutes=night_regular_minutes,
                        night_overtime_minutes=night_overtime_minutes,
                        night_differential_rate=night_differential_rate,
                        raw_late_minutes=raw_late_minutes,
                        grace_minutes=grace_minutes,
                        paid_absence=(paid_leave or paid_holiday)
                        and (
                            dtr is None
                            or dtr.is_absent
                            or (approved_leave_record and worked_minutes == 0)
                        ),
                        absence=bool(
                            (dtr and dtr.is_absent and not (paid_leave or paid_holiday))
                            or (
                                dtr is None
                                and resolved_no_punch_day
                                and not (paid_leave or paid_holiday)
                            )
                            or (
                                approved_leave_record
                                and worked_minutes == 0
                                and not (paid_leave or paid_holiday)
                            )
                        ),
                        paid_leave_minutes=paid_partial_leave_minutes,
                        unpaid_leave_minutes=unpaid_partial_leave_minutes,
                        monthly_period_fraction=monthly_period_fraction,
                        monthly_period_scheduled_days=monthly_period_scheduled_days,
                        monthly_salary_proration=str(
                            policy.policy.get(
                                "monthly_salary_proration",
                                "scheduled_workday_fraction",
                            )
                        ),  # type: ignore[arg-type]
                        monthly_salary_base_eligible=not is_rest_day,
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
            if night_regular_minutes or night_overtime_minutes:
                formulas.append(
                    f"{cursor}: {night_regular_minutes} regular and "
                    f"{night_overtime_minutes} approved overtime night minutes at "
                    f"{night_differential_rate} night differential rate"
                )
            refs.append(
                f"salary:{effective_salary.id}:effective:{effective_salary.effective_date}"
            )
            refs.append(f"shift-assignment:{effective_assignment.id}")
            refs.append(f"policy:{policy.id}:v{policy.version}")
            formulas.append(
                f"{cursor}: {effective_salary.pay_type.value} basis; {worked_minutes} worked minutes; {approved_ot} of {eligible_ot} overtime minutes approved"
            )
            cursor += timedelta(days=1)

        for (
            monthly_divisor,
            partial_rule,
            multiplier,
            rounding,
            monthly_partial_rule,
            _grace_minutes,
        ), days in calculation_groups.items():
            if blockers:
                break
            try:
                results.append(
                    calculate_attendance_earnings(
                        days,
                        monthly_divisor=monthly_divisor,
                        daily_partial_work=partial_rule,  # type: ignore[arg-type]
                        overtime_multiplier=multiplier,
                        monthly_partial_work=monthly_partial_rule,  # type: ignore[arg-type]
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
        holiday_premium = sum(
            (result.holiday_premium for result in results), Decimal("0.00")
        )
        rest_day_premium = sum(
            (result.rest_day_premium for result in results), Decimal("0.00")
        )
        night_differential = sum(
            (result.night_differential for result in results), Decimal("0.00")
        )
        fixed_allowance = Decimal("0.00")
        try:
            fixed_allowance = _fixed_recurring_allowance_for_period(
                salaries=employee_salaries,
                employee=employee,
                date_from=date_from,
                date_to=date_to,
                policies=policies,
            )
        except StatutoryScheduleUnavailable as exc:
            blockers.append(
                PayrollPreflightBlocker(
                    code="allowance_tax_treatment_unavailable",
                    message=str(exc),
                )
            )
        if fixed_allowance:
            formulas.append(
                f"Fixed recurring allowance: {fixed_allowance} taxable; calendar-day prorated over employed dates; attendance absences do not reduce it"
            )
        attendance_deduction = sum(
            (result.attendance_deduction for result in results), Decimal("0.00")
        )
        short_time_deduction = sum(
            (result.short_time_deduction for result in results), Decimal("0.00")
        )
        previews.append(
            PayrollAttendanceCalculationEntry(
                employee_id=employee_entry.employee_id,
                employee_code=employee_entry.employee_code,
                employee_name=employee_entry.employee_name,
                regular_earnings=regular if not blockers else None,
                approved_overtime=overtime if not blockers else None,
                holiday_premium=holiday_premium if not blockers else None,
                rest_day_premium=rest_day_premium if not blockers else None,
                night_differential=night_differential if not blockers else None,
                fixed_recurring_allowance=fixed_allowance,
                attendance_deduction=attendance_deduction if not blockers else None,
                short_time_deduction=short_time_deduction if not blockers else None,
                gross_before_statutory=(
                    regular
                    + overtime
                    + holiday_premium
                    + rest_day_premium
                    + night_differential
                    + fixed_allowance
                    if not blockers
                    else None
                ),
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
    lock_payroll_roster(session)
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
    policy_by_day: dict[date, PayrollPolicyVersion] = {}
    cursor = obj_in.date_from
    while cursor <= obj_in.date_to:
        applicable = [
            row
            for row in policies
            if row.confirmed
            and row.effective_from <= cursor
            and (row.effective_to is None or row.effective_to >= cursor)
        ]
        if len(applicable) != 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Exactly one confirmed payroll policy must cover every day of the prepared period.",
                    "work_date": cursor.isoformat(),
                },
            )
        policy_by_day[cursor] = applicable[0]
        cursor += timedelta(days=1)
    # The run-level reference is the policy effective on period end. Calculation
    # uses the full effective-dated schedule and snapshots every overlapping row.
    policy = policy_by_day[obj_in.date_to]
    policy_schedule = list({row.id: row for row in policy_by_day.values()}.values())
    policy_schedule.sort(key=lambda row: (row.effective_from, str(row.id)))
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
    month_policy_rows = session.exec(
        select(PayrollPolicyVersion)
        .where(
            PayrollPolicyVersion.effective_from <= month_end,
            (col(PayrollPolicyVersion.effective_to).is_(None))
            | (col(PayrollPolicyVersion.effective_to) >= month_start),
            col(PayrollPolicyVersion.confirmed).is_(True),
        )
        .order_by(col(PayrollPolicyVersion.effective_from))
    ).all()
    roster_employee_ids = {
        row.employee_id for row in roster.entries if row.employee_id is not None
    }
    roster_employees = (
        session.exec(
            select(EmployeeRecords).where(
                col(EmployeeRecords.id).in_(roster_employee_ids)
            )
        ).all()
        if roster_employee_ids
        else []
    )
    separation_dates = {
        employee.id: employee.date_separated
        for employee in roster_employees
        if str(
            getattr(employee.employee_status, "value", employee.employee_status)
        )
        in {"Resigned", "Terminated"}
        and employee.date_separated is not None
        and obj_in.date_from <= employee.date_separated <= obj_in.date_to
    }
    full_month_previews: dict[uuid.UUID, PayrollAttendanceCalculationEntry] = {}
    if obj_in.date_to == month_end or separation_dates:
        # The preview endpoint accepts only complete configured earning
        # periods. Build the statutory monthly basis from the periods through
        # the final-pay period, rather than asking it to evaluate an invalid
        # all-month range for a split-pay group.
        for configured_period in configured_periods:
            configured_period_from = date.fromisoformat(
                str(configured_period.date_from)[:10]
            )
            if configured_period_from > obj_in.date_to:
                continue
            slice_preview = attendance_calculation_preview(
                session=session,
                pay_group_id=obj_in.pay_group_id,
                date_from=configured_period_from,
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
                    holiday_premium=(
                        previous.holiday_premium + entry.holiday_premium
                        if previous.holiday_premium is not None
                        and entry.holiday_premium is not None
                        else None
                    ),
                    rest_day_premium=(
                        previous.rest_day_premium + entry.rest_day_premium
                        if previous.rest_day_premium is not None
                        and entry.rest_day_premium is not None
                        else None
                    ),
                    night_differential=(
                        previous.night_differential + entry.night_differential
                        if previous.night_differential is not None
                        and entry.night_differential is not None
                        else None
                    ),
                    attendance_deduction=(
                        previous.attendance_deduction + entry.attendance_deduction
                        if previous.attendance_deduction is not None
                        and entry.attendance_deduction is not None
                        else None
                    ),
                    short_time_deduction=(
                        previous.short_time_deduction + entry.short_time_deduction
                        if previous.short_time_deduction is not None
                        and entry.short_time_deduction is not None
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
        employee_record = session.get(EmployeeRecords, roster_entry.employee_id)
        fixed_allowance = Decimal("0.00")
        if not employee_salaries:
            blockers.append(
                PayrollPreflightBlocker(
                    code="salary_missing",
                    message="An effective salary is required to calculate this employee's payroll.",
                )
            )
        else:
            try:
                fixed_allowance = _fixed_recurring_allowance_for_period(
                    salaries=employee_salaries,
                    employee=employee_record,
                    date_from=obj_in.date_from,
                    date_to=obj_in.date_to,
                    policies=policy_schedule,
                )
            except StatutoryScheduleUnavailable as exc:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="allowance_tax_treatment_unavailable",
                        message=str(exc),
                    )
                )
        salary_refs = [
            {
                "id": str(salary.id),
                "updated_at": salary.updated_at.isoformat()
                if salary.updated_at
                else None,
                "basic_rate": str(salary.basic_rate),
                "currency": salary.currency,
                "effective_date": salary.effective_date.isoformat(),
                "pay_type": str(getattr(salary.pay_type, "value", salary.pay_type)),
                "overtime_rate": str(salary.overtime_rate),
                "absent_penalty_rate": str(salary.absent_penalty_rate),
                "non_taxable_allowance": str(salary.non_taxable_allowance),
                "de_minimis_monthly": salary.de_minimis_monthly,
                "thirteenth_month_exempt_portion": str(
                    salary.thirteenth_month_exempt_portion
                ),
                "is_active": salary.is_active,
            }
            for salary in employee_salaries
        ]
        monthly_contributions: dict[str, Any] | None = None
        final_period_of_month = obj_in.date_to == month_end
        separation_final_pay = roster_entry.employee_id in separation_dates
        if final_period_of_month or separation_final_pay:
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
                    collection_configs = {
                        json.dumps(
                            row.policy.get("contribution_collection"),
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        for row in month_policy_rows
                    }
                    if len(collection_configs) != 1 or "null" in collection_configs:
                        raise StatutoryScheduleUnavailable(
                            "The once-monthly contribution collection rule must be confirmed and consistent across all policy versions in the contribution month"
                        )
                    full_month = full_month_previews.get(roster_entry.employee_id)
                    if full_month is None:
                        raise StatutoryScheduleUnavailable(
                            "Full-month attendance calculation did not return this employee"
                        )
                    if full_month.blockers:
                        raise StatutoryScheduleUnavailable(
                            "Resolve the full month's attendance and overtime blockers before assessing SSS compensation"
                        )
                    full_month_fixed_allowance = _fixed_recurring_allowance_for_period(
                        salaries=employee_salaries,
                        employee=employee_record,
                        date_from=month_start,
                        date_to=month_start.replace(
                            day=calendar.monthrange(month_start.year, month_start.month)[1]
                        ),
                        policies=month_policy_rows,
                    )
                    sss_basis = (
                        full_month.regular_earnings
                        - full_month.attendance_deduction
                        + full_month.approved_overtime
                        + full_month_fixed_allowance
                        if full_month.regular_earnings is not None
                        and full_month.attendance_deduction is not None
                        and full_month.approved_overtime is not None
                        else None
                    )
                    if sss_basis is None or sss_basis <= 0:
                        raise StatutoryScheduleUnavailable(
                            "Full-month regular and approved overtime earnings are required for the SSS compensation basis"
                        )
                    pagibig_basis = sss_basis
                    policy_sources_set: set[str] = set()
                    for month_policy in month_policy_rows:
                        sources = month_policy.policy.get("statutory_sources_reviewed")
                        if (
                            not isinstance(sources, list)
                            or not sources
                            or any(
                                not isinstance(source, str)
                                or not source.startswith("https://")
                                for source in sources
                            )
                        ):
                            raise StatutoryScheduleUnavailable(
                                "Each confirmed monthly payroll policy must retain its reviewed HTTPS statutory source list"
                            )
                        policy_sources_set.update(sources)
                    policy_sources = sorted(policy_sources_set)
                    philhealth_basis = _philhealth_monthly_basic_salary_basis(
                        session=session,
                        employee_id=roster_entry.employee_id,
                        salaries=employee_salaries,
                        contribution_month=month_start,
                        policies=month_policy_rows,
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
                        "sss": "full-month regular earnings less unpaid absence and monthly short-time deductions, plus approved overtime and the confirmed taxable fixed recurring allowance; indexed by the effective SSS schedule",
                        "philhealth": (
                            "contractual fixed-basic monthly equivalent; monthly salary is weighted by calendar days, while daily/hourly rates use each effective policy divisor and the effective scheduled shift minutes; overtime and absence deductions excluded"
                        ),
                        "pagibig": "full-month regular earnings less unpaid absence and monthly short-time deductions, plus approved overtime and taxable fixed recurring allowances; de minimis amounts remain blocked pending category and eligibility evidence",
                        "fixed_recurring_allowance": "monthly fixed amount prorated by employed calendar days; taxable under the confirmed company policy, not reduced for attendance, included in SSS and Pag-IBIG compensation, and excluded from PhilHealth monthly basic salary",
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
        elif (
            tax_declaration.tax_classification == "minimum_wage_earner"
            and not (tax_declaration.source_reference or "").strip()
        ):
            blockers.append(
                PayrollPreflightBlocker(
                    code="bir_mwe_evidence_unavailable",
                    message="A verified minimum-wage-earner classification needs a source note for the assigned work location and applicable DOLE wage order.",
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
                "work_date": row.work_date.isoformat() if row.work_date else None,
                "shift_id": str(row.shift_id) if row.shift_id else None,
                "login_date": row.login_date.isoformat() if row.login_date else None,
                "logout_date": row.logout_date.isoformat() if row.logout_date else None,
                "rendered_minutes": row.rendered_minutes,
                "late_minutes": row.late_minutes,
                "undertime_minutes": row.undertime_minutes,
                "overtime_minutes": row.overtime_minutes,
                "overtime_approved": row.overtime_approved,
                "overtime_approved_minutes": row.overtime_approved_minutes,
                "overtime_decision_reason": row.overtime_decision_reason,
                "overtime_decided_by": str(row.overtime_decided_by)
                if row.overtime_decided_by
                else None,
                "is_absent": row.is_absent,
            }
            for row in dtr_rows
        ]
        employee_record = session.get(EmployeeRecords, roster_entry.employee_id)
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
                "employee_id": str(row.employee_id),
                "shift_id": str(row.shift_id),
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat()
                if row.effective_to
                else None,
                "is_deleted": row.is_deleted,
            }
            for row in shift_rows
        ]
        shift_ids = {row.shift_id for row in shift_rows}
        shift_model_rows = (
            session.exec(select(Shift).where(col(Shift.id).in_(shift_ids))).all()
            if shift_ids
            else []
        )
        shift_references = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "code": row.code,
                "name": row.name,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "lunch_break_duration": row.lunch_break_duration,
                "total_hours_minus_lunch": row.total_hours_minus_lunch,
                "days_of_week": list(row.days_of_week),
                "is_deleted": row.is_deleted,
            }
            for row in sorted(shift_model_rows, key=lambda item: str(item.id))
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
                "employee_id": str(row.employee_id),
                "pay_group_id": str(row.pay_group_id),
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat()
                if row.effective_to
                else None,
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
                "employee_id": str(row.employee_id) if row.employee_id else None,
                "policy_id": str(row.policy_id) if row.policy_id else None,
                "date_start": row.date_start.isoformat(),
                "date_end": row.date_end.isoformat(),
                "requested_hours": str(row.requested_hours)
                if row.requested_hours is not None
                else None,
                "total_days_requested": str(row.total_days_requested),
                "status": str(getattr(row.status, "value", row.status)),
            }
            for row in leave_rows
        ]
        leave_policy_ids = {
            row.policy_id for row in leave_rows if row.policy_id is not None
        }
        leave_policy_rows = (
            session.exec(
                select(LeavePolicy).where(col(LeavePolicy.id).in_(leave_policy_ids))
            ).all()
            if leave_policy_ids
            else []
        )
        leave_policy_refs = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "is_paid": row.is_paid,
                "is_active": row.is_active,
                "is_deleted": row.is_deleted,
            }
            for row in sorted(leave_policy_rows, key=lambda item: str(item.id))
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
                "config_id": str(row.config_id),
                "observed_date": row.observed_date.isoformat(),
                "raw_date": row.raw_date.isoformat() if row.raw_date else None,
                "is_active": row.is_active,
                "is_deleted": row.is_deleted,
            }
            for row in holiday_rows
        ]
        holiday_config_rows = session.exec(
            select(HolidayConfig)
            .join(
                HolidayInstance,
                col(HolidayInstance.config_id) == col(HolidayConfig.id),
            )
            .where(
                HolidayInstance.observed_date >= obj_in.date_from,
                HolidayInstance.observed_date <= obj_in.date_to,
                col(HolidayInstance.is_active).is_(True),
                col(HolidayInstance.is_deleted).is_(False),
                col(HolidayConfig.is_active).is_(True),
                col(HolidayConfig.is_deleted).is_(False),
            )
            .distinct()
        ).all()
        holiday_config_refs = [
            {
                "id": str(row.id),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "type": str(getattr(row.type, "value", row.type)),
                "multiplier_regular": str(row.multiplier_regular),
                "multiplier_overtime": str(row.multiplier_overtime),
                "multiplier_regular_rest_day": str(row.multiplier_regular_rest_day),
                "multiplier_overtime_rest_day": str(row.multiplier_overtime_rest_day),
                "region_code": row.region_code,
            }
            for row in holiday_config_rows
        ]
        snapshot: dict[str, Any] = {
            "attendance_revisions": attendance_refs,
            "salary_versions": salary_refs,
            "shift_assignments": shift_refs,
            "shift_revisions": shift_references,
            "pay_group_assignments": group_refs,
            "leave_revisions": leave_refs,
            "leave_policy_revisions": leave_policy_refs,
            "holiday_revisions": holiday_refs,
            "holiday_config_revisions": holiday_config_refs,
            "policy_versions": [
                {
                    "id": str(policy_row.id),
                    "version": policy_row.version,
                    "effective_from": policy_row.effective_from.isoformat(),
                    "effective_to": policy_row.effective_to.isoformat()
                    if policy_row.effective_to
                    else None,
                    "policy": policy_row.policy,
                    "confirmed": policy_row.confirmed,
                    "confirmed_by": str(policy_row.confirmed_by)
                    if policy_row.confirmed_by
                    else None,
                    "confirmed_at": policy_row.confirmed_at.isoformat()
                    if policy_row.confirmed_at
                    else None,
                }
                for policy_row in sorted(policies, key=lambda item: str(item.id))
            ],
            "employee_id": str(roster_entry.employee_id),
            "employee_record": (
                {
                    "id": str(employee_record.id),
                    "employee_code": employee_record.employee_code,
                    "first_name": employee_record.first_name,
                    "last_name": employee_record.last_name,
                    "email": employee_record.email,
                    "is_deleted": employee_record.is_deleted,
                    "employee_status": str(
                        getattr(employee_record.employee_status, "value", employee_record.employee_status)
                    ),
                    "date_hired": employee_record.date_hired.isoformat()
                    if employee_record.date_hired
                    else None,
                    "date_separated": employee_record.date_separated.isoformat()
                    if employee_record.date_separated
                    else None,
                }
                if employee_record is not None
                else None
            ),
            "pay_group_id": str(group.id),
            "pay_group_cadence": group.cadence.value,
            "pay_group": {
                "id": str(group.id),
                "code": group.code,
                "name": group.name,
                "cadence": group.cadence.value,
                "first_period_end_day": group.first_period_end_day,
                "second_period_end_day": group.second_period_end_day,
                "payment_offset_days": group.payment_offset_days,
                "weekend_rule": group.weekend_rule,
                "is_active": group.is_active,
                "updated_at": group.updated_at.isoformat()
                if group.updated_at
                else None,
            },
            "period": {
                "from": obj_in.date_from.isoformat(),
                "to": obj_in.date_to.isoformat(),
            },
            "fixed_recurring_allowance": {
                "amount": str(fixed_allowance),
                "tax_treatment": "taxable" if fixed_allowance else None,
                "proration": "calendar_days_employed" if fixed_allowance else None,
                "absence_treatment": "not_deducted" if fixed_allowance else None,
                "policy": policy.policy.get("allowance_tax_treatment", {}),
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
                "opening_pay_period_count": tax_declaration.opening_pay_period_count,
                "opening_pay_period_type": tax_declaration.opening_pay_period_type,
                "previous_employer_included": tax_declaration.previous_employer_included,
                "source_reference": tax_declaration.source_reference,
                "opening_benefits_exempt_ytd": str(tax_declaration.opening_benefits_exempt_ytd),
                "opening_benefits_reconciled": tax_declaration.opening_benefits_reconciled,
                "opening_de_minimis_annual_ytd": tax_declaration.opening_de_minimis_annual_ytd,
                "opening_de_minimis_monthly_ytd": tax_declaration.opening_de_minimis_monthly_ytd,
                "opening_unused_vacation_leave_days_ytd": tax_declaration.opening_unused_vacation_leave_days_ytd,
                "opening_as_of": tax_declaration.opening_as_of.isoformat()
                if tax_declaration.opening_as_of
                else None,
                "verified": tax_declaration.is_verified,
            }
            snapshot["bir_tax_benefit_ledger"] = _bir_tax_benefit_rows(
                session,
                roster_entry.employee_id,
                obj_in.date_to.year,
                tax_declaration.opening_as_of,
                obj_in.date_to,
                tax_declaration.opening_de_minimis_annual_ytd,
                tax_declaration.opening_de_minimis_monthly_ytd,
                tax_declaration.opening_unused_vacation_leave_days_ytd,
                bool(
                    tax_declaration.opening_benefits_reconciled
                    or tax_declaration.previous_employer_included
                ),
            )
            seen_benefit_blockers = {blocker.code for blocker in blockers}
            for benefit_row in snapshot["bir_tax_benefit_ledger"]:
                blocker_code = benefit_row.get("calculation_blocker", "")
                if blocker_code and blocker_code not in seen_benefit_blockers:
                    blockers.append(
                        PayrollPreflightBlocker(
                            code=blocker_code,
                            message=benefit_row.get(
                                "calculation_blocker_message",
                                "A de minimis benefit needs verified evidence before tax can be calculated.",
                            ),
                        )
                    )
                    seen_benefit_blockers.add(blocker_code)
        benefit_rows = snapshot.get("bir_tax_benefit_ledger", [])
        benefits_subject_to_shared_cap = sum(
            (
                Decimal(row["taxable_other_benefit_amount"])
                for row in benefit_rows
            ),
            Decimal("0.00"),
        )
        benefits_exempt_remaining = max(
            Decimal("0.00"),
            BIR_13TH_MONTH_AND_OTHER_BENEFITS_EXEMPTION_CAP
            - (
                tax_declaration.opening_benefits_exempt_ytd
                if tax_declaration is not None
                else Decimal("0.00")
            ),
        )
        benefits_taxable_excess = max(
            Decimal("0.00"),
            benefits_subject_to_shared_cap - benefits_exempt_remaining,
        )
        if (
            benefits_taxable_excess > 0
            and tax_declaration is not None
            and not tax_declaration.opening_benefits_reconciled
        ):
            blockers.append(
                PayrollPreflightBlocker(
                    code="bir_benefit_opening_unreconciled",
                    message=(
                        "Taxable benefit excess requires a verified opening balance for the shared annual benefit exemption."
                    ),
                )
            )
        bir_period = group.cadence
        effective_bir_rows = session.exec(
            select(BIRBracket).where(
                BIRBracket.period == bir_period,
                BIRBracket.effective_date <= obj_in.date_to,
                col(BIRBracket.is_active).is_(True),
                col(BIRBracket.is_deleted).is_(False),
            ).order_by(col(BIRBracket.bracket_min))
        ).all()
        bir_first_taxable_regular_amount: Decimal | None = None
        if effective_bir_rows:
            latest_bir_date = max(row.effective_date for row in effective_bir_rows)
            effective_bir_rows = [
                row for row in effective_bir_rows if row.effective_date == latest_bir_date
            ]
            taxable_regular_thresholds = [
                row.bracket_min
                for row in effective_bir_rows
                if row.bracket_min > 0
                and row.base_tax == 0
                and row.excess_rate > 0
            ]
            if taxable_regular_thresholds:
                bir_first_taxable_regular_amount = min(taxable_regular_thresholds)
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
        short_time_deduction = (
            preview.short_time_deduction
            if preview and preview.short_time_deduction is not None
            else Decimal("0.00")
        )
        holiday_premium = (
            preview.holiday_premium
            if preview and preview.holiday_premium is not None
            else Decimal("0.00")
        )
        rest_day_premium = (
            preview.rest_day_premium
            if preview and preview.rest_day_premium is not None
            else Decimal("0.00")
        )
        night_differential = (
            preview.night_differential
            if preview and preview.night_differential is not None
            else Decimal("0.00")
        )
        gross = (
            regular
            + overtime
            + holiday_premium
            + rest_day_premium
            + night_differential
            + fixed_allowance
        )
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
            "attendance_breakdown": {
                "unpaid_absence": str(attendance_deduction - short_time_deduction),
                "monthly_short_time_after_grace": str(short_time_deduction),
            },
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
        employee_contributions = sum(employee_statutory.values(), Decimal("0.00"))
        regular_compensation_before_deductions = regular + fixed_allowance
        attendance_over_regular = max(
            Decimal("0.00"),
            attendance_deduction - regular_compensation_before_deductions,
        )
        regular_taxable_compensation = max(
            Decimal("0.00"),
            regular_compensation_before_deductions - attendance_deduction,
        )
        supplementary_taxable_compensation = max(
            Decimal("0.00"),
            overtime
            + holiday_premium
            + rest_day_premium
            + night_differential
            + benefits_taxable_excess
            - attendance_over_regular,
        )
        contributions_against_regular = min(
            regular_taxable_compensation, employee_contributions
        )
        regular_taxable_compensation -= contributions_against_regular
        supplementary_taxable_compensation = max(
            Decimal("0.00"),
            supplementary_taxable_compensation
            - (employee_contributions - contributions_against_regular),
        )
        bir_withholding = Decimal("0.00")
        is_minimum_wage_earner = (
            tax_declaration is not None
            and tax_declaration.tax_classification == "minimum_wage_earner"
        )
        if (
            tax_declaration is not None
            and tax_declaration.is_verified
            and tax_declaration.tax_classification == "ordinary"
        ):
            snapshot["bir_compensation_breakdown"] = {
                "regular_taxable_compensation": str(regular_taxable_compensation),
                "supplementary_taxable_compensation": str(
                    supplementary_taxable_compensation
                ),
                "attendance_and_employee_contributions_reduce_regular_first": True,
            }
        mwe_has_taxable_allowance = is_minimum_wage_earner and fixed_allowance > 0
        if mwe_has_taxable_allowance:
            blockers.append(
                PayrollPreflightBlocker(
                    code="bir_mwe_taxable_allowance_ineligible",
                    message=(
                        "A taxable fixed recurring allowance is incompatible with the declared minimum-wage-earner exemption under BIR RR 10-2008; verify and update the employee's tax classification before payroll review."
                    ),
                )
            )
        has_mwe_evidence = bool(
            tax_declaration and (tax_declaration.source_reference or "").strip()
        )
        if is_minimum_wage_earner and benefits_taxable_excess > 0:
            blockers.append(
                PayrollPreflightBlocker(
                    code="bir_mwe_taxable_benefit_classification_unavailable",
                    message=(
                        "A minimum-wage-earner with benefits above the shared annual exemption needs a reviewed tax classification before withholding can be calculated."
                    ),
                )
            )
        if (
            tax_declaration is not None
            and tax_declaration.is_verified
            and (
                tax_declaration.tax_classification == "ordinary"
                or (
                    is_minimum_wage_earner
                    and has_mwe_evidence
                    and not mwe_has_taxable_allowance
                )
            )
        ):
            if taxable_pay < 0:
                blockers.append(
                    PayrollPreflightBlocker(
                        code="bir_taxable_compensation_negative",
                        message="Employee-side mandatory contributions exceed this period's gross earnings; BIR taxable compensation requires correction.",
                    )
                )
            else:
                try:
                    bir_taxable_pay = (
                        Decimal("0.00") if is_minimum_wage_earner else taxable_pay
                    )
                    is_year_end = obj_in.date_to == date(
                        obj_in.date_to.year,
                        12,
                        calendar.monthrange(obj_in.date_to.year, 12)[1],
                    )
                    employee_row = session.get(EmployeeRecords, roster_entry.employee_id)
                    employee_status = (
                        str(getattr(employee_row.employee_status, "value", employee_row.employee_status))
                        if employee_row is not None
                        else ""
                    )
                    is_termination_final_pay = (
                        employee_row is not None
                        and employee_status in {"Resigned", "Terminated"}
                        and employee_row.date_separated is not None
                        and obj_in.date_from <= employee_row.date_separated <= obj_in.date_to
                    )
                    annualization_trigger = (
                        "termination_final_pay"
                        if is_termination_final_pay
                        else "year_end"
                        if is_year_end
                        else None
                    )
                    if annualization_trigger is not None:
                        if not tax_declaration.opening_benefits_reconciled:
                            blockers.append(
                                PayrollPreflightBlocker(
                                    code="bir_annual_benefits_unavailable",
                                    message=(
                                        "Annualized BIR withholding requires a verified opening 13th-month/other-benefit exemption balance and all benefit payments after that date."
                                    ),
                                )
                            )
                        opening_as_of = tax_declaration.opening_as_of
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
                            benefit_rows = _bir_tax_benefit_rows(
                                session,
                                roster_entry.employee_id,
                                obj_in.date_to.year,
                                opening_as_of,
                                obj_in.date_to,
                                tax_declaration.opening_de_minimis_annual_ytd,
                                tax_declaration.opening_de_minimis_monthly_ytd,
                                tax_declaration.opening_unused_vacation_leave_days_ytd,
                                bool(
                                    tax_declaration.opening_benefits_reconciled
                                    or tax_declaration.previous_employer_included
                                ),
                            )
                            benefits_gross = benefits_subject_to_shared_cap
                            benefits_exempt_current = min(
                                benefits_gross, benefits_exempt_remaining
                            )
                            annual_taxable = (
                                prior_taxable + bir_taxable_pay + benefits_taxable_excess
                            )
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
                            snapshot["bir_benefit_reconciliation"] = {
                                "exemption_cap": str(BIR_13TH_MONTH_AND_OTHER_BENEFITS_EXEMPTION_CAP),
                                "opening_exempt_benefits": str(
                                    tax_declaration.opening_benefits_exempt_ytd
                                ),
                                "opening_reconciled": tax_declaration.opening_benefits_reconciled,
                                "current_employer_benefit_payments": benefit_rows,
                                "current_employer_benefits_gross": str(
                                    sum(
                                        (Decimal(row["gross_amount"]) for row in benefit_rows),
                                        Decimal("0.00"),
                                    )
                                ),
                                "current_employer_benefits_subject_to_shared_cap": str(
                                    benefits_gross
                                ),
                                "current_employer_benefits_exempt": str(benefits_exempt_current),
                                "current_employer_benefits_taxable_excess": str(
                                    benefits_taxable_excess
                                ),
                            }
                            snapshot["bir_calculation"] = {
                                "method": "annualized_rr_11_2018_2023_onward",
                                "annualization_trigger": annualization_trigger,
                                "taxable_compensation": str(bir_taxable_pay),
                                "annual_taxable_compensation": str(annual_taxable),
                                "taxable_benefit_excess": str(benefits_taxable_excess),
                                "annual_tax_due": str(annual_tax_due),
                                "prior_tax_withheld": str(prior_withheld),
                                "withholding": str(bir_withholding),
                                "schedule_reference": "https://bir-cdn.bir.gov.ph/local/pdf/RR%20No.%2011-2018.pdf",
                                "year_end_adjustment_pending": False,
                            }
                    elif is_minimum_wage_earner:
                        snapshot["bir_calculation"] = {
                            "method": "mwe_exemption_rr_8_2018",
                            "taxable_compensation": "0.00",
                            "withholding": "0.00",
                            "exempt_categories": [
                                "statutory_minimum_wage",
                                "approved_overtime_pay",
                            ],
                            "classification_source": tax_declaration.source_reference,
                            "schedule_reference": "https://bir-cdn.bir.gov.ph/local/pdf/RR%20No.%208-2018.pdf",
                            "year_end_adjustment_pending": False,
                        }
                    else:
                        declaration = tax_declaration
                        has_opening_tax_history = bool(
                            declaration.previous_employer_included
                            or declaration.taxable_compensation_ytd > 0
                            or declaration.tax_withheld_ytd > 0
                        )
                        cumulative_method_previously_applied = (
                            not has_opening_tax_history
                            and benefits_taxable_excess == 0
                            and _bir_cumulative_average_was_used(
                                session,
                                roster_entry.employee_id,
                                obj_in.date_to.year,
                                obj_in.date_from,
                            )
                        )
                        use_cumulative_average = (
                            has_opening_tax_history
                            or benefits_taxable_excess > 0
                            or cumulative_method_previously_applied
                        )
                        if not use_cumulative_average and supplementary_taxable_compensation > 0:
                            if bir_first_taxable_regular_amount is None:
                                raise StatutoryScheduleUnavailable(
                                    "BIR schedule does not identify the first taxable regular-compensation amount needed for supplementary-pay withholding"
                                )
                            use_cumulative_average = cumulative_average_required(
                                regular_compensation=regular_taxable_compensation,
                                supplementary_compensation=supplementary_taxable_compensation,
                                first_taxable_regular_amount=bir_first_taxable_regular_amount,
                            )
                        if use_cumulative_average:
                            if (
                                declaration.opening_as_of is None
                                or declaration.opening_as_of.year != obj_in.date_to.year
                                or declaration.opening_as_of >= obj_in.date_from
                                or (
                                    has_opening_tax_history
                                    and declaration.opening_pay_period_count <= 0
                                )
                                or (
                                    declaration.opening_pay_period_type is not None
                                    and declaration.opening_pay_period_type != group.cadence.value
                                )
                            ):
                                blockers.append(
                                    PayrollPreflightBlocker(
                                        code=(
                                            "bir_cumulative_cadence_mismatch"
                                            if declaration.opening_pay_period_type is not None
                                            and declaration.opening_pay_period_type != group.cadence.value
                                            else "bir_cumulative_opening_unavailable"
                                        ),
                                        message=(
                                            "The prior employer used a different payroll cadence; reconcile the tax-year calculation with a payroll owner before withholding."
                                            if declaration.opening_pay_period_type is not None
                                            and declaration.opening_pay_period_type != group.cadence.value
                                            else "A verified opening tax-year declaration needs its covered date, payroll-period count and cadence before cumulative-average withholding can be calculated."
                                        ),
                                    )
                                )
                            else:
                                employee_row = session.get(EmployeeRecords, roster_entry.employee_id)
                                coverage_start = max(
                                    declaration.opening_as_of + timedelta(days=1),
                                    date(obj_in.date_to.year, 1, 1),
                                    employee_row.date_hired
                                    if employee_row and employee_row.date_hired
                                    else date(obj_in.date_to.year, 1, 1),
                                )
                                history_rows, history_taxable, history_withheld, history_complete = _bir_finalized_history(
                                    session,
                                    roster_entry.employee_id,
                                    obj_in.date_to.year,
                                    declaration.opening_as_of,
                                    obj_in.date_from,
                                    coverage_start,
                                )
                                if not history_complete:
                                    blockers.append(
                                        PayrollPreflightBlocker(
                                            code="bir_cumulative_history_unavailable",
                                            message="Prior finalized payroll periods are incomplete; cumulative-average withholding cannot be reconciled.",
                                        )
                                    )
                                elif any(
                                    item.get("pay_period_type") != group.cadence.value
                                    for item in history_rows
                                ):
                                    blockers.append(
                                        PayrollPreflightBlocker(
                                            code="bir_cumulative_cadence_changed",
                                            message="The pay-period cadence changed during this tax year; payroll-owner review is required before cumulative-average withholding.",
                                        )
                                    )
                                else:
                                    prior_period_count = sum(
                                        item.get("excluded") != "true" for item in history_rows
                                    )
                                    cumulative_period_count = (
                                        declaration.opening_pay_period_count
                                        + prior_period_count
                                        + 1
                                    )
                                    cumulative_taxable = (
                                        declaration.taxable_compensation_ytd
                                        + history_taxable
                                        + bir_taxable_pay
                                        + benefits_taxable_excess
                                    )
                                    prior_withheld = declaration.tax_withheld_ytd + history_withheld
                                    average_compensation = (
                                        cumulative_taxable / Decimal(cumulative_period_count)
                                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                                    tax_per_period = calculate_bir_tax(
                                        session,
                                        average_compensation,
                                        group.cadence.value,
                                        obj_in.date_to.isoformat(),
                                    )
                                    (
                                        average_compensation,
                                        cumulative_tax,
                                        bir_withholding,
                                    ) = cumulative_average_withholding(
                                        cumulative_taxable_compensation=cumulative_taxable,
                                        period_count=cumulative_period_count,
                                        tax_per_period=tax_per_period,
                                        prior_withheld=prior_withheld,
                                    )
                                    snapshot["bir_year_to_date_history"] = {
                                        "opening_taxable_compensation": str(declaration.taxable_compensation_ytd),
                                        "opening_tax_withheld": str(declaration.tax_withheld_ytd),
                                        "opening_as_of": declaration.opening_as_of.isoformat(),
                                        "opening_pay_period_count": declaration.opening_pay_period_count,
                                        "finalized_entries": history_rows,
                                        "finalized_taxable_compensation": str(history_taxable),
                                        "finalized_tax_withheld": str(history_withheld),
                                        "cumulative_period_count": cumulative_period_count,
                                        "complete": history_complete,
                                    }
                                    snapshot["bir_calculation"] = {
                                        "method": "cumulative_average_rr_11_2018",
                                        "period_type": group.cadence.value,
                                        "taxable_compensation": str(bir_taxable_pay),
                                        "taxable_benefit_excess": str(
                                            benefits_taxable_excess
                                        ),
                                        "cumulative_taxable_compensation": str(cumulative_taxable),
                                        "cumulative_period_count": cumulative_period_count,
                                        "average_period_compensation": str(average_compensation),
                                        "tax_per_period": str(tax_per_period),
                                        "cumulative_tax_due": str(cumulative_tax),
                                        "prior_tax_withheld": str(prior_withheld),
                                        "withholding": str(bir_withholding),
                                        "schedule_effective_date": obj_in.date_to.isoformat(),
                                        "schedule_reference": "https://bir-cdn.bir.gov.ph/local/pdf/RR%20No.%2011-2018.pdf",
                                        "cumulative_average_consistent_for_tax_year": True,
                                    }
                        else:
                            bir_withholding = calculate_bir_tax(
                                session,
                                bir_taxable_pay,
                                group.cadence.value,
                                obj_in.date_to.isoformat(),
                                regular_compensation=regular_taxable_compensation,
                            )
                            snapshot["bir_calculation"] = {
                                "method": "periodic_annex_e",
                                "period_type": group.cadence.value,
                                "taxable_compensation": str(bir_taxable_pay),
                                "regular_compensation": str(
                                    regular_taxable_compensation
                                ),
                                "supplementary_compensation": str(
                                    supplementary_taxable_compensation
                                ),
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
        snapshot["earnings_calculation"] = {
            "regular": str(regular),
            "approved_overtime": str(overtime),
            "holiday_premium": str(holiday_premium),
            "rest_day_premium": str(rest_day_premium),
            "night_differential": str(night_differential),
            "fixed_recurring_allowance": str(fixed_allowance),
            "gross": str(gross),
            "attendance_deduction": str(attendance_deduction),
            "employee_statutory_deductions": str(
                sum(employee_statutory.values(), Decimal("0.00"))
            ),
            "bir_withholding": str(bir_withholding),
            "net": str(net_pay),
            "formula": "net = regular + approved overtime + premiums + fixed recurring allowance - attendance deductions - employee statutory contributions - BIR withholding",
        }
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
        entry_is_provisional = bool(blockers)
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
                    "holiday_premium": str(holiday_premium),
                    "rest_day_premium": str(rest_day_premium),
                    "night_differential": str(night_differential),
                    "fixed_recurring_allowance": str(fixed_allowance),
                    "provisional": entry_is_provisional,
                },
                deductions=deductions,
                gross_pay=gross,
                total_deductions=total_deductions,
                net_pay=net_pay,
                overtime_pay=overtime,
                thirteenth_month=Decimal("0.00"),
                non_taxable_income=Decimal("0.00"),
                taxable_income=taxable_pay,
                review_state="blocked" if blockers else "ready",
                calculation_version=(
                    "attendance-v1-provisional"
                    if entry_is_provisional
                    else "attendance-v1"
                ),
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


@router.post(
    "/runs/{run_id}/rebuild-attendance-draft",
    response_model=PayrollRunRead,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def rebuild_attendance_payroll_draft(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    run_id: uuid.UUID,
    obj_in: PayrollDraftRebuildRequest,
    response: Response,
) -> PayrollRunRead:
    """Supersede an unreviewed draft and prepare a fresh snapshot atomically."""
    run = session.exec(
        select(PayrollRun).where(PayrollRun.id == run_id).with_for_update()
    ).first()
    if run is None or run.is_deleted:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if (
        run.status != PayrollRunStatus.DRAFT
        or run.workflow_status not in {"draft", "in_review"}
        or run.is_readonly
        or run.pay_group_id is None
        or not run.input_fingerprint
    ):
        raise HTTPException(
            status_code=409,
            detail="Only a prepared draft with no employee dispositions can be rebuilt",
        )
    if run.input_fingerprint != obj_in.expected_run_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="The payroll draft changed; reload it before rebuilding",
        )
    entries = session.exec(
        select(PayrollEntry)
        .where(
            PayrollEntry.payroll_run_id == run_id,
            col(PayrollEntry.is_deleted).is_(False),
        )
        .with_for_update()
    ).all()
    if not entries or any(
        entry.review_state not in {"blocked", "ready"} for entry in entries
    ):
        raise HTTPException(
            status_code=409,
            detail="A draft with reviewed or excluded employees cannot be rebuilt",
        )
    if any(entry.input_snapshot.get("contribution_corrections") for entry in entries):
        raise HTTPException(
            status_code=409,
            detail="This draft contains an immutable contribution correction; resolve it in place instead of rebuilding",
        )
    if not any(
        entry.blockers or not _payroll_entry_inputs_are_current(session, entry)
        for entry in entries
    ):
        raise HTTPException(
            status_code=409,
            detail="This draft has no blockers or changed inputs to rebuild",
        )

    now = datetime.now(timezone.utc)
    run.status = PayrollRunStatus.VOID
    run.deleted_at = now
    run.updated_at = now
    session.add(run)
    audit = AuditLog(
        method="POST",
        path=f"/api/v1/payroll/runs/{run_id}/rebuild-attendance-draft",
        status_code=201,
        user_id=current_user.id,
        module="payroll",
        action="rebuild_attendance_draft",
        extra={
            "superseded_run_id": str(run_id),
            "pay_group_id": str(run.pay_group_id),
            "date_from": run.date_from.isoformat(),
            "date_to": run.date_to.isoformat(),
            "reason": obj_in.reason.strip(),
        },
    )
    session.add(audit)
    prepared = prepare_attendance_payroll_draft(
        session=session,
        current_user=current_user,
        obj_in=PayrollAttendancePrepareRequest(
            pay_group_id=run.pay_group_id,
            date_from=run.date_from,
            date_to=run.date_to,
        ),
        response=response,
    )
    audit.extra = {**(audit.extra or {}), "replacement_run_id": str(prepared.id)}
    session.add(audit)
    session.commit()
    return prepared


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


def _is_pay_group_period_start(group: PayrollPayGroup, effective_from: date) -> bool:
    cadence = group.cadence.value
    if cadence == CutoffType.DAILY.value:
        return True
    if cadence == CutoffType.MONTHLY.value:
        return effective_from.day == 1
    if cadence == CutoffType.SEMI_MONTHLY.value:
        return effective_from.day == 1 or (
            group.first_period_end_day is not None
            and group.first_period_end_day < calendar.monthrange(
                effective_from.year, effective_from.month
            )[1]
            and effective_from.day == group.first_period_end_day + 1
        )
    # Weekly groups do not yet define an effective-period calendar in the
    # payroll period API, so a bulk change must fail closed for that cadence.
    return False


def _pay_group_bulk_fingerprint(request: EmployeePayGroupBulkRequest) -> str:
    body = request.model_dump(mode="json", exclude={"batch_id"})
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _pay_group_bulk_preflight(
    *, session: Session, request: EmployeePayGroupBulkRequest, actor_id: uuid.UUID
) -> EmployeePayGroupBulkPreflight:
    issues: list[EmployeePayGroupBulkIssue] = []
    fingerprint = _pay_group_bulk_fingerprint(request)
    batch = session.get(EmployeePayGroupBulkBatch, request.batch_id)
    if batch is not None:
        if batch.created_by != actor_id or batch.payload_fingerprint != fingerprint:
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=0,
                    employee_id=request.employee_ids[0],
                    code="batch_identity_conflict",
                    message="This batch ID belongs to a different user or payload; reconcile it before starting another batch.",
                )
            )
        else:
            result_ids = [uuid.UUID(value) for value in batch.result_assignment_ids]
            results = session.exec(
                select(EmployeePayGroupAssignment).where(
                    col(EmployeePayGroupAssignment.id).in_(result_ids)
                )
            ).all()
            if len(results) != len(result_ids):
                issues.append(
                    EmployeePayGroupBulkIssue(
                        row_index=0,
                        employee_id=request.employee_ids[0],
                        code="batch_result_unavailable",
                        message="The saved batch result is incomplete; contact payroll support before retrying.",
                    )
                )
            return EmployeePayGroupBulkPreflight(
                batch_id=request.batch_id,
                valid=not issues,
                requested=len(request.employee_ids),
                replayed=not issues,
                issues=issues,
            )

    seen: set[uuid.UUID] = set()
    employee_ids = sorted(set(request.employee_ids), key=str)
    employees = session.exec(
        select(EmployeeRecords)
        .where(
            col(EmployeeRecords.id).in_(employee_ids),
            col(EmployeeRecords.is_deleted).is_(False),
            EmployeeRecords.employee_status == "Active",
        )
        .order_by(col(EmployeeRecords.id))
        .with_for_update()
    ).all()
    employee_by_id = {employee.id: employee for employee in employees}
    target_group = session.get(PayrollPayGroup, request.pay_group_id)
    if target_group is None or not target_group.is_active:
        for index, employee_id in enumerate(request.employee_ids):
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="pay_group_unavailable",
                    message="The selected pay group is missing or inactive.",
                )
            )
        return EmployeePayGroupBulkPreflight(
            batch_id=request.batch_id,
            valid=False,
            requested=len(request.employee_ids),
            issues=issues,
        )

    assignments = session.exec(
        select(EmployeePayGroupAssignment)
        .where(col(EmployeePayGroupAssignment.employee_id).in_(employee_ids))
        .order_by(
            col(EmployeePayGroupAssignment.employee_id),
            col(EmployeePayGroupAssignment.effective_from),
        )
        .with_for_update()
    ).all()
    by_employee: dict[uuid.UUID, list[EmployeePayGroupAssignment]] = {}
    for assignment in assignments:
        by_employee.setdefault(assignment.employee_id, []).append(assignment)

    for index, employee_id in enumerate(request.employee_ids):
        if employee_id in seen:
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="duplicate_employee",
                    message="Select each employee only once in a pay-group batch.",
                )
            )
            continue
        seen.add(employee_id)
        if employee_id not in employee_by_id:
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="employee_unavailable",
                    message="Employee is missing, inactive, or unavailable.",
                )
            )
            continue
        employee_assignments = by_employee.get(employee_id, [])
        if any(
            assignment.effective_from == request.effective_from
            for assignment in employee_assignments
        ):
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="effective_date_conflict",
                    message="An assignment already starts on this date; choose a later pay-period boundary or resolve the existing row.",
                )
            )
            continue
        covering = [
            assignment
            for assignment in employee_assignments
            if assignment.effective_from <= request.effective_from
            and (
                assignment.effective_to is None
                or assignment.effective_to >= request.effective_from
            )
        ]
        if len(covering) > 1:
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="existing_assignment_overlap",
                    message="Existing pay-group history overlaps this date; resolve it before bulk assignment.",
                )
            )
            continue
        current = covering[0] if covering else None
        if current is not None and current.pay_group_id == target_group.id:
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="already_assigned",
                    message="Employee is already assigned to this pay group on the selected date.",
                )
            )
            continue
        if not _is_pay_group_period_start(target_group, request.effective_from):
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="not_pay_period_boundary",
                    message="Choose the start of a pay period in the target group; weekly group boundaries are not configured yet.",
                )
            )
            continue
        if current is not None:
            current_group = session.get(PayrollPayGroup, current.pay_group_id)
            if current_group is None or not _is_pay_group_period_start(
                current_group, request.effective_from
            ):
                issues.append(
                    EmployeePayGroupBulkIssue(
                        row_index=index,
                        employee_id=employee_id,
                        code="not_current_period_boundary",
                        message="The transfer date must also be a payroll-period boundary for the employee's current group.",
                    )
                )
                continue
        finalized = session.exec(
            select(PayrollRun.id)
            .join(PayrollEntry, col(PayrollEntry.payroll_run_id) == col(PayrollRun.id))
            .where(
                PayrollEntry.employee_id == employee_id,
                col(PayrollEntry.is_deleted).is_(False),
                PayrollRun.workflow_status == "finalized",
                col(PayrollRun.status).in_(
                    [PayrollRunStatus.APPROVED, PayrollRunStatus.PAID]
                ),
                col(PayrollRun.is_deleted).is_(False),
                PayrollRun.date_to >= request.effective_from,
            )
            .limit(1)
        ).first()
        if finalized is not None:
            issues.append(
                EmployeePayGroupBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="finalized_payroll_overlap",
                    message="A finalized payroll covers or follows this effective date; use the correction workflow instead.",
                )
            )

    return EmployeePayGroupBulkPreflight(
        batch_id=request.batch_id,
        valid=not issues,
        requested=len(request.employee_ids),
        issues=issues,
    )


@router.post(
    "/pay-group-assignments/bulk/preflight",
    response_model=EmployeePayGroupBulkPreflight,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def preflight_pay_group_bulk(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: EmployeePayGroupBulkRequest,
) -> EmployeePayGroupBulkPreflight:
    return _pay_group_bulk_preflight(
        session=session, request=request, actor_id=current_user.id
    )


@router.post(
    "/pay-group-assignments/bulk/commit",
    response_model=EmployeePayGroupBulkCommit,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "add"))],
)
def commit_pay_group_bulk(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: EmployeePayGroupBulkRequest,
) -> EmployeePayGroupBulkCommit:
    fingerprint = _pay_group_bulk_fingerprint(request)
    lock_key = int.from_bytes(request.batch_id.bytes[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    lock_payroll_roster(session)
    existing_batch = session.get(EmployeePayGroupBulkBatch, request.batch_id)
    if existing_batch is not None:
        if (
            existing_batch.created_by != current_user.id
            or existing_batch.payload_fingerprint != fingerprint
        ):
            raise HTTPException(
                status_code=409,
                detail="Pay-group batch ID belongs to another user or different data; reconcile before retrying.",
            )
        result_ids = [uuid.UUID(value) for value in existing_batch.result_assignment_ids]
        rows = session.exec(
            select(EmployeePayGroupAssignment).where(
                col(EmployeePayGroupAssignment.id).in_(result_ids)
            )
        ).all()
        if len(rows) != len(result_ids):
            raise HTTPException(
                status_code=409,
                detail="The saved pay-group batch result is incomplete; contact payroll support before retrying.",
            )
        return EmployeePayGroupBulkCommit(
            batch_id=request.batch_id,
            replayed=True,
            assignments=[EmployeePayGroupAssignmentPublic.model_validate(row) for row in rows],
        )

    preflight = _pay_group_bulk_preflight(
        session=session, request=request, actor_id=current_user.id
    )
    if not preflight.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Pay-group batch has conflicts; no assignments were saved.",
                "issues": [issue.model_dump(mode="json") for issue in preflight.issues],
            },
        )
    assignment_history = session.exec(
        select(EmployeePayGroupAssignment)
        .where(col(EmployeePayGroupAssignment.employee_id).in_(request.employee_ids))
        .order_by(
            col(EmployeePayGroupAssignment.employee_id),
            col(EmployeePayGroupAssignment.effective_from),
        )
        .with_for_update()
    ).all()
    by_employee: dict[uuid.UUID, list[EmployeePayGroupAssignment]] = {}
    for row in assignment_history:
        by_employee.setdefault(row.employee_id, []).append(row)
    now = datetime.now(timezone.utc)
    new_rows: list[EmployeePayGroupAssignment] = []
    for employee_id in request.employee_ids:
        history = by_employee.get(employee_id, [])
        current = next(
            (
                row
                for row in history
                if row.effective_from <= request.effective_from
                and (row.effective_to is None or row.effective_to >= request.effective_from)
            ),
            None,
        )
        if current is not None:
            current.effective_to = request.effective_from - timedelta(days=1)
            current.updated_at = now
            session.add(current)
        next_assignment = next(
            (row for row in history if row.effective_from > request.effective_from),
            None,
        )
        new_rows.append(
            EmployeePayGroupAssignment(
                employee_id=employee_id,
                pay_group_id=request.pay_group_id,
                effective_from=request.effective_from,
                effective_to=(
                    next_assignment.effective_from - timedelta(days=1)
                    if next_assignment is not None
                    else None
                ),
                assigned_by=current_user.id,
                created_at=now,
                updated_at=now,
            )
        )
    session.add_all(new_rows)
    session.flush()
    session.add(
        EmployeePayGroupBulkBatch(
            id=request.batch_id,
            payload_fingerprint=fingerprint,
            created_by=current_user.id,
            result_assignment_ids=[str(row.id) for row in new_rows],
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Pay-group assignment changed while saving; reload the roster and preflight again. No partial batch was saved.",
        ) from exc
    return EmployeePayGroupBulkCommit(
        batch_id=request.batch_id,
        replayed=False,
        assignments=[EmployeePayGroupAssignmentPublic.model_validate(row) for row in new_rows],
    )


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
    lock_payroll_roster(session)
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
    lock_payroll_roster(session)
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
        "monthly_partial_work",
        "monthly_salary_proration",
        "monthly_holiday_pay_divisor",
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
    if row.policy["monthly_partial_work"] not in {
        "deduct_after_grace",
        "no_deduction",
    }:
        raise HTTPException(
            status_code=422,
            detail=(
                "monthly_partial_work must be deduct_after_grace or no_deduction"
            ),
        )
    if row.policy["monthly_salary_proration"] not in {
        "scheduled_workday_fraction",
        "monthly_divisor_per_workday",
    }:
        raise HTTPException(
            status_code=422,
            detail=(
                "monthly_salary_proration must be scheduled_workday_fraction or monthly_divisor_per_workday"
            ),
        )
    try:
        monthly_holiday_divisor = Decimal(
            str(row.policy["monthly_holiday_pay_divisor"])
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="monthly_holiday_pay_divisor must be a positive number",
        ) from exc
    if monthly_holiday_divisor <= 0:
        raise HTTPException(
            status_code=422,
            detail="monthly_holiday_pay_divisor must be a positive number",
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
    allowance_treatment = row.policy["allowance_tax_treatment"]
    if "fixed_recurring" in allowance_treatment and any(
        allowance_treatment.get(key) != expected
        for key, expected in (
            ("fixed_recurring", "taxable"),
            ("proration", "calendar_days"),
            ("absence", "not_deducted"),
        )
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Fixed recurring allowance policy is unsupported",
                "required": {
                    "fixed_recurring": "taxable",
                    "proration": "calendar_days",
                    "absence": "not_deducted",
                },
            },
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

    employee_ids = {entry.employee_id for entry in entries if entry.employee_id}
    employees = (
        session.exec(
            select(EmployeeRecords).where(col(EmployeeRecords.id).in_(employee_ids))
        ).all()
        if employee_ids
        else []
    )
    employee_by_id = {employee.id: employee for employee in employees}
    entry_list = []
    for entry in entries:
        employee = employee_by_id.get(entry.employee_id)
        entry_list.append(
            PayrollEntryRead.model_validate(
                entry,
                update={
                    "employee_name": (
                        f"{employee.first_name} {employee.last_name}".strip()
                        if employee
                        else None
                    ),
                    "employee_code": employee.employee_code if employee else None,
                },
            )
        )
    return PayrollRunRead.model_validate(
        run,
        update={
            "entries": entry_list,
            "payroll_finalization_enabled": settings.PAYROLL_FINALIZATION_ENABLED,
            "payslip_delivery_enabled": settings.PAYSLIP_DELIVERY_ENABLED,
        },
    )


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

    has_contribution_correction = session.exec(
        select(PayrollContributionLedger.id)
        .join(PayrollEntry, col(PayrollEntry.id) == col(PayrollContributionLedger.payroll_entry_id))
        .where(
            PayrollEntry.payroll_run_id == run_id,
            PayrollContributionLedger.sequence > 0,
        )
        .limit(1)
    ).first()
    if has_contribution_correction is not None:
        raise HTTPException(
            status_code=409,
            detail="A payroll run containing a statutory contribution correction cannot be voided",
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
    "/employees/{employee_id}/tax-year-benefits/{tax_year}",
    response_model=list[EmployeeTaxBenefitPublic],
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def list_employee_tax_year_benefits(
    *,
    session: SessionDep,
    employee_id: uuid.UUID,
    tax_year: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[EmployeeTaxBenefitPublic]:
    if tax_year < 2000 or tax_year > 2200:
        raise HTTPException(status_code=422, detail="tax_year must be between 2000 and 2200")
    rows = session.exec(
        select(EmployeeTaxBenefit)
        .where(
            EmployeeTaxBenefit.employee_id == employee_id,
            EmployeeTaxBenefit.tax_year == tax_year,
        )
        .order_by(
            col(EmployeeTaxBenefit.paid_on),
            col(EmployeeTaxBenefit.created_at),
            col(EmployeeTaxBenefit.id),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return [EmployeeTaxBenefitPublic.model_validate(row) for row in rows]


@router.post(
    "/employees/{employee_id}/tax-year-benefits/{tax_year}",
    response_model=EmployeeTaxBenefitPublic,
    status_code=201,
    dependencies=[Depends(require_permission("payroll", "approve"))],
)
def record_employee_tax_year_benefit(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    employee_id: uuid.UUID,
    tax_year: int,
    obj_in: EmployeeTaxBenefitCreate,
) -> EmployeeTaxBenefitPublic:
    """Record a paid benefit against the shared RR 11-2018 annual ceiling."""
    if tax_year < 2000 or tax_year > 2200 or obj_in.paid_on.year != tax_year:
        raise HTTPException(status_code=422, detail="paid_on must be within the declared tax year")
    if not obj_in.source_reference.strip():
        raise HTTPException(status_code=422, detail="A nonblank source reference is required")
    employee = session.exec(
        select(EmployeeRecords)
        .where(EmployeeRecords.id == employee_id, col(EmployeeRecords.is_deleted).is_(False))
        .with_for_update()
    ).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    if obj_in.correction_of_id is None:
        existing_source = session.exec(
            select(EmployeeTaxBenefit.id).where(
                EmployeeTaxBenefit.source_reference == obj_in.source_reference.strip()
            )
        ).first()
        if existing_source is not None:
            raise HTTPException(
                status_code=409,
                detail="This payment source reference is already recorded; reconcile the existing benefit before retrying.",
            )
    vacation_policy: LeavePolicy | None = None
    vacation_enrollment: EmployeeLeaveEnrollment | None = None
    vacation_eligibility_snapshot: dict[str, Any] | None = None
    if (
        obj_in.de_minimis_category == "monetized_unused_vacation_leave"
        and obj_in.correction_of_id is None
    ):
        assert obj_in.vacation_leave_policy_id is not None
        vacation_policy = session.exec(
            select(LeavePolicy)
            .where(
                LeavePolicy.id == obj_in.vacation_leave_policy_id,
                col(LeavePolicy.is_deleted).is_(False),
                col(LeavePolicy.is_active).is_(True),
            )
            .with_for_update()
        ).first()
        if (
            vacation_policy is None
            or not vacation_policy.is_paid
            or not vacation_policy.tax_exempt_unused_vacation_leave
        ):
            raise HTTPException(
                status_code=422,
                detail="Select an active paid vacation policy explicitly configured as eligible for unused-vacation monetization.",
            )
        vacation_enrollment = session.exec(
            select(EmployeeLeaveEnrollment)
            .where(
                EmployeeLeaveEnrollment.employee_id == employee_id,
                EmployeeLeaveEnrollment.policy_id == vacation_policy.id,
                EmployeeLeaveEnrollment.leave_year == tax_year,
                col(EmployeeLeaveEnrollment.is_active).is_(True),
                col(EmployeeLeaveEnrollment.is_deleted).is_(False),
            )
            .with_for_update()
        ).first()
        if vacation_enrollment is None:
            raise HTTPException(
                status_code=422,
                detail="Employee has no active enrollment in this vacation policy for the tax year.",
            )
        available_days = session.exec(
            select(func.coalesce(func.sum(LeaveLedgerEntry.amount), 0)).where(
                LeaveLedgerEntry.employee_id == employee_id,
                LeaveLedgerEntry.policy_id == vacation_policy.id,
                LeaveLedgerEntry.leave_year == tax_year,
                col(LeaveLedgerEntry.is_deleted).is_(False),
            )
        ).one()
        available_days = Decimal(str(available_days))
        if obj_in.qualifying_days is None or available_days < Decimal(obj_in.qualifying_days):
            raise HTTPException(
                status_code=422,
                detail=f"Insufficient unused vacation leave balance: {available_days} day(s) are available.",
            )
        vacation_eligibility_snapshot = {
            "policy_id": str(vacation_policy.id),
            "policy_code": vacation_policy.code,
            "policy_name": vacation_policy.name,
            "policy_is_paid": vacation_policy.is_paid,
            "policy_tax_exempt_unused_vacation_leave": vacation_policy.tax_exempt_unused_vacation_leave,
            "enrollment_id": str(vacation_enrollment.id),
            "leave_year": tax_year,
            "available_days_before": str(available_days),
            "qualifying_days": obj_in.qualifying_days,
            "available_days_after": str(available_days - Decimal(obj_in.qualifying_days)),
        }
    if (
        obj_in.de_minimis_category == "daily_meal_ot_night"
        and obj_in.correction_of_id is None
    ):
        _verify_daily_meal_allowance_attendance(
            session=session,
            employee_id=employee_id,
            work_dates=obj_in.qualifying_work_dates or [],
        )
        existing_benefits = session.exec(
            select(EmployeeTaxBenefit).where(
                EmployeeTaxBenefit.employee_id == employee_id,
                EmployeeTaxBenefit.tax_year == tax_year,
                EmployeeTaxBenefit.de_minimis_category == "daily_meal_ot_night",
            )
        ).all()
        reversed_benefit_ids = {
            row.correction_of_id
            for row in existing_benefits
            if row.correction_of_id is not None
        }
        already_claimed_dates = {
            date.fromisoformat(day)
            for row in existing_benefits
            if row.correction_of_id is None and row.id not in reversed_benefit_ids
            for day in row.qualifying_work_dates or []
        }
        duplicate_dates = already_claimed_dates.intersection(
            obj_in.qualifying_work_dates or []
        )
        if duplicate_dates:
            duplicate_list = ", ".join(sorted(day.isoformat() for day in duplicate_dates))
            raise HTTPException(
                status_code=409,
                detail=f"Meal allowance attendance dates were already claimed: {duplicate_list}. Reverse the prior record before replacing it.",
            )
    if obj_in.correction_of_id is None:
        if obj_in.gross_amount <= 0 or obj_in.correction_reason is not None:
            raise HTTPException(
                status_code=422,
                detail="A new benefit payment must be positive and cannot include correction fields.",
            )
    else:
        if obj_in.gross_amount >= 0 or not (obj_in.correction_reason or "").strip():
            raise HTTPException(
                status_code=422,
                detail="A correction must be a negative full reversal with a reason.",
            )
        original = session.exec(
            select(EmployeeTaxBenefit)
            .where(
                EmployeeTaxBenefit.id == obj_in.correction_of_id,
                EmployeeTaxBenefit.employee_id == employee_id,
                EmployeeTaxBenefit.tax_year == tax_year,
            )
            .with_for_update()
        ).first()
        if (
            original is None
            or original.correction_of_id is not None
            or original.gross_amount <= 0
            or original.benefit_type != obj_in.benefit_type
            or original.de_minimis_category != obj_in.de_minimis_category
            or original.eligibility_evidence != obj_in.eligibility_evidence
            or original.qualifying_days != obj_in.qualifying_days
            or (original.qualifying_work_dates or [])
            != [day.isoformat() for day in (obj_in.qualifying_work_dates or [])]
            or original.regional_daily_minimum_wage != obj_in.regional_daily_minimum_wage
            or original.region_code != obj_in.region_code
            or original.wage_order_reference != obj_in.wage_order_reference
            or original.wage_order_effective_from != obj_in.wage_order_effective_from
            or original.wage_order_effective_to != obj_in.wage_order_effective_to
            or original.vacation_leave_policy_id != obj_in.vacation_leave_policy_id
            or obj_in.gross_amount != -original.gross_amount
        ):
            raise HTTPException(
                status_code=422,
                detail="Only the original benefit record can be reversed, for its full amount and same benefit type.",
            )
        correction_exists = session.exec(
            select(EmployeeTaxBenefit.id).where(
                EmployeeTaxBenefit.correction_of_id == original.id
            )
        ).first()
        if correction_exists:
            raise HTTPException(status_code=409, detail="This benefit record was already reversed.")
        if original.de_minimis_category == "monetized_unused_vacation_leave":
            vacation_eligibility_snapshot = original.eligibility_snapshot
    finalized_snapshots = session.exec(
        select(PayrollEntry.input_snapshot)
        .join(PayrollRun, col(PayrollEntry.payroll_run_id) == col(PayrollRun.id))
        .where(
            PayrollEntry.employee_id == employee_id,
            PayrollRun.date_to >= date(tax_year, 1, 1),
            PayrollRun.date_to < date(tax_year + 1, 1, 1),
            PayrollRun.workflow_status == "finalized",
            col(PayrollRun.is_deleted).is_(False),
            col(PayrollEntry.is_deleted).is_(False),
        )
        .limit(366)
    ).all()
    if any(
        isinstance(snapshot, dict) and "bir_benefit_reconciliation" in snapshot
        for snapshot in finalized_snapshots
    ):
        raise HTTPException(
            status_code=409,
            detail="Tax-year benefits are locked after payroll finalization; use the reasoned tax correction workflow.",
        )
    row = EmployeeTaxBenefit(
        employee_id=employee_id,
        tax_year=tax_year,
        paid_on=obj_in.paid_on,
        benefit_type=obj_in.benefit_type,
        de_minimis_category=obj_in.de_minimis_category,
        eligibility_evidence=obj_in.eligibility_evidence,
        qualifying_days=obj_in.qualifying_days,
        qualifying_work_dates=(
            [day.isoformat() for day in obj_in.qualifying_work_dates]
            if obj_in.qualifying_work_dates is not None
            else None
        ),
        regional_daily_minimum_wage=obj_in.regional_daily_minimum_wage,
        region_code=obj_in.region_code.strip() if obj_in.region_code else None,
        wage_order_reference=(
            obj_in.wage_order_reference.strip() if obj_in.wage_order_reference else None
        ),
        wage_order_effective_from=obj_in.wage_order_effective_from,
        wage_order_effective_to=obj_in.wage_order_effective_to,
        vacation_leave_policy_id=obj_in.vacation_leave_policy_id,
        eligibility_snapshot=vacation_eligibility_snapshot,
        gross_amount=obj_in.gross_amount,
        source_reference=obj_in.source_reference.strip(),
        correction_of_id=obj_in.correction_of_id,
        correction_reason=(obj_in.correction_reason.strip() if obj_in.correction_reason else None),
        created_by=current_user.id,
    )
    session.add(row)
    if obj_in.de_minimis_category == "monetized_unused_vacation_leave":
        if obj_in.correction_of_id is None:
            assert vacation_enrollment is not None
            assert obj_in.qualifying_days is not None
            ledger_reference = f"PayrollTaxBenefit:{row.id}"
            if vacation_eligibility_snapshot is not None:
                vacation_eligibility_snapshot["ledger_reference"] = ledger_reference
                row.eligibility_snapshot = vacation_eligibility_snapshot
            session.add(
                LeaveLedgerEntry(
                    employee_id=employee_id,
                    policy_id=obj_in.vacation_leave_policy_id,
                    enrollment_id=vacation_enrollment.id,
                    leave_year=tax_year,
                    source=LeaveLedgerSource.CONSUMED,
                    amount=-Decimal(obj_in.qualifying_days),
                    reference=ledger_reference,
                    note="Unused vacation leave monetized as a paid de minimis benefit",
                    actor_user_id=current_user.id,
                )
            )
        else:
            assert original is not None
            original_snapshot = original.eligibility_snapshot or {}
            enrollment_id = original_snapshot.get("enrollment_id")
            if not enrollment_id or obj_in.qualifying_days is None:
                raise HTTPException(
                    status_code=409,
                    detail="The original vacation-leave benefit has no reversible ledger evidence.",
                )
            session.add(
                LeaveLedgerEntry(
                    employee_id=employee_id,
                    policy_id=original.vacation_leave_policy_id,
                    enrollment_id=uuid.UUID(enrollment_id),
                    leave_year=tax_year,
                    source=LeaveLedgerSource.REVERSAL,
                    amount=Decimal(obj_in.qualifying_days),
                    reference=f"PayrollTaxBenefitReversal:{original.id}",
                    original_year=tax_year,
                    note=f"Reversal of monetized vacation leave: {obj_in.correction_reason}",
                    actor_user_id=current_user.id,
                )
            )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="This benefit payment or its linked leave-ledger entry already exists; reconcile the saved record before retrying.",
        ) from exc
    session.refresh(row)
    return EmployeeTaxBenefitPublic.model_validate(row)


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
    if obj_in.tax_classification == "minimum_wage_earner" and not (
        obj_in.source_reference or ""
    ).strip():
        raise HTTPException(
            status_code=422,
            detail="Minimum-wage-earner classification requires a source note identifying the assigned work location and applicable DOLE wage order.",
        )
    if obj_in.opening_as_of.year != tax_year or obj_in.opening_as_of > date.today():
        raise HTTPException(
            status_code=422,
            detail="opening_as_of must be a date in the declared tax year that is not in the future",
        )
    for period_date in (
        obj_in.previous_employer_period_from,
        obj_in.previous_employer_period_to,
    ):
        if period_date is not None and period_date.year != tax_year:
            raise HTTPException(
                status_code=422,
                detail="Previous-employer covered dates must be within the declared tax year.",
            )
    if (
        obj_in.previous_employer_period_to is not None
        and obj_in.previous_employer_period_to > obj_in.opening_as_of
    ):
        raise HTTPException(
            status_code=422,
            detail="Previous-employer coverage cannot extend beyond the opening balance cutoff date.",
        )
    opening_history_included = (
        obj_in.previous_employer_included
        or obj_in.taxable_compensation_ytd > 0
        or obj_in.tax_withheld_ytd > 0
        or obj_in.opening_benefits_exempt_ytd > 0
    )
    if opening_history_included and (
        obj_in.opening_pay_period_count < 1
        or obj_in.opening_pay_period_type is None
        or not (obj_in.source_reference or "").strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="Opening tax-year figures require a source note, the covered payroll-period count and cadence.",
        )
    if not opening_history_included and (
        obj_in.opening_pay_period_count != 0 or obj_in.opening_pay_period_type is not None
    ):
        raise HTTPException(
            status_code=422,
            detail="Previous-employer period inputs must be empty when previous-employer figures are not included.",
        )
    if obj_in.opening_benefits_reconciled and not (obj_in.source_reference or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Benefit reconciliation requires a source note for the opening date and benefit records.",
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
        if isinstance(value, str):
            value = value.strip() or None
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
    search: str | None = Query(default=None, min_length=1, max_length=120),
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
    if search and search.strip():
        term = search.strip()
        search_filter = or_(
            col(EmployeeRecords.employee_code).contains(term, autoescape=True),
            col(EmployeeRecords.first_name).contains(term, autoescape=True),
            col(EmployeeRecords.last_name).contains(term, autoescape=True),
            func.concat(EmployeeRecords.first_name, " ", EmployeeRecords.last_name).contains(
                term, autoescape=True
            ),
        )
        base = base.where(search_filter)
    if missing_salary:
        base = base.where(~has_salary)
    statement = select(EmployeeRecords, has_salary.label("has_effective_salary")).where(
        col(EmployeeRecords.is_deleted).is_(False),
        EmployeeRecords.employee_status == "Active",
    )
    if search and search.strip():
        statement = statement.where(search_filter)
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


def _salary_increment_preview(
    *, session: Session, request: EmployeeSalaryIncrementRequest, actor_id: uuid.UUID
) -> EmployeeSalaryIncrementResult:
    issues: list[EmployeeSalaryBulkIssue] = []
    changes = []
    employees = session.exec(
        select(EmployeeRecords)
        .where(
            col(EmployeeRecords.id).in_(request.employee_ids),
            col(EmployeeRecords.is_deleted).is_(False),
            EmployeeRecords.employee_status == "Active",
        )
        .order_by(col(EmployeeRecords.id))
    ).all()
    employee_ids = {employee.id for employee in employees}
    employee_by_id = {employee.id: employee for employee in employees}
    fingerprint = hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json", exclude={"batch_id"}),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    batch = session.get(EmployeeSalaryBulkBatch, request.batch_id)
    if batch is not None and (
        batch.created_by != actor_id or batch.payload_fingerprint != fingerprint
    ):
        issues.append(
            EmployeeSalaryBulkIssue(
                row_index=0,
                employee_id=request.employee_ids[0],
                code="batch_identity_conflict",
                message="This batch ID belongs to another request; create a new batch for different employees or values.",
            )
        )
    for index, employee_id in enumerate(request.employee_ids):
        if employee_id not in employee_ids:
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="employee_unavailable",
                    message="Employee is missing, inactive, or unavailable.",
                )
            )
            continue
        if session.exec(
            select(EmployeeSalary.id).where(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.effective_date == request.effective_date,
            )
        ).first():
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="effective_date_conflict",
                    message="A salary already starts on the selected date; choose another effective date or resolve that record.",
                )
            )
            continue
        finalized_run = session.exec(
            select(PayrollRun.id)
            .join(PayrollEntry, col(PayrollEntry.payroll_run_id) == col(PayrollRun.id))
            .where(
                PayrollEntry.employee_id == employee_id,
                col(PayrollEntry.is_deleted).is_(False),
                PayrollRun.workflow_status == "finalized",
                col(PayrollRun.is_deleted).is_(False),
                PayrollRun.date_to >= request.effective_date,
            )
            .limit(1)
        ).first()
        if finalized_run is not None:
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="finalized_payroll_coverage",
                    message="A finalized payroll covers or follows this date; use the reasoned payroll correction workflow instead.",
                )
            )
            continue
        current = session.exec(
            select(EmployeeSalary)
            .where(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.effective_date <= request.effective_date,
                col(EmployeeSalary.is_active).is_(True),
                col(EmployeeSalary.is_deleted).is_(False),
            )
            .order_by(col(EmployeeSalary.effective_date).desc(), col(EmployeeSalary.id))
            .limit(1)
        ).first()
        if current is None:
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="salary_missing",
                    message="No active salary exists on the effective date; set up the employee's salary first.",
                )
            )
            continue
        proposed = (current.basic_rate + request.increment).quantize(Decimal("0.01"))
        if proposed > Decimal("9999999999.99"):
            issues.append(
                EmployeeSalaryBulkIssue(
                    row_index=index,
                    employee_id=employee_id,
                    code="rate_out_of_range",
                    message="The proposed salary exceeds the supported PHP rate range.",
                )
            )
            continue
        changes.append(
            {
                "employee_id": employee_id,
                "employee_code": employee_by_id[employee_id].employee_code,
                "employee_name": " ".join(
                    part
                    for part in (
                        employee_by_id[employee_id].first_name,
                        employee_by_id[employee_id].last_name,
                    )
                    if part
                ),
                "current_salary_id": current.id,
                "current_rate": current.basic_rate,
                "proposed_rate": proposed,
                "pay_type": current.pay_type,
            }
        )
    return EmployeeSalaryIncrementResult(
        batch_id=request.batch_id,
        valid=not issues,
        issues=issues,
        changes=changes,
    )


@router.post(
    "/salaries/bulk/increment/preview",
    response_model=EmployeeSalaryIncrementResult,
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def preview_salary_increment(
    *, session: SessionDep, current_user: CurrentUser, request: EmployeeSalaryIncrementRequest
) -> EmployeeSalaryIncrementResult:
    return _salary_increment_preview(session=session, request=request, actor_id=current_user.id)


@router.post(
    "/salaries/bulk/increment/commit",
    response_model=EmployeeSalaryIncrementResult,
    dependencies=[Depends(require_permission("payroll", "edit"))],
)
def commit_salary_increment(
    *, session: SessionDep, current_user: CurrentUser, request: EmployeeSalaryIncrementRequest
) -> EmployeeSalaryIncrementResult:
    fingerprint = hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json", exclude={"batch_id"}),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    lock_key = int.from_bytes(request.batch_id.bytes[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    lock_payroll_roster(session)
    existing = session.get(EmployeeSalaryBulkBatch, request.batch_id)
    if existing is not None:
        if existing.created_by != current_user.id or existing.payload_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="Salary increment batch ID was used with different data.")
        ids = [uuid.UUID(value) for value in existing.result_salary_ids]
        rows = session.exec(select(EmployeeSalary).where(col(EmployeeSalary.id).in_(ids))).all()
        if len(rows) != len(ids):
            raise HTTPException(status_code=409, detail="Saved salary increment result is incomplete; contact payroll support.")
        return EmployeeSalaryIncrementResult(
            batch_id=request.batch_id,
            valid=True,
            replayed=True,
            salaries=[EmployeeSalaryRead.model_validate(row) for row in rows],
        )
    preview = _salary_increment_preview(session=session, request=request, actor_id=current_user.id)
    if not preview.valid:
        raise HTTPException(status_code=422, detail={"message": "Salary increment has conflicts; no rows were saved.", "issues": [issue.model_dump(mode="json") for issue in preview.issues]})
    current_by_id = {
        row.id: row
        for row in session.exec(
            select(EmployeeSalary)
            .where(col(EmployeeSalary.id).in_([change.current_salary_id for change in preview.changes]))
            .with_for_update()
        ).all()
    }
    new_rows: list[EmployeeSalary] = []
    for change in preview.changes:
        current = current_by_id.get(change.current_salary_id)
        if current is None or current.basic_rate != change.current_rate:
            session.rollback()
            raise HTTPException(status_code=409, detail="A selected salary changed after preview; reload and preview the increment again.")
        new_rows.append(EmployeeSalary(
            employee_id=change.employee_id,
            basic_rate=change.proposed_rate,
            currency=current.currency,
            effective_date=request.effective_date,
            pay_type=current.pay_type,
            overtime_rate=current.overtime_rate,
            absent_penalty_rate=current.absent_penalty_rate,
            non_taxable_allowance=current.non_taxable_allowance,
            de_minimis_monthly=current.de_minimis_monthly,
            thirteenth_month_exempt_portion=current.thirteenth_month_exempt_portion,
            is_active=True,
        ))
    session.add_all(new_rows)
    session.flush()
    session.add(EmployeeSalaryBulkBatch(
        id=request.batch_id,
        payload_fingerprint=fingerprint,
        created_by=current_user.id,
        result_salary_ids=[str(row.id) for row in new_rows],
    ))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Salary changed while saving; preview again. No partial increments were saved.") from exc
    return EmployeeSalaryIncrementResult(
        batch_id=request.batch_id,
        valid=True,
        salaries=[EmployeeSalaryRead.model_validate(row) for row in new_rows],
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
    lock_payroll_roster(session)
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
    lock_payroll_roster(session)
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
    lock_payroll_roster(session)
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
    lock_payroll_roster(session)
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
    "/runs/{run_id}/entries/{entry_id}/payslip.pdf",
    dependencies=[Depends(require_permission("payroll", "view"))],
)
def download_finalized_payslip_pdf(
    *,
    session: SessionDep,
    request: Request,
    run_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> Response:
    """Download only the finalized, frozen payslip document for an entry."""
    entry = session.get(PayrollEntry, entry_id)
    if entry is None or entry.payroll_run_id != run_id or entry.is_deleted:
        raise HTTPException(status_code=404, detail="Payslip not found")
    run = session.get(PayrollRun, run_id)
    if run is None or run.is_deleted:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if run.workflow_status != "finalized" or run.frozen_snapshot is None:
        raise HTTPException(
            status_code=409,
            detail="Payslips are available only after the payroll run is finalized",
        )
    delivery = session.exec(
        select(PayrollDeliveryOutbox)
        .where(PayrollDeliveryOutbox.payroll_entry_id == entry_id)
        .order_by(col(PayrollDeliveryOutbox.document_version).desc())
    ).first()
    if delivery is None or not delivery.content_snapshot:
        raise HTTPException(status_code=404, detail="Frozen payslip document not found")

    from app.payroll.delivery_worker import render_payslip_pdf

    request.state.audit_module = "payroll"
    request.state.audit_action = "payslip_download"
    pdf = render_payslip_pdf(delivery.content_snapshot)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="payslip-{entry_id}.pdf"',
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


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

    # Period order is authoritative: an older run can be created later during
    # a correction/rebuild and must not replace the employee's latest statement.
    latest_run = max(
        matching_runs,
        key=lambda run: (run.date_to, run.created_at or datetime.min),
    )
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
