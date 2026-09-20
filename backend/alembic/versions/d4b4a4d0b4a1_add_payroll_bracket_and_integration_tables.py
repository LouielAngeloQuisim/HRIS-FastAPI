"""add payroll bracket, integration, salary, run, entry, loan tables (Phase B4A)

Revision ID: d4b4a4d0b4a1
Revises: b9748b3e7b5c
Create Date: 2026-09-14 08:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "d4b4a4d0b4a1"
down_revision = "b9748b3e7b5c"
branch_labels = None
depends_on = None


def upgrade():
    # --- sss_bracket ---
    op.create_table(
        "sss_bracket",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("msc_min", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("msc_max", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("employer_ss", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("employer_ec", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("employer_mpf", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("employee_ss", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("employee_mpf", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sss_bracket_effective_date", "sss_bracket", ["effective_date"], unique=False)

    # --- philhealth_bracket ---
    op.create_table(
        "philhealth_bracket",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("salary_min", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("salary_max", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("rate", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("employer_share", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("employee_share", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_philhealth_bracket_effective_date", "philhealth_bracket", ["effective_date"], unique=False)

    # --- pagibig_bracket ---
    op.create_table(
        "pagibig_bracket",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("salary_min", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("salary_max", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("employee_rate", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("employer_rate", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pagibig_bracket_effective_date", "pagibig_bracket", ["effective_date"], unique=False)

    # --- bir_bracket ---
    op.create_table(
        "bir_bracket",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.Enum("daily", "weekly", "semi_monthly", "monthly", name="cutofftype"), nullable=False),
        sa.Column("bracket_min", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("bracket_max", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("base_tax", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("excess_rate", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bir_bracket_period", "bir_bracket", ["period"], unique=False)
    op.create_index("ix_bir_bracket_effective_date", "bir_bracket", ["effective_date"], unique=False)

    # --- employee_salary ---
    op.create_table(
        "employee_salary",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("basic_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(length=3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("pay_type", sa.Enum("monthly", "daily", "hourly", name="paytype"), nullable=False),
        sa.Column("overtime_rate", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("absent_penalty_rate", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("non_taxable_allowance", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("de_minimis_monthly", sa.JSON(), nullable=True),
        sa.Column("thirteenth_month_exempt_portion", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", name="uq_employee_salary_employee_id"),
    )
    op.create_index("ix_employee_salary_employee_deleted", "employee_salary", ["employee_id", "is_deleted"], unique=False)
    op.create_index("ix_employee_salary_effective_date", "employee_salary", ["effective_date"], unique=False)

    # --- payroll_run ---
    op.create_table(
        "payroll_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cutoff_type", sa.Enum("daily", "weekly", "semi_monthly", "monthly", name="cutofftype"), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("draft", "approved", "paid", "void", name="payrollrunstatus"), nullable=False),
        sa.Column("adjustment_type", sa.Enum("regular", "supplemental", "post_run_correction", name="payrolladjustmenttype"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- payroll_entry ---
    op.create_table(
        "payroll_entry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payroll_run_id", sa.Uuid(), nullable=True),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("basic_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("rate_date_from", sa.Date(), nullable=False),
        sa.Column("rate_date_to", sa.Date(), nullable=False),
        sa.Column("earnings", sa.JSON(), nullable=True),
        sa.Column("deductions", sa.JSON(), nullable=True),
        sa.Column("gross_pay", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("net_pay", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("overtime_pay", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("thirteenth_month", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("non_taxable_income", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("taxable_income", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payroll_run_id"], ["payroll_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_entry_run_employee"),
    )
    op.create_index("ix_payroll_entry_run_deleted", "payroll_entry", ["payroll_run_id", "is_deleted"], unique=False)
    op.create_index("ix_payroll_entry_employee_deleted", "payroll_entry", ["employee_id", "is_deleted"], unique=False)

    # --- loan ---
    op.create_table(
        "loan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("loan_type", sa.Enum("salary", "ssls", "pagibig", "other", name="loantype"), nullable=False),
        sa.Column("principal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("balance", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("terms_months", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loan_employee_deleted", "loan", ["employee_id", "is_deleted"], unique=False)

    # --- loan_amortization ---
    op.create_table(
        "loan_amortization",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("loan_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["loan_id"], ["loan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loan_amortization_loan_deleted", "loan_amortization", ["loan_id", "is_deleted"], unique=False)

    # --- integration_config ---
    op.create_table(
        "integration_config",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("connector_type", sa.Enum("generic_rest", name="connectortype"), nullable=False),
        sa.Column("api_url", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("http_method", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("schedule", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- integration_mapping ---
    op.create_table(
        "integration_mapping",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("integration_config_id", sa.Uuid(), nullable=True),
        sa.Column("source_json_path", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("target_field", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("transform_rule", sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["integration_config_id"], ["integration_config.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_mapping_config_deleted", "integration_mapping", ["integration_config_id", "is_deleted"], unique=False)


def downgrade():
    op.drop_table("integration_mapping")
    op.drop_table("integration_config")
    op.drop_table("loan_amortization")
    op.drop_table("loan")
    op.drop_table("payroll_entry")
    op.drop_table("payroll_run")
    op.drop_table("employee_salary")
    op.drop_table("bir_bracket")
    op.drop_table("pagibig_bracket")
    op.drop_table("philhealth_bracket")
    op.drop_table("sss_bracket")
