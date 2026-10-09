"""Add a Manila-calendar work date to attendance records.

Revision ID: 2c3d4e5f6071
Revises: 1b2c3d4e5f60
"""

import sqlalchemy as sa

from alembic import op

revision = "2c3d4e5f6071"
down_revision = "1b2c3d4e5f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("daily_time_record", sa.Column("work_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE daily_time_record
        SET work_date = (login_date AT TIME ZONE 'Asia/Manila')::date
        WHERE login_date IS NOT NULL AND work_date IS NULL
        """
    )
    op.create_index(
        "ix_daily_time_record_employee_work_date",
        "daily_time_record",
        ["employee_id", "work_date"],
    )
    op.create_index(
        "ix_daily_time_record_work_date", "daily_time_record", ["work_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_daily_time_record_work_date", table_name="daily_time_record")
    op.drop_index(
        "ix_daily_time_record_employee_work_date", table_name="daily_time_record"
    )
    op.drop_column("daily_time_record", "work_date")
