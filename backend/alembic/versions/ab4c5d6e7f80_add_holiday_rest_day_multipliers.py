"""Add explicit combined holiday and rest-day pay factors.

Revision ID: ab4c5d6e7f80
Revises: f3a4b5c6d7e8
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "ab4c5d6e7f80"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "holiday_config",
        sa.Column("multiplier_regular_rest_day", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "holiday_config",
        sa.Column("multiplier_overtime_rest_day", sa.Numeric(6, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("holiday_config", "multiplier_overtime_rest_day")
    op.drop_column("holiday_config", "multiplier_regular_rest_day")
