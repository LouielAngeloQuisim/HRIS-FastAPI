"""Attendance/DTR pure time-math (design §2).

No DB access, no FastAPI deps — deterministic functions fully unit-testable in
isolation. The API/DB layers call these; they never embed math themselves.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class ShiftParams:
    """Decoupled input built from a Shift row (or DEFAULT_SHIFT) by the service."""

    start_minutes: int
    end_minutes: int
    lunch_minutes: int
    shift_minutes: int
    grace_minutes: int = 0
    days_of_week: tuple[int, ...] = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class DtrResult:
    rendered_minutes: int
    late_minutes: int
    undertime_minutes: int
    overtime_minutes: int


# No shift assigned: legacy DEFAULT_SHIFT_MINUTES=480, HARDCODED_LUNCH_DEDUCT=60.
DEFAULT_SHIFT = ShiftParams(
    start_minutes=480,
    end_minutes=1020,
    lunch_minutes=60,
    shift_minutes=480,
    grace_minutes=0,
    days_of_week=(1, 2, 3, 4, 5),
)


def minutes_since_midnight(dt: datetime) -> int:
    """Whole minutes since midnight of the datetime's wall-clock time."""
    return dt.hour * 60 + dt.minute


def parse_time_to_minutes(hhmm: str) -> int:
    """'HH:MM' -> minutes since midnight. Builds ShiftParams from a Shift row."""
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def diff_minutes(login: datetime, logout: datetime) -> int:
    """Absolute whole-minute difference. Handles overnight (logout next calendar day)."""
    return int((logout - login).total_seconds() // 60)


def compute_dtr(
    login: datetime,
    logout: datetime,
    shift: ShiftParams,
    *,
    straight_time: bool = False,
) -> DtrResult:
    """The core formula (design §2.3)."""
    gross = diff_minutes(login, logout)
    base = max(0, gross - shift.lunch_minutes)
    late = max(
        0,
        minutes_since_midnight(login) - shift.start_minutes - shift.grace_minutes,
    )
    if straight_time:
        rendered = base + shift.lunch_minutes
    else:
        rendered = base
    undertime = max(0, shift.shift_minutes - rendered)
    overtime = max(0, base - shift.shift_minutes)
    return DtrResult(
        rendered_minutes=rendered,
        late_minutes=late,
        undertime_minutes=undertime,
        overtime_minutes=overtime,
    )


def is_scheduled_workday(d: date, shift: ShiftParams) -> bool:
    """True if ISO weekday of `d` is in shift.days_of_week. Drives absence generation."""
    return d.isoweekday() in shift.days_of_week


def absent_row_values() -> DtrResult:
    """rendered/late/undertime/overtime = 0. Used by the absence-row builder."""
    return DtrResult(
        rendered_minutes=0,
        late_minutes=0,
        undertime_minutes=0,
        overtime_minutes=0,
    )
