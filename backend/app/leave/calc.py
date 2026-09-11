"""Pure functions for leave day-counting, accrual math, and carry-over (design doc §1.3).

All functions are deterministic and unit-testable without a DB.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.leave.models import LeaveCadence, LeavePolicy


def leave_days_in_range(
    start: date,
    end: date,
    *,
    requested_hours: Decimal | None,
    workday_hours: Decimal = Decimal("8.0"),
    schedule: set[date] | None = None,
    holidays: set[date] | None = None,
) -> Decimal:
    """Return the number of leave days in the range.

    - If ``requested_hours`` is provided, returns ``requested_hours / workday_hours``.
    - Otherwise counts only days in ``schedule`` that are not in ``holidays``.
    - Raises ``ValueError`` if ``end < start``.
    """
    if end < start:
        raise ValueError("date_end must be greater than or equal to date_start")

    if requested_hours is not None:
        if workday_hours <= 0:
            return Decimal("0")
        return (Decimal(str(requested_hours)) / workday_hours).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    if holidays is None:
        holidays = set()
    if schedule is None:
        schedule = _default_workdays(start.year)

    count = Decimal("0")
    current = start
    while current <= end:
        if current in schedule and current not in holidays:
            count += Decimal("1")
        current = _next_day(current)
    return count.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _default_workdays(year: int) -> set[date]:
    """Return Monday-Friday for the full year as a set of dates."""
    result: set[date] = set()
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            result.add(d)
        d = _next_day(d)
    return result


def _next_day(d: date) -> date:
    return date.fromordinal(d.toordinal() + 1)


def accrue_for_year(
    policy: LeavePolicy,
    hire_date: date | None,
    leave_year: int,
) -> Decimal:
    """Return granted days for the year.

    For ``annual`` cadence, returns ``annual_entitlement_days`` (prorated if
    ``prorate_on_hire`` is true and hire_date is within the year).
    For ``monthly`` cadence, returns the full annual entitlement (monthly
    accrual is applied separately via ``run_monthly_accrual``).
    """
    entitlement = policy.annual_entitlement_days

    if policy.cadence == LeaveCadence.MONTHLY:
        return entitlement

    if not policy.prorate_on_hire or hire_date is None:
        return entitlement

    if hire_date.year > leave_year:
        return Decimal("0")

    year_start = date(leave_year, 1, 1)
    year_end = date(leave_year, 12, 31)

    if hire_date < year_start:
        return entitlement

    if hire_date > year_end:
        return Decimal("0")

    total_days = (year_end - year_start).days + 1
    remaining_days = (year_end - hire_date).days + 1
    if remaining_days < 0:
        return Decimal("0")
    return (entitlement * Decimal(remaining_days) / Decimal(total_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def monthly_accrual_chunk(policy: LeavePolicy) -> Decimal:
    """Return the monthly accrual amount (annual / 12, rounded to 2 dp)."""
    if policy.annual_entitlement_days <= 0:
        return Decimal("0")
    return (policy.annual_entitlement_days / Decimal("12")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def carryover_amount(
    remaining: Decimal,
    policy: LeavePolicy,
    now: date | None = None,
) -> Decimal:
    """Return the number of days to carry over.

    Returns 0 if carry_over_enabled is false. Otherwise returns
    min(remaining, carry_over_max_days), subject to expiry.
    """
    if not policy.carry_over_enabled:
        return Decimal("0")

    cap = policy.carry_over_max_days
    if cap is None:
        amount = remaining
    else:
        amount = min(remaining, cap)

    if amount <= 0:
        return Decimal("0")

    if policy.carry_over_expires_on and now is not None:
        if now > policy.carry_over_expires_on:
            return Decimal("0")

    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LeaveStateError(ValueError):
    """Raised on an illegal leave status transition."""


def validate_state_transition(current: str, target: str) -> None:
    """Raise ``LeaveStateError`` if the transition is not allowed.

    Allowed transitions:
      - pending  -> approved, rejected, cancelled
      - approved  -> cancelled
      - rejected  -> (terminal)
      - cancelled -> (terminal)
    """
    allowed: dict[str, set[str]] = {
        "pending": {"approved", "rejected", "cancelled"},
        "approved": {"cancelled"},
        "rejected": set(),
        "cancelled": set(),
    }
    if target not in allowed.get(current, set()):
        raise LeaveStateError(f"Cannot transition from {current} to {target}")


def workday_set(
    shift_days_of_week: list[str] | None,
    holidays: set[date],
    year: int,
    company_default_hours: Decimal = Decimal("8.0"),
) -> tuple[set[date], Decimal]:
    """Derive the set of work dates and workday_hours for an employee.

    - If ``shift_days_of_week`` is provided, use those (1=Mon ... 7=Sun).
    - Otherwise return Monday-Friday for the year.
    Returns (workdate_set, workday_hours).
    """
    workdates: set[date] = set()
    d = date(year, 1, 1)
    year_end = date(year, 12, 31)

    if shift_days_of_week:
        weekday_nums = {(int(x) - 1) % 7 for x in shift_days_of_week}
    else:
        weekday_nums = {0, 1, 2, 3, 4}

    while d <= year_end:
        if d.weekday() in weekday_nums and d not in holidays:
            workdates.add(d)
        d = _next_day(d)

    return workdates, company_default_hours
