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
    }
    values.update(updates)
    return AttendancePayDay(**values)  # type: ignore[arg-type]


def test_hourly_earnings_use_minutes_and_approved_overtime_only() -> None:
    result = calculate_attendance_earnings(
        [_day(overtime_eligible_minutes=60, overtime_approved_minutes=30)],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )

    assert result.regular == Decimal("960.00")
    assert result.overtime == Decimal("112.50")
    assert result.worked_minutes == 480


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
