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
    paid_absence: bool = False
    absence: bool = False


@dataclass(frozen=True)
class EarningsResult:
    regular: Decimal
    overtime: Decimal
    attendance_deduction: Decimal
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
    rounding: str = "half_up",
) -> EarningsResult:
    """Calculate regular and approved-overtime earnings from reviewed daily rows.

    ``days`` contains only configured scheduled work dates. An unmarked row
    with zero minutes is ambiguous and blocks; callers must explicitly classify
    it as absence or paid leave. Monthly salaries are prorated by the confirmed
    divisor only for unpaid absence. Effective salary changes are represented
    as separate daily inputs, so each date uses its own rate.
    """
    if monthly_divisor <= 0:
        raise CalculationBlocker("A positive confirmed monthly divisor is required")
    if overtime_multiplier < 0:
        raise CalculationBlocker("Overtime multiplier cannot be negative")
    if rounding not in {"half_up", "half_even", "down"}:
        raise CalculationBlocker("Unsupported payroll rounding mode")
    rounding_mode = {
        "half_up": ROUND_HALF_UP,
        "half_even": ROUND_HALF_EVEN,
        "down": ROUND_DOWN,
    }[rounding]

    regular = Decimal("0")
    overtime = Decimal("0")
    deduction = Decimal("0")
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
        if not day.absence and not day.paid_absence and day.worked_minutes == 0:
            raise CalculationBlocker(f"Attendance disposition is missing for {day.work_date}")
        if day.overtime_eligible_minutes < 0 or day.overtime_eligible_minutes > day.worked_minutes:
            raise CalculationBlocker(f"Invalid eligible overtime minutes on {day.work_date}")
        if day.overtime_eligible_minutes and day.overtime_approved_minutes is None:
            raise CalculationBlocker(f"Overtime decision is pending on {day.work_date}")
        approved = day.overtime_approved_minutes or 0
        if approved < 0 or approved > day.overtime_eligible_minutes:
            raise CalculationBlocker(f"Approved overtime exceeds eligible minutes on {day.work_date}")

        if day.pay_type == "hourly":
            payable_minutes = day.scheduled_minutes if day.paid_absence else day.worked_minutes
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
            elif daily_partial_work == "full_day":
                if day.worked_minutes >= day.scheduled_minutes:
                    regular += day.basic_rate
                    payable_days += 1
            elif daily_partial_work == "pro_rated":
                regular += day.basic_rate * min(day.worked_minutes, day.scheduled_minutes) / Decimal(day.scheduled_minutes)
                payable_days += 1
            else:  # hours_based: daily rate is normalized to scheduled hours.
                regular += day.basic_rate * Decimal(min(day.worked_minutes, day.scheduled_minutes)) / Decimal(day.scheduled_minutes)
                payable_days += 1
        elif day.pay_type == "monthly":
            daily_rate = day.basic_rate / monthly_divisor
            # Accrue the scheduled-period base first; deduct unpaid absences
            # separately so an absent day is not subtracted twice.
            regular += daily_rate
            if day.absence:
                deduction += daily_rate
            else:
                payable_days += 1
        else:
            raise CalculationBlocker(f"Unsupported salary basis on {day.work_date}")

        total_worked += day.worked_minutes
        overtime += day.overtime_rate * Decimal(approved) / Decimal(60) * overtime_multiplier

    def quantize(amount: Decimal) -> Decimal:
        return amount.quantize(CENT, rounding=rounding_mode)

    return EarningsResult(
        regular=quantize(regular),
        overtime=quantize(overtime),
        attendance_deduction=quantize(deduction),
        payable_days=payable_days,
        worked_minutes=total_worked,
    )
