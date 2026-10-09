"""Store reconciled de minimis category opening balances.

Revision ID: ef8091a2b3c4
Revises: de7f8091a2b3
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "ef8091a2b3c4"
down_revision = "de7f8091a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column(
            "opening_de_minimis_annual_ytd",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column(
            "opening_de_minimis_monthly_ytd",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT 1 FROM employee_tax_year_declaration "
            "WHERE opening_de_minimis_annual_ytd <> '{}' "
            "OR opening_de_minimis_monthly_ytd <> '{}' LIMIT 1"
        )
    ).first():
        raise RuntimeError(
            "Cannot downgrade reconciled de minimis opening balances; preserve payroll evidence."
        )
    op.drop_column("employee_tax_year_declaration", "opening_de_minimis_monthly_ytd")
    op.drop_column("employee_tax_year_declaration", "opening_de_minimis_annual_ytd")
