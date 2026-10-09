"""Create effective-dated employee shift assignments."""

import sqlalchemy as sa

from alembic import op

revision = "1b2c3d4e5f60"
down_revision = "8c12ab55d901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_shift_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("shift_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employee_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["shift_id"], ["shift.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employee_shift_assignment_employee_id",
        "employee_shift_assignment",
        ["employee_id"],
    )
    op.create_index(
        "ix_employee_shift_assignment_shift_id",
        "employee_shift_assignment",
        ["shift_id"],
    )
    op.create_index(
        "ix_employee_shift_assignment_employee_dates",
        "employee_shift_assignment",
        ["employee_id", "effective_from", "effective_to"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_employee_shift_assignment_employee_dates",
        table_name="employee_shift_assignment",
    )
    op.drop_index(
        "ix_employee_shift_assignment_shift_id", table_name="employee_shift_assignment"
    )
    op.drop_index(
        "ix_employee_shift_assignment_employee_id",
        table_name="employee_shift_assignment",
    )
    op.drop_table("employee_shift_assignment")
