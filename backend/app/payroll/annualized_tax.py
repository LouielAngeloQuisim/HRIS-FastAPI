"""Annualized compensation tax calculation for Philippine tax year 2023 onward.

Rates and thresholds follow RR 11-2018, Section 2.79(B)(5)(b), as amended by
the TRAIN law. This helper computes annual tax due only; callers must supply a
complete, verified taxable-compensation total and subtract verified prior
withholding to determine the current adjustment.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def cumulative_average_withholding(
    *,
    cumulative_taxable_compensation: Decimal,
    period_count: int,
    tax_per_period: Decimal,
    prior_withheld: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return average pay, cumulative tax due, and current withholding.

    Implements the arithmetic steps in RR 11-2018, Section 2.79(B)(5)(a).
    Historical totals and the applicable period table are supplied by the
    caller; this helper deliberately does not infer either input.
    """
    values = (cumulative_taxable_compensation, tax_per_period, prior_withheld)
    if any(not value.is_finite() or value < 0 for value in values):
        raise ValueError("Cumulative tax inputs must be finite and non-negative")
    if period_count < 1:
        raise ValueError("At least one payroll period is required")
    average = (cumulative_taxable_compensation / Decimal(period_count)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    cumulative_tax_due = (tax_per_period * period_count).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    current_withholding = max(Decimal("0.00"), cumulative_tax_due - prior_withheld)
    return average, cumulative_tax_due, current_withholding.quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def cumulative_average_required(
    *,
    regular_compensation: Decimal,
    supplementary_compensation: Decimal,
    first_taxable_regular_amount: Decimal,
    previously_applied: bool = False,
) -> bool:
    """Apply the RR 11-2018 cumulative-average triggers consistently.

    The method starts when regular compensation is below the table's first
    taxable regular-compensation amount and any supplementary compensation is
    paid, or when supplementary compensation equals/exceeds regular
    compensation. Once used in a tax year, it remains in use for that year.
    """
    values = (
        regular_compensation,
        supplementary_compensation,
        first_taxable_regular_amount,
    )
    if any(not value.is_finite() or value < 0 for value in values):
        raise ValueError("BIR compensation inputs must be finite and non-negative")
    if previously_applied:
        return True
    if supplementary_compensation == 0:
        return False
    return (
        regular_compensation < first_taxable_regular_amount
        or supplementary_compensation >= regular_compensation
    )

# (lower bound, base tax, marginal rate), as prescribed for 2023 onward.
ANNUAL_BRACKETS: tuple[tuple[Decimal, Decimal, Decimal], ...] = (
    (Decimal("0"), Decimal("0"), Decimal("0")),
    (Decimal("250000"), Decimal("0"), Decimal("0.15")),
    (Decimal("400000"), Decimal("22500"), Decimal("0.20")),
    (Decimal("800000"), Decimal("102500"), Decimal("0.25")),
    (Decimal("2000000"), Decimal("402500"), Decimal("0.30")),
    (Decimal("8000000"), Decimal("2202500"), Decimal("0.35")),
)


def calculate_annualized_compensation_tax(taxable_compensation: Decimal) -> Decimal:
    """Return annual income tax due, rounded to centavo using half-up rounding."""
    if not taxable_compensation.is_finite() or taxable_compensation < 0:
        raise ValueError("Taxable compensation must be a finite non-negative amount")

    lower, base_tax, marginal_rate = ANNUAL_BRACKETS[0]
    for bracket_lower, bracket_base, bracket_rate in ANNUAL_BRACKETS[1:]:
        if taxable_compensation < bracket_lower:
            break
        lower, base_tax, marginal_rate = bracket_lower, bracket_base, bracket_rate

    tax = base_tax + (taxable_compensation - lower) * marginal_rate
    return tax.quantize(CENT, rounding=ROUND_HALF_UP)
