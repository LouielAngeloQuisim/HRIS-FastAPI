"""Seed published PhilHealth and Pag-IBIG mandatory schedules when absent.

Revision ID: a0f1a2b3c4d5
Revises: 9e0f1a2b3c4d
Create Date: 2026-10-07
"""

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa

revision = "a0f1a2b3c4d5"
down_revision = "9e0f1a2b3c4d"
branch_labels = None
depends_on = None

PHILHEALTH_EFFECTIVE_DATE = "2025-01-01"
PAGIBIG_EFFECTIVE_DATE = "2024-02-01"


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc)

    has_philhealth = connection.execute(
        sa.text(
            """SELECT EXISTS (
                SELECT 1 FROM philhealth_bracket
                WHERE effective_date = :effective_date
                  AND is_active = true AND is_deleted = false
            )"""
        ),
        {"effective_date": PHILHEALTH_EFFECTIVE_DATE},
    ).scalar()
    if not has_philhealth:
        connection.execute(
            sa.text(
                """INSERT INTO philhealth_bracket
                (id, salary_min, salary_max, rate, employer_share, employee_share,
                 effective_date, is_active, is_deleted, created_at, updated_at)
                VALUES (:id, 10000.00, 100000.00, 5.000, 2.500, 2.500,
                        :effective_date, true, false, :created_at, :updated_at)"""
            ),
            {
                "id": str(uuid.uuid4()),
                "effective_date": PHILHEALTH_EFFECTIVE_DATE,
                "created_at": now,
                "updated_at": now,
            },
        )

    has_pagibig = connection.execute(
        sa.text(
            """SELECT EXISTS (
                SELECT 1 FROM pagibig_bracket
                WHERE effective_date = :effective_date
                  AND is_active = true AND is_deleted = false
            )"""
        ),
        {"effective_date": PAGIBIG_EFFECTIVE_DATE},
    ).scalar()
    if not has_pagibig:
        rows = [
            {
                "id": str(uuid.uuid4()),
                "salary_min": "0.01",
                "salary_max": "1500.00",
                "employee_rate": "1.000",
                "employer_rate": "2.000",
                "effective_date": PAGIBIG_EFFECTIVE_DATE,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "salary_min": "1500.01",
                "salary_max": "10000.00",
                "employee_rate": "2.000",
                "employer_rate": "2.000",
                "effective_date": PAGIBIG_EFFECTIVE_DATE,
                "created_at": now,
                "updated_at": now,
            },
        ]
        connection.execute(
            sa.text(
                """INSERT INTO pagibig_bracket
                (id, salary_min, salary_max, employee_rate, employer_rate,
                 effective_date, is_active, is_deleted, created_at, updated_at)
                VALUES (:id, :salary_min, :salary_max, :employee_rate,
                        :employer_rate, :effective_date, true, false,
                        :created_at, :updated_at)"""
            ),
            rows,
        )


def downgrade() -> None:
    # Keep mandatory schedule data when rolling code back.
    pass
