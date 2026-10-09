"""Request/response DTOs for the payroll domain (Phase B4).

Naming follows the leave-domain convention (``*Public``/``*Create``/``*Update``/
``*List`` with ``data``+``count`` envelopes) and the frontend API contract in
``frontendv3/src/lib/api/types.ts``.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import ConfigDict, EmailStr, Field, model_validator
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
    compensation_min: Decimal
    compensation_max: Decimal | None = None
    monthly_salary_credit: Decimal
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
    compensation_min: Decimal | None = None
    compensation_max: Decimal | None = None
    monthly_salary_credit: Decimal | None = None
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
    source_reference: str | None = Field(default=None, max_length=512)


class BIRBracketCreate(BIRBracketBase):
    is_active: bool = Field(default=True)


class BIRBracketUpdate(SQLModel):
    period: CutoffType | None = None
    bracket_min: Decimal | None = None
    bracket_max: Decimal | None = None
    base_tax: Decimal | None = None
    excess_rate: Decimal | None = None
    effective_date: date | None = None
    source_reference: str | None = Field(default=None, max_length=512)
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


class EmployeeTaxYearDeclarationUpdate(SQLModel):
    tax_classification: Literal["ordinary", "minimum_wage_earner"] = "ordinary"
    opening_as_of: date
    taxable_compensation_ytd: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    tax_withheld_ytd: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    opening_pay_period_count: int = Field(default=0, ge=0, le=366)
    opening_pay_period_type: Literal["daily", "weekly", "semi_monthly", "monthly"] | None = None
    previous_employer_included: bool = False
    previous_employer_period_from: date | None = None
    previous_employer_period_to: date | None = None
    opening_benefits_exempt_ytd: Decimal = Field(default=Decimal("0.00"), ge=0, le=90000, max_digits=14, decimal_places=2)
    opening_benefits_reconciled: bool = False
    opening_de_minimis_annual_ytd: dict[str, str] = Field(default_factory=dict)
    opening_de_minimis_monthly_ytd: dict[str, str] = Field(default_factory=dict)
    opening_unused_vacation_leave_days_ytd: int | None = Field(default=None, ge=0, le=12)
    source_reference: str | None = Field(default=None, max_length=512)
    is_verified: bool = False

    @model_validator(mode="after")
    def validate_opening_de_minimis(self) -> "EmployeeTaxYearDeclarationUpdate":
        if self.previous_employer_period_from and self.previous_employer_period_to:
            if self.previous_employer_period_from > self.previous_employer_period_to:
                raise ValueError("previous-employer period start must not follow its end")
        if not self.previous_employer_included and any(
            (self.previous_employer_period_from, self.previous_employer_period_to)
        ):
            raise ValueError("Previous-employer details require previous_employer_included")
        annual_categories = {
            "uniform_clothing",
            "actual_medical_assistance",
            "achievement_award",
            "christmas_anniversary_gift",
            "cba_productivity_incentive",
        }
        monthly_categories = {
            "medical_cash_dependents",
            "rice_subsidy",
            "laundry_allowance",
        }
        for field_name, balances, categories in (
            ("opening_de_minimis_annual_ytd", self.opening_de_minimis_annual_ytd, annual_categories),
            ("opening_de_minimis_monthly_ytd", self.opening_de_minimis_monthly_ytd, monthly_categories),
        ):
            for category, raw_amount in balances.items():
                if category not in categories:
                    raise ValueError(f"{field_name} contains an unsupported category: {category}")
                try:
                    amount = Decimal(raw_amount)
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise ValueError(f"{field_name}.{category} must be a decimal amount") from exc
                if not amount.is_finite() or amount < 0:
                    raise ValueError(f"{field_name}.{category} must be finite and non-negative")
        if (self.opening_de_minimis_annual_ytd or self.opening_de_minimis_monthly_ytd) and not self.opening_benefits_reconciled:
            raise ValueError("Opening de minimis amounts require benefit reconciliation")
        if self.opening_unused_vacation_leave_days_ytd is not None and not self.opening_benefits_reconciled:
            raise ValueError("Opening unused vacation leave days require benefit reconciliation")
        if self.previous_employer_included or self.opening_benefits_exempt_ytd > 0:
            if set(self.opening_de_minimis_annual_ytd) != annual_categories or set(
                self.opening_de_minimis_monthly_ytd
            ) != monthly_categories:
                raise ValueError(
                    "A reconciled previous-employer or benefit opening requires explicit annual and monthly balances for every de minimis category, including zeros"
                )
        return self


class EmployeeTaxYearDeclarationPublic(EmployeeTaxYearDeclarationUpdate):
    id: uuid.UUID
    employee_id: uuid.UUID
    tax_year: int
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmployeeTaxBenefitCreate(SQLModel):
    paid_on: date
    benefit_type: Literal["thirteenth_month", "other_benefit", "de_minimis"]
    de_minimis_category: Literal[
        "medical_cash_dependents",
        "rice_subsidy",
        "uniform_clothing",
        "actual_medical_assistance",
        "laundry_allowance",
        "achievement_award",
        "christmas_anniversary_gift",
        "cba_productivity_incentive",
        "daily_meal_ot_night",
        "monetized_unused_vacation_leave",
    ] | None = None
    eligibility_evidence: list[Literal[
        "actual_medical_documentation",
        "written_non_discriminatory_award_plan",
        "cba_or_productivity_incentive_evidence",
        "approved_overtime_or_night_shift_records",
        "unused_vacation_leave_balance_verified",
    ]] = Field(default_factory=list)
    qualifying_days: int | None = Field(default=None, ge=1, le=366)
    qualifying_work_dates: list[date] | None = Field(default=None, max_length=366)
    vacation_leave_policy_id: uuid.UUID | None = None
    regional_daily_minimum_wage: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    region_code: str | None = Field(default=None, min_length=2, max_length=32)
    wage_order_reference: str | None = Field(default=None, min_length=3, max_length=512)
    wage_order_effective_from: date | None = None
    wage_order_effective_to: date | None = None
    gross_amount: Decimal = Field(max_digits=14, decimal_places=2)
    source_reference: str = Field(min_length=3, max_length=512)
    correction_of_id: uuid.UUID | None = None
    correction_reason: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_benefit_category(self) -> "EmployeeTaxBenefitCreate":
        if (self.benefit_type == "de_minimis") != (self.de_minimis_category is not None):
            raise ValueError("de_minimis_category is required only for de_minimis records")
        conditional_evidence = {
            "actual_medical_assistance": "actual_medical_documentation",
            "achievement_award": "written_non_discriminatory_award_plan",
            "cba_productivity_incentive": "cba_or_productivity_incentive_evidence",
            "daily_meal_ot_night": "approved_overtime_or_night_shift_records",
        }
        required_evidence = conditional_evidence.get(self.de_minimis_category or "")
        if required_evidence and required_evidence not in self.eligibility_evidence:
            raise ValueError(
                f"{self.de_minimis_category} requires eligibility evidence {required_evidence}"
            )
        if self.benefit_type != "de_minimis" and self.eligibility_evidence:
            raise ValueError("eligibility_evidence applies only to de minimis records")
        regional_values = (
            self.regional_daily_minimum_wage,
            self.region_code,
            self.wage_order_reference,
        )
        if self.de_minimis_category == "daily_meal_ot_night":
            if self.vacation_leave_policy_id is not None:
                raise ValueError("Vacation leave policy applies only to monetized vacation leave")
            if (
                self.qualifying_days is None
                or any(not value for value in regional_values)
                or self.wage_order_effective_from is None
            ):
                raise ValueError(
                    "Daily meal allowance requires eligible days, region, daily minimum wage, wage-order source, and its effective start date"
                )
            if (
                self.wage_order_effective_to is not None
                and self.wage_order_effective_to < self.wage_order_effective_from
            ):
                raise ValueError("Wage-order effective end date cannot precede its start date")
            if (
                self.qualifying_work_dates is None
                or len(self.qualifying_work_dates) != self.qualifying_days
                or len(set(self.qualifying_work_dates)) != len(self.qualifying_work_dates)
                or any(day > self.paid_on or day.year != self.paid_on.year for day in self.qualifying_work_dates)
                or any(day < self.wage_order_effective_from for day in self.qualifying_work_dates)
                or any(
                    self.wage_order_effective_to is not None
                    and day > self.wage_order_effective_to
                    for day in self.qualifying_work_dates
                )
            ):
                raise ValueError(
                    "Daily meal allowance requires unique attendance dates within the payment year and wage-order effective dates, on or before payment"
                )
        elif self.de_minimis_category == "monetized_unused_vacation_leave":
            if self.qualifying_days is None or self.vacation_leave_policy_id is None:
                raise ValueError("Monetized unused vacation leave requires eligible days and a verified vacation leave policy")
            if any(value is not None for value in regional_values):
                raise ValueError("Regional wage fields apply only to daily meal allowance")
            if self.qualifying_work_dates is not None or self.wage_order_effective_from is not None or self.wage_order_effective_to is not None:
                raise ValueError("Attendance and wage-order dates apply only to daily meal allowance")
        elif (
            self.qualifying_days is not None
            or self.qualifying_work_dates is not None
            or self.wage_order_effective_from is not None
            or self.wage_order_effective_to is not None
            or any(value is not None for value in regional_values)
            or self.vacation_leave_policy_id is not None
        ):
            raise ValueError("Day and regional wage evidence is unsupported for this category")
        return self


class EmployeeTaxBenefitPublic(EmployeeTaxBenefitCreate):
    eligibility_snapshot: dict[str, Any] | None = None
    id: uuid.UUID
    employee_id: uuid.UUID
    tax_year: int
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None


class PayrollSalaryRosterItem(SQLModel):
    employee_id: uuid.UUID
    employee_code: str
    first_name: str
    last_name: str
    employee_status: str
    has_effective_salary: bool


class PayrollSalaryRosterList(SQLModel):
    data: list[PayrollSalaryRosterItem]
    count: int


class PayrollPreflightBlocker(SQLModel):
    code: str
    message: str
    work_date: date | None = None


class PayrollPreflightEmployee(SQLModel):
    employee_id: uuid.UUID
    employee_code: str
    employee_name: str
    email: str | None = None
    blockers: list[PayrollPreflightBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    attendance_records: int = 0
    eligible_overtime_minutes: int = 0
    approved_overtime_minutes: int = 0


class PayrollRunPreflight(SQLModel):
    pay_group_id: uuid.UUID
    date_from: date
    date_to: date
    policy_versions: list[int] = Field(default_factory=list)
    entries: list[PayrollPreflightEmployee]
    count: int
    blocked_count: int
    ready_count: int
    has_more: bool


class PayrollAttendanceCalculationEntry(SQLModel):
    employee_id: uuid.UUID
    employee_code: str
    employee_name: str
    regular_earnings: Decimal | None = None
    approved_overtime: Decimal | None = None
    holiday_premium: Decimal | None = None
    rest_day_premium: Decimal | None = None
    night_differential: Decimal | None = None
    fixed_recurring_allowance: Decimal | None = None
    attendance_deduction: Decimal | None = None
    short_time_deduction: Decimal | None = None
    gross_before_statutory: Decimal | None = None
    blockers: list[PayrollPreflightBlocker] = Field(default_factory=list)
    formula: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)


class PayrollAttendanceCalculationPreview(SQLModel):
    pay_group_id: uuid.UUID
    date_from: date
    date_to: date
    calculation_status: Literal["provisional_earnings_only"] = (
        "provisional_earnings_only"
    )
    entries: list[PayrollAttendanceCalculationEntry]
    count: int
    has_more: bool


class EmployeeSalaryBulkRow(SQLModel):
    employee_id: uuid.UUID
    basic_rate: Decimal = Field(gt=0)
    pay_type: PayType
    overtime_rate: Decimal = Field(default=Decimal("0"), ge=0)
    non_taxable_allowance: Decimal = Field(default=Decimal("0"), ge=0)


class EmployeeSalaryBulkRequest(SQLModel):
    batch_id: uuid.UUID
    effective_date: date
    rows: list[EmployeeSalaryBulkRow] = Field(min_length=1, max_length=500)


class EmployeeSalaryIncrementRequest(SQLModel):
    batch_id: uuid.UUID
    effective_date: date
    increment: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    employee_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_employees(self) -> "EmployeeSalaryIncrementRequest":
        if len(set(self.employee_ids)) != len(self.employee_ids):
            raise ValueError("Select each employee only once")
        return self


class EmployeeSalaryIncrementPreview(SQLModel):
    employee_id: uuid.UUID
    employee_code: str
    employee_name: str
    current_salary_id: uuid.UUID
    current_rate: Decimal
    proposed_rate: Decimal
    pay_type: PayType


class EmployeeSalaryBulkIssue(SQLModel):
    row_index: int
    employee_id: uuid.UUID
    code: str
    message: str


class EmployeeSalaryIncrementResult(SQLModel):
    batch_id: uuid.UUID
    valid: bool
    replayed: bool = False
    issues: list[EmployeeSalaryBulkIssue] = Field(default_factory=list)
    changes: list[EmployeeSalaryIncrementPreview] = Field(default_factory=list)
    salaries: list[EmployeeSalaryPublic] = Field(default_factory=list)


class EmployeeSalaryBulkPreflight(SQLModel):
    batch_id: uuid.UUID
    valid: bool
    requested: int
    issues: list[EmployeeSalaryBulkIssue]


class EmployeeSalaryBulkCommit(SQLModel):
    batch_id: uuid.UUID
    replayed: bool
    salaries: list[EmployeeSalaryPublic]


# === Payroll run lifecycle (B4B) =========================================================


class PayrollRunCreate(SQLModel):
    cutoff_type: CutoffType = Field(default=CutoffType.MONTHLY)
    date_from: date
    date_to: date
    adjustment_type: PayrollAdjustmentType = Field(
        default=PayrollAdjustmentType.REGULAR
    )
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
    workflow_status: str = "draft"
    payroll_finalization_enabled: bool = False
    payslip_delivery_enabled: bool = False
    pay_group_id: uuid.UUID | None = None
    policy_version_id: uuid.UUID | None = None
    payment_date: date | None = None
    finalized_by: uuid.UUID | None = None
    finalized_at: datetime | None = None
    input_fingerprint: str | None = None
    total_gross_pay: Decimal = Field(default=Decimal("0.00"))
    total_deductions: Decimal = Field(default=Decimal("0.00"))
    total_net_pay: Decimal = Field(default=Decimal("0.00"))
    entries: list["PayrollEntryPublic"] = Field(default_factory=list)


PayrollRunRead = PayrollRunPublic


class PayrollEntryPublic(SQLModel):
    id: uuid.UUID
    payroll_run_id: uuid.UUID | None
    employee_id: uuid.UUID | None
    employee_name: str | None = None
    employee_code: str | None = None
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
    review_state: str = "ready"
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    review_reason: str | None = None
    calculation_version: str | None = None
    input_fingerprint: str | None = None
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    blockers: list[dict[str, str]] = Field(default_factory=list)


class PayrollEntryReviewRequest(SQLModel):
    action: Literal["reviewed", "excluded"]
    expected_input_fingerprint: str = Field(min_length=64, max_length=64)
    reason: str | None = Field(default=None, max_length=1024)


class PayrollAttendancePrepareRequest(SQLModel):
    """Create an immutable-source draft from one configured pay period."""

    pay_group_id: uuid.UUID
    date_from: date
    date_to: date


class PayrollDraftRebuildRequest(SQLModel):
    expected_run_fingerprint: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=5, max_length=1024)


class PayrollReviewActionResult(SQLModel):
    run_id: uuid.UUID
    entry_id: uuid.UUID | None = None
    workflow_status: str
    reviewed_count: int
    excluded_count: int
    unresolved_count: int


class PayrollDeliveryStatusPublic(SQLModel):
    id: uuid.UUID
    payroll_entry_id: uuid.UUID
    document_version: int
    recipient_snapshot: str | None
    status: str
    attempts: int
    next_attempt_at: datetime | None
    sent_at: datetime | None
    last_error_code: str | None
    last_action_by: uuid.UUID | None
    last_action_at: datetime | None
    last_action_reason: str | None


class PayrollContributionLedgerPublic(SQLModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_code: str
    employee_name: str
    payroll_entry_id: uuid.UUID
    scheme: Literal["sss", "philhealth", "pagibig"]
    contribution_month: date
    sequence: int
    monthly_basis: Decimal
    employee_amount: Decimal
    employer_amount: Decimal
    source_references: list[str]
    adjustment_reason: str | None
    reverses_id: uuid.UUID | None
    created_at: datetime | None


class PayrollContributionLedgerList(SQLModel):
    data: list[PayrollContributionLedgerPublic]
    count: int


class PayrollContributionCorrectionCreate(SQLModel):
    """Apply a reasoned contribution correction to a later draft payroll."""

    source_ledger_id: uuid.UUID
    target_entry_id: uuid.UUID
    employee_amount: Decimal = Field(max_digits=14, decimal_places=2)
    employer_amount: Decimal = Field(max_digits=14, decimal_places=2)
    bir_withholding_delta: Decimal = Field(
        default=Decimal("0.00"), max_digits=14, decimal_places=2
    )
    tax_review_reference: str | None = Field(default=None, max_length=512)
    reason: str = Field(min_length=5, max_length=1024)
    source_reference: str = Field(min_length=3, max_length=512)

    @model_validator(mode="after")
    def validate_correction_amounts(self) -> "PayrollContributionCorrectionCreate":
        if self.employee_amount == 0 and self.employer_amount == 0:
            raise ValueError("At least one contribution correction amount is required")
        for value in (
            self.employee_amount,
            self.employer_amount,
            self.bir_withholding_delta,
        ):
            if not value.is_finite():
                raise ValueError("Contribution corrections must be finite amounts")
            if value != value.quantize(Decimal("0.01")):
                raise ValueError("Contribution corrections must use whole cents")
        if self.employee_amount != 0 and not (self.tax_review_reference or "").strip():
            raise ValueError(
                "Employee contribution corrections require a reviewed BIR withholding reference"
            )
        if self.bir_withholding_delta != 0 and self.employee_amount == 0:
            raise ValueError(
                "A BIR withholding change must accompany an employee contribution correction"
            )
        if not self.reason.strip() or not self.source_reference.strip():
            raise ValueError("A correction reason and source reference are required")
        return self


class PayrollContributionCorrectionTarget(SQLModel):
    entry_id: uuid.UUID
    run_id: uuid.UUID
    date_from: date
    date_to: date
    review_state: Literal["blocked", "ready"]
    net_pay: Decimal


class PayrollDeliveryAddressUpdate(SQLModel):
    email: EmailStr
    reason: str = Field(min_length=5, max_length=1024)


class PayrollDeliveryResendRequest(SQLModel):
    reason: str = Field(min_length=5, max_length=1024)
    confirm_duplicate_risk: bool = False


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
    adjustment_type: PayrollAdjustmentType = Field(
        default=PayrollAdjustmentType.REGULAR
    )
    entries: list[PayrollReviewOverride] | None = None
    employee_ids: list[uuid.UUID] | None = None
    department_id: uuid.UUID | None = None

    model_config = ConfigDict(use_enum_values=True)  # type: ignore[assignment]


class PayrollGenerateRequest(PayrollPreviewRequest):
    request_id: uuid.UUID


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


# === Attendance-driven payroll setup ================================================


class PayrollPayGroupCreate(SQLModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    cadence: CutoffType
    first_period_end_day: int | None = Field(default=None, ge=1, le=30)
    second_period_end_day: int | None = Field(default=None, ge=1, le=31)
    payment_offset_days: int = Field(default=0, ge=0, le=60)
    weekend_rule: Literal[
        "next_business_day", "previous_business_day", "nearest_business_day"
    ] = "next_business_day"


class PayrollPayGroupPublic(PayrollPayGroupCreate):
    id: uuid.UUID
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime | None
    updated_at: datetime | None


class EmployeePayGroupAssignmentCreate(SQLModel):
    employee_id: uuid.UUID
    pay_group_id: uuid.UUID
    effective_from: date
    effective_to: date | None = None


class EmployeePayGroupAssignmentPublic(EmployeePayGroupAssignmentCreate):
    id: uuid.UUID
    assigned_by: uuid.UUID | None
    created_at: datetime | None


class EmployeePayGroupAssignmentUpdate(SQLModel):
    effective_to: date


class EmployeePayGroupBulkRequest(SQLModel):
    batch_id: uuid.UUID
    pay_group_id: uuid.UUID
    effective_from: date
    employee_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class EmployeePayGroupBulkIssue(SQLModel):
    row_index: int
    employee_id: uuid.UUID
    code: str
    message: str


class EmployeePayGroupBulkPreflight(SQLModel):
    batch_id: uuid.UUID
    valid: bool
    requested: int
    replayed: bool = False
    issues: list[EmployeePayGroupBulkIssue]


class EmployeePayGroupBulkCommit(SQLModel):
    batch_id: uuid.UUID
    replayed: bool
    assignments: list[EmployeePayGroupAssignmentPublic]


class PayrollPolicyVersionCreate(SQLModel):
    effective_from: date
    policy: dict[str, Any]


class PayrollPolicyVersionPublic(SQLModel):
    id: uuid.UUID
    version: int
    effective_from: date
    effective_to: date | None
    policy: dict[str, Any]
    confirmed: bool
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime | None


class PayrollPayPeriodPublic(SQLModel):
    pay_group_id: uuid.UUID
    date_from: date
    date_to: date
    payment_date: date
    cadence: CutoffType
