"""Add durable payroll generation fingerprint.

Revision ID: 8c12ab55d901
Revises: 7ab12cd44e91
"""
from alembic import op
import sqlalchemy as sa

revision = "8c12ab55d901"
down_revision = "7ab12cd44e91"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payroll_run", sa.Column("generation_fingerprint", sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column("payroll_run", "generation_fingerprint")
