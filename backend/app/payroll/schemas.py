"""Request/response DTOs for the payroll domain (Phase B4).

Naming follows the leave-domain convention (``*Public``/``*Create``/``*Update``/
``*List`` with ``data``+``count`` envelopes) and the frontend API contract in
``frontendv3/src/lib/api/types.ts``.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from app.payroll.models import (
    ConnectorType,
    CutoffType,
    LoanType,
    PayrollAdjustmentType,
    PayrollRunStatus,
    PayType,
)

# === Government contribution brackets ====================================================


class SSSBracketBase(SQLModel):
    msc_min: Decimal
    msc_max: Decimal
    employer_ss: Decimal
    employer_ec: Decimal
    employer_mpf: Decimal
    employee_ss: Decimal
    employee_mpf: Decimal
    effective_date: date


class SSSBracketCreate(SSSBracketBase):
    is_active: bool = Field(default=True)


class SSSBracketUpdate(SQLModel):
    msc_min: Decimal | None = None
    msc_max: Decimal | None = None
    employer_ss: Decimal | None = None
    employer_ec: Decimal | None = None
    employer_mpf: Decimal | None = None
    employee_ss: Decimal | None = None
    employee_mpf: Decimal | None = None
    effective_date: date | None = None
    is_active: bool | None = None


class SSSBracketPublic(SSSBracketBase):
    id: uuid.UUID
    is_active: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


SSSBracketRead = SSSBracketPublic


class SSSBracketList(SQLModel):
    data: list[SSSBracketPublic]
    count: int


class PhilHealthBracketBase(SQLModel):
    salary_min: Decimal
    salary_max: Decimal
    rate: Decimal
    employer_share: Decimal
    employee_share: Decimal
    effective_date: date


class PhilHealthBracketCreate(PhilHealthBracketBase):
    is_active: bool = Field(default=True)


class PhilHealthBracketUpdate(SQLModel):
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    rate: Decimal | None = None
    employer_share: Decimal | None = None
    employee_share: Decimal | None = None
    effective_date: date | None = None
    is_active: bool | None = None


class PhilHealthBracketPublic(PhilHealthBracketBase):
    id: uuid.UUID
    is_active: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


PhilHealthBracketRead = PhilHealthBracketPublic


class PhilHealthBracketList(SQLModel):
    data: list[PhilHealthBracketPublic]
    count: int


class PagIBIGBracketBase(SQLModel):
    salary_min: Decimal
    salary_max: Decimal
    employee_rate: Decimal
    employer_rate: Decimal
    effective_date: date


class PagIBIGBracketCreate(PagIBIGBracketBase):
    is_active: bool = Field(default=True)


class PagIBIGBracketUpdate(SQLModel):
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    employee_rate: Decimal | None = None
    employer_rate: Decimal | None = None
    effective_date: date | None = None
    is_active: bool | None = None


class PagIBIGBracketPublic(PagIBIGBracketBase):
    id: uuid.UUID
    is_active: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


PagIBIGBracketRead = PagIBIGBracketPublic
PagibigBracketRead = PagIBIGBracketPublic


class PagIBIGBracketList(SQLModel):
    data: list[PagIBIGBracketPublic]
    count: int


class BIRBracketBase(SQLModel):
    period: CutoffType = Field(default=CutoffType.MONTHLY)
    bracket_min: Decimal
    bracket_max: Decimal | None = None
    base_tax: Decimal
    excess_rate: Decimal
    effective_date: date


class BIRBracketCreate(BIRBracketBase):
    is_active: bool = Field(default=True)


class BIRBracketUpdate(SQLModel):
    period: CutoffType | None = None
    bracket_min: Decimal | None = None
    bracket_max: Decimal | None = None
    base_tax: Decimal | None = None
    excess_rate: Decimal | None = None
    effective_date: date | None = None
    is_active: bool | None = None


class BIRBracketPublic(BIRBracketBase):
    id: uuid.UUID
    is_active: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


BIRBracketRead = BIRBracketPublic


class BIRBracketList(SQLModel):
    data: list[BIRBracketPublic]
    count: int


# === Employee salary (B4B.2a) ============================================================


class EmployeeSalaryBase(SQLModel):
    basic_rate: Decimal
    currency: str = Field(default="PHP", max_length=3)
    effective_date: date
    pay_type: PayType = Field(default=PayType.MONTHLY)
    overtime_rate: Decimal = Field(default=Decimal("0.000"))
    absent_penalty_rate: Decimal = Field(default=Decimal("0.000"))
    non_taxable_allowance: Decimal = Field(default=Decimal("0.00"))
    de_minimis_monthly: dict[str, Any] = Field(default_factory=dict)
    thirteenth_month_exempt_portion: Decimal = Field(default=Decimal("90000.00"))
    is_active: bool = Field(default=True)


class EmployeeSalaryCreate(EmployeeSalaryBase):
    employee_id: uuid.UUID


class EmployeeSalaryUpdate(SQLModel):
    basic_rate: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    effective_date: date | None = None
    pay_type: PayType | None = None
    overtime_rate: Decimal | None = None
    absent_penalty_rate: Decimal | None = None
    non_taxable_allowance: Decimal | None = None
    de_minimis_monthly: dict[str, Any] | None = None
    thirteenth_month_exempt_portion: Decimal | None = None
    is_active: bool | None = None


class EmployeeSalaryPublic(EmployeeSalaryBase):
    id: uuid.UUID
    employee_id: uuid.UUID | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


EmployeeSalaryRead = EmployeeSalaryPublic


class EmployeeSalaryList(SQLModel):
    data: list[EmployeeSalaryPublic]
    count: int


# === Payroll run lifecycle (B4B) =========================================================


class PayrollRunCreate(SQLModel):
    cutoff_type: CutoffType = Field(default=CutoffType.MONTHLY)
    date_from: date
    date_to: date
    adjustment_type: PayrollAdjustmentType = Field(default=PayrollAdjustmentType.REGULAR)
    employee_ids: list[uuid.UUID] | None = None
    department_id: uuid.UUID | None = None

    model_config = ConfigDict(use_enum_values=True)  # type: ignore[assignment]


class PayrollRunPublic(SQLModel):
    id: uuid.UUID
    cutoff_type: CutoffType
    date_from: date
    date_to: date
    status: PayrollRunStatus
    adjustment_type: PayrollAdjustmentType
    created_by: uuid.UUID | None
    is_readonly: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None
    total_gross_pay: Decimal = Field(default=Decimal("0.00"))
    total_deductions: Decimal = Field(default=Decimal("0.00"))
    total_net_pay: Decimal = Field(default=Decimal("0.00"))
    entries: list["PayrollEntryPublic"] = Field(default_factory=list)


PayrollRunRead = PayrollRunPublic


class PayrollEntryPublic(SQLModel):
    id: uuid.UUID
    payroll_run_id: uuid.UUID | None
    employee_id: uuid.UUID | None
    basic_rate: Decimal
    rate_date_from: date
    rate_date_to: date
    earnings: dict[str, Any] | None
    deductions: dict[str, Any] | None
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    overtime_pay: Decimal
    thirteenth_month: Decimal
    non_taxable_income: Decimal
    taxable_income: Decimal
    is_readonly: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


PayrollEntryRead = PayrollEntryPublic


class PayrollEntryPreview(SQLModel):
    employee_id: uuid.UUID
    basic_rate: Decimal
    rate_date_from: date
    rate_date_to: date
    earnings: dict[str, Any]
    deductions: dict[str, Any]
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    overtime_pay: Decimal
    thirteenth_month: Decimal
    non_taxable_income: Decimal
    taxable_income: Decimal
    warnings: list[dict[str, str]] = Field(default_factory=list)


class PayrollRunDetail(PayrollRunPublic):
    entries: list[PayrollEntryPublic] = Field(default_factory=list)


class PayrollRunList(SQLModel):
    data: list[PayrollRunPublic]
    count: int


class PayrollRunPreview(SQLModel):
    run: PayrollRunPublic
    entries: list[PayrollEntryPreview]


class PayrollReviewLoan(SQLModel):
    """Existing loan id when adding an amortization against a known loan."""

    id: uuid.UUID | None = None
    due_date: date | None = None
    amount: Decimal


class PayrollReviewOverride(SQLModel):
    """HR edits captured during Step 2 (Review/Edit).

    The payload is carried to the backend on both recalc (preview) and
    generation so generation uses exactly what was reviewed.
    """

    employee_id: uuid.UUID
    overtime_pay: Decimal | None = None
    allowances: Decimal | None = None
    other_earnings: Decimal | None = None
    non_taxable_income: Decimal | None = None
    attendance_deduction_override: Decimal | None = None
    attendance_deduction_reason: str | None = Field(default=None, max_length=1024)
    loan_amortizations: list[PayrollReviewLoan] | None = None


class PayrollPreviewRequest(SQLModel):
    cutoff_type: CutoffType = Field(default=CutoffType.MONTHLY)
    date_from: date
    date_to: date
    adjustment_type: PayrollAdjustmentType = Field(default=PayrollAdjustmentType.REGULAR)
    entries: list[PayrollReviewOverride] | None = None
    employee_ids: list[uuid.UUID] | None = None
    department_id: uuid.UUID | None = None

    model_config = ConfigDict(use_enum_values=True)  # type: ignore[assignment]


class PayrollGenerateRequest(PayrollPreviewRequest):
    pass


class PayrollPreviewResponse(SQLModel):
    payroll_run_id: uuid.UUID
    entries: list[PayrollEntryPublic]


class PayrunStatusResponse(SQLModel):
    """Response with payroll run status summary (dashboard KPI)."""

    draft: int = 0
    approved: int = 0
    paid: int = 0
    void: int = 0
    total_payroll_runs: int = 0


# === Loans (B4B.2d/2e) ===================================================================


class LoanCreate(SQLModel):
    employee_id: uuid.UUID
    loan_type: LoanType = Field(default=LoanType.SALARY)
    principal: Decimal
    terms_months: int
    start_date: date


class LoanUpdate(SQLModel):
    loan_type: LoanType | None = None
    principal: Decimal | None = None
    balance: Decimal | None = None
    terms_months: int | None = None
    start_date: date | None = None
    is_active: bool | None = None


class LoanPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID | None
    loan_type: LoanType
    principal: Decimal
    balance: Decimal
    terms_months: int
    start_date: date
    is_active: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


LoanRead = LoanPublic


class LoanList(SQLModel):
    data: list[LoanPublic]
    count: int


class LoanAmortizationCreate(SQLModel):
    loan_id: uuid.UUID
    due_date: date
    amount: Decimal


class LoanAmortizationUpdate(SQLModel):
    due_date: date | None = None
    amount: Decimal | None = None
    is_paid: bool | None = None


class LoanAmortizationPublic(SQLModel):
    id: uuid.UUID
    loan_id: uuid.UUID | None
    due_date: date
    amount: Decimal
    remaining_balance: Decimal
    is_paid: bool
    paid_date: date | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


LoanAmortizationRead = LoanAmortizationPublic


class LoanAmortizationList(SQLModel):
    data: list[LoanAmortizationPublic]
    count: int


# === Integration platform (B4A.2) ========================================================


class IntegrationConfigBase(SQLModel):
    name: str = Field(max_length=255)
    connector_type: ConnectorType = Field(default=ConnectorType.GENERIC_REST)
    api_url: str | None = Field(default=None, max_length=512)
    http_method: str = Field(default="GET", max_length=10)
    headers: dict[str, Any] | None = None
    schedule: str | None = Field(default=None, max_length=128)
    is_active: bool = Field(default=True)


class IntegrationConfigCreate(IntegrationConfigBase):
    pass


class IntegrationConfigUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    connector_type: ConnectorType | None = None
    api_url: str | None = Field(default=None, max_length=512)
    http_method: str | None = Field(default=None, max_length=10)
    headers: dict[str, Any] | None = None
    schedule: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None


class IntegrationConfigPublic(IntegrationConfigBase):
    id: uuid.UUID
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


FleetIntegrationConfigBase = IntegrationConfigBase
FleetIntegrationConfigCreate = IntegrationConfigCreate
FleetIntegrationConfigRead = IntegrationConfigPublic


class IntegrationMappingCreate(SQLModel):
    integration_config_id: uuid.UUID
    source_json_path: str = Field(max_length=512)
    target_field: str = Field(max_length=255)
    transform_rule: str | None = Field(default=None, max_length=1024)


class IntegrationMappingUpdate(SQLModel):
    source_json_path: str | None = Field(default=None, max_length=512)
    target_field: str | None = Field(default=None, max_length=255)
    transform_rule: str | None = Field(default=None, max_length=1024)


class IntegrationMappingPublic(SQLModel):
    id: uuid.UUID
    integration_config_id: uuid.UUID | None
    source_json_path: str
    target_field: str
    transform_rule: str | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class IntegrationConfigDetail(IntegrationConfigPublic):
    mappings: list[IntegrationMappingPublic] = Field(default_factory=list)


FleetIntegrationMappingBase = IntegrationMappingCreate
FleetIntegrationMappingCreate = IntegrationMappingCreate
FleetIntegrationMappingRead = IntegrationMappingPublic


class IntegrationMappingList(SQLModel):
    data: list[IntegrationMappingPublic]
    count: int


class IntegrationConfigList(SQLModel):
    data: list[IntegrationConfigPublic]
    count: int


class IntegrationExecutionRequest(SQLModel):
    """Trigger one integration execution against its configured REST endpoint."""

    payload: dict[str, Any] | None = None


class IntegrationExecutionResult(SQLModel):
    integration_config_id: uuid.UUID
    status: str
    status_code: int | None = None
    mapped_result: dict[str, Any] | None = None
    error: str | None = None


# === Payslips (B4B.2f) ============================================================


class PayrollPayslipPublic(SQLModel):
    run_id: uuid.UUID
    employee_id: uuid.UUID | None
    employee_name: str | None = None
    cutoff_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    basic_rate: Decimal
    rate_date_from: date | None = None
    rate_date_to: date | None = None
    earnings: dict[str, Any] | None = None
    deductions: dict[str, Any] | None = None
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    overtime_pay: Decimal
    thirteenth_month: Decimal
    non_taxable_income: Decimal
    taxable_income: Decimal
    status: str | None = None


class PayrollPayslipList(SQLModel):
    data: list[PayrollPayslipPublic]
    count: int
