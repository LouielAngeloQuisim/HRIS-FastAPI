from datetime import date
from decimal import Decimal

import pytest

from app.payroll.attendance_calculator import (
    AttendancePayDay,
    CalculationBlocker,
    calculate_attendance_earnings,
)


def _day(**updates: object) -> AttendancePayDay:
    values: dict[str, object] = {
        "work_date": date(2026, 10, 1),
        "pay_type": "hourly",
        "basic_rate": Decimal("120"),
        "overtime_rate": Decimal("180"),
        "scheduled_minutes": 480,
        "worked_minutes": 480,
        "monthly_period_fraction": Decimal("0.5"),
        "monthly_period_scheduled_days": 11,
    }
    values.update(updates)
    return AttendancePayDay(**values)  # type: ignore[arg-type]


def test_hourly_earnings_use_minutes_and_approved_overtime_only() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                worked_minutes=540,
                overtime_eligible_minutes=60,
                overtime_approved_minutes=30,
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("960.00")
    assert result.overtime == Decimal("112.50")
    assert result.worked_minutes == 540


def test_hourly_overtime_minutes_are_not_paid_again_at_the_base_rate() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                basic_rate=Decimal("120"),
                overtime_rate=Decimal("120"),
                worked_minutes=540,
                overtime_eligible_minutes=60,
                overtime_approved_minutes=60,
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("960.00")
    assert result.overtime == Decimal("150.00")
    assert result.regular + result.overtime == Decimal("1110.00")


def test_hourly_paid_partial_leave_fills_only_the_unworked_scheduled_minutes() -> None:
    result = calculate_attendance_earnings(
        [_day(worked_minutes=240, paid_leave_minutes=240)],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("960.00")
    assert result.worked_minutes == 240


def test_daily_partial_leave_uses_the_confirmed_partial_work_rule() -> None:
    day = _day(
        pay_type="daily",
        basic_rate=Decimal("960"),
        worked_minutes=240,
        paid_leave_minutes=240,
    )
    pro_rated = calculate_attendance_earnings(
        [day], monthly_divisor=Decimal("22"), daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1"),
    )
    full_day = calculate_attendance_earnings(
        [day], monthly_divisor=Decimal("22"), daily_partial_work="full_day",
        overtime_multiplier=Decimal("1"),
    )

    assert pro_rated.regular == Decimal("960.00")
    assert full_day.regular == Decimal("960.00")


def test_monthly_paid_partial_leave_prevents_deduction_for_the_approved_minutes() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                pay_type="monthly",
                basic_rate=Decimal("26000"),
                worked_minutes=240,
                paid_leave_minutes=240,
                monthly_period_fraction=Decimal("0.5"),
                monthly_period_scheduled_days=11,
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        monthly_partial_work="deduct_after_grace",
        overtime_multiplier=Decimal("1"),
    )

    assert result.regular == Decimal("1181.82")
    assert result.attendance_deduction == Decimal("0.00")


def test_unpaid_partial_leave_is_deducted_even_when_short_time_rule_waives_undertime() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                pay_type="monthly",
                basic_rate=Decimal("26000"),
                worked_minutes=240,
                unpaid_leave_minutes=240,
                monthly_period_fraction=Decimal("0.5"),
                monthly_period_scheduled_days=11,
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        monthly_partial_work="no_deduction",
        overtime_multiplier=Decimal("1"),
    )

    assert result.regular == Decimal("1181.82")
    assert result.short_time_deduction == Decimal("0.00")
    assert result.attendance_deduction == Decimal("590.91")


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"paid_leave_minutes": -1}, "cannot be negative"),
        ({"paid_leave_minutes": 240, "unpaid_leave_minutes": 60}, "overlap"),
        ({"worked_minutes": 300, "paid_leave_minutes": 240}, "exceed the shift"),
    ],
)
def test_invalid_partial_leave_blocks_calculation(
    updates: dict[str, int], message: str
) -> None:
    with pytest.raises(CalculationBlocker, match=message):
        calculate_attendance_earnings(
            [_day(**updates)],
            monthly_divisor=Decimal("22"),
            daily_partial_work="pro_rated",
            overtime_multiplier=Decimal("1"),
        )


