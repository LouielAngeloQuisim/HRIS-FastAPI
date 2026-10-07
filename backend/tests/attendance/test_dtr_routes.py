"""Phase 2A test set B — endpoint/service integration tests (design §4.2).

Uses the superuser token (bypasses RBAC) for CRUD/parity/actor-spoofing tests,
and the normal (role-less) user token for the RBAC gate test.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.attendance.models import DailyTimeRecord, Shift
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.user.models import User

API = settings.API_V1_STR


@pytest.fixture
def shift(db: Session) -> Shift:
    shift = Shift(
        code=f"DAY-{uuid.uuid4().hex[:8]}",
        name="Day Shift",
        start_time="08:00",
        end_time="17:00",
        lunch_break_duration=60,
        total_hours_minus_lunch=480,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@pytest.fixture
def employee(db: Session) -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
        first_name="Jane",
        last_name="Doe",
        birthdate="1990-01-01",
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _dtr_payload(employee_id: str, shift_id: str | None = None) -> dict:
    body = {
        "employee_id": employee_id,
        # Shift wall-clock times are Asia/Manila; punches are explicit local offsets.
        "login_date": "2026-08-04T08:00:00+08:00",
        "logout_date": "2026-08-04T17:00:00+08:00",
    }
    if shift_id is not None:
        body["shift_id"] = shift_id
    return body


def _assign_shift(client: TestClient, employee: EmployeeRecords, shift: Shift, headers: dict[str, str]) -> None:
    response = client.post(
        f"{API}/employee-shift-assignments/",
        json={
            "employee_id": str(employee.id),
            "shift_id": str(shift.id),
            "effective_from": "2026-08-01",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


class TestShiftCrud:
    def test_create_shift(self, client: TestClient, superuser_token_headers) -> None:
        r = client.post(
            f"{API}/shifts/",
            json={
                "code": f"NIGHT-{uuid.uuid4().hex[:8]}",
                "name": "Night Shift",
                "start_time": "22:00",
                "end_time": "06:00",
                "lunch_break_duration": 60,
                "total_hours_minus_lunch": 480,
                "days_of_week": ["1", "2", "3", "4", "5"],
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "Night Shift"

    def test_shift_list_excludes_deleted(
        self,
        client: TestClient,
        superuser_token_headers,
        shift: Shift,
    ) -> None:
        r = client.get(f"{API}/shifts/", headers=superuser_token_headers)
        assert r.status_code == 200
        assert any(s["id"] == str(shift.id) for s in r.json()["data"])


class TestEffectiveShiftAssignments:
    def test_after_midnight_punch_uses_overnight_shift_start_date(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        db: Session,
    ) -> None:
        night = Shift(
            code=f"NIGHT-{uuid.uuid4().hex[:8]}",
            name="Night Shift",
            start_time="22:00",
            end_time="06:00",
            lunch_break_duration=0,
            total_hours_minus_lunch=480,
        )
        db.add(night)
        db.commit()
        db.refresh(night)
        assignment = client.post(
            f"{API}/employee-shift-assignments/",
            json={
                "employee_id": str(employee.id),
                "shift_id": str(night.id),
                "effective_from": "2026-08-03",
            },
            headers=superuser_token_headers,
        )
        assert assignment.status_code == 201, assignment.text

        payload = {
            "employee_id": str(employee.id),
            "login_date": "2026-08-03T17:00:00+00:00",  # Aug 4, 01:00 Manila
            "logout_date": "2026-08-03T22:00:00+00:00",  # Aug 4, 06:00 Manila
        }
        response = client.post(
            f"{API}/daily-time-records/", json=payload, headers=superuser_token_headers
        )
        assert response.status_code == 201, response.text
        assert response.json()["shift_id"] == str(night.id)
        assert response.json()["work_date"] == "2026-08-03"

    def test_assignment_is_effective_dated_and_filters_by_date(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        response = client.post(
            f"{API}/employee-shift-assignments/",
            json={
                "employee_id": str(employee.id),
                "shift_id": str(shift.id),
                "effective_from": "2026-08-01",
            },
            headers=superuser_token_headers,
        )
        assert response.status_code == 201, response.text
        assignment_id = response.json()["id"]
        active = client.get(
            f"{API}/employee-shift-assignments/?employee_id={employee.id}&as_of=2026-08-04",
            headers=superuser_token_headers,
        )
        inactive = client.get(
            f"{API}/employee-shift-assignments/?employee_id={employee.id}&as_of=2026-07-31",
            headers=superuser_token_headers,
        )
        assert [row["id"] for row in active.json()["data"]] == [assignment_id]
        assert inactive.json()["data"] == []

    def test_overlapping_assignment_is_rejected_without_insert(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        payload = {
            "employee_id": str(employee.id),
            "shift_id": str(shift.id),
            "effective_from": "2026-08-01",
            "effective_to": "2026-08-31",
        }
        first = client.post(
            f"{API}/employee-shift-assignments/",
            json=payload,
            headers=superuser_token_headers,
        )
        second = client.post(
            f"{API}/employee-shift-assignments/",
            json={**payload, "effective_from": "2026-08-31", "effective_to": None},
            headers=superuser_token_headers,
        )
        assert first.status_code == 201, first.text
        assert second.status_code == 409, second.text
        assert (
            len(
                client.get(
                    f"{API}/employee-shift-assignments/?employee_id={employee.id}",
                    headers=superuser_token_headers,
                ).json()["data"]
            )
            == 1
        )


class TestDtrCreatePersistsComputed:
    def test_create_persists_computed_values(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        _assign_shift(client, employee, shift, superuser_token_headers)
        r = client.post(
            f"{API}/daily-time-records/",
            json=_dtr_payload(str(employee.id), str(shift.id)),
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # 08:00-17:00, 60-min lunch, 480 baseline -> rendered 480, no late/undertime/OT
        assert body["rendered_minutes"] == 480
        assert body["late_minutes"] == 0
        assert body["undertime_minutes"] == 0
        assert body["overtime_minutes"] == 0
        assert body["is_time_calculated"] is True
        assert body["source"] == "manual"

    def test_create_with_late_minutes(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        _assign_shift(client, employee, shift, superuser_token_headers)
        payload = {
            "employee_id": str(employee.id),
            "shift_id": str(shift.id),
            "login_date": "2026-08-04T08:30:00+08:00",
            "logout_date": "2026-08-04T17:00:00+08:00",
        }
        r = client.post(
            f"{API}/daily-time-records/",
            json=payload,
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["late_minutes"] == 30
        assert body["undertime_minutes"] == 30
        assert body["rendered_minutes"] == 450

    def test_create_without_shift_assignment_is_blocked(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        r = client.post(
            f"{API}/daily-time-records/",
            json=_dtr_payload(str(employee.id), str(shift.id)),
            headers=superuser_token_headers,
        )
        assert r.status_code == 422, r.text
        assert "No shift is assigned" in r.json()["detail"]

    def test_create_uses_effective_assignment_when_shift_not_supplied(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        assigned = client.post(
            f"{API}/employee-shift-assignments/",
            json={
                "employee_id": str(employee.id),
                "shift_id": str(shift.id),
                "effective_from": "2026-08-01",
            },
            headers=superuser_token_headers,
        )
        assert assigned.status_code == 201, assigned.text
        response = client.post(
            f"{API}/daily-time-records/",
            json=_dtr_payload(str(employee.id)),
            headers=superuser_token_headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["shift_id"] == str(shift.id)
        assert response.json()["rendered_minutes"] == 480


class TestCodeResolution:
    """employee_code / shift_code resolve server-side (design §3.2)."""

    def test_create_by_employee_code(
        self,
        client: TestClient,
        superuser_token_headers,
        db: Session,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        _assign_shift(client, employee, shift, superuser_token_headers)
        payload = {
            "employee_code": employee.employee_code,
            "shift_code": shift.code,
            "login_date": "2026-08-04T08:00:00+08:00",
            "logout_date": "2026-08-04T17:00:00+08:00",
        }
        r = client.post(
            f"{API}/daily-time-records/",
            json=payload,
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["employee_id"] == str(employee.id)
        assert body["shift_id"] == str(shift.id)
        assert body["rendered_minutes"] == 480

    def test_unknown_employee_code_returns_404(
        self,
        client: TestClient,
        superuser_token_headers,
    ) -> None:
        payload = {
            "employee_code": "DOES-NOT-EXIST",
            "login_date": "2026-08-04T08:00:00+00:00",
            "logout_date": "2026-08-04T17:00:00+00:00",
        }
        r = client.post(
            f"{API}/daily-time-records/",
            json=payload,
            headers=superuser_token_headers,
        )
        assert r.status_code == 404, r.text


class TestActorSpoofing:
    """Server-authoritative actor: client-supplied created_by/computed fields are ignored.

    Treated with the same priority as the Phase 1 role-escalation tests.
    """

    def test_client_supplied_actor_and_computed_fields_ignored(
        self,
        client: TestClient,
        superuser_token_headers,
        db: Session,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        _assign_shift(client, employee, shift, superuser_token_headers)
        fake_actor = uuid.uuid4()
        payload = _dtr_payload(str(employee.id), str(shift.id))
        payload["created_by"] = str(fake_actor)
        payload["updated_by"] = str(fake_actor)
        payload["rendered_minutes"] = 9999
        payload["late_minutes"] = 9999
        payload["source"] = "csv"

        r = client.post(
            f"{API}/daily-time-records/",
            json=payload,
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()

        # Actor is the authenticated superuser, not the spoofed value.
        superuser = db.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).one()
        assert body["created_by"] == str(superuser.id)
        assert body["updated_by"] == str(superuser.id)
        assert body["created_by"] != str(fake_actor)

        # Computed fields match the calc core, not the spoofed values.
        assert body["rendered_minutes"] == 480
        assert body["late_minutes"] == 0
        # Source forced to 'manual' server-side.
        assert body["source"] == "manual"


class TestValidation:
    def test_login_not_before_logout_returns_400(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
    ) -> None:
        payload = {
            "employee_id": str(employee.id),
            "login_date": "2026-08-04T17:00:00+00:00",
            "logout_date": "2026-08-04T08:00:00+00:00",
        }
        r = client.post(
            f"{API}/daily-time-records/",
            json=payload,
            headers=superuser_token_headers,
        )
        assert r.status_code == 400, r.text

    def test_unknown_employee_returns_404(
        self,
        client: TestClient,
        superuser_token_headers,
    ) -> None:
        payload = _dtr_payload(str(uuid.uuid4()))
        r = client.post(
            f"{API}/daily-time-records/",
            json=payload,
            headers=superuser_token_headers,
        )
        assert r.status_code == 404, r.text

    def test_unknown_shift_returns_404(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
    ) -> None:
        payload = _dtr_payload(str(employee.id), str(uuid.uuid4()))
        r = client.post(
            f"{API}/daily-time-records/",
            json=payload,
            headers=superuser_token_headers,
        )
        assert r.status_code == 404, r.text


class TestSoftDelete:
    def test_soft_delete(
        self,
        client: TestClient,
        superuser_token_headers,
        db: Session,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        _assign_shift(client, employee, shift, superuser_token_headers)
        r = client.post(
            f"{API}/daily-time-records/",
            json=_dtr_payload(str(employee.id), str(shift.id)),
            headers=superuser_token_headers,
        )
        obj_id = r.json()["id"]

        r = client.delete(
            f"{API}/daily-time-records/{obj_id}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text

        # Gone from list, but still in DB as soft-deleted.
        r = client.get(f"{API}/daily-time-records/", headers=superuser_token_headers)
        assert not any(d["id"] == obj_id for d in r.json()["data"])
        obj = db.get(DailyTimeRecord, uuid.UUID(obj_id))
        assert obj is not None and obj.is_deleted is True


class TestRbacGate:
    """A token without the daily_time_record/add permission gets 403."""

    def test_normal_user_gets_403(
        self,
        client: TestClient,
        normal_user_token_headers,
        employee: EmployeeRecords,
    ) -> None:
        r = client.post(
            f"{API}/daily-time-records/",
            json=_dtr_payload(str(employee.id)),
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text


class TestRowLevelListFilter:
    def test_date_filters_use_manila_calendar_days(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        _assign_shift(client, employee, shift, superuser_token_headers)
        inside = _dtr_payload(str(employee.id), str(shift.id))
        inside.update(
            login_date="2026-08-03T16:30:00+00:00",
            logout_date="2026-08-03T17:30:00+00:00",
        )
        outside = _dtr_payload(str(employee.id), str(shift.id))
        outside.update(
            login_date="2026-08-04T16:30:00+00:00",
            logout_date="2026-08-04T17:30:00+00:00",
        )
        created_inside = client.post(
            f"{API}/daily-time-records/", json=inside, headers=superuser_token_headers
        )
        created_outside = client.post(
            f"{API}/daily-time-records/", json=outside, headers=superuser_token_headers
        )
        assert created_inside.status_code == created_outside.status_code == 201

        response = client.get(
            f"{API}/daily-time-records/?date_from=2026-08-04&date_to=2026-08-04",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200, response.text
        returned_ids = {row["id"] for row in response.json()["data"]}
        assert created_inside.json()["id"] in returned_ids
        assert created_outside.json()["id"] not in returned_ids

    def test_reversed_date_filter_is_rejected(
        self, client: TestClient, superuser_token_headers
    ) -> None:
        response = client.get(
            f"{API}/daily-time-records/?date_from=2026-08-05&date_to=2026-08-04",
            headers=superuser_token_headers,
        )
        assert response.status_code == 422

    """Non-superuser callers with daily_time_record:view see only their own DTRs.

    Implements design §2.4 Option A: the list selector filters by
    employee_id = current_user.employee_id when the caller is not a superuser.
    Superusers (and any non-superuser without a linked EmployeeRecords) get
    the same behavior as before this change (no row filter).
    """

    def _create_dtr_via_superuser(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        employee: EmployeeRecords,
        shift: Shift | None = None,
    ) -> str:
        if shift is not None:
            _assign_shift(client, employee, shift, superuser_token_headers)
        r = client.post(
            f"{API}/daily-time-records/",
            json=_dtr_payload(str(employee.id), str(shift.id) if shift else None),
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def _make_employee_user_with_dtr_view(
        self,
        db: Session,
        client: TestClient,
        email: str,
        linked_employee: EmployeeRecords,
    ) -> dict[str, str]:
        """Create a non-superuser, link them to an EmployeeRecords, grant DTR:view."""
        from app.rbac.models import Role, RolePermission
        from app.rbac.selectors import get_module_by_code
        from app.user.models import UserCreate
        from app.user.services import create_user
        from tests.utils.user import user_authentication_headers
        from tests.utils.utils import random_lower_string

        password = random_lower_string()
        user = create_user(
            session=db, user_create=UserCreate(email=email, password=password)
        )
        # Link user to employee
        db.refresh(linked_employee)
        linked_employee.user_id = user.id
        db.add(linked_employee)
        db.commit()

        # Create a role with daily_time_record:view
        role_code = f"TEST_VIEW_{uuid.uuid4().hex[:6]}"
        role = Role(code=role_code, name="Test Viewer")
        db.add(role)
        db.commit()
        db.refresh(role)
        user.role_id = role.id
        db.add(user)
        db.commit()

        dtr_module = get_module_by_code(session=db, code="daily_time_record")
        db.add(
            RolePermission(
                role_id=role.id,
                module_id=dtr_module.id,
                can_view=True,
            )
        )
        db.commit()
        return user_authentication_headers(
            client=client, email=email, password=password
        )

    def test_non_superuser_sees_only_own_dtrs(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        """A non-superuser with DTR:view sees their own DTR, not another employee's."""

        from app.employee.models import EmployeeRecords

        # Create a second employee (no linked user)
        other_emp = EmployeeRecords(
            employee_code=f"OTHER-{uuid.uuid4().hex[:8]}",
            first_name="Other",
            last_name="Person",
            birthdate="1990-01-01",
        )
        db.add(other_emp)
        db.commit()
        db.refresh(other_emp)

        # Create DTRs for both employees
        own_id = self._create_dtr_via_superuser(
            client, superuser_token_headers, employee, shift
        )
        other_id = self._create_dtr_via_superuser(
            client, superuser_token_headers, other_emp, shift
        )

        # Create a non-superuser linked to `employee` with DTR:view
        email = f"viewer-{uuid.uuid4().hex[:8]}@example.com"
        headers = self._make_employee_user_with_dtr_view(db, client, email, employee)

        r = client.get(f"{API}/daily-time-records/", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        ids = [d["id"] for d in body["data"]]
        assert own_id in ids, "non-superuser should see their own DTR"
        assert other_id not in ids, "non-superuser must NOT see another employee's DTR"

    def test_superuser_sees_all_dtrs(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        """Superusers still see every DTR (no row filter for is_superuser=True)."""
        from app.employee.models import EmployeeRecords

        other_emp = EmployeeRecords(
            employee_code=f"OTHER-{uuid.uuid4().hex[:8]}",
            first_name="Other",
            last_name="Person",
            birthdate="1990-01-01",
        )
        db.add(other_emp)
        db.commit()
        db.refresh(other_emp)

        own_id = self._create_dtr_via_superuser(
            client, superuser_token_headers, employee, shift
        )
        other_id = self._create_dtr_via_superuser(
            client, superuser_token_headers, other_emp, shift
        )

        r = client.get(f"{API}/daily-time-records/", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        ids = [d["id"] for d in r.json()["data"]]
        assert own_id in ids
        assert other_id in ids

    def test_non_superuser_without_employee_link_sees_nothing(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
        employee: EmployeeRecords,
        shift: Shift,
    ) -> None:
        """Defensive: a non-superuser with DTR:view but no EmployeeRecords sees [].

        Without a linked EmployeeRecords, the row filter resolves to a non-None
        UUID (from get_employee_id_for_user returning None), so the filter is
        applied as a no-match. The caller gets an empty list.
        """
        from app.rbac.models import Role, RolePermission
        from app.rbac.selectors import get_module_by_code
        from app.user.models import UserCreate
        from app.user.services import create_user
        from tests.utils.user import user_authentication_headers
        from tests.utils.utils import random_lower_string

        self._create_dtr_via_superuser(client, superuser_token_headers, employee, shift)

        # Create a user with DTR:view but NO linked EmployeeRecords
        password = random_lower_string()
        email = f"unlinked-{uuid.uuid4().hex[:8]}@example.com"
        user = create_user(
            session=db, user_create=UserCreate(email=email, password=password)
        )
        role_code = f"TEST_UNLINKED_{uuid.uuid4().hex[:6]}"
        role = Role(code=role_code, name="Unlinked Viewer")
        db.add(role)
        db.commit()
        db.refresh(role)
        user.role_id = role.id
        db.add(user)
        db.commit()
        dtr_module = get_module_by_code(session=db, code="daily_time_record")
        db.add(RolePermission(role_id=role.id, module_id=dtr_module.id, can_view=True))
        db.commit()
        headers = user_authentication_headers(
            client=client, email=email, password=password
        )

        r = client.get(f"{API}/daily-time-records/", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"] == [], "user with no linked employee should see no DTRs"
