"""Write operations for Phase 1 resources.

Follows the Phase 0 service shape (keyword-only args, ``session`` first,
``model_validate``/``sqlmodel_update``, add/commit/refresh). Soft delete is the
uniform Phase 1 convention: ``is_deleted = True`` + ``deleted_at`` rather than a
physical delete.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import EmployeeAdditionalRecords, EmployeeAttachments
from app.employee.selectors import (
    count_active_categories_referencing,
    get_active_by_id,
    get_additional_records_for_employee,
)

T = TypeVar("T")


def create_obj(*, session: Session, model: type[T], data) -> T:
    db_obj = model.model_validate(data)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_obj(*, session: Session, db_obj: T, data) -> T:
    update_dict = data.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_dict)
    db_obj.updated_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def soft_delete_obj(*, session: Session, db_obj: T) -> T:
    db_obj.is_deleted = True
    db_obj.deleted_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def ensure_not_referenced_by_active_category(
    *, session: Session, blocks_id: uuid.UUID | None = None, lot_id: uuid.UUID | None = None
) -> bool:
    """Return True if deletable, False if an ACTIVE Category still references it."""
    return (
        count_active_categories_referencing(
            session=session, blocks_id=blocks_id, lot_id=lot_id
        )
        == 0
    )


def get_or_404(*, session: Session, model: type[T], obj_id: uuid.UUID) -> T:
    """Fetch a non-deleted row; used by routes that raise 404 on absence."""
    db_obj = get_active_by_id(session=session, model=model, obj_id=obj_id)
    if db_obj is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Resource not found")
    return db_obj


def upsert_additional_records(
    *, session: Session, employee_id: uuid.UUID, data
) -> EmployeeAdditionalRecords:
    """Create or update the single 201-file annex row for an employee."""
    existing = get_additional_records_for_employee(session=session, employee_id=employee_id)
    update_dict = data.model_dump(exclude_unset=True)
    if existing is None:
        db_obj = EmployeeAdditionalRecords.model_validate(
            update_dict, update={"employee_id": employee_id}
        )
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj
    existing.sqlmodel_update(update_dict)
    existing.updated_at = datetime.now(timezone.utc)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def _ensure_upload_dir() -> Path:
    upload_dir = Path(settings.FILE_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def store_attachment_file(*, employee_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Persist the file outside the web root and return the stored path.

    Matches the design: files live on disk/object storage, only the path is
    stored on the DB row. The legacy bug of dumping files into the public web
    root is deliberately not reproduced.
    """
    from fastapi import HTTPException

    if not filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    safe_name = Path(filename).name  # strip any directory components
    upload_dir = _ensure_upload_dir() / str(employee_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}-{safe_name}"
    target = upload_dir / stored_name
    try:
        target.write_bytes(content)
    except OSError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Could not store attachment") from exc
    return str(target)


def create_attachment(
    *, session: Session, employee_id: uuid.UUID, data, file_path: str, attachment_size: int
) -> EmployeeAttachments:
    db_obj = EmployeeAttachments.model_validate(
        data,
        update={
            "employee_id": employee_id,
            "file_path": file_path,
            "attachment_size": attachment_size,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def soft_delete_attachment(
    *, session: Session, db_obj: EmployeeAttachments
) -> EmployeeAttachments:
    db_obj.is_deleted = True
    db_obj.deleted_at = datetime.now(timezone.utc)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj
