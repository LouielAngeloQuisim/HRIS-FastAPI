"""Atomic CSV attendance import validation, fingerprinting and commit."""

import hashlib
import json
import uuid
from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.attendance.models import DailyTimeRecord, DtrImportBatch
from app.attendance.schemas import (
    DailyTimeRecordCreate,
    DailyTimeRecordPublic,
    DtrImportBatchCommitResponse,
    DtrImportBatchRequest,
    DtrImportExcluded,
    DtrImportIssue,
    DtrImportPreflightResponse,
)
from app.attendance.selectors import get_employee_by_code, get_employee_shift_assignment
from app.attendance.services import (
    _as_utc,
    create_dtr,
    replace_dtr_intervals,
    resolve_attendance_work_date,
)
from app.employee.models import EmployeeRecords
from app.user.models import User


def payload_fingerprint(request: DtrImportBatchRequest) -> str:
    payload = [row.model_dump(mode="json") for row in request.rows]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source_ref(batch_id: uuid.UUID, row_index: int) -> str:
    return f"dtr-import-{batch_id}-r{row_index}"


def _issue(
    row_index: int,
    employee_code: str,
    code: str,
    message: str,
    work_date: date | None = None,
) -> DtrImportIssue:
    return DtrImportIssue(
        row_index=row_index,
        employee_code=employee_code,
        work_date=work_date,
        code=code,
        message=message,
    )


def _out_of_scope_issues(
    *, session: Session, request: DtrImportBatchRequest, actor_id: uuid.UUID
) -> list[DtrImportIssue]:
    """Apply the same employee-row visibility boundary as DTR list/reconcile."""
    actor = session.get(User, actor_id)
    if actor is None or actor.is_superuser:
        return []

    issues: list[DtrImportIssue] = []
    for index, row in enumerate(request.rows):
        employee = session.exec(
            select(EmployeeRecords).where(
                EmployeeRecords.employee_code == row.employee_code.strip(),
                EmployeeRecords.is_deleted == False,  # noqa: E712
            )
        ).first()
        if employee is not None and employee.user_id != actor_id:
            issues.append(
                _issue(
                    index,
                    row.employee_code,
                    "employee_out_of_scope",
                    "You are not authorized to import attendance for this employee.",
                )
            )
    return issues


