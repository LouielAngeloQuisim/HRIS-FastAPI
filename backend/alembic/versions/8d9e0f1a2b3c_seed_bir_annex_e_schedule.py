"""Record source references and seed BIR Annex E when no schedule exists.

Revision ID: 8d9e0f1a2b3c
Revises: 7c8d9e0f1a2b
Create Date: 2026-10-07
"""

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa

revision = "8d9e0f1a2b3c"
down_revision = "7c8d9e0f1a2b"
branch_labels = None
depends_on = None

ANNEX_E = "https://bir-cdn.bir.gov.ph/local/pdf/Annex%20E%20RR%2011-2018.pdf"

# Annex E's six columns, encoded as (lower bound, upper bound, fixed tax, rate).
# Values are effective 2023-01-01 onward and transcribed from the official BIR PDF.
SCHEDULES: dict[str, tuple[tuple[str, str | None, str, str], ...]] = {
    "daily": (
        ("0.00", "684.99", "0.00", "0.000"),
        ("685.00", "1095.99", "0.00", "15.000"),
        ("1096.00", "2191.99", "61.65", "20.000"),
        ("2192.00", "5478.99", "280.85", "25.000"),
        ("5479.00", "21917.99", "1102.60", "30.000"),
        ("21918.00", None, "6034.00", "35.000"),
    ),
    "weekly": (
        ("0.00", "4807.99", "0.00", "0.000"),
        ("4808.00", "7691.99", "0.00", "15.000"),
        ("7692.00", "15384.99", "432.60", "20.000"),
        ("15385.00", "38461.99", "1971.20", "25.000"),
        ("38462.00", "153845.99", "7740.45", "30.000"),
        ("153846.00", None, "42355.65", "35.000"),
    ),
    "semi_monthly": (
        ("0.00", "10416.99", "0.00", "0.000"),
        ("10417.00", "16666.99", "0.00", "15.000"),
        ("16667.00", "33332.99", "937.50", "20.000"),
        ("33333.00", "83332.99", "4270.70", "25.000"),
        ("83333.00", "333332.99", "16770.70", "30.000"),
        ("333333.00", None, "91770.70", "35.000"),
    ),
    "monthly": (
        ("0.00", "20832.99", "0.00", "0.000"),
        ("20833.00", "33332.99", "0.00", "15.000"),
        ("33333.00", "66666.99", "1875.00", "20.000"),
        ("66667.00", "166666.99", "8541.80", "25.000"),
        ("166667.00", "666666.99", "33541.80", "30.000"),
        ("666667.00", None, "183541.80", "35.000"),
    ),
}


def upgrade() -> None:
    op.add_column(
        "bir_bracket", sa.Column("source_reference", sa.String(length=512), nullable=True)
    )
    connection = op.get_bind()
    created_at = datetime.now(timezone.utc)
    rows: list[dict[str, object]] = []
    for period, brackets in SCHEDULES.items():
        has_period_table = connection.execute(
            sa.text(
                """SELECT EXISTS (
                    SELECT 1 FROM bir_bracket
                    WHERE period = :period
                      AND effective_date = '2023-01-01'
                      AND is_active = true
                      AND is_deleted = false
                )"""
            ),
            {"period": period},
        ).scalar()
        if has_period_table:
            continue
        rows.extend(
            {
                "id": str(uuid.uuid4()),
                "period": period,
                "bracket_min": minimum,
                "bracket_max": maximum,
                "base_tax": base_tax,
                "excess_rate": rate,
                "effective_date": "2023-01-01",
                "source_reference": ANNEX_E,
                "created_at": created_at,
                "updated_at": created_at,
            }
            for minimum, maximum, base_tax, rate in brackets
        )
    if rows:
        connection.execute(
            sa.text(
                """INSERT INTO bir_bracket
            (id, period, bracket_min, bracket_max, base_tax, excess_rate,
             effective_date, source_reference, is_active, is_deleted, created_at, updated_at)
            VALUES
            (:id, :period, :bracket_min, :bracket_max, :base_tax, :excess_rate,
             :effective_date, :source_reference, true, false, :created_at, :updated_at)"""
            ),
            rows,
        )


def downgrade() -> None:
    # Keep the published schedule data on downgrade; deleting tax-table rows
    # could make an older running application silently calculate zero/incorrect tax.
    op.drop_column("bir_bracket", "source_reference")
