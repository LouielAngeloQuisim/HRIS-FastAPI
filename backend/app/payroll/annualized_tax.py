"""Annualized compensation tax calculation for Philippine tax year 2023 onward.

Rates and thresholds follow RR 11-2018, Section 2.79(B)(5)(b), as amended by
the TRAIN law. This helper computes annual tax due only; callers must supply a
complete, verified taxable-compensation total and subtract verified prior
withholding to determine the current adjustment.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")

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
