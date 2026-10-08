"""Add reviewed, tax-year-scoped identity for Form 2316.

Revision ID: f1a2b3c4d5e6
Revises: ef8091a2b3c4
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "ef8091a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employee_tax_year_declaration", sa.Column("employee_tin", sa.String(32)))
    op.add_column("employee_tax_year_declaration", sa.Column("employee_rdo_code", sa.String(8)))
    op.add_column(
        "employee_tax_year_declaration", sa.Column("employee_registered_address", sa.String(512))
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("employee_registered_postal_code", sa.String(10)),
    )
    op.add_column(
        "employee_tax_year_declaration", sa.Column("employee_local_home_address", sa.String(512))
    )
    op.add_column(
        "employee_tax_year_declaration", sa.Column("employee_local_postal_code", sa.String(10))
    )
    op.add_column("employee_tax_year_declaration", sa.Column("previous_employer_tin", sa.String(32)))
    op.add_column(
        "employee_tax_year_declaration", sa.Column("previous_employer_name", sa.String(255))
    )
    op.add_column(
        "employee_tax_year_declaration", sa.Column("previous_employer_address", sa.String(512))
    )
    op.add_column(
        "employee_tax_year_declaration", sa.Column("previous_employer_postal_code", sa.String(10))
    )
    op.add_column(
        "employee_tax_year_declaration", sa.Column("previous_employer_period_from", sa.Date())
    )
    op.add_column(
        "employee_tax_year_declaration", sa.Column("previous_employer_period_to", sa.Date())
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("certificate_identity_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "employee_tax_year_declaration", sa.Column("certificate_identity_source", sa.String(512))
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("certificate_identity_verified_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_employee_tax_declaration_identity_verifier",
        "employee_tax_year_declaration",
        "user",
        ["certificate_identity_verified_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("certificate_identity_verified_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT 1 FROM employee_tax_year_declaration WHERE "
            "certificate_identity_verified IS TRUE OR employee_tin IS NOT NULL "
            "OR employee_rdo_code IS NOT NULL OR employee_registered_address IS NOT NULL "
            "OR employee_registered_postal_code IS NOT NULL OR employee_local_home_address IS NOT NULL "
            "OR employee_local_postal_code IS NOT NULL OR previous_employer_tin IS NOT NULL "
            "OR previous_employer_name IS NOT NULL OR previous_employer_address IS NOT NULL "
            "OR previous_employer_postal_code IS NOT NULL OR previous_employer_period_from IS NOT NULL "
            "OR previous_employer_period_to IS NOT NULL OR certificate_identity_source IS NOT NULL "
            "OR certificate_identity_verified_by IS NOT NULL "
            "OR certificate_identity_verified_at IS NOT NULL LIMIT 1"
        )
    ).first():
        raise RuntimeError(
            "Cannot remove reviewed tax-certificate identity; preserve statutory payroll evidence."
        )
    op.drop_constraint(
        "fk_employee_tax_declaration_identity_verifier",
        "employee_tax_year_declaration",
        type_="foreignkey",
    )
    for column in (
        "certificate_identity_verified_at",
        "certificate_identity_verified_by",
        "certificate_identity_source",
        "certificate_identity_verified",
        "previous_employer_period_to",
        "previous_employer_period_from",
        "previous_employer_postal_code",
        "previous_employer_address",
        "previous_employer_name",
        "previous_employer_tin",
        "employee_local_postal_code",
        "employee_local_home_address",
        "employee_registered_postal_code",
        "employee_registered_address",
        "employee_rdo_code",
        "employee_tin",
    ):
        op.drop_column("employee_tax_year_declaration", column)
