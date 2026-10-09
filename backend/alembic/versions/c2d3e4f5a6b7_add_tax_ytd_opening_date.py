"""Track the date covered by opening tax-year balances.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("opening_as_of", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employee_tax_year_declaration", "opening_as_of")
