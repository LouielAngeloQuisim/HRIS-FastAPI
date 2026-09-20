"""change employee_salary unique constraint to include effective_date

Revision ID: 3f0e3e733925
Revises: 54ff6e36652b
Create Date: 2026-09-19 01:52:45.968210

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '3f0e3e733925'
down_revision = '54ff6e36652b'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f('uq_employee_salary_employee_id'), 'employee_salary', type_='unique')
    op.create_unique_constraint('uq_employee_salary_employee_date', 'employee_salary', ['employee_id', 'effective_date'])


def downgrade():
    op.drop_constraint('uq_employee_salary_employee_date', 'employee_salary', type_='unique')
    op.create_unique_constraint(op.f('uq_employee_salary_employee_id'), 'employee_salary', ['employee_id'])
