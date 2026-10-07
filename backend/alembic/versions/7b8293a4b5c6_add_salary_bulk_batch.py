"""Record idempotent identities for atomic, explicit salary batches."""

import sqlalchemy as sa

from alembic import op

revision = "7b8293a4b5c6"
down_revision = "6a718293a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_salary_bulk_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("result_salary_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("employee_salary_bulk_batch")
