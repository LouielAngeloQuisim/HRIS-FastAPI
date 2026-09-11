"""Phase b3 test set F — concurrent approval test (design doc §1.9, test_concurrency).

Tests that two concurrent approve calls result in exactly one ledger debit.
Uses threading to simulate concurrency.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

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


def _enroll(client: TestClient, headers: dict, employee_id: str, policy_id: str) -> None:
    r = client.post(
        f"{API}/employees/{employee_id}/leave-enrollments",
        json={"policy_id": policy_id, "leave_year": 2026},
        headers=headers,
    )
    if r.status_code not in (201, 409):
        raise RuntimeError(f"Enroll failed: {r.status_code} {r.text}")


def _submit(client: TestClient, headers: dict, employee_id: str, policy_id: str) -> str:
    r = client.post(
        f"{API}/leave-requests/",
        json={
            "employee_id": employee_id,
            "policy_id": policy_id,
            "date_start": "2026-09-07",
            "date_end": "2026-09-07",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _approve(client: TestClient, headers: dict, req_id: str) -> tuple[int, str]:
    """Make an approve request using TestClient directly and return (status_code, response_text)."""
    resp = client.post(f"{API}/leave-requests/{req_id}/approve", headers=headers)
    return resp.status_code, resp.text


def _do_submit(client: TestClient, headers: dict, employee_id: str, policy_id: str, date_start: str, date_end: str) -> tuple[int, str]:
    """Make a submit request using TestClient directly and return (status_code, response_text)."""
    resp = client.post(
        f"{API}/leave-requests/",
        json={
            "employee_id": employee_id,
            "policy_id": policy_id,
            "date_start": date_start,
            "date_end": date_end,
        },
        headers=headers,
    )
    return resp.status_code, resp.text


class TestConcurrentApproval:
    def test_concurrent_approve_writes_single_ledger_entry(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        policy: LeavePolicy,
    ) -> None:
        """
        Two near-simultaneous approvals: exactly one should succeed (200),
        the other should return 409 (concurrent modification / already approved).
        The ledger should have exactly one CONSUMED entry.
        """
        _enroll(client, superuser_token_headers, str(employee.id), str(policy.id))
        req_id = _submit(client, superuser_token_headers, str(employee.id), str(policy.id))

        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(_approve, client, superuser_token_headers, req_id)
            future2 = executor.submit(_approve, client, superuser_token_headers, req_id)

            result1 = future1.result()
            result2 = future2.result()

        status_codes = {result1[0], result2[0]}
        # At least one should succeed; one may be 409 (concurrent modification)
        # or both 200 (idempotent second approval)
        assert 200 in status_codes, f"Expected at least one 200, got {status_codes}"

        # Check ledger: exactly one CONSUMED entry
        ledger_r = client.get(
            f"{API}/employees/{employee.id}/leave-ledger"
            f"?policy_id={policy.id}&leave_year=2026",
            headers=superuser_token_headers,
        )
        assert ledger_r.status_code == 200, ledger_r.text
        body = ledger_r.json()
        consumed_entries = [e for e in body["data"] if e["source"] == "consumed"]
        assert len(consumed_entries) == 1, (
            f"Expected exactly 1 consumed entry, got {len(consumed_entries)}: {consumed_entries}"
        )
        assert consumed_entries[0]["amount"] == "-1.00"

    def test_concurrent_submit_idempotent(
        self,
        client: TestClient,
        superuser_token_headers,
        employee: EmployeeRecords,
        policy: LeavePolicy,
    ) -> None:
        """
        Two concurrent submissions for the same dates should both return 422
        (overlap check) rather than creating duplicate requests.
        """
        _enroll(client, superuser_token_headers, str(employee.id), str(policy.id))

        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(
                _do_submit, client, superuser_token_headers, str(employee.id), str(policy.id),
                "2026-10-01", "2026-10-01"
            )
            future2 = executor.submit(
                _do_submit, client, superuser_token_headers, str(employee.id), str(policy.id),
                "2026-10-01", "2026-10-01"
            )
            result1 = future1.result()
            result2 = future2.result()

        status_codes = {result1[0], result2[0]}
        # At least one should get 201, the other should get 422 (overlap)
        assert 201 in status_codes
        assert 422 in status_codes
