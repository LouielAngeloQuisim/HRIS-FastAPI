"""The migration-seeded employer schedule matches SSS Circular 2024-006."""

from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.payroll.calc import calculate_sss_employee_share, calculate_sss_employer_share
from app.payroll.models import SSSBracket


def test_official_employer_schedule_has_all_61_effective_bands(db: Session) -> None:
    rows = db.exec(
        select(SSSBracket).where(
            SSSBracket.effective_date == date(2025, 1, 1),
            SSSBracket.is_active.is_(True),  # type: ignore[attr-defined]
            SSSBracket.is_deleted.is_(False),  # type: ignore[attr-defined]
        )
    ).all()

    assert len(rows) == 61
    assert rows[0].compensation_min == Decimal("0.01")
    assert rows[0].compensation_max == Decimal("5249.99")
    assert rows[-1].compensation_min == Decimal("34750.00")
    assert rows[-1].compensation_max is None


def test_official_schedule_boundaries_and_mpf_shares(db: Session) -> None:
    # Circular 2024-006: below ₱5,250 maps to ₱5,000 MSC; ₱5,250
    # maps to ₱5,500 MSC. EC is employer-only.
    assert calculate_sss_employee_share(db, Decimal("5249.99"), "2025-01-01") == Decimal("250.00")
    assert calculate_sss_employer_share(db, Decimal("5249.99"), "2025-01-01") == Decimal("510.00")
    assert calculate_sss_employee_share(db, Decimal("5250.00"), "2025-01-01") == Decimal("275.00")

    # ₱26,000 compensation maps to ₱20,000 regular MSC + ₱6,000 MPF.
    assert calculate_sss_employee_share(db, Decimal("26000.00"), "2025-01-01") == Decimal("1300.00")
    assert calculate_sss_employer_share(db, Decimal("26000.00"), "2025-01-01") == Decimal("2630.00")

    # At the ₱35,000 cap, employee/employer shares include MPF and employer EC.
    assert calculate_sss_employee_share(db, Decimal("99999.00"), "2025-01-01") == Decimal("1750.00")
    assert calculate_sss_employer_share(db, Decimal("99999.00"), "2025-01-01") == Decimal("3530.00")
