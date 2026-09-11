"""Leave and holiday routers (design doc §1.6).

All write endpoints enforce ``require_permission(module, action)``; all read endpoints
enforce the matching view permission. Actions follow the exact literals:
``view | add | edit | delete | approve | admin``.
"""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.dependencies import CurrentUser, SessionDep
from app.common.schemas import Message
from app.leave import selectors, services
from app.leave.schemas import (
    EmployeeLeaveEnrollmentCreate,
    EmployeeLeaveEnrollmentList,
    EmployeeLeaveEnrollmentPublic,
    HolidayConfigCreate,
    HolidayConfigList,
    HolidayConfigPublic,
    HolidayConfigUpdate,
    HolidayInstanceCreate,
    HolidayInstanceList,
    HolidayInstancePublic,
    LeaveCalendarEvent,
    LeaveLedgerEntryPublic,
    LeaveLedgerEventPage,
    LeaveLedgerResponse,
    LeaveLedgerSummary,
    LeavePolicyCreate,
    LeavePolicyList,
    LeavePolicyPublic,
    LeavePolicyUpdate,
    LeaveRequestCreate,
    LeaveRequestDetail,
    LeaveRequestEventPublic,
    LeaveRequestList,
    LeaveRequestPublic,
    ManualAdjustment,
    MonthlyAccrualRun,
    YearEndCarryoverRun,
)
from app.rbac.dependencies import require_permission

# === LeavePolicy CRUD ===================================================================


policy_router = APIRouter(prefix="/leave-policies", tags=["leave_policies"])


