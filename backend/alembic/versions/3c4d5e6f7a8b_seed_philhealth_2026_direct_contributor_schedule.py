"""Seed the verified PhilHealth direct-contributor schedule for 2026.

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f70
Create Date: 2026-10-08

PhilHealth Advisory 2026-0042 reiterates that direct contributors pay 5%
effective January 2025 and confirms the premium floor. Advisory 2025-0002 and
Circular 2020-0005 (Revision 1) establish the employer MBS basis, floor,
ceiling, and equal employee/employer sharing. This explicit 2026 row represents
the continuing schedule; the calculator intentionally rejects silent
calendar-year carry-forward.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

revision = "3c4d5e6f7a8b"
down_revision = "2b3c4d5e6f70"
branch_labels = None
depends_on = None

EFFECTIVE_DATE = "2026-01-01"


def upgrade() -> None:
    connection = op.get_bind()
    exists = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM philhealth_bracket "
            "WHERE effective_date = :effective_date "
            "AND is_active = true AND is_deleted = false)"
        ),
        {"effective_date": EFFECTIVE_DATE},
    ).scalar()
    if exists:
        return

    now = datetime.now(timezone.utc)
    philhealth_bracket = sa.table(
        "philhealth_bracket",
        sa.column("id", sa.Uuid()),
        sa.column("salary_min", sa.Numeric(12, 2)),
        sa.column("salary_max", sa.Numeric(12, 2)),
        sa.column("rate", sa.Numeric(6, 3)),
        sa.column("employer_share", sa.Numeric(12, 2)),
        sa.column("employee_share", sa.Numeric(12, 2)),
        sa.column("effective_date", sa.Date()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_deleted", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        philhealth_bracket,
        [
            {
                "id": uuid.uuid4(),
                "salary_min": Decimal("10000.00"),
                "salary_max": Decimal("100000.00"),
                "rate": Decimal("5.000"),
                "employer_share": Decimal("2.500"),
                "employee_share": Decimal("2.500"),
                "effective_date": datetime.strptime(EFFECTIVE_DATE, "%Y-%m-%d").date(),
                "is_active": True,
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    # Preserve statutory schedule data once payroll history can reference it.
    pass