def test_configured_holiday_factors_add_regular_premium_and_override_overtime_factor() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                worked_minutes=540,
                overtime_eligible_minutes=60,
                overtime_approved_minutes=60,
                holiday_regular_multiplier=Decimal("2"),
                holiday_overtime_multiplier=Decimal("2.6"),
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("960.00")
    assert result.holiday_premium == Decimal("960.00")
    assert result.overtime == Decimal("468.00")


def test_rest_day_factors_apply_to_daily_and_approved_overtime_earnings() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                pay_type="daily",
                basic_rate=Decimal("960"),
                overtime_rate=Decimal("120"),
                worked_minutes=540,
                overtime_eligible_minutes=60,
                overtime_approved_minutes=60,
                rest_day_regular_multiplier=Decimal("1.30"),
                rest_day_overtime_multiplier=Decimal("1.69"),
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("960.00")
    assert result.rest_day_premium == Decimal("288.00")
    assert result.overtime == Decimal("202.80")


def test_monthly_rest_day_work_adds_only_the_premium_over_monthly_base() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                pay_type="monthly",
                basic_rate=Decimal("26000"),
                worked_minutes=480,
                monthly_salary_base_eligible=False,
                rest_day_regular_multiplier=Decimal("1.30"),
                rest_day_overtime_multiplier=Decimal("1.69"),
                rest_day_regular_base=Decimal("26000") / Decimal("22"),
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("0.00")
    assert result.rest_day_premium == Decimal("354.55")


def test_rest_day_policy_below_statutory_factors_blocks() -> None:
    with pytest.raises(CalculationBlocker, match="at least 1.30"):
        calculate_attendance_earnings(
            [_day(rest_day_regular_multiplier=Decimal("1.29"))],
            monthly_divisor=Decimal("22"),
            daily_partial_work="pro_rated",
            overtime_multiplier=Decimal("1.25"),
        )


def test_daily_rest_day_partial_work_uses_actual_worked_minutes() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                pay_type="daily",
                basic_rate=Decimal("960"),
                worked_minutes=240,
                rest_day_regular_multiplier=Decimal("1.30"),
                rest_day_overtime_multiplier=Decimal("1.69"),
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="full_day",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("480.00")
    assert result.rest_day_premium == Decimal("144.00")


def test_holiday_premium_uses_the_calculated_daily_base_and_not_absence_days() -> None:
    worked = _day(
        pay_type="daily",
        basic_rate=Decimal("800"),
        holiday_regular_multiplier=Decimal("2"),
        holiday_overtime_multiplier=Decimal("2.6"),
    )
    absent = _day(
        work_date=date(2026, 10, 2),
        pay_type="daily",
        basic_rate=Decimal("800"),
        worked_minutes=0,
        absence=True,
        holiday_regular_multiplier=Decimal("2"),
        holiday_overtime_multiplier=Decimal("2.6"),
    )
    result = calculate_attendance_earnings(
        [worked, absent],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )
    assert result.regular == Decimal("800.00")
    assert result.holiday_premium == Decimal("800.00")


def test_invalid_holiday_multiplier_blocks_calculation() -> None:
    with pytest.raises(CalculationBlocker, match="Holiday regular multiplier"):
        calculate_attendance_earnings(
            [_day(holiday_regular_multiplier=Decimal("0.9"))],
            monthly_divisor=Decimal("22"),
            daily_partial_work="pro_rated",
            overtime_multiplier=Decimal("1.25"),
        )


def test_pending_overtime_blocks_amount_calculation() -> None:
    with pytest.raises(CalculationBlocker, match="Overtime decision is pending"):
        calculate_attendance_earnings(
            [_day(overtime_eligible_minutes=30)],
            monthly_divisor=Decimal("22"),
            daily_partial_work="pro_rated",
            overtime_multiplier=Decimal("1.25"),
        )


def test_daily_partial_work_is_policy_driven_and_absence_is_deducted_once() -> None:
    day = _day(pay_type="daily", basic_rate=Decimal("800"), worked_minutes=240)
    pro_rated = calculate_attendance_earnings(
        [day], monthly_divisor=Decimal("22"), daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1"),
    )
    full_day = calculate_attendance_earnings(
        [day], monthly_divisor=Decimal("22"), daily_partial_work="full_day",
        overtime_multiplier=Decimal("1"),
    )
    assert pro_rated.regular == Decimal("400.00")
    assert full_day.regular == Decimal("0.00")

    absent = calculate_attendance_earnings(
        [_day(pay_type="monthly", basic_rate=Decimal("26000"), worked_minutes=0, absence=True)],
        monthly_divisor=Decimal("26"), daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1"),
    )
    assert absent.attendance_deduction == Decimal("1000.00")


