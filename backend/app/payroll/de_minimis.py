"""BIR de minimis ceilings for ordinary private-sector employees.

This module calculates only the BIR ceiling allocation. Callers must supply
paid amounts and the employee's prior month/year totals from an authoritative
ledger; it does not infer attendance, payment timing, or statutory-fund bases.
Amounts above a category ceiling become "other benefits" and are subject to
the shared annual exemption only to the extent that exemption remains.

Ceilings are from BIR RR 29-2025, amending RR 2-98, section 2.78.1(A)(3).
"Medical cash allowance to dependents" uses the expressly allowed monthly
option (P333/month), rather than mixing monthly and semester ceilings.
"Achievement award" requires evidence of the prescribed written plan.
"Actual medical assistance" requires source documentation. CBA and
productivity incentives share one annual ceiling.
Daily meal allowance has a per-region, per-eligible-day cap and is handled by
``calculate_daily_meal_exemption`` with a reviewed wage-order source. Monetized
private-sector unused vacation leave has a twelve-day annual limit and is
handled by ``calculate_unused_vacation_leave_exemption`` with reconciled day
balances; neither may be treated as a flat monetary ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
OTHER_BENEFITS_ANNUAL_EXEMPTION = Decimal("90000.00")
UNUSED_VACATION_LEAVE_EXEMPT_DAYS = 12
DAILY_MEAL_ALLOWANCE_WAGE_FACTOR = Decimal("0.30")

# category: (period, ceiling, required evidence flag)
_CAPS: dict[str, tuple[str, Decimal, str | None]] = {
    "medical_cash_dependents": ("month", Decimal("333.00"), None),
    "rice_subsidy": ("month", Decimal("2500.00"), None),
    "uniform_clothing": ("year", Decimal("8000.00"), None),
    "actual_medical_assistance": (
        "year",
        Decimal("12000.00"),
        "actual_medical_documentation",
    ),
    "laundry_allowance": ("month", Decimal("400.00"), None),
    "achievement_award": (
        "year",
        Decimal("12000.00"),
        "written_non_discriminatory_award_plan",
    ),
    "christmas_anniversary_gift": ("year", Decimal("6000.00"), None),
    "cba_productivity_incentive": (
        "year",
        Decimal("12000.00"),
        "cba_or_productivity_incentive_evidence",
    ),
}


class DeMinimisInputError(ValueError):
    """Raised when a benefit cannot be safely assigned a statutory ceiling."""


@dataclass(frozen=True)
class DeMinimisResult:
    eligible_exempt: dict[str, Decimal]
    category_excess: dict[str, Decimal]
    other_benefits_exempt: Decimal
    taxable_excess: Decimal


@dataclass(frozen=True)
class DeMinimisDayResult:
    eligible_exempt: Decimal
    category_excess: Decimal
    qualifying_days: int
    exempt_days: int


def _amount(value: object, *, field: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DeMinimisInputError(f"{field} must be a valid decimal amount") from exc
    if not amount.is_finite() or amount < 0:
        raise DeMinimisInputError(f"{field} must be finite and non-negative")
    return amount.quantize(CENT)


def calculate_de_minimis_allocation(
    *,
    current_paid: dict[str, Decimal],
    month_to_date_paid: dict[str, Decimal],
    year_to_date_paid: dict[str, Decimal],
    other_benefits_exempt_remaining: Decimal,
    evidence: set[str] | None = None,
) -> DeMinimisResult:
    """Split current benefits into exempt de minimis, excess, and taxable.

    ``current_paid`` contains actual amounts paid in this payroll period.
    ``month_to_date_paid`` and ``year_to_date_paid`` are finalized-ledger
    amounts strictly before this period. The shared P90,000 other-benefit
    exemption balance must likewise be read from verified opening figures and
    finalized benefit records; it is never inferred here.
    """
    allowed_keys = set(_CAPS)
    unsupported = set(current_paid) - allowed_keys
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise DeMinimisInputError(
            f"Unsupported de minimis categories require a separate verified rule: {names}"
        )
    if set(month_to_date_paid) - allowed_keys or set(year_to_date_paid) - allowed_keys:
        raise DeMinimisInputError("Prior benefit totals contain an unsupported category")

    remaining_other = _amount(
        other_benefits_exempt_remaining,
        field="other_benefits_exempt_remaining",
    )
    if remaining_other > OTHER_BENEFITS_ANNUAL_EXEMPTION:
        raise DeMinimisInputError("Remaining other-benefit exemption exceeds P90,000")
    evidence = evidence or set()
    exempt: dict[str, Decimal] = {}
    excess: dict[str, Decimal] = {}
    total_excess = Decimal("0.00")

    for category, raw_current in current_paid.items():
        period, cap, required_evidence = _CAPS[category]
        current = _amount(raw_current, field=f"current_paid.{category}")
        if required_evidence is not None and current and required_evidence not in evidence:
            raise DeMinimisInputError(
                f"{category} requires evidence flag {required_evidence}"
            )
        if period == "month":
            prior = _amount(
                month_to_date_paid.get(category, Decimal("0.00")),
                field=f"month_to_date_paid.{category}",
            )
        else:
            prior = _amount(
                year_to_date_paid.get(category, Decimal("0.00")),
                field=f"year_to_date_paid.{category}",
            )

        remaining_cap = max(Decimal("0.00"), cap - prior)
        eligible = min(current, remaining_cap).quantize(CENT)
        category_excess = (current - eligible).quantize(CENT)
        exempt[category] = eligible
        excess[category] = category_excess
        total_excess += category_excess

    other_exempt = min(total_excess, remaining_other).quantize(CENT)
    taxable = (total_excess - other_exempt).quantize(CENT)
    return DeMinimisResult(
        eligible_exempt=exempt,
        category_excess=excess,
        other_benefits_exempt=other_exempt,
        taxable_excess=taxable,
    )


def calculate_daily_meal_exemption(
    *,
    gross_amount: Decimal,
    regional_daily_minimum_wage: Decimal,
    qualifying_days: int,
    evidence_verified: bool,
) -> DeMinimisDayResult:
    """Apply RR 29-2025's 30% regional daily minimum-wage limit per day."""
    gross = _amount(gross_amount, field="gross_amount")
    wage = _amount(regional_daily_minimum_wage, field="regional_daily_minimum_wage")
    if wage <= 0:
        raise DeMinimisInputError("A positive regional minimum wage is required")
    if qualifying_days < 1 or qualifying_days > 366:
        raise DeMinimisInputError("qualifying_days must be between 1 and 366")
    if not evidence_verified:
        raise DeMinimisInputError(
            "Daily meal allowance requires verified overtime/night-shift and wage-order evidence"
        )
    cap = (wage * DAILY_MEAL_ALLOWANCE_WAGE_FACTOR * qualifying_days).quantize(
        CENT, rounding=ROUND_DOWN
    )
    exempt = min(gross, cap).quantize(CENT)
    return DeMinimisDayResult(
        eligible_exempt=exempt,
        category_excess=(gross - exempt).quantize(CENT),
        qualifying_days=qualifying_days,
        exempt_days=qualifying_days if exempt > 0 else 0,
    )


