"""Add employer identity needed for payroll tax certificates.

Revision ID: cd6e7f8091a2
Revises: bc5d6e7f8091
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "cd6e7f8091a2"
down_revision = "bc5d6e7f8091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payroll_employer_profile",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("tin_number", sa.String(length=32), nullable=True),
        sa.Column("registered_name", sa.String(length=255), nullable=True),
        sa.Column("registered_address", sa.String(length=512), nullable=True),
        sa.Column("postal_code", sa.String(length=10), nullable=True),
        sa.Column("rdo_code", sa.String(length=8), nullable=True),
        sa.Column("employer_type", sa.String(length=16), nullable=True),
        sa.Column("signatory_name", sa.String(length=255), nullable=True),
        sa.Column("signatory_title", sa.String(length=128), nullable=True),
        sa.Column("source_reference", sa.String(length=512), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 'default'", name="ck_payroll_employer_profile_singleton"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("payroll_employer_profile")
