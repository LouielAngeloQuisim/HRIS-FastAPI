"""add pre_payday_check to notificationtype enum

Revision ID: a1b2c3d4e5f6
Revises: cc9df25cd8ed
Create Date: 2026-09-15 13:20:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "cc9df25cd8ed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase B5 pre-payday compliance notifications use a dedicated type; the
    # original enum predates it and must be extended in-place.
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'pre_payday_check'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; leaving it is harmless.
    pass
