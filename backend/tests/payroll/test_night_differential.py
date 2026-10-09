from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.payroll.attendance_calculator import (
    AttendancePayDay,
    CalculationBlocker,
    calculate_attendance_earnings,
)
from app.payroll.night_differential import (
    NightDifferentialInputError,
    allocate_night_work_minutes,
)

MANILA = ZoneInfo("Asia/Manila")


def test_allocate_night_minutes_splits_regular_and_approved_overtime() -> None:
    regular, overtime = allocate_night_work_minutes(
        [
            (
                datetime.fromisoformat("2026-10-01T21:00:00+08:00"),
                datetime.fromisoformat("2026-10-02T07:00:00+08:00"),
            )
        ],
        scheduled_minutes=480,
        expected_worked_minutes=600,
        approved_overtime_minutes=60,
        unpaid_break_minutes=0,
        zone=MANILA,
    )
    assert (regular, overtime) == (420, 60)


def test_interval_gap_keeps_unpaid_break_out_of_night_work() -> None:
    regular, overtime = allocate_night_work_minutes(
        [
            (
                datetime.fromisoformat("2026-10-01T21:00:00+08:00"),
                datetime.fromisoformat("2026-10-02T01:00:00+08:00"),
            ),
            (
                datetime.fromisoformat("2026-10-02T02:00:00+08:00"),
                datetime.fromisoformat("2026-10-02T07:00:00+08:00"),
            ),
        ],
        scheduled_minutes=480,
        expected_worked_minutes=540,
        approved_overtime_minutes=60,
        unpaid_break_minutes=60,
        zone=MANILA,
    )
    assert (regular, overtime) == (420, 0)


def test_legacy_single_interval_with_night_break_is_blocked() -> None:
    with pytest.raises(NightDifferentialInputError, match="Split the attendance interval"):
        allocate_night_work_minutes(
            [
                (
                    datetime.fromisoformat("2026-10-01T21:00:00+08:00"),
                    datetime.fromisoformat("2026-10-02T06:00:00+08:00"),
                )
            ],
            scheduled_minutes=480,
            expected_worked_minutes=480,
            approved_overtime_minutes=0,
            unpaid_break_minutes=60,
            zone=MANILA,
        )


def test_interval_duration_must_match_reviewed_attendance_minutes() -> None:
    with pytest.raises(NightDifferentialInputError, match="do not match"):
        allocate_night_work_minutes(
            [
                (
                    datetime.fromisoformat("2026-10-01T22:00:00+08:00"),
                    datetime.fromisoformat("2026-10-02T06:00:00+08:00"),
                )
            ],
            scheduled_minutes=480,
            expected_worked_minutes=479,
            approved_overtime_minutes=0,
            unpaid_break_minutes=0,
            zone=MANILA,
        )


def test_night_differential_uses_pay_basis_and_overtime_multiplier() -> None:
    day = AttendancePayDay(
        work_date=datetime(2026, 10, 1).date(),
        pay_type="hourly",
        basic_rate=Decimal("120"),
        overtime_rate=Decimal("120"),
        scheduled_minutes=480,
        worked_minutes=540,
        overtime_eligible_minutes=60,
        overtime_approved_minutes=60,
        night_regular_minutes=420,
        night_overtime_minutes=60,
        night_differential_rate=Decimal("0.10"),
    )
    result = calculate_attendance_earnings(
        [day],
        monthly_divisor=Decimal("22"),
        daily_partial_work="pro_rated",
        overtime_multiplier=Decimal("1.25"),
    )
    assert result.night_differential == Decimal("99.00")


def test_night_differential_cannot_be_below_statutory_minimum() -> None:
    day = AttendancePayDay(
        work_date=datetime(2026, 10, 1).date(),
        pay_type="hourly",
        basic_rate=Decimal("120"),
        overtime_rate=Decimal("120"),
        scheduled_minutes=480,
        worked_minutes=480,
        night_regular_minutes=60,
        night_differential_rate=Decimal("0.09"),
    )
    with pytest.raises(CalculationBlocker, match="no less than 10%"):
        calculate_attendance_earnings(
            [day],
            monthly_divisor=Decimal("22"),
            daily_partial_work="pro_rated",
            overtime_multiplier=Decimal("1.25"),
        )
