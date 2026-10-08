"""Table-driven government contribution calculators (Phase B4A).

No hardcoded rates. All values come from the bracket tables in the database.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from app.payroll.models import (
    BIRBracket,
    PagIBIGBracket,
    PhilHealthBracket,
    SSSBracket,
)

T = TypeVar("T", bound=Any)


class StatutoryScheduleUnavailable(ValueError):
    """The requested effective statutory schedule is absent or incomplete."""


def _effective_date(value: str | None) -> date:
    if value:
        return datetime.fromisoformat(value).date()
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def _get_effective_bracket(session: Session, model: type[T], as_of: date) -> T | None:
    stmt = (
        select(model)
        .where(model.effective_date <= as_of, model.is_deleted.is_(False), model.is_active.is_(True))
        .order_by(model.effective_date.desc())
    )
    row = session.exec(stmt).first()
    # PhilHealth schedules are annual: require an explicitly effective row
    # for the requested calendar year instead of silently carrying one forward.
    if isinstance(row, PhilHealthBracket) and row.effective_date.year != as_of.year:
        return None
    return row


def _get_effective_sss_bracket(
    session: Session, monthly_compensation: Decimal, as_of: date
) -> SSSBracket | None:
    """Map compensation to its row in the latest effective employer schedule.

    SSS employer tables are compensation ranges mapped to MSC. The legacy
    ``msc_min``/``msc_max`` columns are not valid selectors for employee pay.
    """
    rows = session.exec(
        select(SSSBracket)
        .where(
            col(SSSBracket.effective_date) <= as_of,
            col(SSSBracket.is_deleted).is_(False),
            col(SSSBracket.is_active).is_(True),
        )
        .order_by(col(SSSBracket.effective_date).desc(), col(SSSBracket.compensation_min))
    ).all()
    if not rows:
        return None
    latest_date = rows[0].effective_date
    schedule = [row for row in rows if row.effective_date == latest_date]

    def contains_compensation(row: SSSBracket) -> bool:
        if row.compensation_min is None:
            return False
        try:
            lower = Decimal(str(row.compensation_min))
            upper = (
                Decimal(str(row.compensation_max))
                if row.compensation_max is not None
                else None
            )
        except InvalidOperation:
            return False
        return (
            lower.is_finite()
            and (upper is None or upper.is_finite())
            and lower <= monthly_compensation
            and (upper is None or monthly_compensation <= upper)
        )

    matching = next(
        (row for row in schedule if contains_compensation(row)),
        None,
    )
    return matching


def _get_effective_pagibig_bracket(
    session: Session, salary: Decimal, as_of: date
) -> PagIBIGBracket | None:
    """Select the salary band from the latest effective Pag-IBIG schedule."""
    rows = session.exec(
        select(PagIBIGBracket)
        .where(
            col(PagIBIGBracket.effective_date) <= as_of,
            col(PagIBIGBracket.is_deleted).is_(False),
            col(PagIBIGBracket.is_active).is_(True),
        )
        .order_by(
            col(PagIBIGBracket.effective_date).desc(),
            col(PagIBIGBracket.salary_min),
        )
    ).all()
    if not rows:
        return None
    effective_date = rows[0].effective_date
    schedule = [row for row in rows if row.effective_date == effective_date]
    matching = next(
        (row for row in schedule if row.salary_min <= salary <= row.salary_max), None
    )
    # The top published fund-salary band also defines the contribution cap.
    if matching is None and salary > max(row.salary_max for row in schedule):
        return max(schedule, key=lambda row: row.salary_max)
    return matching


# --- SSS -----------------------------------------------------------------------


def calculate_sss_employee_share(
    session: Session, monthly_compensation: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_sss_bracket(session, monthly_compensation, as_of)
    if not bracket:
        raise StatutoryScheduleUnavailable(
            f"No SSS compensation band covers PHP {monthly_compensation} on {as_of.isoformat()}"
        )
    return bracket.employee_ss + bracket.employee_mpf


def calculate_sss_employer_share(
    session: Session, monthly_compensation: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_sss_bracket(session, monthly_compensation, as_of)
    if not bracket:
        raise StatutoryScheduleUnavailable(
            f"No SSS compensation band covers PHP {monthly_compensation} on {as_of.isoformat()}"
        )
    return bracket.employer_ss + bracket.employer_ec + bracket.employer_mpf


# --- PhilHealth -----------------------------------------------------------------


def calculate_philhealth_employee_share(
    session: Session, salary: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_bracket(session, PhilHealthBracket, as_of)
    if not bracket:
        raise StatutoryScheduleUnavailable(
            f"No active PhilHealth schedule is configured for calendar year {as_of.year}"
        )
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
    bracket = _get_effective_pagibig_bracket(session, salary, as_of)
    if not bracket:
        raise StatutoryScheduleUnavailable(
            f"No complete active Pag-IBIG schedule is effective on {as_of.isoformat()}"
        )
    if salary < bracket.salary_min:
        return Decimal("0.00")
    basis = salary if salary <= bracket.salary_max else bracket.salary_max
    rate = bracket.employee_rate
    return (basis * rate / Decimal("100.0")).quantize(Decimal("0.01"))


def calculate_pagibig_employer_share(
    session: Session, salary: Decimal, effective_date: str | None = None
) -> Decimal:
    as_of = _effective_date(effective_date)
    bracket = _get_effective_pagibig_bracket(session, salary, as_of)
    if not bracket:
        raise StatutoryScheduleUnavailable(
            f"No complete active Pag-IBIG schedule is effective on {as_of.isoformat()}"
        )
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
            BIRBracket.is_active.is_(True),  # type: ignore[attr-defined]
        )
        .order_by(BIRBracket.bracket_min)  # type: ignore[arg-type]
    )
    brackets = session.exec(stmt).all()
    if not brackets:
        raise StatutoryScheduleUnavailable(
            f"No active BIR {period_type} tax table is effective on {as_of.isoformat()}"
        )
    latest_effective_date = max(bracket.effective_date for bracket in brackets)
    current_brackets = [bracket for bracket in brackets if bracket.effective_date == latest_effective_date]
    bracket = next(
        (
            row
            for row in current_brackets
            if row.bracket_min <= taxable_income
            and (row.bracket_max is None or taxable_income <= row.bracket_max)
        ),
        None,
    )
    if bracket is None:
        raise StatutoryScheduleUnavailable(
            f"BIR {period_type} tax table has no bracket for taxable compensation {taxable_income}"
        )
    taxable_excess = max(Decimal("0"), taxable_income - bracket.bracket_min)
    return (bracket.base_tax + taxable_excess * bracket.excess_rate / Decimal("100.0")).quantize(
        Decimal("0.01")
    )


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