def calculate_unused_vacation_leave_exemption(
    *,
    gross_amount: Decimal,
    qualifying_days: int,
    prior_exempt_days: int,
    evidence_verified: bool,
) -> DeMinimisDayResult:
    """Apply the annual twelve-day private-sector unused-vacation limit.

    A payment record represents a single uniform daily rate. Any current days
    beyond the annual remaining allowance are taxable as other benefits.
    """
    gross = _amount(gross_amount, field="gross_amount")
    if qualifying_days < 1 or qualifying_days > 366:
        raise DeMinimisInputError("qualifying_days must be between 1 and 366")
    if prior_exempt_days < 0 or prior_exempt_days > UNUSED_VACATION_LEAVE_EXEMPT_DAYS:
        raise DeMinimisInputError("prior_exempt_days must be between 0 and 12")
    if not evidence_verified:
        raise DeMinimisInputError(
            "Monetized unused vacation leave requires verified unused leave balance evidence"
        )
    exempt_days = min(
        qualifying_days,
        max(0, UNUSED_VACATION_LEAVE_EXEMPT_DAYS - prior_exempt_days),
    )
    exempt = (gross * Decimal(exempt_days) / Decimal(qualifying_days)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    return DeMinimisDayResult(
        eligible_exempt=exempt,
        category_excess=(gross - exempt).quantize(CENT),
        qualifying_days=qualifying_days,
        exempt_days=exempt_days if exempt > 0 else 0,
    )
