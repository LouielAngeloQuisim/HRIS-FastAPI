"""Phase B5 — notification service tests (triggers, pre-payday, recipients)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlmodel import Session, select

from app.notification import models as m
from app.notification.services import (
    notify_payroll_run_event,
    run_pre_payday_check,
    send_email_notification,
)
from app.payroll.models import CutoffType, PayrollRun, PayrollRunStatus
from app.rbac.models import Module, Role, RolePermission
from app.user.models import User, UserCreate
from app.user.services import create_user


def _user_with_payroll_view(session: Session) -> User:
    module = session.exec(select(Module).where(Module.code == "payroll")).first()
    if module is None:
        module = Module(code="payroll", name="Payroll", sort_order=1)
        session.add(module)
        session.commit()
        session.refresh(module)
    role = Role(code=f"NTSVC_{uuid.uuid4().hex[:6]}", name="Notif payroll viewer")
    session.add(role)
    session.commit()
    session.refresh(role)
    session.add(RolePermission(role_id=role.id, module_id=module.id, can_view=True))
    session.commit()

    user = create_user(
        session=session,
        user_create=UserCreate(email=f"nv-{uuid.uuid4().hex[:8]}@example.com", password="testpass123"),
    )
    user.role_id = role.id
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _draft_run(session: Session, date_from: date) -> PayrollRun:
    run = PayrollRun(
        id=uuid.uuid4(),
        cutoff_type=CutoffType.MONTHLY,
        date_from=date_from,
        date_to=date_from + timedelta(days=14),
        status=PayrollRunStatus.DRAFT,
        is_deleted=False,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


class TestPayrollRunEvents:
    def test_generated_event_notifies_permission_holders(self, db: Session) -> None:
        viewer = _user_with_payroll_view(db)
        run = _draft_run(db, date(2026, 9, 1))

        created = notify_payroll_run_event(session=db, run=run, event="generated")
        assert created, "expected at least one notification"

        mine = db.exec(
            select(m.Notification).where(
                m.Notification.user_id == viewer.id,
                m.Notification.type == m.NotificationType.PAYROLL_RUN_GENERATED,
            )
        ).all()
        assert len(mine) == 1
        assert mine[0].data is not None
        assert mine[0].data["run_id"] == str(run.id)
        assert mine[0].data["link"] == f"/payroll-runs/{run.id}"

    def test_approved_and_voided_events_use_correct_types(self, db: Session) -> None:
        _user_with_payroll_view(db)
        run = _draft_run(db, date(2026, 10, 1))

        notify_payroll_run_event(session=db, run=run, event="approved")
        notify_payroll_run_event(session=db, run=run, event="voided")

        for event_type in (
            m.NotificationType.PAYROLL_RUN_APPROVED,
            m.NotificationType.PAYROLL_RUN_VOIDED,
        ):
            rows = db.exec(select(m.Notification).where(m.Notification.type == event_type)).all()
            assert rows, f"no notification for {event_type}"

    def test_unknown_event_is_noop(self, db: Session) -> None:
        run = _draft_run(db, date(2026, 11, 1))
        assert notify_payroll_run_event(session=db, run=run, event="bogus") == []


class TestPrePaydayCheck:
    def test_window_honours_days_before(self, db: Session) -> None:
        viewer = _user_with_payroll_view(db)
        today = date.today()
        _draft_run(db, today + timedelta(days=10))

        far = run_pre_payday_check(session=db, days_before=3, today=today)
        assert far["upcoming_runs"] == 0

        near = run_pre_payday_check(session=db, days_before=10, today=today)
        assert near["upcoming_runs"] >= 1

        rows = db.exec(
            select(m.Notification).where(
                m.Notification.user_id == viewer.id,
                m.Notification.type == m.NotificationType.PRE_PAYDAY_CHECK,
            )
        ).all()
        assert rows, "pre-payday notification was not created"

    def test_flags_missing_salary_with_deep_link(self, db: Session) -> None:
        from app.employee.models import EmployeeRecords, EmployeeStatus

        emp = EmployeeRecords(
            id=uuid.uuid4(),
            employee_code=f"PPD-{uuid.uuid4().hex[:6]}",
            first_name="No",
            last_name="Salary",
            birthdate=date(1990, 1, 1),
            employment_type="regular",
            employee_status=EmployeeStatus.ACTIVE,
            date_hired=date(2020, 1, 1),
            is_deleted=False,
        )
        db.add(emp)
        db.commit()

        run = _draft_run(db, date.today() + timedelta(days=1))
        result = run_pre_payday_check(session=db, days_before=3)

        matching = [f for f in result["flags"] if f["employee_code"] == emp.employee_code]
        assert matching, "missing-salary employee was not flagged"
        assert matching[0]["missing_salary"] is True
        assert matching[0]["run_id"] == str(run.id)
        assert matching[0]["link"] == f"/payroll-runs/{run.id}"


class TestEmailGuard:
    def test_email_is_skipped_when_not_configured(self) -> None:
        from app.config.settings import settings

        assert settings.emails_enabled is False
        assert send_email_notification(email_to="x@example.com", subject="s", html_content="<p>x</p>") is False

    def test_email_is_skipped_without_recipient(self) -> None:
        assert send_email_notification(email_to=None, subject="s", html_content="<p>x</p>") is False


class TestNoHardcodedRecipients:
    def test_notification_is_addressed_to_resolved_user(self, db: Session) -> None:
        viewer = _user_with_payroll_view(db)
        run = _draft_run(db, date(2026, 12, 1))
        notify_payroll_run_event(session=db, run=run, event="generated")

        rows = db.exec(
            select(m.Notification).where(
                m.Notification.type == m.NotificationType.PAYROLL_RUN_GENERATED
            )
        ).all()
        matching = [r for r in rows if r.data and r.data.get("run_id") == str(run.id)]
        assert matching
        assert all(r.user_id is not None for r in matching)
        assert viewer.id in {r.user_id for r in matching}