@policy_router.get("/", response_model=LeavePolicyList, dependencies=[Depends(require_permission("leave_policy", "view"))])
def list_policies(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    rows, count = selectors.list_policies(session=session, skip=skip, limit=limit)
    return LeavePolicyList(data=[LeavePolicyPublic.model_validate(r) for r in rows], count=count)


@policy_router.get("/{policy_id}", response_model=LeavePolicyPublic, dependencies=[Depends(require_permission("leave_policy", "view"))])
def get_policy(session: SessionDep, policy_id: uuid.UUID) -> Any:
    db_obj = selectors.get_policy(session=session, policy_id=policy_id)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Leave policy not found")
    return LeavePolicyPublic.model_validate(db_obj)


@policy_router.post("/", response_model=LeavePolicyPublic, status_code=201, dependencies=[Depends(require_permission("leave_policy", "add"))])
def create_policy(session: SessionDep, _current_user: CurrentUser, data: LeavePolicyCreate) -> Any:
    db_obj = services.create_policy(session=session, data=data.model_dump())
    return LeavePolicyPublic.model_validate(db_obj)


@policy_router.patch("/{policy_id}", response_model=LeavePolicyPublic, dependencies=[Depends(require_permission("leave_policy", "edit"))])
def update_policy(session: SessionDep, _current_user: CurrentUser, policy_id: uuid.UUID, data: LeavePolicyUpdate) -> Any:
    db_obj = services.update_policy(session=session, policy_id=policy_id, data=data.model_dump(exclude_unset=True))
    return LeavePolicyPublic.model_validate(db_obj)


@policy_router.delete("/{policy_id}", response_model=Message, dependencies=[Depends(require_permission("leave_policy", "delete"))])
def delete_policy(session: SessionDep, current_user: CurrentUser, policy_id: uuid.UUID) -> Any:
    services.deactivate_policy(session=session, _actor=current_user, policy_id=policy_id)
    return Message(message="Leave policy deactivated successfully")


# === Employee Leave Enrollment ==========================================================


enrollment_router = APIRouter(prefix="/employees", tags=["leave_enrollments"])


@enrollment_router.get(
    "/{employee_id}/leave-enrollments",
    response_model=EmployeeLeaveEnrollmentList,
    dependencies=[Depends(require_permission("emp_leaves", "view"))],
)
def list_enrollments(
    session: SessionDep,
    employee_id: uuid.UUID,
    leave_year: int = Query(default=2026),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    rows, count = selectors.list_enrollments(
        session=session, employee_id=employee_id, leave_year=leave_year, skip=skip, limit=limit
    )
    return EmployeeLeaveEnrollmentList(
        data=[EmployeeLeaveEnrollmentPublic.model_validate(r) for r in rows],
        count=count,
    )


@enrollment_router.post(
    "/{employee_id}/leave-enrollments",
    response_model=EmployeeLeaveEnrollmentPublic,
    status_code=201,
    dependencies=[Depends(require_permission("emp_leaves", "add"))],
)
def enroll_employee(
    session: SessionDep,
    current_user: CurrentUser,
    employee_id: uuid.UUID,
    data: EmployeeLeaveEnrollmentCreate,
) -> Any:
    enrollment = services.enroll_employee(
        session=session,
        actor=current_user,
        employee_id=employee_id,
        policy_id=data.policy_id,
        leave_year=data.leave_year,
    )
    return EmployeeLeaveEnrollmentPublic.model_validate(enrollment)


# === Leave Request =======================================================================


request_router = APIRouter(prefix="/leave-requests", tags=["leave_requests"])


@request_router.get("/", response_model=LeaveRequestList, dependencies=[Depends(require_permission("leave_request", "view"))])
def list_requests(
    session: SessionDep,
    status: str | None = None,
    employee_id: uuid.UUID | None = None,
    leave_year: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    rows, count = selectors.list_leave_requests(
        session=session,
        status=status,
        employee_id=employee_id,
        leave_year=leave_year,
        skip=skip,
        limit=limit,
    )
    return LeaveRequestList(data=[LeaveRequestPublic.model_validate(r) for r in rows], count=count)


@request_router.get("/{request_id}", response_model=LeaveRequestDetail, dependencies=[Depends(require_permission("leave_request", "view"))])
def get_request(session: SessionDep, request_id: uuid.UUID) -> Any:
    db_obj = selectors.get_leave_request(session=session, request_id=request_id)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    events = selectors.get_request_events(session=session, request_id=request_id)
    return LeaveRequestDetail(
        request=LeaveRequestPublic.model_validate(db_obj),
        events=[LeaveRequestEventPublic.model_validate(e) for e in events],
    )


@request_router.post("/", response_model=LeaveRequestPublic, status_code=201, dependencies=[Depends(require_permission("leave_request", "add"))])
def submit_request(session: SessionDep, current_user: CurrentUser, data: LeaveRequestCreate) -> Any:
    db_obj = services.submit_request(session=session, actor=current_user, payload=data.model_dump())
    return LeaveRequestPublic.model_validate(db_obj)


@request_router.post("/{request_id}/approve", response_model=LeaveRequestPublic, dependencies=[Depends(require_permission("leave_request", "approve"))])
def approve_request(session: SessionDep, current_user: CurrentUser, request_id: uuid.UUID) -> Any:
    db_obj = services.approve_request(session=session, actor=current_user, request_id=request_id)
    return LeaveRequestPublic.model_validate(db_obj)


@request_router.post("/{request_id}/reject", response_model=LeaveRequestPublic, dependencies=[Depends(require_permission("leave_request", "approve"))])
def reject_request(
    session: SessionDep, current_user: CurrentUser, request_id: uuid.UUID, note: str | None = None
) -> Any:
    db_obj = services.reject_request(session=session, actor=current_user, request_id=request_id, note=note)
    return LeaveRequestPublic.model_validate(db_obj)


@request_router.post("/{request_id}/cancel", response_model=LeaveRequestPublic, dependencies=[Depends(require_permission("leave_request", "approve"))])
def cancel_request(
    session: SessionDep, current_user: CurrentUser, request_id: uuid.UUID, note: str | None = None
) -> Any:
    db_obj = services.cancel_request(session=session, actor=current_user, request_id=request_id, note=note)
    return LeaveRequestPublic.model_validate(db_obj)


# === Leave Ledger =======================================================================


ledger_router = APIRouter(prefix="/employees", tags=["leave_ledger"])


@ledger_router.get(
    "/{employee_id}/leave-ledger",
    response_model=LeaveLedgerResponse,
    dependencies=[Depends(require_permission("emp_leaves", "view"))],
)
def get_ledger(
    session: SessionDep,
    employee_id: uuid.UUID,
    policy_id: uuid.UUID,
    leave_year: int = Query(default=2026),
) -> Any:
    events, count, granted_total, consumed_total, remaining = selectors.get_employee_ledger_events(
        session=session,
        employee_id=employee_id,
        policy_id=policy_id,
        leave_year=leave_year,
        skip=0,
        limit=100,
    )
    return LeaveLedgerResponse(
        data=[LeaveLedgerEntryPublic.model_validate(e) for e in events],
        summary=LeaveLedgerSummary(
            granted_total=granted_total,
            consumed_total=consumed_total,
            remaining=remaining,
        ),
    )


@ledger_router.get(
    "/{employee_id}/leave-ledger/events",
    response_model=LeaveLedgerEventPage,
    dependencies=[Depends(require_permission("emp_leaves", "view"))],
)
def get_ledger_events(
    session: SessionDep,
    employee_id: uuid.UUID,
    policy_id: uuid.UUID,
    leave_year: int = Query(default=2026),
    skip: int = 0,
    limit: int = 20,
) -> Any:
    events, count, granted_total, consumed_total, remaining = selectors.get_employee_ledger_events(
        session=session,
        employee_id=employee_id,
        policy_id=policy_id,
        leave_year=leave_year,
        skip=skip,
        limit=limit,
    )
    return LeaveLedgerEventPage(
        data=[LeaveLedgerEntryPublic.model_validate(e) for e in events],
        pagination={"skip": skip, "limit": limit, "count": count},
        summary=LeaveLedgerSummary(
            granted_total=granted_total,
            consumed_total=consumed_total,
            remaining=remaining,
        ),
    )


# === Calendar ===========================================================================


calendar_router = APIRouter(prefix="/employees", tags=["leave_calendar"])


@calendar_router.get(
    "/{employee_id}/leave-calendar",
    response_model=list[LeaveCalendarEvent],
    dependencies=[Depends(require_permission("emp_leaves", "view"))],
)
def get_leave_calendar(
    session: SessionDep,
    employee_id: uuid.UUID,
    from_date: date = Query(),
    to_date: date = Query(),
) -> Any:
    events = selectors.get_employee_leave_calendar(
        session=session,
        employee_id=employee_id,
        from_date=from_date,
        to_date=to_date,
    )
    return events


# === Holiday ============================================================================


holiday_router = APIRouter(prefix="/holidays", tags=["holidays"])


@holiday_router.get("/", response_model=HolidayConfigList, dependencies=[Depends(require_permission("holiday_config", "view"))])
def list_holiday_configs(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    rows, count = selectors.list_holiday_configs(session=session, skip=skip, limit=limit)
    return HolidayConfigList(data=[HolidayConfigPublic.model_validate(r) for r in rows], count=count)


@holiday_router.post("/", response_model=HolidayConfigPublic, status_code=201, dependencies=[Depends(require_permission("holiday_config", "add"))])
def create_holiday_config(session: SessionDep, _current_user: CurrentUser, data: HolidayConfigCreate) -> Any:
    db_obj = services.create_holiday_config(session=session, data=data.model_dump())
    return HolidayConfigPublic.model_validate(db_obj)


@holiday_router.patch("/{config_id}", response_model=HolidayConfigPublic, dependencies=[Depends(require_permission("holiday_config", "edit"))])
def update_holiday_config(
    session: SessionDep, _current_user: CurrentUser, config_id: uuid.UUID, data: HolidayConfigUpdate
) -> Any:
    db_obj = services.update_holiday_config(session=session, config_id=config_id, data=data.model_dump(exclude_unset=True))
    return HolidayConfigPublic.model_validate(db_obj)


@holiday_router.get(
    "/instances",
    response_model=HolidayInstanceList,
    dependencies=[Depends(require_permission("holiday_config", "view"))],
)
def list_holiday_instances(
    session: SessionDep,
    leave_year: int = Query(default=2026),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    rows, count = selectors.list_holiday_instances(session=session, leave_year=leave_year, skip=skip, limit=limit)
    return HolidayInstanceList(data=[HolidayInstancePublic.model_validate(r) for r in rows], count=count)


@holiday_router.post(
    "/instances",
    response_model=HolidayInstancePublic,
    status_code=201,
    dependencies=[Depends(require_permission("holiday_config", "add"))],
)
def create_holiday_instance(
    session: SessionDep, _current_user: CurrentUser, data: HolidayInstanceCreate
) -> Any:
    db_obj = services.create_holiday_instance(
        session=session,
        config_id=data.config_id,
        date_val=data.observed_date,
        raw_date_val=data.raw_date,
        leave_year=data.leave_year,
    )
    return HolidayInstancePublic.model_validate(db_obj)


# === Admin actions ======================================================================


admin_router = APIRouter(prefix="/leave/admin", tags=["leave_admin"])


@admin_router.post("/accrue", response_model=Message, dependencies=[Depends(require_permission("leave_policy", "admin"))])
def run_monthly_accrual(session: SessionDep, current_user: CurrentUser, body: MonthlyAccrualRun) -> Any:
    count = services.run_monthly_accrual(
        session=session,
        actor=current_user,
        leave_year=body.target_year,
        target_year=body.target_year,
        target_month=body.target_month,
    )
    return Message(message=f"Monthly accrual run complete. {count} entries created.")


@admin_router.post("/carryover", response_model=Message, dependencies=[Depends(require_permission("leave_policy", "admin"))])
def run_year_end_carryover(session: SessionDep, current_user: CurrentUser, body: YearEndCarryoverRun) -> Any:
    count = services.run_year_end_carryover(
        session=session,
        actor=current_user,
        from_year=body.target_year_from,
        to_year=body.target_year_to,
        target_year_from=body.target_year_from,
        target_year_to=body.target_year_to,
    )
    return Message(message=f"Year-end carryover complete. {count} employees processed.")


@admin_router.post("/adjust", response_model=LeaveLedgerEntryPublic, dependencies=[Depends(require_permission("leave_policy", "admin"))])
def apply_manual_adjustment(session: SessionDep, current_user: CurrentUser, body: ManualAdjustment) -> Any:
    db_obj = services.apply_manual_adjustment(
        session=session,
        actor=current_user,
        employee_id=body.employee_id,
        policy_id=body.policy_id,
        leave_year=body.leave_year,
        delta=body.delta,
        note=body.note,
    )
    return LeaveLedgerEntryPublic.model_validate(db_obj)


# === Router list for mounting ==========================================================


routers = [
    policy_router,
    enrollment_router,
    request_router,
    ledger_router,
    calendar_router,
    holiday_router,
    admin_router,
]
