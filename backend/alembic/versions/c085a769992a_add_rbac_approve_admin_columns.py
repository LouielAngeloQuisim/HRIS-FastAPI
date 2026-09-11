"""add can_approve and can_admin columns to role_permission (Phase b3)

Revision ID: c085a769992a
Revises: c3b726b97e47
Create Date: 2026-09-02 08:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c085a769992a'
down_revision = 'c3b726b97e47'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('role_permission', sa.Column('can_approve', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('role_permission', sa.Column('can_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('role_permission', 'can_admin')
    op.drop_column('role_permission', 'can_approve')
