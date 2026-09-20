"""REST API routes for payroll module.

All payroll endpoints exposed under /api/v1/payroll/* pathway.
Includes government calculators, payroll run lifecycle, loan management, employee salary config, and integration platform.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.common.dependencies import CurrentUser, SessionDep
from app.common.schemas import Message
from app.employee.models import EmployeeRecords
from app.payroll.calc import (
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
from app.payroll.models import PayrollRunStatus
from app.payroll.payroll_tables import (
    EmployeeSalary,
    IntegrationConfig,
    IntegrationMapping,
    Loan,
    LoanAmortization,
    PayrollEntry,
    PayrollRun,
)
from app.payroll.schemas import (
    BIRBracketCreate,
    BIRBracketRead,
    EmployeeSalaryCreate,
    EmployeeSalaryRead,
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
    PayrollEntryRead,
    PayrollGenerateRequest,
    PayrollPayslipPublic,
    PayrollPreviewRequest,
    PayrollPreviewResponse,
    PayrollRunRead,
    PayrunStatusResponse,
    PhilHealthBracketCreate,
    PhilHealthBracketRead,
    SSSBracketCreate,
    SSSBracketRead,
)
from app.payroll.selectors import (
    get_payroll_run_status_counts,
)
from app.payroll.services import (
    generate_payroll,
    preview_payroll,
)
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/payroll", tags=["payroll"])


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
    stmt = select(SSSBracket).where(SSSBracket.is_deleted == include_deleted).order_by(SSSBracket.effective_date, SSSBracket.msc_max)  # type: ignore[arg-type]
    if effective_date:
        eff = datetime.fromisoformat(effective_date).date()
        stmt = select(SSSBracket).where(SSSBracket.effective_date <= eff, SSSBracket.is_deleted == include_deleted).order_by(SSSBracket.effective_date, SSSBracket.msc_max)  # type: ignore[arg-type]
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
    stmt = select(PhilHealthBracket).where(PhilHealthBracket.is_deleted == include_deleted).order_by(PhilHealthBracket.effective_date, PhilHealthBracket.salary_max)  # type: ignore[arg-type]
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
    stmt = select(PagIBIGBracket).where(PagIBIGBracket.is_deleted == include_deleted).order_by(PagIBIGBracket.effective_date, PagIBIGBracket.salary_max)  # type: ignore[arg-type]
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
    period_type: str = Query(default="monthly", description="Filter by payment period type (daily/weekly/semi_monthly/monthly)"),
    effective_date: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[BIRBracketRead]:
    """List all BIR brackets with period type filtering."""
    stmt = select(BIRBracket).where(BIRBracket.is_deleted == include_deleted).order_by(BIRBracket.effective_date, BIRBracket.bracket_min)  # type: ignore[arg-type]
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
    period_type: str = Query(default="monthly", description="Pay period type (daily/weekly/semi_monthly/monthly)"),
    effective_date: str | None = Query(default=None, description="Optional effective date for rate lookup"),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate all government contributions for a given gross pay amount."""
    result = calculate_all_contributions(session, gross_pay, period_type, effective_date)
    return {"contributions": {k: float(v) for k, v in result.items()}}


