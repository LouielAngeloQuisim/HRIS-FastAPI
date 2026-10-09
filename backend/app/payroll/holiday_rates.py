"""Statutory minimum multipliers for ordinary Philippine private-sector holiday work.

Rates follow the DOLE/NWPC Workers' Statutory Monetary Benefits Handbook,
2024 edition, guide-computation table. Company rates may be more generous for
a single holiday; combinations outside the documented statutory schedules fail
closed until an explicit company rule is configured and reviewed.
"""

from decimal import Decimal


class HolidayRateError(ValueError):
    """Raised when holiday rates cannot be combined without guessing."""


_SINGLE: dict[tuple[str, bool], tuple[Decimal, Decimal]] = {
    ("regular", False): (Decimal("2.0"), Decimal("2.6")),
    ("regular", True): (Decimal("2.6"), Decimal("3.38")),
    ("special_non_working", False): (Decimal("1.3"), Decimal("1.69")),
    ("special_non_working", True): (Decimal("1.5"), Decimal("1.95")),
}

_DOUBLE: dict[tuple[str, bool], tuple[Decimal, Decimal]] = {
    ("regular", False): (Decimal("3.0"), Decimal("3.9")),
    ("regular", True): (Decimal("3.9"), Decimal("5.07")),
    ("special_non_working", False): (Decimal("1.5"), Decimal("1.95")),
    ("special_non_working", True): (Decimal("1.95"), Decimal("2.535")),
}


def resolve_holiday_factors(
    holiday_type: str,
    holiday_count: int,
    *,
    rest_day: bool,
    configured_regular: list[Decimal | None],
    configured_overtime: list[Decimal | None],
) -> tuple[Decimal, Decimal]:
    """Return approved factors or explain why the configuration is unsafe.

    Double-holiday factors are supported only when each holiday's configured
    factor is exactly the statutory single-holiday factor. If an employer has a
    more generous individual rate, its interaction with another holiday must
    be explicitly reviewed instead of guessed.
    """
    if holiday_count < 1:
        raise HolidayRateError("Only one or two same-type holidays can be resolved for a date.")
    if len(configured_regular) != holiday_count or len(configured_overtime) != holiday_count:
        raise HolidayRateError("Holiday multiplier configuration is incomplete.")
    if any(value is None for value in configured_regular + configured_overtime):
        raise HolidayRateError("Holiday multiplier configuration is incomplete.")
    if holiday_type == "company":
        if holiday_count != 1:
            raise HolidayRateError("Overlapping company holidays need an explicitly reviewed stacking rule.")
        regular, overtime = configured_regular[0], configured_overtime[0]
        assert regular is not None and overtime is not None
        if regular < 1 or overtime < 1:
            raise HolidayRateError("Company holiday factors cannot be below the ordinary rate.")
        return regular, overtime
    if holiday_type not in {"regular", "special_non_working"}:
        raise HolidayRateError("This holiday type has no supported statutory stacking rule.")
    if holiday_count not in {1, 2}:
        raise HolidayRateError("Only one or two same-type holidays can be resolved for a date.")

    single_regular, single_overtime = _SINGLE[(holiday_type, rest_day)]
    if holiday_count == 1:
        regular, overtime = configured_regular[0], configured_overtime[0]
        assert regular is not None and overtime is not None
        if regular < single_regular or overtime < single_overtime:
            raise HolidayRateError(
                "Configured holiday pay is below the statutory minimum for this day type."
            )
        return regular, overtime

    double_regular, double_overtime = _DOUBLE[(holiday_type, rest_day)]
    if any(value != single_regular for value in configured_regular):
        raise HolidayRateError(
            "Double-holiday work with a non-standard regular factor needs an explicitly reviewed stacking rule."
        )
    if any(value != single_overtime for value in configured_overtime):
        raise HolidayRateError(
            "Double-holiday overtime with a non-standard factor needs an explicitly reviewed stacking rule."
        )
    return double_regular, double_overtime
