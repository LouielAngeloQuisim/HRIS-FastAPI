"""Seed the published 2025 SSS employer and employee contribution schedule.

Revision ID: 9e0f1a2b3c4d
Revises: 8d9e0f1a2b3c
Create Date: 2026-10-07
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from alembic import op
import sqlalchemy as sa

revision = "9e0f1a2b3c4d"
down_revision = "8d9e0f1a2b3c"
branch_labels = None
depends_on = None

EFFECTIVE_DATE = "2025-01-01"
# Source: SSS Circular 2024-006, effective January 2025.


def _rows() -> list[dict[str, object]]:
    """Build the official 61 compensation bands from Circular 2024-006.

    The official table increases regular MSC by ₱500 per band from ₱5,000
    through ₱20,000, then assigns MPF MSC from ₱500 through ₱15,000. Rates
    are 10%/5% for employer/employee regular SS and MPF. Employer EC is ₱10
    through regular MSC ₱14,500 and ₱30 from ₱15,000 onward.
    """
    rows: list[dict[str, object]] = []
    for index in range(61):
        lower = Decimal("0.01") if index == 0 else Decimal("5250.00") + Decimal(index - 1) * Decimal("500.00")
        upper = (
            Decimal("5249.99")
            if index == 0
            else lower + Decimal("499.99") if index < 60 else None
        )
        total_msc = Decimal("5000.00") + Decimal(index) * Decimal("500.00")
        regular_msc = min(total_msc, Decimal("20000.00"))
        mpf_msc = total_msc - regular_msc
        ec = Decimal("10.00") if regular_msc <= Decimal("14500.00") else Decimal("30.00")
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "msc_min": str(total_msc),
                "msc_max": str(total_msc),
                "compensation_min": str(lower),
                "compensation_max": str(upper) if upper is not None else None,
                "monthly_salary_credit": str(total_msc),
                "employer_ss": str(regular_msc * Decimal("0.10")),
                "employer_ec": str(ec),
                "employer_mpf": str(mpf_msc * Decimal("0.10")),
                "employee_ss": str(regular_msc * Decimal("0.05")),
                "employee_mpf": str(mpf_msc * Decimal("0.05")),
                "effective_date": EFFECTIVE_DATE,
            }
        )
    return rows


def upgrade() -> None:
    connection = op.get_bind()
    exists = connection.execute(
        sa.text(
            """SELECT EXISTS (
                SELECT 1 FROM sss_bracket
                WHERE effective_date = :effective_date
                  AND is_active = true AND is_deleted = false
            )"""
        ),
        {"effective_date": EFFECTIVE_DATE},
    ).scalar()
    if exists:
        # Preserve any existing employer-entered schedule; a partial table
        # remains blocked by policy validation and must be reconciled by HR.
        return

    now = datetime.now(timezone.utc)
    rows = _rows()
    connection.execute(
        sa.text(
            """INSERT INTO sss_bracket
            (id, msc_min, msc_max, compensation_min, compensation_max,
             monthly_salary_credit, employer_ss, employer_ec, employer_mpf,
             employee_ss, employee_mpf, effective_date, is_active, is_deleted,
             created_at, updated_at)
            VALUES
            (:id, :msc_min, :msc_max, :compensation_min, :compensation_max,
             :monthly_salary_credit, :employer_ss, :employer_ec, :employer_mpf,
             :employee_ss, :employee_mpf, :effective_date, true, false,
             :created_at, :updated_at)"""
        ),
        [{**row, "created_at": now, "updated_at": now} for row in rows],
    )


def downgrade() -> None:
    # Retain statutory schedule rows to avoid silently removing payroll data.
    pass