@router.post("/sss/calculate")
async def calculate_sss(
    *,
    msc: Decimal = Query(..., gt=0, description="Monthly Salary Credit"),
    effective_date: str | None = Query(default=None),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate total SSS contribution (employee + employer) for a given MSC."""
    employee = calculate_sss_employee_share(session, msc, effective_date)
    employer = calculate_sss_employer_share(session, msc, effective_date)
    return {"employee_share": float(employee), "employer_share": float(employer), "total": float(employee + employer)}


@router.post("/philhealth/calculate")
async def calculate_philhealth(
    *,
    salary: Decimal = Query(..., gt=0, description="Basic salary"),
    effective_date: str | None = Query(default=None),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate PhilHealth contribution (employee + employer)."""
    employee = calculate_philhealth_employee_share(session, salary, effective_date)
    employer = calculate_philhealth_employer_share(session, salary, effective_date)
    return {"employee_share": float(employee), "employer_share": float(employer), "total": float(employee + employer)}


@router.post("/pagibig/calculate")
async def calculate_pagibig(
    *,
    salary: Decimal = Query(..., gt=0, description="Basic salary"),
    effective_date: str | None = Query(default=None),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate Pag-IBIG contribution (employee + employer)."""
    employee = calculate_pagibig_employee_share(session, salary, effective_date)
    employer = calculate_pagibig_employer_share(session, salary, effective_date)
    return {"employee_share": float(employee), "employer_share": float(employer), "total": float(employee + employer)}


@router.post("/bir/calculate")
async def calculate_bir(
    *,
    taxable_income: Decimal = Query(..., gt=0, description="Taxable income"),
    period_type: str = Query(default="monthly", description="Pay period type for BIR bracket lookup"),
    session: SessionDep,
    _current_user: CurrentUser,
) -> dict[str, Any]:
    """Calculate BIR withholding tax."""
    tax = calculate_bir_tax(session, taxable_income, period_type)
    return {"tax_amount": float(tax)}


# --------------------------------------------------------------------------- #
# Payroll Run Management Endpoints (B4B.2)
# --------------------------------------------------------------------------- #


@router.post("/runs/preview", response_model=PayrollPreviewResponse, dependencies=[Depends(require_permission("payroll", "view"))])
async def preview_payroll_endpoint(
    *,
    session: SessionDep,
    request: PayrollPreviewRequest,
) -> PayrollPreviewResponse:
    """Preview payroll run without persisting entries."""
    run = preview_payroll(session, request)
    entries = session.exec(
        select(PayrollEntry).where(PayrollEntry.payroll_run_id == run.id, PayrollEntry.is_deleted.is_(False))  # type: ignore[attr-defined]
    ).all()
    return PayrollPreviewResponse(payroll_run_id=run.id, entries=[PayrollEntryRead.model_validate(e) for e in entries])


@router.post("/runs/generate", response_model=PayrollRun)
async def generate_payroll_endpoint(
    *,
    session: SessionDep,
    request: PayrollGenerateRequest,
    current_user: CurrentUser,
) -> PayrollRun:
    """Generate payroll run with persisted entries (status=draft)."""
    run = generate_payroll(session, request, current_user.id)
    return run


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
    session: SessionDep,
    run_id: uuid.UUID,
    current_user: CurrentUser,
) -> PayrollRunRead:
    """Approve payroll run (make it ready for payment)."""
    from app.payroll.selectors import (
        get_existing_singleton_payroll_run_for_determination,
    )

    run = get_existing_singleton_payroll_run_for_determination(session, run_id, current_user.id)

    if run.status != PayrollRunStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft payroll runs can be approved")

    run.status = PayrollRunStatus.APPROVED
    run.updated_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    session.refresh(run)

    return PayrollRunRead.model_validate(run)


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

    run = get_existing_singleton_payroll_run_for_voiding(session, run_id, current_user.id)

    if run.status not in [PayrollRunStatus.DRAFT, PayrollRunStatus.APPROVED]:
        raise HTTPException(status_code=400, detail="Only draft or approved payroll runs can be voided")

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
    stmt = select(EmployeeSalary).where(EmployeeSalary.employee_id == employee_id, EmployeeSalary.is_deleted == include_deleted)
    if _effective_date:
        eff = datetime.fromisoformat(_effective_date).date()
        stmt = stmt.where(EmployeeSalary.effective_date <= eff)
    salaries = session.exec(stmt).all()
    return [EmployeeSalaryRead.model_validate(s) for s in salaries]


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
    salary: EmployeeSalaryCreate,
) -> EmployeeSalaryRead:
    """Update employee salary record."""
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
    stmt = select(Loan).where(Loan.employee_id == employee_id, Loan.is_deleted == include_deleted)
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
    stmt = select(IntegrationConfig).where(IntegrationConfig.is_deleted == include_deleted).order_by(IntegrationConfig.name)
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
    stmt = select(IntegrationMapping).where(IntegrationMapping.integration_config_id == config_id, IntegrationMapping.is_deleted == include_deleted)
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
    matching_runs = []
    for run in runs:
        _, entries = select_payroll_run_with_entries(session, run.id, include_deleted=False)
        if any(e.employee_id == employee_id for e in entries):
            matching_runs.append(run)

    if not matching_runs:
        return None

    latest_run = max(matching_runs, key=lambda r: r.created_at or datetime.min)
    _, entries = select_payroll_run_with_entries(session, latest_run.id, include_deleted=False)
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
