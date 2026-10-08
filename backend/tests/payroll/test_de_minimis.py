from datetime import date
from decimal import Decimal

import pytest

from app.payroll.de_minimis import (
    DeMinimisInputError,
    calculate_de_minimis_allocation,
)


def test_monthly_and_annual_ceilings_use_independent_ledgers() -> None:
    result = calculate_de_minimis_allocation(
        paid_on=date(2026, 10, 31),
        current_paid={
            "rice_subsidy": Decimal("2600"),
            "uniform_clothing": Decimal("3000"),
        },
        month_to_date_paid={"rice_subsidy": Decimal("2000")},
        year_to_date_paid={"uniform_clothing": Decimal("6000")},
        other_benefits_exempt_remaining=Decimal("90000"),
    )

    assert result.eligible_exempt == {
        "rice_subsidy": Decimal("500.00"),
        "uniform_clothing": Decimal("2000.00"),
    }
    assert result.category_excess == {
        "rice_subsidy": Decimal("2100.00"),
        "uniform_clothing": Decimal("1000.00"),
    }
    assert result.other_benefits_exempt == Decimal("3100.00")
    assert result.taxable_excess == Decimal("0.00")


def test_excess_over_shared_annual_other_benefit_exemption_is_taxable() -> None:
    result = calculate_de_minimis_allocation(
        paid_on=date(2026, 12, 31),
        current_paid={"uniform_clothing": Decimal("10000")},
        month_to_date_paid={},
        year_to_date_paid={},
        other_benefits_exempt_remaining=Decimal("1500"),
    )

    assert result.eligible_exempt["uniform_clothing"] == Decimal("8000.00")
    assert result.category_excess["uniform_clothing"] == Decimal("2000.00")
    assert result.other_benefits_exempt == Decimal("1500.00")
    assert result.taxable_excess == Decimal("500.00")


@pytest.mark.parametrize(
    ("category", "evidence"),
    [
        ("actual_medical_assistance", set()),
        ("achievement_award", set()),
        ("cba_productivity_incentive", set()),
    ],
)
def test_conditional_categories_require_documented_eligibility(
    category: str, evidence: set[str]
) -> None:
    with pytest.raises(DeMinimisInputError, match="requires evidence flag"):
        calculate_de_minimis_allocation(
            paid_on=date(2026, 10, 31),
            current_paid={category: Decimal("100")},
            month_to_date_paid={},
            year_to_date_paid={},
            other_benefits_exempt_remaining=Decimal("90000"),
            evidence=evidence,
        )


def test_unknown_or_negative_benefits_fail_closed() -> None:
    with pytest.raises(DeMinimisInputError, match="Unsupported de minimis"):
        calculate_de_minimis_allocation(
            paid_on=date(2026, 10, 31),
            current_paid={"misc_allowance": Decimal("100")},
            month_to_date_paid={},
            year_to_date_paid={},
            other_benefits_exempt_remaining=Decimal("90000"),
        )

    with pytest.raises(DeMinimisInputError, match="non-negative"):
        calculate_de_minimis_allocation(
            paid_on=date(2026, 10, 31),
            current_paid={"rice_subsidy": Decimal("-1")},
            month_to_date_paid={},
            year_to_date_paid={},
            other_benefits_exempt_remaining=Decimal("90000"),
        )


def test_conditional_category_with_evidence_uses_published_cap() -> None:
    result = calculate_de_minimis_allocation(
        paid_on=date(2026, 12, 31),
        current_paid={"achievement_award": Decimal("13000")},
        month_to_date_paid={},
        year_to_date_paid={},
        other_benefits_exempt_remaining=Decimal("90000"),
        evidence={"written_non_discriminatory_award_plan"},
    )
    assert result.eligible_exempt["achievement_award"] == Decimal("12000.00")
    assert result.category_excess["achievement_award"] == Decimal("1000.00")


def test_first_day_rejects_nonzero_prior_period_totals() -> None:
    with pytest.raises(DeMinimisInputError, match="must be zero on the first day"):
        calculate_de_minimis_allocation(
            paid_on=date(2026, 10, 1),
            current_paid={"rice_subsidy": Decimal("100")},
            month_to_date_paid={"rice_subsidy": Decimal("1")},
            year_to_date_paid={},
            other_benefits_exempt_remaining=Decimal("90000"),
        )
