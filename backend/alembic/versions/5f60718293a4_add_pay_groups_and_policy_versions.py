"""Add effective pay groups and versioned payroll policies."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "5f60718293a4"
down_revision = "4e5f60718293"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cutoff_type = postgresql.ENUM(
        "daily", "weekly", "semi_monthly", "monthly", name="cutofftype", create_type=False
    )
    op.create_table(
        "payroll_pay_group",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("cadence", cutoff_type, nullable=False),
        sa.Column("first_period_end_day", sa.Integer(), nullable=True),
        sa.Column("second_period_end_day", sa.Integer(), nullable=True),
        sa.Column("payment_offset_days", sa.Integer(), nullable=False),
        sa.Column("weekend_rule", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_payroll_pay_group_code"),
    )
    op.create_table(
        "employee_pay_group_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("pay_group_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pay_group_id"], ["payroll_pay_group.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "effective_from", name="uq_employee_pay_group_assignment_start"),
    )
    op.create_index("ix_employee_pay_group_assignment_employee_id", "employee_pay_group_assignment", ["employee_id"])
    op.create_index("ix_employee_pay_group_assignment_pay_group_id", "employee_pay_group_assignment", ["pay_group_id"])
    op.create_index(
        "ix_employee_pay_group_assignment_employee_dates",
        "employee_pay_group_assignment",
        ["employee_id", "effective_from", "effective_to"],
    )
    op.create_table(
        "payroll_policy_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["confirmed_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_payroll_policy_version"),
    )
    op.create_index(
        "ix_payroll_policy_version_effective",
        "payroll_policy_version",
        ["effective_from", "effective_to"],
    )


def downgrade() -> None:
    op.drop_index("ix_payroll_policy_version_effective", table_name="payroll_policy_version")
    op.drop_table("payroll_policy_version")
    op.drop_index(
        "ix_employee_pay_group_assignment_employee_dates",
        table_name="employee_pay_group_assignment",
    )
    op.drop_index("ix_employee_pay_group_assignment_pay_group_id", table_name="employee_pay_group_assignment")
    op.drop_index("ix_employee_pay_group_assignment_employee_id", table_name="employee_pay_group_assignment")
    op.drop_table("employee_pay_group_assignment")
    op.drop_table("payroll_pay_group")
