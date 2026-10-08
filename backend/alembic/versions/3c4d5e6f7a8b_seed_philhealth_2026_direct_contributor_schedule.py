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
    connection.execute(
        sa.text(
            "INSERT INTO philhealth_bracket "
            "(id, salary_min, salary_max, rate, employer_share, employee_share, "
            "effective_date, is_active, is_deleted, created_at, updated_at) "
            "VALUES (:id, 10000.00, 100000.00, 5.000, 2.500, 2.500, "
            ":effective_date, true, false, :created_at, :updated_at)"
        ),
        {
            "id": str(uuid.uuid4()),
            "effective_date": EFFECTIVE_DATE,
            "created_at": now,
            "updated_at": now,
        },
    )


def downgrade() -> None:
    # Preserve statutory schedule data once payroll history can reference it.
    pass
