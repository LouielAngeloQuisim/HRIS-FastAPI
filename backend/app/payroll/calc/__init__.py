"""Table-driven government contribution calculators (Phase B4A).

No hardcoded rates. All values come from the bracket tables in the database.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, TypeVar

from sqlmodel import Session, select

from app.payroll.models import (
    BIRBracket,
    PagIBIGBracket,
    PhilHealthBracket,
    SSSBracket,
)

T = TypeVar("T", bound=Any)


def _effective_date(value: str | None) -> date:
    if value:
        return datetime.fromisoformat(value).date()
    return datetime.now().date()


def _get_effective_bracket(session: Session, model: type[T], as_of: date) -> T | None:
    stmt = (
        select(model)
        .where(model.effective_date <= as_of, model.is_deleted.is_(False))
        .order_by(model.effective_date.desc())
    )
    return session.exec(stmt).first()


# --- SSS -----------------------------------------------------------------------


def calculate_sss_employee_share(
    session: Session, msc: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_bracket(session, SSSBracket, as_of)
    if not bracket:
        return Decimal("0.00")
    if msc < bracket.msc_min:
        return Decimal("0.00")
    if msc > bracket.msc_max:
        msc = bracket.msc_max
    return bracket.employee_ss


def calculate_sss_employer_share(
    session: Session, msc: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_bracket(session, SSSBracket, as_of)
    if not bracket:
        return Decimal("0.00")
    if msc < bracket.msc_min:
        return Decimal("0.00")
    if msc > bracket.msc_max:
        msc = bracket.msc_max
    return bracket.employer_ss + bracket.employer_ec + bracket.employer_mpf


# --- PhilHealth -----------------------------------------------------------------


def calculate_philhealth_employee_share(
    session: Session, salary: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_bracket(session, PhilHealthBracket, as_of)
    if not bracket:
        return Decimal("0.00")
    if salary < bracket.salary_min:
        basis = bracket.salary_min
    elif salary > bracket.salary_max:
        basis = bracket.salary_max
    else:
        basis = salary
    return (basis * bracket.rate / Decimal("100.0") / Decimal("2.0")).quantize(
        Decimal("0.01")
    )


def calculate_philhealth_employer_share(
    session: Session, salary: Decimal, effective_date: str | None = None
) -> Decimal:
    return calculate_philhealth_employee_share(session, salary, effective_date)


# --- Pag-IBIG -------------------------------------------------------------------


def calculate_pagibig_employee_share(
    session: Session, salary: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_bracket(session, PagIBIGBracket, as_of)
    if not bracket:
        return Decimal("0.00")
    if salary < bracket.salary_min:
        return Decimal("0.00")
    basis = salary if salary <= bracket.salary_max else bracket.salary_max
    rate = bracket.employee_rate
    return (basis * rate / Decimal("100.0")).quantize(Decimal("0.01"))


def calculate_pagibig_employer_share(
    session: Session, salary: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_bracket(session, PagIBIGBracket, as_of)
    if not bracket:
        return Decimal("0.00")
    if salary < bracket.salary_min:
        return Decimal("0.00")
    basis = salary if salary <= bracket.salary_max else bracket.salary_max
    rate = bracket.employer_rate
    return (basis * rate / Decimal("100.0")).quantize(Decimal("0.01"))


# --- BIR ------------------------------------------------------------------------


def calculate_bir_tax(
    session: Session,
    taxable_income: Decimal,
    period_type: str = "monthly",
    effective_date: str | None = None,
) -> Decimal:
    as_of = _effective_date(effective_date)
    stmt = (
        select(BIRBracket)
        .where(
            BIRBracket.period == period_type,
            BIRBracket.effective_date <= as_of,
            BIRBracket.is_deleted.is_(False),  # type: ignore[attr-defined]
        )
        .order_by(BIRBracket.bracket_min)  # type: ignore[arg-type]
    )
    brackets = session.exec(stmt).all()

    tax = Decimal("0.00")
    remaining = taxable_income
    for bracket in brackets:
        if remaining <= 0:
            break
        span = (bracket.bracket_max or Decimal("999999999.99")) - bracket.bracket_min
        in_bracket = min(remaining, span)
        tax += bracket.base_tax + (in_bracket * bracket.excess_rate / Decimal("100.0"))
        remaining -= in_bracket
    return tax.quantize(Decimal("0.01"))


# --- Batch ----------------------------------------------------------------------


def calculate_all_contributions(
    session: Session,
    gross_pay: Decimal,
    period_type: str = "monthly",
    effective_date: str | None = None,
) -> dict[str, Decimal]:
    sss_employee = calculate_sss_employee_share(session, gross_pay, effective_date)
    sss_employer = calculate_sss_employer_share(session, gross_pay, effective_date)
    philhealth_employee = calculate_philhealth_employee_share(
        session, gross_pay, effective_date
    )
    philhealth_employer = calculate_philhealth_employer_share(
        session, gross_pay, effective_date
    )
    pagibig_employee = calculate_pagibig_employee_share(
        session, gross_pay, effective_date
    )
    pagibig_employer = calculate_pagibig_employer_share(
        session, gross_pay, effective_date
    )
    taxable = gross_pay - sss_employee - philhealth_employee - pagibig_employee
    if taxable < 0:
        taxable = Decimal("0.00")
    bir = calculate_bir_tax(session, taxable, period_type, effective_date)
    return {
        "sss_employee": sss_employee,
        "sss_employer": sss_employer,
        "philhealth_employee": philhealth_employee,
        "philhealth_employer": philhealth_employer,
        "pagibig_employee": pagibig_employee,
        "pagibig_employer": pagibig_employer,
        "bir": bir,
        "taxable_income": taxable,
    }