def preflight_import(
    *, session: Session, request: DtrImportBatchRequest, actor_id: uuid.UUID
) -> DtrImportPreflightResponse:
    """Validate a batch by exercising server rules inside a rolled-back savepoint."""
    fingerprint = payload_fingerprint(request)
    scope_issues = _out_of_scope_issues(
        session=session, request=request, actor_id=actor_id
    )
    if scope_issues:
        return DtrImportPreflightResponse(
            batch_id=request.batch_id,
            payload_fingerprint=fingerprint,
            valid=False,
            row_count=len(request.rows),
            issues=scope_issues,
            excluded=[],
        )
    batch = session.get(DtrImportBatch, request.batch_id)
    if batch is not None:
        if batch.created_by != actor_id:
            return DtrImportPreflightResponse(
                batch_id=request.batch_id,
                payload_fingerprint=fingerprint,
                valid=False,
                row_count=len(request.rows),
                issues=[
                    _issue(
                        0,
                        "",
                        "batch_identity_unavailable",
                        "This import identity is unavailable; start a new import batch.",
                    )
                ],
                excluded=[],
            )
        if batch.payload_fingerprint != fingerprint:
            return DtrImportPreflightResponse(
                batch_id=request.batch_id,
                payload_fingerprint=fingerprint,
                valid=False,
                row_count=len(request.rows),
                issues=[
                    _issue(
                        0,
                        "",
                        "batch_identity_conflict",
                        "This import identity was already used with different attendance data.",
                    )
                ],
                excluded=[],
            )
        return DtrImportPreflightResponse(
            batch_id=request.batch_id,
            payload_fingerprint=fingerprint,
            valid=True,
            row_count=len(request.rows),
            issues=[],
            excluded=[],
        )

    issues: list[DtrImportIssue] = []
    excluded: list[DtrImportExcluded] = []
    row_context: dict[int, tuple[EmployeeRecords, date, uuid.UUID | None]] = {}
    grouped_rows: dict[tuple[uuid.UUID, date], list[int]] = {}
    for index, row in enumerate(request.rows):
        employee = get_employee_by_code(session=session, code=row.employee_code.strip())
        if employee is None:
            continue
        work_date = resolve_attendance_work_date(
            session=session, employee_id=employee.id, login_date=row.login_date
        )
        assignment = get_employee_shift_assignment(
            session=session, employee_id=employee.id, work_date=work_date
        )
        row_context[index] = (employee, work_date, assignment.shift_id if assignment else None)
        grouped_rows.setdefault((employee.id, work_date), []).append(index)
    duplicate_rows: set[int] = set()
    for (_employee_id, work_date), indexes in grouped_rows.items():
        if len(indexes) < 2:
            continue
        duplicate_rows.update(indexes)
        for index in indexes:
            issues.append(
                _issue(
                    index,
                    request.rows[index].employee_code,
                    "duplicate_employee_work_date",
                    f"This employee appears more than once on {work_date}; correct the rows so only one daily record remains before saving.",
                    work_date,
                )
            )

    probe = session.begin_nested()
    try:
        for index, row in enumerate(request.rows):
            if index in duplicate_rows:
                continue
            context = row_context.get(index)
            if context is not None:
                employee, hinted_work_date, assigned_shift_id = context
                same_day = list(session.exec(
                    select(DailyTimeRecord).where(
                        DailyTimeRecord.employee_id == employee.id,
                        DailyTimeRecord.work_date == hinted_work_date,
                        col(DailyTimeRecord.is_deleted).is_(False),
                    )
                ).all())
                if same_day:
                    identical = [existing for existing in same_day
                        if _as_utc(existing.login_date) == _as_utc(row.login_date)
                        and _as_utc(existing.logout_date) == _as_utc(row.logout_date)
                        and assigned_shift_id is not None
                        and existing.shift_id == assigned_shift_id]
                    if len(same_day) == 1 and len(identical) == 1:
                        excluded.append(DtrImportExcluded(
                            row_index=index,
                            employee_code=row.employee_code,
                            existing_record_id=identical[0].id,
                            reason="Identical attendance is already saved; excluded from this import.",
                        ))
                    else:
                        issues.append(_issue(
                            index,
                            row.employee_code,
                            "saved_attendance_conflict",
                            "Attendance already exists for this employee and work date with different or ambiguous data; use the attendance adjustment workflow.",
                            hinted_work_date,
                        ))
                    continue
            payload = DailyTimeRecordCreate(
                employee_code=row.employee_code.strip(),
                login_date=row.login_date,
                logout_date=row.logout_date,
                shift_code=row.shift_code,
                source_ref=_source_ref(request.batch_id, index),
            )
            try:
                candidate, replayed = create_dtr(
                    session=session,
                    data=payload,
                    actor_id=actor_id,
                    commit=False,
                )
                if row.intervals:
                    replace_dtr_intervals(
                        session=session,
                        dtr=candidate,
                        intervals=row.intervals,
                        actor_id=actor_id,
                        commit=False,
                    )
            except HTTPException as exc:
                detail = str(exc.detail)
                detail_lower = detail.lower()
                if "employee not found" in detail_lower:
                    issue_code = "missing_employee"
                elif "shift" in detail_lower and ("assigned" in detail_lower or "assignment" in detail_lower or "match" in detail_lower):
                    issue_code = "missing_shift"
                elif "login_date" in detail_lower or "logout_date" in detail_lower:
                    issue_code = "incomplete_punch"
                elif "attendance already exists for employee" in detail_lower or "attendance already exists for this employee and work date" in detail_lower:
                    issue_code = "saved_attendance_conflict"
                else:
                    issue_code = "attendance_invalid"
                issues.append(
                    _issue(
                        index,
                        row.employee_code,
                        issue_code,
                        detail,
                    )
                )
                continue

            candidate_work_date = candidate.work_date
            if candidate_work_date is None:
                issues.append(
                    _issue(
                        index,
                        row.employee_code,
                        "attendance_invalid",
                        "The server could not determine this attendance work date.",
                    )
                )
                continue
            same_day = list(
                session.exec(
                    select(DailyTimeRecord).where(
                        DailyTimeRecord.employee_id == candidate.employee_id,
                        DailyTimeRecord.work_date == candidate_work_date,
                        col(DailyTimeRecord.is_deleted).is_(False),
                        DailyTimeRecord.id != candidate.id,
                    )
                ).all()
            )
            if same_day:
                identical = [
                    existing
                    for existing in same_day
                    if _as_utc(existing.login_date) == _as_utc(row.login_date)
                    and _as_utc(existing.logout_date) == _as_utc(row.logout_date)
                    and existing.shift_id == candidate.shift_id
                ]
                if len(same_day) == 1 and len(identical) == 1:
                    excluded.append(
                        DtrImportExcluded(
                            row_index=index,
                            employee_code=row.employee_code,
                            existing_record_id=identical[0].id,
                            reason="Identical attendance is already saved; excluded from this import.",
                        )
                    )
                else:
                    issues.append(
                        _issue(
                            index,
                            row.employee_code,
                            "saved_attendance_conflict",
                            "Attendance already exists for this employee and work date with different or ambiguous data; use the attendance adjustment workflow.",
                            candidate_work_date,
                        )
                    )
            elif replayed:
                excluded.append(
                    DtrImportExcluded(
                        row_index=index,
                        employee_code=row.employee_code,
                        existing_record_id=candidate.id,
                        reason="This row identity has already been committed.",
                    )
                )
    finally:
        probe.rollback()

    return DtrImportPreflightResponse(
        batch_id=request.batch_id,
        payload_fingerprint=fingerprint,
        valid=not issues,
        row_count=len(request.rows),
        issues=issues,
        excluded=excluded,
    )


