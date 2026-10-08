"""Night-shift work-minute allocation for Philippine payroll."""

from datetime import datetime, time, timedelta, tzinfo


class NightDifferentialInputError(ValueError):
    """Raised when actual night work or break timing cannot be proven."""


def _overlap_minutes(
    start: datetime, end: datetime, window_start: datetime, window_end: datetime
) -> int:
    overlap_start = max(start, window_start)
    overlap_end = min(end, window_end)
    if overlap_end <= overlap_start:
        return 0
    return int((overlap_end - overlap_start).total_seconds() // 60)


def _night_overlap_minutes(start: datetime, end: datetime, zone: tzinfo) -> int:
    if end <= start:
        return 0
    local_start = start.astimezone(zone)
    local_end = end.astimezone(zone)
    anchor = local_start.date() - timedelta(days=1)
    total = 0
    while anchor <= local_end.date():
        night_start = datetime.combine(anchor, time(22), tzinfo=zone)
        night_end = datetime.combine(anchor + timedelta(days=1), time(6), tzinfo=zone)
        total += _overlap_minutes(local_start, local_end, night_start, night_end)
        anchor += timedelta(days=1)
    return total


def allocate_night_work_minutes(
    intervals: list[tuple[datetime, datetime]],
    *,
    scheduled_minutes: int,
    expected_worked_minutes: int,
    approved_overtime_minutes: int,
    unpaid_break_minutes: int,
    zone: tzinfo,
) -> tuple[int, int]:
    """Allocate actual 22:00–06:00 minutes between regular and approved OT.

    The first ``scheduled_minutes`` of chronological worked intervals are
    regular; subsequent worked minutes are eligible OT, of which the first
    approved minutes are payable. Interval gaps represent non-work time.
    A legacy single punch with an automatic unpaid break cannot prove whether
    the break fell in the night window, so it fails closed when that window is
    crossed. New records can represent the break as an interval gap.
    """
    if scheduled_minutes <= 0 or expected_worked_minutes < 0:
        raise NightDifferentialInputError("Scheduled and worked minutes are invalid.")
    if approved_overtime_minutes < 0 or unpaid_break_minutes < 0:
        raise NightDifferentialInputError("Approved overtime and break minutes cannot be negative.")
    ordered = sorted(intervals, key=lambda value: value[0])
    for start, end in ordered:
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            raise NightDifferentialInputError("Attendance intervals must be valid timezone-aware ranges.")
    if not any(_night_overlap_minutes(start, end, zone) for start, end in ordered):
        return 0, 0
    raw_minutes = sum(
        int((end - start).total_seconds() // 60) for start, end in ordered
    )
    break_deduction = unpaid_break_minutes if len(ordered) == 1 else 0
    worked_minutes = raw_minutes - break_deduction
    if worked_minutes != expected_worked_minutes:
        raise NightDifferentialInputError(
            "Attendance interval minutes do not match the reviewed daily total."
        )
    eligible_overtime = max(0, worked_minutes - scheduled_minutes)
    if approved_overtime_minutes > eligible_overtime:
        raise NightDifferentialInputError(
            "Approved overtime exceeds overtime minutes supported by the intervals."
        )
    if len(ordered) == 1 and unpaid_break_minutes and _night_overlap_minutes(
        ordered[0][0], ordered[0][1], zone
    ):
        raise NightDifferentialInputError(
            "Split the attendance interval around the unpaid break to calculate night differential accurately."
        )

    regular_night = 0
    overtime_night = 0
    regular_remaining = scheduled_minutes
    approved_ot_remaining = approved_overtime_minutes
    for start, end in ordered:
        interval_minutes = int((end - start).total_seconds() // 60)
        if len(ordered) == 1 and unpaid_break_minutes:
            interval_minutes -= unpaid_break_minutes
        if interval_minutes <= 0:
            continue
        local_start = start.astimezone(zone)
        regular_minutes = min(interval_minutes, regular_remaining)
        if regular_minutes:
            regular_end = local_start + timedelta(minutes=regular_minutes)
            regular_night += _night_overlap_minutes(local_start, regular_end, zone)
            regular_remaining -= regular_minutes
            local_start = regular_end
        overtime_minutes = interval_minutes - regular_minutes
        payable_overtime = min(overtime_minutes, approved_ot_remaining)
        if payable_overtime:
            overtime_end = local_start + timedelta(minutes=payable_overtime)
            overtime_night += _night_overlap_minutes(local_start, overtime_end, zone)
            approved_ot_remaining -= payable_overtime
    return regular_night, overtime_night
