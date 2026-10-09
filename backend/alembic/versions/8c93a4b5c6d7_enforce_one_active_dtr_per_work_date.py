"""Enforce one active daily attendance record per employee and work date.

Legacy duplicate rows are reported with their IDs and are never changed by this
migration. Operators must reconcile those rows before retrying the upgrade.
"""

import sqlalchemy as sa

from alembic import op

revision = "8c93a4b5c6d7"
down_revision = "7b8293a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicate_keys = connection.execute(
        sa.text(
            """
            SELECT employee_id, work_date
            FROM daily_time_record
            WHERE is_deleted = false AND work_date IS NOT NULL
            GROUP BY employee_id, work_date
            HAVING count(*) > 1
            ORDER BY work_date, employee_id
            LIMIT 1000
            """
        )
    ).mappings().all()
    if duplicate_keys:
        duplicates = []
        for key in duplicate_keys:
            ids = connection.execute(
                sa.text(
                    "SELECT id FROM daily_time_record "
                    "WHERE employee_id = :employee_id AND work_date = :work_date "
                    "AND is_deleted = false ORDER BY id"
                ),
                {"employee_id": key["employee_id"], "work_date": key["work_date"]},
            ).scalars().all()
            duplicates.append({**key, "record_ids": ids})
        details = "; ".join(
            f"employee={row['employee_id']} work_date={row['work_date']} records={row['record_ids']}"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot enforce one active DTR per employee/work date. "
            "No attendance rows were changed; reconcile these legacy duplicates "
            f"and retry the migration: {details}"
        )

    op.create_index(
        "uq_daily_time_record_employee_work_date_active",
        "daily_time_record",
        ["employee_id", "work_date"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND work_date IS NOT NULL"),
        sqlite_where=sa.text("is_deleted = 0 AND work_date IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_daily_time_record_employee_work_date_active",
        table_name="daily_time_record",
    )
