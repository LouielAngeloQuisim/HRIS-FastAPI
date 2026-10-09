from decimal import Decimal

import pytest

from app.payroll.de_minimis import (
    DeMinimisInputError,
    calculate_de_minimis_allocation,
    calculate_daily_meal_exemption,
    calculate_unused_vacation_leave_exemption,
)


def test_monthly_and_annual_ceilings_use_independent_ledgers() -> None:
    result = calculate_de_minimis_allocation(
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
            current_paid={category: Decimal("100")},
            month_to_date_paid={},
            year_to_date_paid={},
            other_benefits_exempt_remaining=Decimal("90000"),
            evidence=evidence,
        )


def test_unknown_or_negative_benefits_fail_closed() -> None:
    with pytest.raises(DeMinimisInputError, match="Unsupported de minimis"):
        calculate_de_minimis_allocation(
            current_paid={"misc_allowance": Decimal("100")},
            month_to_date_paid={},
            year_to_date_paid={},
            other_benefits_exempt_remaining=Decimal("90000"),
        )

    with pytest.raises(DeMinimisInputError, match="non-negative"):
        calculate_de_minimis_allocation(
            current_paid={"rice_subsidy": Decimal("-1")},
            month_to_date_paid={},
            year_to_date_paid={},
            other_benefits_exempt_remaining=Decimal("90000"),
        )


def test_conditional_category_with_evidence_uses_published_cap() -> None:
    result = calculate_de_minimis_allocation(
        current_paid={"achievement_award": Decimal("13000")},
        month_to_date_paid={},
        year_to_date_paid={},
        other_benefits_exempt_remaining=Decimal("90000"),
        evidence={"written_non_discriminatory_award_plan"},
    )
    assert result.eligible_exempt["achievement_award"] == Decimal("12000.00")
    assert result.category_excess["achievement_award"] == Decimal("1000.00")


def test_first_day_accepts_prior_same_day_payments_from_the_ledger() -> None:
    result = calculate_de_minimis_allocation(
        current_paid={"rice_subsidy": Decimal("1000")},
        month_to_date_paid={"rice_subsidy": Decimal("2000")},
        year_to_date_paid={},
        other_benefits_exempt_remaining=Decimal("90000"),
    )
    assert result.eligible_exempt["rice_subsidy"] == Decimal("500.00")
    assert result.category_excess["rice_subsidy"] == Decimal("500.00")


def test_daily_meal_exemption_uses_regional_wage_times_verified_days() -> None:
    result = calculate_daily_meal_exemption(
        gross_amount=Decimal("500.00"),
        regional_daily_minimum_wage=Decimal("610.00"),
        qualifying_days=2,
        evidence_verified=True,
    )
    assert result.eligible_exempt == Decimal("366.00")
    assert result.category_excess == Decimal("134.00")


@pytest.mark.parametrize(
    ("wage", "days", "verified"),
    [(Decimal("0"), 1, True), (Decimal("610"), 0, True), (Decimal("610"), 1, False)],
)
def test_daily_meal_exemption_fails_closed_without_valid_inputs(
    wage: Decimal, days: int, verified: bool
) -> None:
    with pytest.raises(DeMinimisInputError):
        calculate_daily_meal_exemption(
            gross_amount=Decimal("100"),
            regional_daily_minimum_wage=wage,
            qualifying_days=days,
            evidence_verified=verified,
        )


def test_unused_vacation_exemption_allocates_only_remaining_days() -> None:
    result = calculate_unused_vacation_leave_exemption(
        gross_amount=Decimal("9000.00"),
        qualifying_days=3,
        prior_exempt_days=11,
        evidence_verified=True,
    )
    assert result.eligible_exempt == Decimal("3000.00")
    assert result.category_excess == Decimal("6000.00")
    assert result.exempt_days == 1

    next_payment = calculate_unused_vacation_leave_exemption(
        gross_amount=Decimal("6000.00"),
        qualifying_days=3,
        prior_exempt_days=12,
        evidence_verified=True,
    )
    assert next_payment.eligible_exempt == Decimal("0.00")
    assert next_payment.category_excess == Decimal("6000.00")
    assert next_payment.exempt_days == 0


def test_unused_vacation_exemption_requires_verified_balance() -> None:
    with pytest.raises(DeMinimisInputError, match="verified unused leave"):
        calculate_unused_vacation_leave_exemption(
            gross_amount=Decimal("1000"),
            qualifying_days=1,
            prior_exempt_days=0,
            evidence_verified=False,
        )
