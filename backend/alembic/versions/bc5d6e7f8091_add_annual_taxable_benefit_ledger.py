"""Add verified benefit records for annual BIR exemption reconciliation.

Revision ID: bc5d6e7f8091
Revises: ab4c5d6e7f80
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "bc5d6e7f8091"
down_revision = "ab4c5d6e7f80"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("opening_benefits_exempt_ytd", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("opening_benefits_reconciled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_employee_tax_opening_benefits_nonnegative",
        "employee_tax_year_declaration",
        "opening_benefits_exempt_ytd >= 0 AND opening_benefits_exempt_ytd <= 90000",
    )
    op.create_table(
        "employee_tax_benefit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("benefit_type", sa.String(length=32), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("source_reference", sa.String(length=512), nullable=False),
        sa.Column("correction_of_id", sa.Uuid(), nullable=True),
        sa.Column("correction_reason", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tax_year >= 2000 AND tax_year <= 2200", name="ck_employee_tax_benefit_year"),
        sa.CheckConstraint(
            "(correction_of_id IS NULL AND gross_amount > 0 AND correction_reason IS NULL) OR "
            "(correction_of_id IS NOT NULL AND gross_amount < 0 AND length(trim(correction_reason)) > 0)",
            name="ck_employee_tax_benefit_correction_shape",
        ),
        sa.CheckConstraint(
            "benefit_type IN ('thirteenth_month', 'other_benefit')",
            name="ck_employee_tax_benefit_type",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["correction_of_id"], ["employee_tax_benefit.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "tax_year",
            "benefit_type",
            "source_reference",
            name="uq_employee_tax_benefit_source_reference",
        ),
    )
    op.create_unique_constraint(
        "uq_employee_tax_benefit_correction_of",
        "employee_tax_benefit",
        ["correction_of_id"],
    )
    op.create_index(
        "ix_employee_tax_benefit_employee_year_date",
        "employee_tax_benefit",
        ["employee_id", "tax_year", "paid_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_employee_tax_benefit_employee_year_date", table_name="employee_tax_benefit")
    op.drop_constraint(
        "uq_employee_tax_benefit_correction_of", "employee_tax_benefit", type_="unique"
    )
    op.drop_table("employee_tax_benefit")
    op.drop_constraint(
        "ck_employee_tax_opening_benefits_nonnegative",
        "employee_tax_year_declaration",
        type_="check",
    )
    op.drop_column("employee_tax_year_declaration", "opening_benefits_reconciled")
    op.drop_column("employee_tax_year_declaration", "opening_benefits_exempt_ytd")
