"""Store prior-employer periods used by cumulative-average tax.

Revision ID: e7f8a9b0c1d2
Revises: c2d3e4f5a6b7
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("opening_pay_period_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column(
        "employee_tax_year_declaration",
        "opening_pay_period_count",
        server_default=None,
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("opening_pay_period_type", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_employee_tax_opening_period_count",
        "employee_tax_year_declaration",
        "opening_pay_period_count >= 0 AND opening_pay_period_count <= 366",
    )
    op.create_check_constraint(
        "ck_employee_tax_opening_period_type",
        "employee_tax_year_declaration",
        "opening_pay_period_type IS NULL OR opening_pay_period_type IN ('daily', 'weekly', 'semi_monthly', 'monthly')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_employee_tax_opening_period_type",
        "employee_tax_year_declaration",
        type_="check",
    )
    op.drop_constraint(
        "ck_employee_tax_opening_period_count",
        "employee_tax_year_declaration",
        type_="check",
    )
    op.drop_column("employee_tax_year_declaration", "opening_pay_period_count")
    op.drop_column("employee_tax_year_declaration", "opening_pay_period_type")
