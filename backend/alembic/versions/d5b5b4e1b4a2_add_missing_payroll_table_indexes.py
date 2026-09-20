"""add missing payroll table indexes (standalone FK indexes)

Revision ID: d5b5b4e1b4a2
Revises: d4b4a4d0b4a1
Create Date: 2026-09-14 08:30:00.000000
"""
from alembic import op

revision = "d5b5b4e1b4a2"
down_revision = "d4b4a4d0b4a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_employee_salary_employee_id", "employee_salary", ["employee_id"], unique=False)
    op.create_index("ix_payroll_run_created_by", "payroll_run", ["created_by"], unique=False)
    op.create_index("ix_payroll_entry_payroll_run_id", "payroll_entry", ["payroll_run_id"], unique=False)
    op.create_index("ix_payroll_entry_employee_id", "payroll_entry", ["employee_id"], unique=False)
    op.create_index("ix_loan_employee_id", "loan", ["employee_id"], unique=False)
    op.create_index("ix_loan_amortization_loan_id", "loan_amortization", ["loan_id"], unique=False)
    op.create_index("ix_integration_mapping_integration_config_id", "integration_mapping", ["integration_config_id"], unique=False)


def downgrade():
    op.drop_index("ix_integration_mapping_integration_config_id", table_name="integration_mapping")
    op.drop_index("ix_loan_amortization_loan_id", table_name="loan_amortization")
    op.drop_index("ix_loan_employee_id", table_name="loan")
    op.drop_index("ix_payroll_entry_employee_id", table_name="payroll_entry")
    op.drop_index("ix_payroll_entry_payroll_run_id", table_name="payroll_entry")
    op.drop_index("ix_payroll_run_created_by", table_name="payroll_run")
    op.drop_index("ix_employee_salary_employee_id", table_name="employee_salary")
