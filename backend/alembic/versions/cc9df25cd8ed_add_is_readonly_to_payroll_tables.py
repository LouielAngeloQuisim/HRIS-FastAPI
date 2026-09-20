"""add is_readonly to payroll_run and payroll_entry (Phase B6)

Revision ID: cc9df25cd8ed
Revises: 9c7a54c3b67f
Create Date: 2026-09-15 04:08:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "cc9df25cd8ed"
down_revision = "9c7a54c3b67f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payroll_run",
        sa.Column("is_readonly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "payroll_entry",
        sa.Column("is_readonly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade():
    op.drop_column("payroll_entry", "is_readonly")
    op.drop_column("payroll_run", "is_readonly")
