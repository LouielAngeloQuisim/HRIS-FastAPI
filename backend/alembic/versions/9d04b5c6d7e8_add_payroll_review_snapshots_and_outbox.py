"""Add payroll review snapshots and durable payslip-delivery outbox."""

import sqlalchemy as sa

from alembic import op

revision = "9d04b5c6d7e8"
down_revision = "8c93a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payroll_run", sa.Column("workflow_status", sa.String(32), server_default="draft", nullable=False))
    op.add_column("payroll_run", sa.Column("pay_group_id", sa.Uuid(), nullable=True))
    op.add_column("payroll_run", sa.Column("policy_version_id", sa.Uuid(), nullable=True))
    op.add_column("payroll_run", sa.Column("payment_date", sa.Date(), nullable=True))
    op.add_column("payroll_run", sa.Column("input_fingerprint", sa.String(64), nullable=True))
    op.add_column("payroll_run", sa.Column("finalized_by", sa.Uuid(), nullable=True))
    op.add_column("payroll_run", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payroll_run", sa.Column("frozen_snapshot", sa.JSON(), nullable=True))
    op.create_foreign_key("fk_payroll_run_pay_group_id", "payroll_run", "payroll_pay_group", ["pay_group_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_payroll_run_policy_version_id", "payroll_run", "payroll_policy_version", ["policy_version_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_payroll_run_finalized_by", "payroll_run", "user", ["finalized_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_payroll_run_pay_group_id", "payroll_run", ["pay_group_id"])
    op.create_index("ix_payroll_run_policy_version_id", "payroll_run", ["policy_version_id"])

    op.add_column("payroll_entry", sa.Column("review_state", sa.String(16), server_default="ready", nullable=False))
    op.add_column("payroll_entry", sa.Column("reviewed_by", sa.Uuid(), nullable=True))
    op.add_column("payroll_entry", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payroll_entry", sa.Column("review_reason", sa.String(1024), nullable=True))
    op.add_column("payroll_entry", sa.Column("calculation_version", sa.String(64), nullable=True))
    op.add_column("payroll_entry", sa.Column("input_fingerprint", sa.String(64), nullable=True))
    op.add_column("payroll_entry", sa.Column("input_snapshot", sa.JSON(), server_default="{}", nullable=False))
    op.add_column("payroll_entry", sa.Column("blockers", sa.JSON(), server_default="[]", nullable=False))
    op.create_foreign_key("fk_payroll_entry_reviewed_by", "payroll_entry", "user", ["reviewed_by"], ["id"], ondelete="SET NULL")

    op.create_table(
        "payroll_delivery_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payroll_entry_id", sa.Uuid(), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("recipient_snapshot", sa.String(320), nullable=True),
        sa.Column("content_snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(16), server_default="scheduled", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_action_by", sa.Uuid(), nullable=True),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_action_reason", sa.String(1024), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payroll_entry_id"], ["payroll_entry.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["last_action_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payroll_entry_id", "document_version", name="uq_payroll_delivery_document"),
    )
    op.create_index("ix_payroll_delivery_outbox_payroll_entry_id", "payroll_delivery_outbox", ["payroll_entry_id"])
    op.create_index("ix_payroll_delivery_due", "payroll_delivery_outbox", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_payroll_delivery_due", table_name="payroll_delivery_outbox")
    op.drop_index("ix_payroll_delivery_outbox_payroll_entry_id", table_name="payroll_delivery_outbox")
    op.drop_table("payroll_delivery_outbox")
    op.drop_constraint("fk_payroll_entry_reviewed_by", "payroll_entry", type_="foreignkey")
    for column in ("blockers", "input_snapshot", "input_fingerprint", "calculation_version", "review_reason", "reviewed_at", "reviewed_by", "review_state"):
        op.drop_column("payroll_entry", column)
    op.drop_index("ix_payroll_run_policy_version_id", table_name="payroll_run")
    op.drop_index("ix_payroll_run_pay_group_id", table_name="payroll_run")
    op.drop_constraint("fk_payroll_run_finalized_by", "payroll_run", type_="foreignkey")
    op.drop_constraint("fk_payroll_run_policy_version_id", "payroll_run", type_="foreignkey")
    op.drop_constraint("fk_payroll_run_pay_group_id", "payroll_run", type_="foreignkey")
    for column in ("frozen_snapshot", "finalized_at", "finalized_by", "input_fingerprint", "payment_date", "policy_version_id", "pay_group_id", "workflow_status"):
        op.drop_column("payroll_run", column)
