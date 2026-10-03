"""add partial unique index for DTR import idempotency (QA-01)

Revision ID: 7ab12cd44e91
Revises: 3f0e3e733925
Create Date: 2026-10-03 04:00:00.000000

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '7ab12cd44e91'
down_revision = '3f0e3e733925'
branch_labels = None
depends_on = None


def upgrade():
    # QA-01 import idempotency: the SELECT-then-INSERT replay check in
    # create_dtr is not atomic on its own, so the database enforces "at most
    # one ACTIVE row per (employee_id, source_ref)". Partial so that soft-
    # deleted punches never participate — a deliberate fresh re-import under
    # the same key creates a new row while replay attempts against the
    # deleted identity are rejected with 409 by create_dtr (no automatic
    # resurrection) — and keyless manual creates (source_ref IS NULL) are
    # exempt.
    #
    # DATA SAFETY: this migration never deletes or alters attendance rows.
    # If the deployed data already violates the invariant (two active rows
    # sharing one employee+key — only possible from non-wizard writes), the
    # unique index cannot be created. Instead of guessing which punch to
    # keep or silently clearing identities, the migration FAILS with a
    # diagnostic listing the offending identities, so an operator resolves
    # them deliberately before deploying.
    dup = op.get_bind().execute(
        text(
            """
            SELECT employee_id, source_ref, count(*) AS c,
                   array_agg(id::text ORDER BY created_at) AS ids
            FROM daily_time_record
            WHERE is_deleted = false AND source_ref IS NOT NULL
            GROUP BY employee_id, source_ref
            HAVING count(*) > 1
            ORDER BY employee_id, source_ref
            """
        )
    ).fetchall()
    if dup:
        detail = "; ".join(
            f"employee={row.employee_id} source_ref={row.source_ref!r} rows={row.c} ids={row.ids}"
            for row in dup[:20]
        )
        raise RuntimeError(
            "Cannot create uq_daily_time_record_source_ref_active: "
            f"{len(dup)} duplicate (employee_id, source_ref) identities exist "
            "in daily_time_record. No rows were modified. Resolve them "
            "deliberately (restore, delete, or re-key the intended rows) and "
            f"re-run the migration. Offenders: {detail}"
        )
    op.create_index(
        "uq_daily_time_record_source_ref_active",
        "daily_time_record",
        ["employee_id", "source_ref"],
        unique=True,
        postgresql_where=text("is_deleted = false AND source_ref IS NOT NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_daily_time_record_source_ref_active",
        table_name="daily_time_record",
    )
