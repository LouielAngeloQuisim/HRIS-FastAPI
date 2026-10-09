"""Seeded PhilHealth and Pag-IBIG tables follow published schedules."""

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.payroll.calc import (
    StatutoryScheduleUnavailable,
    calculate_pagibig_employee_share,
    calculate_pagibig_employer_share,
    calculate_philhealth_employee_share,
    calculate_philhealth_employer_share,
)
from app.payroll.models import PagIBIGBracket, PhilHealthBracket
from app.payroll.routes import _statutory_schedule_errors


def test_seeded_philhealth_and_pagibig_schedules_are_complete(db: Session) -> None:
    philhealth = db.exec(
        select(PhilHealthBracket).where(
            PhilHealthBracket.effective_date.in_([date(2025, 1, 1), date(2026, 1, 1)]),
            PhilHealthBracket.is_active.is_(True),  # type: ignore[attr-defined]
            PhilHealthBracket.is_deleted.is_(False),  # type: ignore[attr-defined]
        )
    ).all()
    pagibig = db.exec(
        select(PagIBIGBracket).where(
            PagIBIGBracket.effective_date == date(2024, 2, 1),
            PagIBIGBracket.is_active.is_(True),  # type: ignore[attr-defined]
            PagIBIGBracket.is_deleted.is_(False),  # type: ignore[attr-defined]
        )
    ).all()

    assert {row.effective_date for row in philhealth} == {
        date(2025, 1, 1), date(2026, 1, 1)
    }
    assert len(philhealth) == 2
    assert all(
        (row.salary_min, row.salary_max, row.rate, row.employee_share, row.employer_share)
        == (
            Decimal("10000.00"), Decimal("100000.00"), Decimal("5.000"),
            Decimal("2.500"), Decimal("2.500"),
        )
        for row in philhealth
    )
    assert len(pagibig) == 2
    assert [(row.salary_min, row.salary_max, row.employee_rate, row.employer_rate) for row in pagibig] == [
        (Decimal("0.01"), Decimal("1500.00"), Decimal("1.000"), Decimal("2.000")),
        (Decimal("1500.01"), Decimal("10000.00"), Decimal("2.000"), Decimal("2.000")),
    ]


def test_statutory_calculators_apply_published_floors_caps_and_rates(db: Session) -> None:
    # PhilHealth uses fixed monthly basic salary, 5% split equally, clamped
    # to the published ₱10,000 floor and ₱100,000 ceiling.
    assert calculate_philhealth_employee_share(db, Decimal("9000"), "2025-01-01") == Decimal("250.00")
    assert calculate_philhealth_employer_share(db, Decimal("26000"), "2025-01-01") == Decimal("650.00")
    assert calculate_philhealth_employee_share(db, Decimal("120000"), "2025-01-01") == Decimal("2500.00")
    # Advisory 2026-0042 reaffirms the 5% rate effective since January 2025;
    # Circular 2020-0005 and Advisory 2025-0002 establish employer treatment.
    assert calculate_philhealth_employee_share(db, Decimal("26000"), "2026-01-01") == Decimal("650.00")
    assert calculate_philhealth_employer_share(db, Decimal("26000"), "2026-01-01") == Decimal("650.00")

    # Pag-IBIG Circular 460: employee 1% through ₱1,500, then 2%; employer
    # 2%; both shares use the ₱10,000 MFS ceiling.
    assert calculate_pagibig_employee_share(db, Decimal("1500"), "2024-02-01") == Decimal("15.00")
    assert calculate_pagibig_employer_share(db, Decimal("1500"), "2024-02-01") == Decimal("30.00")
    assert calculate_pagibig_employee_share(db, Decimal("1500.01"), "2024-02-01") == Decimal("30.00")
    assert calculate_pagibig_employee_share(db, Decimal("26000"), "2024-02-01") == Decimal("200.00")
    assert calculate_pagibig_employer_share(db, Decimal("26000"), "2024-02-01") == Decimal("200.00")


def test_philhealth_does_not_carry_a_schedule_into_an_unconfigured_year(
    db: Session,
) -> None:
    # Other payroll tests seed synthetic future schedules in the shared DB;
    # use a distant year outside those fixtures to isolate this guard check.
    with pytest.raises(StatutoryScheduleUnavailable, match="calendar year 2099"):
        calculate_philhealth_employee_share(db, Decimal("26000"), "2099-01-01")

    errors = _statutory_schedule_errors(db, date(2099, 1, 1))
    assert any("PhilHealth requires one active floor/ceiling schedule" in error for error in errors)
