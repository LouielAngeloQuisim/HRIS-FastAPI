"""Pure attendance-to-earnings calculation primitives.

This module intentionally does not apply statutory deductions or finalize a
payroll run. Callers must supply the effective salary and reviewed attendance
for every scheduled work date; incomplete input is an error, never an implicit
zero or template-shift fallback.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Literal


@dataclass(frozen=True)
class AttendancePayDay:
    work_date: date
    pay_type: Literal["hourly", "daily", "monthly"]
    basic_rate: Decimal
    overtime_rate: Decimal
    scheduled_minutes: int
    worked_minutes: int
    overtime_eligible_minutes: int = 0
    overtime_approved_minutes: int | None = None
    # Configured total-pay factors for holiday work. A multiplier of 2.0 means
    # total regular-time pay is 2x base; because normal earnings already include
    # the base portion, only the premium is added here. Holiday overtime factors
    # replace the general overtime factor for that day.
    holiday_regular_multiplier: Decimal | None = None
    holiday_overtime_multiplier: Decimal | None = None
    holiday_regular_base: Decimal | None = None
    rest_day_regular_multiplier: Decimal | None = None
    rest_day_overtime_multiplier: Decimal | None = None
    rest_day_regular_base: Decimal | None = None
    night_regular_minutes: int = 0
    night_overtime_minutes: int = 0
    night_differential_rate: Decimal | None = None
    raw_late_minutes: int = 0
    grace_minutes: int = 0
    paid_absence: bool = False
    absence: bool = False
    paid_leave_minutes: int = 0
    unpaid_leave_minutes: int = 0
    monthly_period_fraction: Decimal | None = None
    monthly_period_scheduled_days: int | None = None
    monthly_salary_proration: Literal[
        "scheduled_workday_fraction", "monthly_divisor_per_workday"
    ] = "scheduled_workday_fraction"
    monthly_salary_base_eligible: bool = True


@dataclass(frozen=True)
class EarningsResult:
    regular: Decimal
    overtime: Decimal
    holiday_premium: Decimal
    rest_day_premium: Decimal
    night_differential: Decimal
    attendance_deduction: Decimal
    short_time_deduction: Decimal
    payable_days: int
    worked_minutes: int


class CalculationBlocker(ValueError):
    """Raised when payroll input cannot support an explainable amount."""


CENT = Decimal("0.01")


def calculate_attendance_earnings(
    days: list[AttendancePayDay],
    *,
    monthly_divisor: Decimal,
    daily_partial_work: Literal["full_day", "pro_rated", "hours_based"],
    overtime_multiplier: Decimal,
    monthly_partial_work: Literal["deduct_after_grace", "no_deduction"] | None = None,
    rounding: str = "half_up",
) -> EarningsResult:
    """Calculate regular and approved-overtime earnings from reviewed daily rows.

    ``days`` contains only configured scheduled work dates. An unmarked row
    with zero minutes is ambiguous and blocks; callers must explicitly classify
    it as absence or paid leave. Monthly salaries are prorated by the confirmed
    divisor only for unpaid absence. Monthly base pay is apportioned across the
    scheduled workdays in the pay period, then prorated by the configured
    period fraction. Effective salary changes are represented as separate
    daily inputs, so each date uses its own rate.
    """
    if monthly_divisor <= 0:
        raise CalculationBlocker("A positive confirmed monthly divisor is required")
    if overtime_multiplier < 0:
        raise CalculationBlocker("Overtime multiplier cannot be negative")
    if monthly_partial_work not in {None, "deduct_after_grace", "no_deduction"}:
        raise CalculationBlocker("Unsupported monthly partial-work rule")
    if rounding not in {"half_up", "half_even", "down"}:
        raise CalculationBlocker("Unsupported payroll rounding mode")
    rounding_mode = {
        "half_up": ROUND_HALF_UP,
        "half_even": ROUND_HALF_EVEN,
        "down": ROUND_DOWN,
    }[rounding]

    regular = Decimal("0")
    overtime = Decimal("0")
    holiday_premium = Decimal("0")
    rest_day_premium = Decimal("0")
    night_differential = Decimal("0")
    deduction = Decimal("0")
    short_time_deduction = Decimal("0")
    payable_days = 0
    total_worked = 0
    seen_dates: set[date] = set()
    for day in sorted(days, key=lambda item: item.work_date):
        if day.work_date in seen_dates:
            raise CalculationBlocker(f"Duplicate attendance date {day.work_date}")
        seen_dates.add(day.work_date)
        if day.basic_rate < 0 or day.overtime_rate < 0:
            raise CalculationBlocker(f"Negative compensation rate on {day.work_date}")
        if day.scheduled_minutes <= 0 or day.worked_minutes < 0:
            raise CalculationBlocker(f"Invalid scheduled/worked minutes on {day.work_date}")
        if day.worked_minutes > 24 * 60:
            raise CalculationBlocker(f"Worked minutes exceed one day on {day.work_date}")
        if day.absence and day.paid_absence:
            raise CalculationBlocker(f"Date {day.work_date} cannot be both absence and paid leave")
        if day.paid_leave_minutes < 0 or day.unpaid_leave_minutes < 0:
            raise CalculationBlocker(f"Partial leave minutes cannot be negative on {day.work_date}")
        if day.paid_leave_minutes and day.unpaid_leave_minutes:
            raise CalculationBlocker(f"Paid and unpaid partial leave overlap on {day.work_date}")
        leave_minutes = day.paid_leave_minutes + day.unpaid_leave_minutes
        if leave_minutes > day.scheduled_minutes:
            raise CalculationBlocker(f"Partial leave exceeds scheduled minutes on {day.work_date}")
        if leave_minutes and (day.absence or day.paid_absence):
            raise CalculationBlocker(f"Partial leave conflicts with a full-day disposition on {day.work_date}")
        if leave_minutes and day.worked_minutes + leave_minutes > day.scheduled_minutes:
            raise CalculationBlocker(f"Worked and leave minutes exceed the shift on {day.work_date}")
        if not day.absence and not day.paid_absence and day.worked_minutes == 0:
            raise CalculationBlocker(f"Attendance disposition is missing for {day.work_date}")
        if day.overtime_eligible_minutes < 0 or day.overtime_eligible_minutes > day.worked_minutes:
            raise CalculationBlocker(f"Invalid eligible overtime minutes on {day.work_date}")
        if day.raw_late_minutes < 0 or day.grace_minutes < 0:
            raise CalculationBlocker(f"Invalid lateness/grace minutes on {day.work_date}")
        if day.night_regular_minutes < 0 or day.night_overtime_minutes < 0:
            raise CalculationBlocker(f"Invalid night-work minutes on {day.work_date}")
        if day.night_regular_minutes + day.night_overtime_minutes > day.worked_minutes:
            raise CalculationBlocker(f"Night-work minutes exceed attendance on {day.work_date}")
        if day.night_regular_minutes or day.night_overtime_minutes:
            if day.night_differential_rate is None or day.night_differential_rate < Decimal("0.10"):
                raise CalculationBlocker(
                    f"Night differential must be configured at no less than 10% on {day.work_date}"
                )
        if day.overtime_eligible_minutes and day.overtime_approved_minutes is None:
            raise CalculationBlocker(f"Overtime decision is pending on {day.work_date}")
        approved = day.overtime_approved_minutes or 0
        if approved < 0 or approved > day.overtime_eligible_minutes:
            raise CalculationBlocker(f"Approved overtime exceeds eligible minutes on {day.work_date}")
        for label, factor in (
            ("regular", day.holiday_regular_multiplier),
            ("overtime", day.holiday_overtime_multiplier),
        ):
            if factor is not None and factor < 1:
                raise CalculationBlocker(
                    f"Holiday {label} multiplier must be at least 1 on {day.work_date}"
                )
        for label, factor, minimum in (
            ("regular", day.rest_day_regular_multiplier, Decimal("1.30")),
            ("overtime", day.rest_day_overtime_multiplier, Decimal("1.69")),
        ):
            if factor is not None and (not factor.is_finite() or factor < minimum):
                raise CalculationBlocker(
                    f"Rest-day {label} multiplier must be at least {minimum} on {day.work_date}"
                )

        regular_before = regular
        if day.pay_type == "hourly":
            # The overtime line is paid separately below. Cap regular hourly
            # earnings at the scheduled shift so approved overtime is not also
            # paid a second time at the base rate.
            payable_minutes = (
                day.scheduled_minutes
                if day.paid_absence
                else min(day.worked_minutes + day.paid_leave_minutes, day.scheduled_minutes)
            )
            regular += day.basic_rate * Decimal(payable_minutes) / Decimal(60)
            if day.paid_absence:
                payable_days += 1
        elif day.pay_type == "daily":
            if day.paid_absence:
                regular += day.basic_rate
                payable_days += 1
            elif day.absence:
                # Daily workers earn only for payable days; the day is already
                # absent from gross earnings, so an extra deduction would double-count it.
                pass
            elif day.rest_day_regular_multiplier is not None:
                # Rest-day work is paid by actual hours, even if the normal
                # scheduled-day partial-work rule pays only a full shift.
                regular += (
                    day.basic_rate
                    * Decimal(min(day.worked_minutes, day.scheduled_minutes))
                    / Decimal(day.scheduled_minutes)
                )
                payable_days += 1
            elif daily_partial_work == "full_day":
                if day.worked_minutes + day.paid_leave_minutes >= day.scheduled_minutes:
                    regular += day.basic_rate
                    payable_days += 1
            elif daily_partial_work == "pro_rated":
                regular += day.basic_rate * min(day.worked_minutes + day.paid_leave_minutes, day.scheduled_minutes) / Decimal(day.scheduled_minutes)
                payable_days += 1
            else:  # hours_based: daily rate is normalized to scheduled hours.
                regular += day.basic_rate * Decimal(min(day.worked_minutes + day.paid_leave_minutes, day.scheduled_minutes)) / Decimal(day.scheduled_minutes)
                payable_days += 1
        elif day.pay_type == "monthly":
            daily_rate = day.basic_rate / monthly_divisor
            if not day.monthly_salary_base_eligible:
                pass
            elif day.monthly_salary_proration == "scheduled_workday_fraction":
                if (
                    day.monthly_period_fraction is None
                    or day.monthly_period_fraction <= 0
                    or day.monthly_period_fraction > 1
                    or day.monthly_period_scheduled_days is None
                    or day.monthly_period_scheduled_days <= 0
                ):
                    raise CalculationBlocker(
                        f"Monthly salary period entitlement is missing or invalid on {day.work_date}"
                    )
                # The monthly salary base is fixed for the pay period and is
                # apportioned over all scheduled workdays. Partial employment
                # and effective-dated rates therefore prorate transparently.
                regular += (
                    day.basic_rate
                    * day.monthly_period_fraction
                    / Decimal(day.monthly_period_scheduled_days)
                )
            elif day.monthly_salary_proration == "monthly_divisor_per_workday":
                regular += daily_rate
            else:
                raise CalculationBlocker(
                    f"Unsupported monthly salary proration on {day.work_date}"
                )
            if day.absence:
                if day.monthly_salary_base_eligible:
                    deduction += daily_rate
            else:
                if day.monthly_salary_base_eligible:
                    payable_days += 1
                    if day.unpaid_leave_minutes:
                        deduction += (
                            daily_rate
                            * Decimal(day.unpaid_leave_minutes)
                            / Decimal(day.scheduled_minutes)
                        )
                shortfall = (
                    max(
                        0,
                        day.scheduled_minutes
                        - day.worked_minutes
                        - day.paid_leave_minutes
                        - day.unpaid_leave_minutes,
                    )
                    if day.monthly_salary_base_eligible and not day.paid_absence
                    else 0
                )
                if shortfall:
                    if monthly_partial_work is None:
                        raise CalculationBlocker(
                            f"Monthly partial-work policy is missing on {day.work_date}"
                        )
                    if monthly_partial_work == "deduct_after_grace":
                        lateness_grace = min(day.raw_late_minutes, day.grace_minutes)
                        deductible_minutes = max(0, shortfall - lateness_grace)
                        short_time_amount = (
                            daily_rate
                            * Decimal(deductible_minutes)
                            / Decimal(day.scheduled_minutes)
                        )
                        deduction += short_time_amount
                        short_time_deduction += short_time_amount
        else:
            raise CalculationBlocker(f"Unsupported salary basis on {day.work_date}")

        if (
            day.holiday_regular_multiplier is not None
            and day.worked_minutes > 0
            and not day.absence
            and not day.paid_absence
        ):
            premium_base = (
                day.holiday_regular_base
                if day.holiday_regular_base is not None
                else regular - regular_before
            )
            if premium_base < 0:
                raise CalculationBlocker(
                    f"Holiday regular base cannot be negative on {day.work_date}"
                )
            holiday_premium += premium_base * (
                day.holiday_regular_multiplier - Decimal("1")
            )

        if (
            day.rest_day_regular_multiplier is not None
            and day.worked_minutes > 0
            and not day.absence
            and not day.paid_absence
        ):
            rest_day_base = (
                day.rest_day_regular_base
                if day.rest_day_regular_base is not None
                else regular - regular_before
            )
            if rest_day_base < 0:
                raise CalculationBlocker(
                    f"Rest-day regular base cannot be negative on {day.work_date}"
                )
            rest_day_premium += rest_day_base * (
                day.rest_day_regular_multiplier - Decimal("1")
            )

        total_worked += day.worked_minutes
        effective_overtime_multiplier = (
            day.holiday_overtime_multiplier
            if day.holiday_overtime_multiplier is not None
            else (
                day.rest_day_overtime_multiplier
                if day.rest_day_overtime_multiplier is not None
                else overtime_multiplier
            )
        )
        overtime += (
            day.overtime_rate
            * Decimal(approved)
            / Decimal(60)
            * effective_overtime_multiplier
        )
        if day.night_regular_minutes or day.night_overtime_minutes:
            assert day.night_differential_rate is not None
            if day.pay_type == "hourly":
                hourly_rate = day.basic_rate
            elif day.pay_type == "daily":
                hourly_rate = (
                    day.basic_rate * Decimal(60) / Decimal(day.scheduled_minutes)
                )
            else:
                hourly_rate = (
                    day.basic_rate
                    / monthly_divisor
                    * Decimal(60)
                    / Decimal(day.scheduled_minutes)
                )
            regular_factor = (
                day.holiday_regular_multiplier
                or day.rest_day_regular_multiplier
                or Decimal("1")
            )
            night_differential += (
                hourly_rate
                * Decimal(day.night_regular_minutes)
                / Decimal(60)
                * day.night_differential_rate
                * regular_factor
            )
            night_differential += (
                day.overtime_rate
                * Decimal(day.night_overtime_minutes)
                / Decimal(60)
                * day.night_differential_rate
                * effective_overtime_multiplier
            )

    def quantize(amount: Decimal) -> Decimal:
        return amount.quantize(CENT, rounding=rounding_mode)

    return EarningsResult(
        regular=quantize(regular),
        overtime=quantize(overtime),
        holiday_premium=quantize(holiday_premium),
        rest_day_premium=quantize(rest_day_premium),
        night_differential=quantize(night_differential),
        attendance_deduction=quantize(deduction),
        short_time_deduction=quantize(short_time_deduction),
        payable_days=payable_days,
        worked_minutes=total_worked,
    )
