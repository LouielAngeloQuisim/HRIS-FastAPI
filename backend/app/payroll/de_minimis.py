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
"daily_meal_ot_night" is deliberately rejected here because its 30% cap
depends on the applicable regional statutory minimum wage and eligible days;
callers must use a future region-aware implementation instead of guessing.
"Monetized unused vacation leave" is also excluded because the ceiling is in
days and needs leave-ledger evidence, not merely a monetary amount.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

CENT = Decimal("0.01")
OTHER_BENEFITS_ANNUAL_EXEMPTION = Decimal("90000.00")

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
