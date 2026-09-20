"""Phase B5 — Audit log routes."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.audit.sink import get_audit_log, list_audit_logs
from app.common.dependencies import SessionDep
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get(
    "/",
    dependencies=[Depends(require_permission("audit", "view"))],
)
def get_audit_logs(
    session: SessionDep,
    user_id: str | None = None,
    module: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    rows, count = list_audit_logs(
        session=session,
        user_id=user_id,
        module=module,
        action=action,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "data": [
            {
                "id": str(r.id),
                "request_id": r.request_id,
                "method": r.method,
                "path": r.path,
                "status_code": r.status_code,
                "duration_ms": r.duration_ms,
                "user_id": str(r.user_id) if r.user_id else None,
                "user_email": r.user_email,
                "ip_address": r.ip_address,
                "module": r.module,
                "action": r.action,
                "security_event": r.security_event,
                "error": r.error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "count": count,
    }


@router.get(
    "/{log_id}",
    dependencies=[Depends(require_permission("audit", "view"))],
)
def get_audit_log_detail(session: SessionDep, log_id: uuid.UUID) -> Any:
    log = get_audit_log(session=session, log_id=log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return {
        "id": str(log.id),
        "request_id": log.request_id,
        "method": log.method,
        "path": log.path,
        "status_code": log.status_code,
        "duration_ms": log.duration_ms,
        "user_id": str(log.user_id) if log.user_id else None,
        "user_email": log.user_email,
        "ip_address": log.ip_address,
        "module": log.module,
        "action": log.action,
        "redacted_body": log.redacted_body,
        "security_event": log.security_event,
        "error": log.error,
        "extra": log.extra,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
