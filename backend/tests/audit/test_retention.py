from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect
from sqlmodel import Session

from app.audit.models import AuditLog
from app.audit.retention import prune_audit_logs

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def make_logs(db):
    rows = [
        AuditLog(
            method="GET", path="/retention-test", created_at=NOW - timedelta(days=91)
        ),
        AuditLog(
            method="GET", path="/retention-test", created_at=NOW - timedelta(days=90)
        ),
        AuditLog(
            method="GET", path="/retention-test", created_at=NOW - timedelta(days=89)
        ),
    ]
    for row in rows:
        db.add(row)
    db.commit()
    return rows


def cleanup(db, rows):
    for row in rows:
        existing = db.get(AuditLog, inspect(row).identity[0])
        if existing:
            db.delete(existing)
    db.commit()


def test_retention_disabled_preserves_eligible_records(db: Session):
    rows = make_logs(db)
    try:
        assert prune_audit_logs(db, now=NOW, retention_days=90) >= 1
        assert db.get(AuditLog, rows[0].id) is not None
    finally:
        cleanup(db, rows)


def test_retention_deletes_only_before_boundary(db: Session):
    rows = make_logs(db)
    old_id, boundary_id, recent_id = (row.id for row in rows)
    try:
        prune_audit_logs(db, now=NOW, retention_days=90, enabled=True)
        db.expire_all()
        assert db.get(AuditLog, old_id) is None
        assert db.get(AuditLog, boundary_id) is not None
        assert db.get(AuditLog, recent_id) is not None
    finally:
        cleanup(db, rows)


def test_retention_batch_is_bounded(db: Session):
    rows = [
        AuditLog(
            method="GET",
            path="/retention-test",
            created_at=NOW - timedelta(days=1000 + i),
        )
        for i in range(3)
    ]
    for row in rows:
        db.add(row)
    db.commit()
    try:
        assert (
            prune_audit_logs(db, now=NOW, retention_days=90, batch_size=1, enabled=True)
            == 1
        )
        db.expire_all()
        assert (
            sum(db.get(AuditLog, inspect(row).identity[0]) is not None for row in rows)
            == 2
        )
    finally:
        cleanup(db, rows)


@pytest.mark.parametrize("days,batch", [(0, 1), (-1, 1), (90, 0)])
def test_invalid_retention_rejected(db: Session, days, batch):
    with pytest.raises(ValueError):
        prune_audit_logs(
            db, now=NOW, retention_days=days, batch_size=batch, enabled=True
        )


def test_naive_cutoff_rejected(db: Session):
    with pytest.raises(ValueError):
        prune_audit_logs(db, now=NOW.replace(tzinfo=None), retention_days=90)
