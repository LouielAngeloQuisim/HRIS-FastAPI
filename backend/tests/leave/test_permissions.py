"""Phase b3 test set E — permission gate tests (design doc §1.9, test_permissions).

Each gated leave route is blocked for a low-privilege token without the required permission.
Mirrors the existing `tests/rbac/test_route_protection.py` pattern.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.leave.models import LeavePolicy

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


class TestLeaveRequestPermissions:
    """leave_request routes gated by leave_request:view, add, approve."""

    def test_list_requests_requires_view(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        r = client.get(f"{API}/leave-requests/", headers=normal_user_token_headers)
        assert r.status_code == 403, r.text

    def test_submit_requires_add(
        self, client: TestClient, normal_user_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy,
    ) -> None:
        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": str(employee.id),
                "policy_id": str(policy.id),
                "date_start": "2026-09-07",
                "date_end": "2026-09-07",
            },
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text

    def test_approve_requires_approve_permission(
        self, client: TestClient, normal_user_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy, superuser_token_headers,
    ) -> None:
        """An employee without leave_request:approve cannot approve requests."""
        # Submit as superuser
        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": str(employee.id),
                "policy_id": str(policy.id),
                "date_start": "2026-09-07",
                "date_end": "2026-09-07",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]

        # Approve as normal user (no leave_request:approve)
        r = client.post(
            f"{API}/leave-requests/{req_id}/approve",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text

    def test_reject_requires_approve_permission(
        self, client: TestClient, normal_user_token_headers,
        employee: EmployeeRecords, policy: LeavePolicy, superuser_token_headers,
    ) -> None:
        r = client.post(
            f"{API}/leave-requests/",
            json={
                "employee_id": str(employee.id),
                "policy_id": str(policy.id),
                "date_start": "2026-09-07",
                "date_end": "2026-09-07",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]

        r = client.post(
            f"{API}/leave-requests/{req_id}/reject",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text


class TestLeavePolicyPermissions:
    """leave_policy routes gated by leave_policy:view, add, edit, delete."""

    def test_list_policies_requires_view(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        r = client.get(f"{API}/leave-policies/", headers=normal_user_token_headers)
        assert r.status_code == 403, r.text

    def test_create_policy_requires_add(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        r = client.post(
            f"{API}/leave-policies/",
            json={
                "code": f"NEW-{uuid.uuid4().hex[:6]}",
                "name": "New Policy",
                "annual_entitlement_days": "10.00",
            },
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text

    def test_update_policy_requires_edit(
        self, client: TestClient, normal_user_token_headers, policy: LeavePolicy,
    ) -> None:
        r = client.patch(
            f"{API}/leave-policies/{policy.id}",
            json={"name": "Hacked Name"},
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text

    def test_delete_policy_requires_delete(
        self, client: TestClient, normal_user_token_headers, policy: LeavePolicy,
    ) -> None:
        r = client.delete(f"{API}/leave-policies/{policy.id}", headers=normal_user_token_headers)
        assert r.status_code == 403, r.text


class TestHolidayConfigPermissions:
    """holiday_config routes gated by holiday_config:view, add, edit."""

    def test_list_holidays_requires_view(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        r = client.get(f"{API}/holidays/", headers=normal_user_token_headers)
        assert r.status_code == 403, r.text

    def test_create_holiday_requires_add(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        r = client.post(
            f"{API}/holidays/",
            json={
                "code": f"NEWHOL-{uuid.uuid4().hex[:6]}",
                "name": "New Holiday",
                "month_day": "08-15",
            },
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403, r.text


class TestAdminPermissions:
    """Admin endpoints require leave_policy:admin."""

    def test_admin_endpoints_require_admin(
        self, client: TestClient, normal_user_token_headers,
    ) -> None:
        for endpoint, payload in [
            (f"{API}/leave/admin/accrue", {"target_year": 2026, "target_month": 6}),
            (f"{API}/leave/admin/carryover", {"target_year_from": 2025, "target_year_to": 2026}),
            (
                f"{API}/leave/admin/adjust",
                {
                    "employee_id": str(uuid.uuid4()),
                    "policy_id": str(uuid.uuid4()),
                    "leave_year": 2026,
                    "delta": "-1.00",
                    "note": "Test",
                },
            ),
        ]:
            r = client.post(endpoint, json=payload, headers=normal_user_token_headers)
            assert r.status_code == 403, f"{endpoint} returned {r.status_code}, expected 403"
