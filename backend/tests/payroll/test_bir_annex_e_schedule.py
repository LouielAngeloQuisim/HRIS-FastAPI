"""Regression checks for the migration-seeded BIR Annex E schedule."""

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.payroll.calc import calculate_bir_tax
from app.payroll.models import BIRBracket

ANNEX_E = "https://bir-cdn.bir.gov.ph/local/pdf/Annex%20E%20RR%2011-2018.pdf"


def test_migration_seeds_source_attributed_annex_e_for_all_periods(db: Session) -> None:
    rows = db.exec(
        select(BIRBracket).where(
            BIRBracket.effective_date == date(2023, 1, 1),
            BIRBracket.source_reference == ANNEX_E,
            BIRBracket.is_active.is_(True),  # type: ignore[attr-defined]
        )
    ).all()

    assert len(rows) == 24
    assert {row.period for row in rows} == {
        "daily",
        "weekly",
        "semi_monthly",
        "monthly",
    }
    assert all(sum(row.period == period for row in rows) == 6 for period in {row.period for row in rows})


def test_annex_e_monthly_tax_boundaries_match_published_base_and_rates(db: Session) -> None:
    # Annex E: ₱33,333–₱66,666 => ₱1,875 + 20% over ₱33,333.
    assert calculate_bir_tax(db, Decimal("33333.00"), "monthly", "2023-01-01") == Decimal("1875.00")
    assert calculate_bir_tax(db, Decimal("35000.00"), "monthly", "2023-01-01") == Decimal("2208.40")

    # The next band starts at ₱66,667 with the published ₱8,541.80 base.
    assert calculate_bir_tax(db, Decimal("66667.00"), "monthly", "2023-01-01") == Decimal("8541.80")


def test_annex_e_uses_regular_band_for_supplementary_compensation(db: Session) -> None:
    # RR 11-2018 selects the band from regular pay (₱33,000), then taxes
    # supplementary pay at that band's marginal rate. Selecting from total
    # compensation (₱43,000) would incorrectly move the whole amount to 20%.
    assert calculate_bir_tax(
        db,
        Decimal("43000.00"),
        "monthly",
        "2023-01-01",
        regular_compensation=Decimal("33000.00"),
    ) == Decimal("3325.05")


def test_annex_e_rejects_regular_compensation_above_taxable_total(db: Session) -> None:
    with pytest.raises(ValueError, match="at least regular compensation"):
        calculate_bir_tax(
            db,
            Decimal("30000.00"),
            "monthly",
            "2023-01-01",
            regular_compensation=Decimal("33000.00"),
        )


def test_annex_e_daily_tax_boundary_matches_published_base_and_rate(db: Session) -> None:
    # Annex E: ₱2,192–₱5,478 => ₱280.85 + 25% over ₱2,192.
    assert calculate_bir_tax(db, Decimal("2500.00"), "daily", "2023-01-01") == Decimal("357.85")
