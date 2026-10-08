"""Shared serialization lock for payroll roster mutations and snapshots."""

from sqlalchemy import text
from sqlmodel import Session

# Stable transaction-scoped PostgreSQL advisory-lock key shared by employee and
# pay-group assignment writes, draft preparation, and finalization.
PAYROLL_ROSTER_LOCK_KEY = 0x4852495350524F53


def lock_payroll_roster(session: Session) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": PAYROLL_ROSTER_LOCK_KEY},
    )
