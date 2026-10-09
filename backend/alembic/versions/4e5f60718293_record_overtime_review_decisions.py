"""Record bounded overtime review decisions on attendance records."""

import sqlalchemy as sa

from alembic import op

revision = "4e5f60718293"
down_revision = "3d4e5f607182"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_time_record",
        sa.Column("overtime_approved_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "daily_time_record",
        sa.Column("overtime_decision_reason", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "daily_time_record",
        sa.Column("overtime_decided_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "daily_time_record",
        sa.Column("overtime_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_daily_time_record_overtime_decided_by_user",
        "daily_time_record",
        "user",
        ["overtime_decided_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_daily_time_record_overtime_approved_minutes_nonnegative",
        "daily_time_record",
        "overtime_approved_minutes IS NULL OR overtime_approved_minutes >= 0",
    )
    op.create_check_constraint(
        "ck_daily_time_record_overtime_approved_minutes_bounded",
        "daily_time_record",
        "overtime_approved_minutes IS NULL OR (overtime_minutes IS NOT NULL AND overtime_approved_minutes <= overtime_minutes)",
    )
    op.create_table(
        "dtr_overtime_decision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_time_record_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("eligible_minutes", sa.Integer(), nullable=False),
        sa.Column("approved_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('approved', 'rejected')", name="ck_dtr_overtime_decision_status"
        ),
        sa.ForeignKeyConstraint(
            ["daily_time_record_id"], ["daily_time_record.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dtr_overtime_decision_daily_time_record_id",
        "dtr_overtime_decision",
        ["daily_time_record_id"],
    )
    op.create_index(
        "ix_dtr_overtime_decision_record_created",
        "dtr_overtime_decision",
        ["daily_time_record_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dtr_overtime_decision_record_created", table_name="dtr_overtime_decision"
    )
    op.drop_index(
        "ix_dtr_overtime_decision_daily_time_record_id",
        table_name="dtr_overtime_decision",
    )
    op.drop_table("dtr_overtime_decision")
    op.drop_constraint(
        "ck_daily_time_record_overtime_approved_minutes_bounded",
        "daily_time_record",
        type_="check",
    )
    op.drop_constraint(
        "ck_daily_time_record_overtime_approved_minutes_nonnegative",
        "daily_time_record",
        type_="check",
    )
    op.drop_constraint(
        "fk_daily_time_record_overtime_decided_by_user",
        "daily_time_record",
        type_="foreignkey",
    )
    op.drop_column("daily_time_record", "overtime_decided_at")
    op.drop_column("daily_time_record", "overtime_decided_by")
    op.drop_column("daily_time_record", "overtime_decision_reason")
    op.drop_column("daily_time_record", "overtime_approved_minutes")
