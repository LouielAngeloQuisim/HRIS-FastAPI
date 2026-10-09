"""Statutory holiday-factor rules backed by the NWPC 2024 handbook table."""

from decimal import Decimal

import pytest

from app.payroll.holiday_rates import HolidayRateError, resolve_holiday_factors


@pytest.mark.parametrize(
    ("kind", "rest_day", "expected"),
    [
        ("regular", False, ("3.0", "3.9")),
        ("regular", True, ("3.9", "5.07")),
        ("special_non_working", False, ("1.5", "1.95")),
        ("special_non_working", True, ("1.95", "2.535")),
    ],
)
def test_double_holiday_factors_match_official_schedule(
    kind: str, rest_day: bool, expected: tuple[str, str]
) -> None:
    singles = {
        ("regular", False): ("2.0", "2.6"),
        ("regular", True): ("2.6", "3.38"),
        ("special_non_working", False): ("1.3", "1.69"),
        ("special_non_working", True): ("1.5", "1.95"),
    }
    regular, overtime = singles[(kind, rest_day)]
    result = resolve_holiday_factors(
        kind,
        2,
        rest_day=rest_day,
        configured_regular=[Decimal(regular)] * 2,
        configured_overtime=[Decimal(overtime)] * 2,
    )
    assert result == (Decimal(expected[0]), Decimal(expected[1]))


@pytest.mark.parametrize(
    ("kind", "rest_day", "regular", "overtime"),
    [
        ("regular", False, "1.99", "2.6"),
        ("regular", True, "2.6", "3.37"),
        ("special_non_working", False, "1.3", "1.68"),
        ("special_non_working", True, "1.49", "1.95"),
    ],
)
def test_single_holiday_below_statutory_floor_is_rejected(
    kind: str, rest_day: bool, regular: str, overtime: str
) -> None:
    with pytest.raises(HolidayRateError, match="below the statutory minimum"):
        resolve_holiday_factors(
            kind,
            1,
            rest_day=rest_day,
            configured_regular=[Decimal(regular)],
            configured_overtime=[Decimal(overtime)],
        )


def test_double_holiday_does_not_guess_custom_enhanced_stacking() -> None:
    with pytest.raises(HolidayRateError, match="explicitly reviewed stacking rule"):
        resolve_holiday_factors(
            "regular",
            2,
            rest_day=False,
            configured_regular=[Decimal("2.0"), Decimal("2.5")],
            configured_overtime=[Decimal("2.6"), Decimal("3.25")],
        )


def test_unsupported_or_more_than_two_holidays_fail_closed() -> None:
    for kind, count in (("company", 2), ("regular", 3)):
        with pytest.raises(HolidayRateError):
            resolve_holiday_factors(
                kind,
                count,
                rest_day=False,
                configured_regular=[Decimal("2.0")] * count,
                configured_overtime=[Decimal("2.6")] * count,
            )


def test_single_company_holiday_uses_explicit_company_factors() -> None:
    assert resolve_holiday_factors(
        "company",
        1,
        rest_day=False,
        configured_regular=[Decimal("1.25")],
        configured_overtime=[Decimal("1.5")],
    ) == (Decimal("1.25"), Decimal("1.5"))
