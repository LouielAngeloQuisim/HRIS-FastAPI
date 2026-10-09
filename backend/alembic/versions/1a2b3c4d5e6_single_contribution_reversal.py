"""Allow only one correction to reverse each contribution ledger row.

Revision ID: 1a2b3c4d5e6f
Revises: f1a2b3c4d5e6
Create Date: 2026-10-08
"""

import sqlalchemy as sa

from alembic import op

revision = "1a2b3c4d5e6f"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT reverses_id::text, array_agg(id::text ORDER BY id::text) AS row_ids "
            "FROM payroll_contribution_ledger WHERE reverses_id IS NOT NULL "
            "GROUP BY reverses_id HAVING count(*) > 1 ORDER BY reverses_id"
        )
    ).all()
    if duplicates:
        details = "; ".join(f"{parent}: {rows}" for parent, rows in duplicates)
        raise RuntimeError(
            "Cannot enforce one contribution correction per source row; "
            f"review duplicate reversal records before retrying: {details}"
        )
    op.create_unique_constraint(
        "uq_payroll_contribution_single_reversal",
        "payroll_contribution_ledger",
        ["reverses_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_payroll_contribution_single_reversal",
        "payroll_contribution_ledger",
        type_="unique",
    )
