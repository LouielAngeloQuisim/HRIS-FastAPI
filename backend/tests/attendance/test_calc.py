"""Phase 2A test set A — pure calc unit tests (design §4.1).

Hand-defined expected values, no DB. Each scenario asserts exact ``DtrResult``
integers. Scenario table + boundary table from the design doc are both covered.
"""

from datetime import date, datetime

import pytest

from app.attendance import calc


def _dt(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 8, day, hour, minute)


# A Monday so is_scheduled_workday defaults hold without specifying days_of_week.
MON = 4  # 2026-08-04 is a Monday


# --- Scenario table ----------------------------------------------------------------
class TestScenarioTable:
    def test_on_time(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 17, 0), shift)
        assert r == calc.DtrResult(rendered_minutes=480, late_minutes=0, undertime_minutes=0, overtime_minutes=0)

    def test_late(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 30), _dt(MON, 17, 0), shift)
        assert r == calc.DtrResult(rendered_minutes=450, late_minutes=30, undertime_minutes=30, overtime_minutes=0)

    def test_early_out_undertime(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 16, 0), shift)
        assert r == calc.DtrResult(rendered_minutes=420, late_minutes=0, undertime_minutes=60, overtime_minutes=0)

    def test_overtime(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 19, 0), shift)
        assert r == calc.DtrResult(rendered_minutes=600, late_minutes=0, undertime_minutes=0, overtime_minutes=120)

    def test_late_plus_overtime_same_day(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 30), _dt(MON, 18, 0), shift)
        assert r == calc.DtrResult(rendered_minutes=510, late_minutes=30, undertime_minutes=0, overtime_minutes=30)

    def test_configurable_lunch(self) -> None:
        """A 30-min lunch must produce different rendered minutes than 60-min.

        Proves the hardcoded-lunch bug is fixed: the active lunch duration is used.
        """
        shift = calc.ShiftParams(
            start_minutes=480, end_minutes=1020, lunch_minutes=30,
            shift_minutes=450, days_of_week=(1, 2, 3, 4, 5),
        )
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 17, 0), shift)
        # gross 540 - 30 lunch = 510 rendered (NOT 480 as a hardcoded-60 would give)
        assert r.rendered_minutes == 510
        assert r.overtime_minutes == 60  # 510 - 450 baseline

    def test_default_shift_unassigned(self) -> None:
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 17, 0), calc.DEFAULT_SHIFT)
        assert r == calc.DtrResult(rendered_minutes=480, late_minutes=0, undertime_minutes=0, overtime_minutes=0)

    def test_straight_time_variant(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 17, 0), shift, straight_time=True)
        # lunch added back to rendered (480 + 60 = 540); OT still on lunch-subtracted base (0)
        assert r.rendered_minutes == 540
        assert r.overtime_minutes == 0

    def test_absent_row_values(self) -> None:
        r = calc.absent_row_values()
        assert r == calc.DtrResult(rendered_minutes=0, late_minutes=0, undertime_minutes=0, overtime_minutes=0)

    def test_scheduled_workday(self) -> None:
        shift = calc.DEFAULT_SHIFT  # Mon-Fri
        assert calc.is_scheduled_workday(date(2026, 8, 3), shift) is True   # Monday
        assert calc.is_scheduled_workday(date(2026, 8, 8), shift) is False  # Saturday


# --- Boundary tests ----------------------------------------------------------------
class TestBoundaries:
    def test_login_exactly_at_shift_start(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 17, 0), shift)
        assert r.late_minutes == 0

    def test_login_one_minute_late(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 1), _dt(MON, 17, 0), shift)
        assert r.late_minutes == 1

    def test_rendered_exactly_equals_shift_minutes(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 17, 0), shift)
        assert r.overtime_minutes == 0
        assert r.undertime_minutes == 0

    def test_zero_render_day(self) -> None:
        shift = calc.DEFAULT_SHIFT
        r = calc.compute_dtr(_dt(MON, 8, 0), _dt(MON, 8, 0), shift)
        assert r.rendered_minutes == 0
        assert r.undertime_minutes == shift.shift_minutes

    def test_grace_period_within(self) -> None:
        shift = calc.ShiftParams(
            start_minutes=480, end_minutes=1020, lunch_minutes=60,
            shift_minutes=480, grace_minutes=10, days_of_week=(1, 2, 3, 4, 5),
        )
        r = calc.compute_dtr(_dt(MON, 8, 7), _dt(MON, 17, 0), shift)
        assert r.late_minutes == 0

    def test_grace_period_exceeded(self) -> None:
        shift = calc.ShiftParams(
            start_minutes=480, end_minutes=1020, lunch_minutes=60,
            shift_minutes=480, grace_minutes=10, days_of_week=(1, 2, 3, 4, 5),
        )
        r = calc.compute_dtr(_dt(MON, 8, 12), _dt(MON, 17, 0), shift)
        assert r.late_minutes == 2

    def test_overnight_shift(self) -> None:
        """22:00 -> 06:00 next day = 8h gross; logout on the next calendar day.

        The shift itself starts at 22:00 (1320), so a 22:00 login is on time
        (late=0), and diff_minutes handles the midnight crossing.
        """
        shift = calc.ShiftParams(
            start_minutes=1320, end_minutes=360, lunch_minutes=60,
            shift_minutes=480, days_of_week=(1, 2, 3, 4, 5),
        )
        r = calc.compute_dtr(_dt(MON, 22, 0), _dt(MON + 1, 6, 0), shift)
        assert r.rendered_minutes == 420  # 480 gross - 60 lunch
        assert r.overtime_minutes == 0
        assert r.late_minutes == 0  # logged in exactly at shift start


# --- Pure-function helpers ---------------------------------------------------------
class TestHelpers:
    def test_minutes_since_midnight(self) -> None:
        assert calc.minutes_since_midnight(datetime(2026, 1, 1, 8, 30)) == 510

    def test_parse_time_to_minutes(self) -> None:
        assert calc.parse_time_to_minutes("08:30") == 510
        assert calc.parse_time_to_minutes("00:00") == 0
        assert calc.parse_time_to_minutes("23:59") == 1439

    def test_diff_minutes_overnight(self) -> None:
        assert calc.diff_minutes(_dt(MON, 22, 0), _dt(MON + 1, 6, 0)) == 480
