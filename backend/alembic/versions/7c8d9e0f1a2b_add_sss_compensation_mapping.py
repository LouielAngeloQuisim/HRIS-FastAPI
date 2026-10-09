"""Add compensation-to-MSC mapping fields to SSS schedules.

Revision ID: 7c8d9e0f1a2b
Revises: 67e279f8c3cc
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa

revision = "7c8d9e0f1a2b"
down_revision = "67e279f8c3cc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sss_bracket", sa.Column("compensation_min", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "sss_bracket", sa.Column("compensation_max", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "sss_bracket", sa.Column("monthly_salary_credit", sa.Numeric(12, 2), nullable=True)
    )


def downgrade() -> None:
    # These fields contain no migrated values; removal is a safe rollback.
    op.drop_column("sss_bracket", "monthly_salary_credit")
    op.drop_column("sss_bracket", "compensation_max")
    op.drop_column("sss_bracket", "compensation_min")
