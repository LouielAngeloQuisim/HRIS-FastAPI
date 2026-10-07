"""Store reviewed employee tax classification and opening YTD amounts.

Revision ID: b1c2d3e4f5a6
Revises: a0f1a2b3c4d5
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_tax_year_declaration",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("tax_classification", sa.String(length=32), nullable=False, server_default="ordinary"),
        sa.Column("taxable_compensation_ytd", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_withheld_ytd", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("previous_employer_included", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_reference", sa.String(length=512), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tax_year >= 2000 AND tax_year <= 2200", name="ck_employee_tax_year_range"),
        sa.CheckConstraint("tax_classification IN ('ordinary', 'minimum_wage_earner')", name="ck_employee_tax_classification"),
        sa.CheckConstraint("taxable_compensation_ytd >= 0 AND tax_withheld_ytd >= 0", name="ck_employee_tax_ytd_nonnegative"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "tax_year", name="uq_employee_tax_year_declaration"),
    )
    op.create_index("ix_employee_tax_year_declaration_employee_id", "employee_tax_year_declaration", ["employee_id"])
    op.create_index("ix_employee_tax_year_declaration_year", "employee_tax_year_declaration", ["tax_year"])


def downgrade() -> None:
    op.drop_index("ix_employee_tax_year_declaration_year", table_name="employee_tax_year_declaration")
    op.drop_index("ix_employee_tax_year_declaration_employee_id", table_name="employee_tax_year_declaration")
    op.drop_table("employee_tax_year_declaration")
