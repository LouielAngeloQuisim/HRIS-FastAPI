"""Phase b3 test set B — endpoint/service integration tests (design doc §1.9).

Uses the superuser token (bypasses RBAC) for CRUD/actor-spoofing/ledger tests,
and the normal employee token for RBAC gate tests.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.leave.models import LeavePolicy
from app.user.models import User

API = settings.API_V1_STR


@pytest.fixture
def employee(db: Session) -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
        first_name="Jane", last_name="Doe", birthdate="1990-01-01",
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def policy(db: Session) -> LeavePolicy:
    pol = LeavePolicy(
        code=f"VL-{uuid.uuid4().hex[:6]}",
        name="Vacation Leave",
        annual_entitlement_days="15.00",
        cadence="annual",
        prorate_on_hire=False,
        carry_over_enabled=False,
        is_paid=True,
        eligible_departments=[],
        gender_scope="all",
        marital_status_scope="all",
        is_active=True,
        is_system=False,
        is_deleted=False,
    )
    db.add(pol)
    db.commit()
    db.refresh(pol)
    return pol


@pytest.fixture
def hr_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    """Create a user with the HR role (has leave_policy:admin, leave_request:approve, etc.)."""
    from app.rbac.selectors import get_role_by_code
    from app.user.models import UserCreate
    from app.user.services import create_user
    from tests.utils.user import user_authentication_headers
    from tests.utils.utils import random_lower_string

    password = random_lower_string()
    email = f"hr-{uuid.uuid4().hex[:8]}@example.com"
    user = create_user(session=db, user_create=UserCreate(email=email, password=password))
    hr_role = get_role_by_code(session=db, code="HR")
    assert hr_role is not None, "HR role should be seeded"
    user.role_id = hr_role.id
    db.add(user)
    db.commit()
    return user_authentication_headers(client=client, email=email, password=password)


@pytest.fixture
def employee_user_token_headers(client: TestClient, db: Session, employee: EmployeeRecords) -> dict[str, str]:
    """Create a user linked to an employee with leave_request:view+add."""
    from app.user.models import UserCreate
    from app.user.services import create_user
    from tests.utils.user import user_authentication_headers
    from tests.utils.utils import random_lower_string

    password = random_lower_string()
    email = f"emp-{uuid.uuid4().hex[:8]}@example.com"
    user = create_user(session=db, user_create=UserCreate(email=email, password=password))
    user.role_id = employee.user_id
    db.add(user)
    db.commit()
    return user_authentication_headers(client=client, email=email, password=password)


# --- Policy CRUD ------------------------------------------------------------------------


class TestPolicyCrud:
    def test_create_policy(self, client: TestClient, superuser_token_headers) -> None:
        r = client.post(
            f"{API}/leave-policies/",
            json={
                "code": f"SL-{uuid.uuid4().hex[:6]}",
                "name": "Sick Leave",
                "annual_entitlement_days": "10.00",
                "cadence": "annual",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "Sick Leave"

    def test_list_policies(self, client: TestClient, superuser_token_headers, policy: LeavePolicy) -> None:
        r = client.get(f"{API}/leave-policies/", headers=superuser_token_headers)
        assert r.status_code == 200
        assert any(p["id"] == str(policy.id) for p in r.json()["data"])

    def test_get_policy(self, client: TestClient, superuser_token_headers, policy: LeavePolicy) -> None:
        r = client.get(f"{API}/leave-policies/{policy.id}", headers=superuser_token_headers)
        assert r.status_code == 200
        assert r.json()["code"] == policy.code

    def test_update_policy(self, client: TestClient, superuser_token_headers, policy: LeavePolicy) -> None:
        r = client.patch(
            f"{API}/leave-policies/{policy.id}",
            json={"name": "Updated Name"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"


# --- Enrollment ------------------------------------------------------------------------


class TestEnrollmentFlow:
    def _enroll(self, client: TestClient, headers: dict, employee_id: str, policy_id: str, year: int = 2026) -> None:
        r = client.post(
            f"{API}/employees/{employee_id}/leave-enrollments",
            json={"policy_id": policy_id, "leave_year": year},
            headers=headers,
        )
        assert r.status_code == 201, r.text

    def test_enroll_employee(
        self, client: TestClient, superuser_token_headers, employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))

    def test_enroll_duplicate_returns_409(
        self, client: TestClient, superuser_token_headers, employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))
        r = client.post(
            f"{API}/employees/{employee.id}/leave-enrollments",
            json={"policy_id": str(policy.id), "leave_year": 2026},
            headers=superuser_token_headers,
        )
        assert r.status_code == 409, r.text

    def test_list_enrollments(
        self, client: TestClient, superuser_token_headers, employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))
        r = client.get(
            f"{API}/employees/{employee.id}/leave-enrollments?leave_year=2026",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        assert any(e["policy_id"] == str(policy.id) for e in r.json()["data"])


# --- Leave Request lifecycle ------------------------------------------------------------


class TestLeaveRequestFlow:
    def _enroll(self, client: TestClient, headers: dict, employee_id: str, policy_id: str) -> None:
        r = client.post(
            f"{API}/employees/{employee_id}/leave-enrollments",
            json={"policy_id": policy_id, "leave_year": 2026},
            headers=headers,
        )
        if r.status_code != 201:
            raise RuntimeError(f"Enroll failed: {r.status_code} {r.text}")

    def _submit(
        self, client: TestClient, headers: dict, employee_id: str, policy_id: str,
        date_start: str, date_end: str,
    ) -> dict:
        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": employee_id,
                "policy_id": policy_id,
                "date_start": date_start,
                "date_end": date_end,
            },
            headers=headers,
        )
        return r

    def test_submit_approve_balance_decreases(
        self, client: TestClient, superuser_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        """Submit a request, approve it, ledger shows consumed entry."""
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))

        r = self._submit(
            client, superuser_token_headers,
            str(employee.id), str(policy.id),
            "2026-09-07", "2026-09-11",  # Mon-Fri = 5 days
        )
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]
        assert r.json()["status"] == "pending"

        # Approve
        r = client.post(f"{API}/leave-requests/{req_id}/approve", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"

        # Check ledger balance: granted 15, consumed 5, remaining 10
        ledger_r = client.get(
            f"{API}/employees/{employee.id}/leave-ledger"
            f"?policy_id={policy.id}&leave_year=2026",
            headers=superuser_token_headers,
        )
        assert ledger_r.status_code == 200, ledger_r.text
        body = ledger_r.json()
        assert body["summary"]["granted_total"] == "15.00"
        assert body["summary"]["consumed_total"] == "5.00"
        assert body["summary"]["remaining"] == "10.00"

    def test_approve_idempotent_single_ledger_debit(
        self, client: TestClient, superuser_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        """Approving twice must not write two consumed ledger entries."""
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))
        r = self._submit(
            client, superuser_token_headers,
            str(employee.id), str(policy.id), "2026-09-07", "2026-09-07",
        )
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]

        r = client.post(f"{API}/leave-requests/{req_id}/approve", headers=superuser_token_headers)
        assert r.status_code == 200, r.text

        r = client.post(f"{API}/leave-requests/{req_id}/approve", headers=superuser_token_headers)
        assert r.status_code == 200, r.text  # idempotent

        ledger_r = client.get(
            f"{API}/employees/{employee.id}/leave-ledger"
            f"?policy_id={policy.id}&leave_year=2026",
            headers=superuser_token_headers,
        )
        body = ledger_r.json()
        consumed_str = body["summary"]["consumed_total"]
        assert consumed_str == "1.00", f"Expected 1.00 consumed, got {consumed_str}"

    def test_submit_reject_balance_unchanged(
        self, client: TestClient, superuser_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        """Rejecting a request does not affect the ledger."""
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))
        r = self._submit(
            client, superuser_token_headers,
            str(employee.id), str(policy.id), "2026-09-07", "2026-09-11",
        )
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]

        r = client.post(
            f"{API}/leave-requests/{req_id}/reject?note=Insufficient+staffing",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "rejected"

        ledger_r = client.get(
            f"{API}/employees/{employee.id}/leave-ledger"
            f"?policy_id={policy.id}&leave_year=2026",
            headers=superuser_token_headers,
        )
        body = ledger_r.json()
        assert body["summary"]["consumed_total"] == "0.00"

    def test_submit_approve_cancel_reversal_entry(
        self, client: TestClient, superuser_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        """Cancel after approval creates a reversal entry and restores balance."""
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))
        r = self._submit(
            client, superuser_token_headers,
            str(employee.id), str(policy.id), "2026-09-07", "2026-09-11",
        )
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]

        r = client.post(f"{API}/leave-requests/{req_id}/approve", headers=superuser_token_headers)
        assert r.status_code == 200, r.text

        r = client.post(f"{API}/leave-requests/{req_id}/cancel", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"

        ledger_r = client.get(
            f"{API}/employees/{employee.id}/leave-ledger"
            f"?policy_id={policy.id}&leave_year=2026",
            headers=superuser_token_headers,
        )
        body = ledger_r.json()
        assert body["summary"]["consumed_total"] == "0.00"
        assert body["summary"]["remaining"] == "15.00"
        # Check reversal entry exists
        sources = [e["source"] for e in body["data"]]
        assert "reversal" in sources, f"Expected reversal in ledger, got {sources}"

    def test_actor_spoofing_ignored(
        self, client: TestClient, superuser_token_headers, db: Session,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        """Client-supplied created_by_user is ignored; server uses authenticated user."""
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))
        fake_actor = str(uuid.uuid4())
        r = self._submit(
            client, superuser_token_headers,
            str(employee.id), str(policy.id), "2026-09-07", "2026-09-07",
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # created_by_user should be the superuser, not the spoofed value
        superuser = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
        assert body["created_by_user"] == str(superuser.id)
        assert body["created_by_user"] != fake_actor


# --- Validation ------------------------------------------------------------------------


class TestValidation:
    def test_date_end_before_date_start_returns_422(
        self, client: TestClient, superuser_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": str(employee.id),
                "policy_id": str(policy.id),
                "date_start": "2026-09-11",
                "date_end": "2026-09-07",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 422, r.text

    def test_overlap_returns_422(
        self, client: TestClient, superuser_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        """Two overlapping requests for the same employee return 422."""
        self._enroll(client, superuser_token_headers, str(employee.id), str(policy.id))

        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": str(employee.id),
                "policy_id": str(policy.id),
                "date_start": "2026-09-07",
                "date_end": "2026-09-11",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text

        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": str(employee.id),
                "policy_id": str(policy.id),
                "date_start": "2026-09-10",  # overlaps Sep 7-11
                "date_end": "2026-09-14",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 422, r.text
        assert "overlap" in r.json()["detail"].lower()

    def _enroll(self, client: TestClient, headers: dict, employee_id: str, policy_id: str) -> None:
        r = client.post(
            f"{API}/employees/{employee_id}/leave-enrollments",
            json={"policy_id": policy_id, "leave_year": 2026},
            headers=headers,
        )
        if r.status_code != 201:
            raise RuntimeError(f"Enroll failed: {r.status_code} {r.text}")


# --- Admin endpoints -------------------------------------------------------------------


class TestAdminEndpoints:
    def test_accrue_requires_admin_permission(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        r = client.post(
            f"{API}/leave/admin/accrue",
            json={"target_year": 2026, "target_month": 6},
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text

    def test_accrue_missing_params_returns_422(
        self, client: TestClient, hr_user_token_headers,
    ) -> None:
        r = client.post(
            f"{API}/leave/admin/accrue",
            json={"target_year": 2026},  # missing target_month
            headers=hr_user_token_headers,
        )
        assert r.status_code == 422, r.text

    def test_carryover_requires_admin_permission(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        r = client.post(
            f"{API}/leave/admin/carryover",
            json={"target_year_from": 2025, "target_year_to": 2026},
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text

    def test_carryover_missing_params_returns_422(
        self, client: TestClient, hr_user_token_headers,
    ) -> None:
        r = client.post(
            f"{API}/leave/admin/carryover",
            json={"target_year_from": 2025},  # missing target_year_to
            headers=hr_user_token_headers,
        )
        assert r.status_code == 422, r.text

    def _enroll(self, client: TestClient, headers: dict, employee_id: str, policy_id: str, year: int) -> None:
        r = client.post(
            f"{API}/employees/{employee_id}/leave-enrollments",
            json={"policy_id": policy_id, "leave_year": year},
            headers=headers,
        )
        if r.status_code not in (201, 409):  # 409 if already enrolled
            raise RuntimeError(f"Enroll failed: {r.status_code} {r.text}")


# --- Policy deactivation ---------------------------------------------------------------


class TestDeactivatePolicy:
    def test_deactivate_with_active_requests_returns_409(
        self, client: TestClient, superuser_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        """Cannot deactivate a policy with pending or approved requests."""
        # Enroll and submit
        r = client.post(
            f"{API}/employees/{employee.id}/leave-enrollments",
            json={"policy_id": str(policy.id), "leave_year": 2026},
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text

        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": str(employee.id),
                "policy_id": str(policy.id),
                "date_start": "2026-09-07",
                "date_end": "2026-09-11",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text

        r = client.delete(f"{API}/leave-policies/{policy.id}", headers=superuser_token_headers)
        assert r.status_code == 409, r.text
        assert "request" in r.json()["detail"].lower()

    def test_deactivate_no_active_requests_returns_200(
        self, client: TestClient, superuser_token_headers, policy: LeavePolicy,
    ) -> None:
        r = client.delete(f"{API}/leave-policies/{policy.id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
