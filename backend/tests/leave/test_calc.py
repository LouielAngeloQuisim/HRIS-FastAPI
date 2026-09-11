"""Phase b3 test set A — pure calc unit tests (design doc §1.3).

Hand-defined expected values, no DB. Each scenario exercises calc.py directly.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.leave import calc
from app.leave.calc import LeaveStateError, leave_days_in_range
from app.leave.models import LeaveCadence, LeavePolicy


def _policy(
    *,
    annual_entitlement_days: Decimal = Decimal("15.00"),
    cadence: LeaveCadence = LeaveCadence.ANNUAL,
    prorate_on_hire: bool = False,
    carry_over_enabled: bool = False,
    carry_over_max_days: Decimal | None = None,
    carry_over_expires_on: date | None = None,
) -> LeavePolicy:
    return LeavePolicy(
        id=None,
        code="TEST",
        name="Test Policy",
        annual_entitlement_days=annual_entitlement_days,
        cadence=cadence,
        prorate_on_hire=prorate_on_hire,
        carry_over_enabled=carry_over_enabled,
        carry_over_max_days=carry_over_max_days,
        carry_over_expires_on=carry_over_expires_on,
        gender_scope=None,
        marital_status_scope=None,
        is_active=True,
        is_system=False,
        is_deleted=False,
    )


class TestLeaveDaysInRange:
    def test_friday_to_monday_with_weekend_and_holiday(self) -> None:
        """Fri->Mon range with Sat holiday and weekend excluded = 2 workdays."""
        fri = date(2026, 9, 4)   # 2026-09-04 is a Friday
        mon = date(2026, 9, 7)   # 2026-09-07 is a Monday
        holiday = {date(2026, 9, 5)}  # Saturday is a holiday
        schedule = {date(2026, 9, 4), date(2026, 9, 7)}  # Fri+Mon are workdays

        result = leave_days_in_range(
            fri, mon,
            requested_hours=None,
            workday_hours=Decimal("8.0"),
            schedule=schedule,
            holidays=holiday,
        )
        assert result == Decimal("2")

    def test_requested_hours_partial_day(self) -> None:
        """requested_hours=3.0 / workday_hours=8.0 = 0.375."""
        result = leave_days_in_range(
            date(2026, 9, 4),
            date(2026, 9, 4),
            requested_hours=Decimal("3.0"),
            workday_hours=Decimal("8.0"),
        )
        assert result == Decimal("0.38")

    def test_requested_hours_zero_workday_hours(self) -> None:
        """Zero workday_hours returns 0 to avoid division by zero."""
        result = leave_days_in_range(
            date(2026, 9, 4),
            date(2026, 9, 4),
            requested_hours=Decimal("3.0"),
            workday_hours=Decimal("0"),
        )
        assert result == Decimal("0")

    def test_null_requested_hours_falls_back_to_monday_friday(self) -> None:
        """With no schedule/holidays, counts Mon-Fri within range."""
        # 2026-09-07 (Mon) to 2026-09-11 (Fri) = 5 weekdays
        result = leave_days_in_range(
            date(2026, 9, 7),
            date(2026, 9, 11),
            requested_hours=None,
        )
        assert result == Decimal("5.00")

    def test_end_before_start_raises(self) -> None:
        with pytest.raises(ValueError, match="date_end must be greater than or equal"):
            leave_days_in_range(
                date(2026, 9, 11),
                date(2026, 9, 7),
                requested_hours=None,
            )


class TestAccrueForYear:
    def test_annual_no_proration(self) -> None:
        policy = _policy(annual_entitlement_days=Decimal("15.00"), prorate_on_hire=False)
        result = calc.accrue_for_year(policy, hire_date=None, leave_year=2026)
        assert result == Decimal("15.00")

    def test_annual_with_proration_same_year(self) -> None:
        """Hire Sept 1 -> ~4 months left of 15 days = ~5.00."""
        policy = _policy(annual_entitlement_days=Decimal("15.00"), prorate_on_hire=True)
        hire_date = date(2026, 9, 1)
        result = calc.accrue_for_year(policy, hire_date=hire_date, leave_year=2026)
        # (365 - 244) / 365 * 15 ≈ 4.97 - 5.01 depending on exact day count
        assert result < Decimal("15.00")
        assert result >= Decimal("4.00")

    def test_annual_with_proration_different_year(self) -> None:
        """Hired in 2025, querying 2026 = full entitlement."""
        policy = _policy(annual_entitlement_days=Decimal("15.00"), prorate_on_hire=True)
        hire_date = date(2025, 1, 1)
        result = calc.accrue_for_year(policy, hire_date=hire_date, leave_year=2026)
        assert result == Decimal("15.00")

    def test_annual_proration_hire_after_year_end(self) -> None:
        """Hire Jan 2027, querying 2026 = 0."""
        policy = _policy(annual_entitlement_days=Decimal("15.00"), prorate_on_hire=True)
        hire_date = date(2027, 1, 1)
        result = calc.accrue_for_year(policy, hire_date=hire_date, leave_year=2026)
        assert result == Decimal("0")

    def test_monthly_returns_full_entitlement(self) -> None:
        """Monthly cadence always returns annual_entitlement_days."""
        policy = _policy(
            annual_entitlement_days=Decimal("12.00"),
            cadence=LeaveCadence.MONTHLY,
        )
        result = calc.accrue_for_year(policy, hire_date=date(2026, 6, 1), leave_year=2026)
        assert result == Decimal("12.00")


class TestMonthlyAccrualChunk:
    def test_annual_15_days(self) -> None:
        policy = _policy(annual_entitlement_days=Decimal("15.00"))
        assert calc.monthly_accrual_chunk(policy) == Decimal("1.25")

    def test_annual_12_days(self) -> None:
        policy = _policy(annual_entitlement_days=Decimal("12.00"))
        assert calc.monthly_accrual_chunk(policy) == Decimal("1.00")

    def test_zero_entitlement(self) -> None:
        policy = _policy(annual_entitlement_days=Decimal("0.00"))
        assert calc.monthly_accrual_chunk(policy) == Decimal("0")

    def test_rounds_to_two_dp(self) -> None:
        policy = _policy(annual_entitlement_days=Decimal("10.00"))
        # 10 / 12 = 0.8333... -> 0.83
        assert calc.monthly_accrual_chunk(policy) == Decimal("0.83")


class TestCarryoverAmount:
    def test_disabled_returns_zero(self) -> None:
        policy = _policy(carry_over_enabled=False)
        assert calc.carryover_amount(Decimal("5.00"), policy) == Decimal("0")

    def test_enabled_no_cap(self) -> None:
        policy = _policy(carry_over_enabled=True, carry_over_max_days=None)
        assert calc.carryover_amount(Decimal("5.00"), policy) == Decimal("5.00")

    def test_enabled_with_cap(self) -> None:
        policy = _policy(carry_over_enabled=True, carry_over_max_days=Decimal("3.00"))
        assert calc.carryover_amount(Decimal("5.00"), policy) == Decimal("3.00")

    def test_enabled_remaining_below_cap(self) -> None:
        policy = _policy(carry_over_enabled=True, carry_over_max_days=Decimal("3.00"))
        assert calc.carryover_amount(Decimal("2.00"), policy) == Decimal("2.00")

    def test_expired_returns_zero(self) -> None:
        policy = _policy(
            carry_over_enabled=True,
            carry_over_max_days=Decimal("3.00"),
            carry_over_expires_on=date(2026, 1, 1),
        )
        assert calc.carryover_amount(Decimal("2.00"), policy, now=date(2026, 12, 31)) == Decimal("0")

    def test_not_yet_expired_returns_amount(self) -> None:
        policy = _policy(
            carry_over_enabled=True,
            carry_over_max_days=Decimal("3.00"),
            carry_over_expires_on=date(2026, 12, 31),
        )
        assert calc.carryover_amount(Decimal("2.00"), policy, now=date(2026, 6, 1)) == Decimal("2.00")

    def test_zero_remaining(self) -> None:
        policy = _policy(carry_over_enabled=True, carry_over_max_days=None)
        assert calc.carryover_amount(Decimal("0.00"), policy) == Decimal("0")


class TestValidateStateTransition:
    def test_pending_to_approved(self) -> None:
        calc.validate_state_transition("pending", "approved")  # no error

    def test_pending_to_rejected(self) -> None:
        calc.validate_state_transition("pending", "rejected")  # no error

    def test_pending_to_cancelled(self) -> None:
        calc.validate_state_transition("pending", "cancelled")  # no error

    def test_approved_to_cancelled(self) -> None:
        calc.validate_state_transition("approved", "cancelled")  # no error

    def test_rejected_to_pending_illegal(self) -> None:
        with pytest.raises(LeaveStateError):
            calc.validate_state_transition("rejected", "pending")

    def test_rejected_to_approved_illegal(self) -> None:
        with pytest.raises(LeaveStateError):
            calc.validate_state_transition("rejected", "approved")

    def test_cancelled_to_approved_illegal(self) -> None:
        with pytest.raises(LeaveStateError):
            calc.validate_state_transition("cancelled", "approved")

    def test_approved_to_rejected_illegal(self) -> None:
        with pytest.raises(LeaveStateError):
            calc.validate_state_transition("approved", "rejected")

    def test_pending_to_pending_illegal(self) -> None:
        with pytest.raises(LeaveStateError):
            calc.validate_state_transition("pending", "pending")

    def test_unknown_current_illegal(self) -> None:
        with pytest.raises(LeaveStateError):
            calc.validate_state_transition("unknown", "approved")


class TestWorkdaySet:
    def test_excludes_weekends(self) -> None:
        holidays: set[date] = set()
        workdates, hours = calc.workday_set(
            shift_days_of_week=None,
            holidays=holidays,
            year=2026,
        )
        # 2026-09-05 is a Saturday, 2026-09-06 is a Sunday
        assert date(2026, 9, 5) not in workdates
        assert date(2026, 9, 6) not in workdates
        # 2026-09-04 is a Friday
        assert date(2026, 9, 4) in workdates

    def test_excludes_holidays(self) -> None:
        holidays = {date(2026, 9, 7)}  # Monday
        workdates, hours = calc.workday_set(
            shift_days_of_week=None,
            holidays=holidays,
            year=2026,
        )
        assert date(2026, 9, 7) not in workdates

    def test_custom_shift_days(self) -> None:
        """Shift with 6-day workweek (Mon-Sat)."""
        holidays: set[date] = set()
        workdates, hours = calc.workday_set(
            shift_days_of_week=["1", "2", "3", "4", "5", "6"],  # Mon-Sat
            holidays=holidays,
            year=2026,
        )
        assert date(2026, 9, 5) in workdates   # Saturday IS a workday in 6-day week
        assert date(2026, 9, 6) not in workdates  # Sunday is NOT a workday

    def test_returns_company_default_hours(self) -> None:
        holidays: set[date] = set()
        _, hours = calc.workday_set(
            shift_days_of_week=None,
            holidays=holidays,
            year=2026,
            company_default_hours=Decimal("9.0"),
        )
        assert hours == Decimal("9.0")

    def test_empty_year_no_days(self) -> None:
        holidays: set[date] = set()
        workdates, _ = calc.workday_set(
            shift_days_of_week=["6", "7"],  # only Sat, Sun
            holidays=holidays,
            year=2026,
        )
        # 52 Saturdays + 52 Sundays = 104 weekend workdays in 2026
        assert len(workdates) == 104
