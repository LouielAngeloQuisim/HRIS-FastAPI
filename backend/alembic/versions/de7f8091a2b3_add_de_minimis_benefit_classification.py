"""Track BIR de minimis benefit category and supporting evidence.

Revision ID: de7f8091a2b3
Revises: cd6e7f8091a2
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "de7f8091a2b3"
down_revision = "cd6e7f8091a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee_tax_benefit",
        sa.Column("de_minimis_category", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column(
            "eligibility_evidence",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.drop_constraint(
        "ck_employee_tax_benefit_type", "employee_tax_benefit", type_="check"
    )
    op.create_check_constraint(
        "ck_employee_tax_benefit_classification",
        "employee_tax_benefit",
        "(benefit_type IN ('thirteenth_month', 'other_benefit') AND de_minimis_category IS NULL) OR "
        "(benefit_type = 'de_minimis' AND de_minimis_category IN "
        "('medical_cash_dependents', 'rice_subsidy', 'uniform_clothing', "
        "'actual_medical_assistance', 'laundry_allowance', 'achievement_award', "
        "'christmas_anniversary_gift', 'cba_productivity_incentive'))",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT 1 FROM employee_tax_benefit WHERE benefit_type = 'de_minimis' LIMIT 1")
    ).first():
        raise RuntimeError(
            "Cannot downgrade de minimis classifications while de minimis benefit records exist; "
            "preserve the ledger and create a forward migration instead."
        )
    op.drop_constraint(
        "ck_employee_tax_benefit_classification", "employee_tax_benefit", type_="check"
    )
    op.create_check_constraint(
        "ck_employee_tax_benefit_type",
        "employee_tax_benefit",
        "benefit_type IN ('thirteenth_month', 'other_benefit')",
    )
    op.drop_column("employee_tax_benefit", "eligibility_evidence")
    op.drop_column("employee_tax_benefit", "de_minimis_category")
