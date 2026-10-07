"""Persist idempotency fingerprints for atomic DTR imports.

Revision ID: 3d4e5f607182
Revises: 2c3d4e5f6071
"""

import sqlalchemy as sa

from alembic import op

revision = "3d4e5f607182"
down_revision = "2c3d4e5f6071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dtr_import_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("excluded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_rows", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("submitted_rows", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("corrections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dtr_import_batch_created_at", "dtr_import_batch", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_dtr_import_batch_created_at", table_name="dtr_import_batch")
    op.drop_table("dtr_import_batch")
