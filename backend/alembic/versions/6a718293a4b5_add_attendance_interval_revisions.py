"""Add immutable multi-interval attendance revisions."""

import sqlalchemy as sa

from alembic import op

revision = "6a718293a4b5"
down_revision = "5f60718293a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_time_record",
        sa.Column("interval_revision", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "dtr_attendance_interval",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_time_record_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_row", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("end_at > start_at", name="ck_dtr_interval_positive_duration"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["daily_time_record_id"], ["daily_time_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_time_record_id", "revision", "sequence", name="uq_dtr_interval_revision_sequence"),
    )
    op.create_index("ix_dtr_attendance_interval_daily_time_record_id", "dtr_attendance_interval", ["daily_time_record_id"])
    op.create_index("ix_dtr_interval_record_current_revision", "dtr_attendance_interval", ["daily_time_record_id", "revision", "sequence"])


def downgrade() -> None:
    op.drop_index("ix_dtr_interval_record_current_revision", table_name="dtr_attendance_interval")
    op.drop_index("ix_dtr_attendance_interval_daily_time_record_id", table_name="dtr_attendance_interval")
    op.drop_table("dtr_attendance_interval")
    op.drop_column("daily_time_record", "interval_revision")
