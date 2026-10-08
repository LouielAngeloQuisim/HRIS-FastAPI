import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session

from app.employee.models import EmployeeRecords
from app.payroll.annualized_tax import (
    calculate_annualized_compensation_tax,
    cumulative_average_required,
    cumulative_average_withholding,
)
from app.payroll.models import PayrollEntry, PayrollRunStatus
from app.payroll.payroll_tables import PayrollRun as PayrollRunTable
from app.payroll.routes import (
    _bir_cumulative_average_was_used,
    _bir_finalized_history,
)


@pytest.mark.parametrize(
    ("taxable", "expected"),
    [
        ("0", "0.00"),
        ("250000", "0.00"),
        ("250001", "0.15"),
        ("400000", "22500.00"),
        ("800000", "102500.00"),
        ("2000000", "402500.00"),
        ("8000000", "2202500.00"),
        ("8100000", "2237500.00"),
        ("250000.05", "0.01"),
    ],
)
def test_annual_tax_uses_2023_onward_statutory_brackets(
    taxable: str, expected: str
) -> None:
    assert calculate_annualized_compensation_tax(Decimal(taxable)) == Decimal(expected)


@pytest.mark.parametrize("taxable", [Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity")])
def test_annual_tax_rejects_invalid_income(taxable: Decimal) -> None:
    with pytest.raises(ValueError):
        calculate_annualized_compensation_tax(taxable)


def test_cumulative_average_withholding_matches_bir_rr_11_2018_example() -> None:
    average, cumulative_tax, current_withholding = cumulative_average_withholding(
        cumulative_taxable_compensation=Decimal("215000.00"),
        period_count=7,
        tax_per_period=Decimal("1976.25"),
        prior_withheld=Decimal("11000.40"),
    )
    assert average == Decimal("30714.29")
    assert cumulative_tax == Decimal("13833.75")
    assert current_withholding == Decimal("2833.35")


def test_cumulative_average_withholding_never_creates_negative_deduction() -> None:
    _, _, current_withholding = cumulative_average_withholding(
        cumulative_taxable_compensation=Decimal("100000.00"),
        period_count=10,
        tax_per_period=Decimal("0.00"),
        prior_withheld=Decimal("25.00"),
    )
    assert current_withholding == Decimal("0.00")


@pytest.mark.parametrize(
    (
        "regular",
        "supplementary",
        "first_taxable",
        "previously_applied",
        "expected",
    ),
    [
        ("9000.00", "300.00", "10416.67", False, True),
        ("12000.00", "12000.00", "10416.67", False, True),
        ("12000.00", "11999.99", "10416.67", False, False),
        ("12000.00", "0.00", "10416.67", False, False),
        ("12000.00", "0.00", "10416.67", True, True),
    ],
)
def test_cumulative_average_method_triggers_and_persists_for_tax_year(
    regular: str,
    supplementary: str,
    first_taxable: str,
    previously_applied: bool,
    expected: bool,
) -> None:
    assert cumulative_average_required(
        regular_compensation=Decimal(regular),
        supplementary_compensation=Decimal(supplementary),
        first_taxable_regular_amount=Decimal(first_taxable),
        previously_applied=previously_applied,
    ) is expected


def test_finalized_tax_history_requires_gapless_periods_and_snapshots(db: Session) -> None:
    employee = EmployeeRecords(
        employee_code=f"YTD-{uuid.uuid4().hex[:8]}",
        first_name="QA",
        last_name="Tax",
        birthdate=date(1990, 1, 1),
        date_hired=date(2026, 1, 1),
    )
    db.add(employee)
    db.flush()
    run = PayrollRunTable(
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 15),
        workflow_status="finalized",
        status=PayrollRunStatus.APPROVED,
    )
    db.add(run)
    db.flush()
    entry = PayrollEntry(
        payroll_run_id=run.id,
        employee_id=employee.id,
        review_state="reviewed",
        basic_rate=Decimal("26000"),
        rate_date_from=run.date_from,
        rate_date_to=run.date_to,
        gross_pay=Decimal("13000"),
        total_deductions=Decimal("100"),
        net_pay=Decimal("12900"),
        taxable_income=Decimal("12900"),
        input_snapshot={
            "bir_calculation": {
                "method": "cumulative_average_rr_11_2018",
                "taxable_compensation": "10850.00",
            }
        },
        deductions={"bir_withholding": "64.95"},
    )
    db.add(entry)
    db.commit()

    history, taxable, withheld, complete = _bir_finalized_history(
        db,
        employee.id,
        2026,
        date(2026, 9, 30),
        date(2026, 10, 16),
        date(2026, 10, 1),
    )
    assert complete is True
    assert taxable == Decimal("10850.00")
    assert withheld == Decimal("64.95")
    assert history == [
        {
            "entry_id": str(entry.id),
            "run_id": str(run.id),
            "date_from": "2026-10-01",
            "date_to": "2026-10-15",
            "taxable_compensation": "10850.00",
            "tax_withheld": "64.95",
            "pay_period_type": "unknown",
        }
    ]
    assert _bir_cumulative_average_was_used(
        db, employee.id, 2026, date(2026, 10, 16)
    ) is True

    # If the prior period's calculation snapshot is damaged, annualization must
    # not treat that period as zero income or zero withholding.
    entry.input_snapshot = {}
    db.add(entry)
    db.commit()
    history, _, _, complete = _bir_finalized_history(
        db,
        employee.id,
        2026,
        date(2026, 9, 30),
        date(2026, 10, 16),
        date(2026, 10, 1),
    )
    assert complete is False
    assert history[0]["unavailable"] == "true"