def test_monthly_salary_period_base_deducts_unpaid_absence_once() -> None:
    scheduled_dates = [
        date(2026, 10, day)
        for day in range(1, 16)
        if date(2026, 10, day).weekday() < 5
    ]
    absent_date = date(2026, 10, 5)
    days = [
        _day(
            work_date=work_date,
            pay_type="monthly",
            basic_rate=Decimal("26000"),
            worked_minutes=0 if work_date == absent_date else 480,
            absence=work_date == absent_date,
        )
        for work_date in scheduled_dates
    ]
    result = calculate_attendance_earnings(
        days,
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    # 11 scheduled dates produce a half-month base of 13,000.00. One unpaid
    # absence deducts 26,000 / 22 once, leaving 11,818.18.
    assert result.regular == Decimal("13000.00")
    assert result.attendance_deduction == Decimal("1181.82")
    assert result.regular - result.attendance_deduction == Decimal("11818.18")


@pytest.mark.parametrize("scheduled_days", [10, 11])
def test_monthly_semi_monthly_base_does_not_change_with_cutoff_weekday_count(
    scheduled_days: int,
) -> None:
    days = [
        _day(
            work_date=date(2026, 10, day),
            pay_type="monthly",
            basic_rate=Decimal("26000"),
            monthly_period_fraction=Decimal("0.5"),
            monthly_period_scheduled_days=scheduled_days,
        )
        for day in range(1, scheduled_days + 1)
    ]

    result = calculate_attendance_earnings(
        days,
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("13000.00")


def test_monthly_divisor_proration_is_an_explicit_company_rule() -> None:
    days = [
        _day(
            work_date=date(2026, 10, day),
            pay_type="monthly",
            basic_rate=Decimal("26000"),
            monthly_salary_proration="monthly_divisor_per_workday",
        )
        for day in (1, 2)
    ]

    result = calculate_attendance_earnings(
        days,
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("2363.64")


def test_monthly_partial_work_deducts_lateness_after_grace() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                pay_type="monthly",
                basic_rate=Decimal("26000"),
                worked_minutes=465,
                raw_late_minutes=15,
                grace_minutes=10,
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        monthly_partial_work="deduct_after_grace",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("1181.82")
    assert result.attendance_deduction == Decimal("12.31")
    assert result.short_time_deduction == Decimal("12.31")


def test_monthly_partial_work_deducts_early_departure_and_can_follow_no_deduction_rule() -> None:
    day = _day(
        pay_type="monthly",
        basic_rate=Decimal("26000"),
        worked_minutes=465,
        raw_late_minutes=0,
        grace_minutes=10,
    )
    common = {
        "monthly_divisor": Decimal("22"),
        "daily_partial_work": "pro_rated",
        "overtime_multiplier": Decimal("1.25"),
    }
    deduct = calculate_attendance_earnings(
        [day], monthly_partial_work="deduct_after_grace", **common
    )
    protect = calculate_attendance_earnings(
        [day], monthly_partial_work="no_deduction", **common
    )

    assert deduct.attendance_deduction == Decimal("36.93")
    assert deduct.short_time_deduction == Decimal("36.93")
    assert protect.attendance_deduction == Decimal("0.00")
    assert protect.short_time_deduction == Decimal("0.00")


def test_monthly_partial_work_without_confirmed_rule_blocks_calculation() -> None:
    with pytest.raises(CalculationBlocker, match="Monthly partial-work policy is missing"):
        calculate_attendance_earnings(
            [
                _day(
                    pay_type="monthly",
                    basic_rate=Decimal("26000"),
                    worked_minutes=465,
                )
            ],
            monthly_divisor=Decimal("22"),
            daily_partial_work="pro_rated",
            overtime_multiplier=Decimal("1.25"),
        )


def test_monthly_paid_holiday_does_not_create_short_time_deduction() -> None:
    result = calculate_attendance_earnings(
        [
            _day(
                pay_type="monthly",
                basic_rate=Decimal("26000"),
                worked_minutes=0,
                paid_absence=True,
            )
        ],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        monthly_partial_work="deduct_after_grace",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("1181.82")
    assert result.attendance_deduction == Decimal("0.00")
    assert result.short_time_deduction == Decimal("0.00")