def commit_import(
    *, session: Session, request: DtrImportBatchRequest, actor_id: uuid.UUID
) -> DtrImportBatchCommitResponse:
    fingerprint = payload_fingerprint(request)
    scope_issues = _out_of_scope_issues(
        session=session, request=request, actor_id=actor_id
    )
    if scope_issues:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Attendance import has unresolved row errors; no records were saved.",
                "issues": [issue.model_dump(mode="json") for issue in scope_issues],
            },
        )
    existing_batch = session.get(DtrImportBatch, request.batch_id)
    if existing_batch is not None:
        if existing_batch.created_by != actor_id:
            # Do not reveal whether another actor owns this import identity or
            # return any of its DTR records through an idempotent replay.
            raise HTTPException(status_code=404, detail="Import batch not found")
        if existing_batch.payload_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409,
                detail="This import identity was already used with different attendance data.",
            )
        records = []
        for index in range(len(request.rows)):
            record = session.exec(
                select(DailyTimeRecord).where(
                    DailyTimeRecord.source_ref == _source_ref(request.batch_id, index),
                    DailyTimeRecord.is_deleted == False,  # noqa: E712
                )
            ).first()
            if record is not None:
                records.append(DailyTimeRecordPublic.model_validate(record))
        return DtrImportBatchCommitResponse(
            batch_id=request.batch_id,
            created_count=existing_batch.created_count,
            replayed=True,
            excluded_count=existing_batch.excluded_count,
            records=records,
        )

    try:
        # Lock every employee in stable order before validating or inserting so
        # concurrent batch imports cannot race the employee/date duplicate check.
        codes = sorted({row.employee_code.strip() for row in request.rows})
        session.exec(
            select(EmployeeRecords)
            .where(
                col(EmployeeRecords.employee_code).in_(codes),
                EmployeeRecords.is_deleted == False,  # noqa: E712
            )
            .order_by(col(EmployeeRecords.id))
            .with_for_update()
        ).all()
        preflight = preflight_import(
            session=session, request=request, actor_id=actor_id
        )
        if not preflight.valid:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Attendance import has unresolved row errors; no records were saved.",
                    "issues": [
                        issue.model_dump(mode="json") for issue in preflight.issues
                    ],
                },
            )

        exclusions = {row.row_index for row in preflight.excluded}
        created: list[DailyTimeRecord] = []
        for index, row in enumerate(request.rows):
            if index in exclusions:
                continue
            record, replayed = create_dtr(
                session=session,
                data=DailyTimeRecordCreate(
                    employee_code=row.employee_code.strip(),
                    login_date=row.login_date,
                    logout_date=row.logout_date,
                    shift_code=row.shift_code,
                    source_ref=_source_ref(request.batch_id, index),
                ),
                actor_id=actor_id,
                commit=False,
            )
            if row.intervals:
                replace_dtr_intervals(
                    session=session,
                    dtr=record,
                    intervals=row.intervals,
                    actor_id=actor_id,
                    commit=False,
                )
            if not replayed:
                created.append(record)
            else:
                created.append(record)

        batch = DtrImportBatch(
            id=request.batch_id,
            payload_fingerprint=fingerprint,
            created_by=actor_id,
            row_count=len(request.rows),
            created_count=len(created),
            excluded_count=len(preflight.excluded),
            source_rows=[dict(row.source_row) for row in request.rows],
            submitted_rows=[row.model_dump(mode="json") for row in request.rows],
            corrections=[
                {
                    "row_index": index,
                    "original": dict(row.source_row),
                    "submitted": row.model_dump(mode="json", exclude={"source_row"}),
                }
                for index, row in enumerate(request.rows)
                if row.source_row
                and any(
                    str(row.source_row.get(field, "")).strip() != str(value)
                    for field, value in {
                        "employee_code": row.employee_code,
                        "login_date": row.login_date.isoformat(),
                        "logout_date": row.logout_date.isoformat(),
                        "shift_code": row.shift_code or "",
                    }.items()
                )
            ],
        )
        session.add(batch)
        session.commit()
        return DtrImportBatchCommitResponse(
            batch_id=request.batch_id,
            created_count=len(created),
            replayed=False,
            excluded_count=len(preflight.excluded),
            records=[DailyTimeRecordPublic.model_validate(row) for row in created],
        )
    except Exception:
        session.rollback()
        raise
