"""Require contribution corrections to stay within their source scope.

Revision ID: 2b3c4d5e6f70
Revises: 1a2b3c4d5e6f
Create Date: 2026-10-08
"""

import sqlalchemy as sa

from alembic import op

revision = "2b3c4d5e6f70"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    mismatches = bind.execute(
        sa.text(
            "SELECT correction.id::text, source.id::text "
            "FROM payroll_contribution_ledger AS correction "
            "JOIN payroll_contribution_ledger AS source "
            "ON source.id = correction.reverses_id "
            "WHERE correction.employee_id <> source.employee_id "
            "OR correction.scheme <> source.scheme "
            "OR correction.contribution_month <> source.contribution_month "
            "ORDER BY correction.id"
        )
    ).all()
    if mismatches:
        details = "; ".join(f"{row}: {source}" for row, source in mismatches)
        raise RuntimeError(
            "Cannot enforce contribution correction scope; correct rows that reverse "
            f"another employee, scheme, or month before retrying: {details}"
        )

    op.create_unique_constraint(
        "uq_payroll_contribution_reversal_scope",
        "payroll_contribution_ledger",
        ["id", "employee_id", "scheme", "contribution_month"],
    )
    op.create_foreign_key(
        "fk_payroll_contribution_reversal_scope",
        "payroll_contribution_ledger",
        "payroll_contribution_ledger",
        ["reverses_id", "employee_id", "scheme", "contribution_month"],
        ["id", "employee_id", "scheme", "contribution_month"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_payroll_contribution_reversal_scope",
        "payroll_contribution_ledger",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_payroll_contribution_reversal_scope",
        "payroll_contribution_ledger",
        type_="unique",
    )
