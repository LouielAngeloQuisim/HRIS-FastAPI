"""Bounded daily audit retention. Deletion is disabled unless explicitly enabled."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.audit.models import AuditLog
from app.config.settings import settings

logger = logging.getLogger(__name__)


def prune_audit_logs(
    session: Session,
    *,
    now: datetime,
    retention_days: int,
    batch_size: int = 1000,
    enabled: bool = False,
) -> int:
    """Return eligible rows in one batch; only commit deletions when enabled."""
    if retention_days <= 0 or batch_size <= 0:
        raise ValueError("Retention days and batch size must be positive")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware cutoff is required")
    cutoff = now - timedelta(days=retention_days)
    ids = list(
        session.exec(
            select(AuditLog.id)
            .where(col(AuditLog.created_at) < cutoff)
            .order_by(col(AuditLog.created_at), col(AuditLog.id))
            .limit(batch_size)
        ).all()
    )
    if enabled and ids:
        session.execute(delete(AuditLog).where(col(AuditLog.id).in_(ids)))
        session.commit()
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheduled", action="store_true", help="Run daily")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from app.config.database import engine

    while True:
        try:
            with Session(engine) as session:
                count = prune_audit_logs(
                    session,
                    now=datetime.now(timezone.utc),
                    retention_days=settings.AUDIT_RETENTION_DAYS,
                    batch_size=settings.AUDIT_RETENTION_BATCH_SIZE,
                    enabled=settings.AUDIT_RETENTION_ENABLED,
                )
            logger.info(
                "audit retention enabled=%s eligible_in_batch=%d",
                settings.AUDIT_RETENTION_ENABLED,
                count,
            )
        except Exception:
            # Never log database credentials, records or exception messages.
            logger.error("Audit retention failed; no record details logged")
            if not args.scheduled:
                raise SystemExit(1) from None
        if not args.scheduled:
            return
        time.sleep(86400)


if __name__ == "__main__":
    main()
