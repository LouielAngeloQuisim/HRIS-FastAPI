"""Phase 1 — EmployeeAdditionalRecords CRUD + ownership (design §1.1 / §2).

A low-privilege user can read/update their OWN annex but gets 403 on someone
else's. An elevated role (HR: emp_list edit) can access any employee's annex.
"""


from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.rbac.selectors import get_role_by_code
from app.user.models import UserCreate
from app.user.services import create_user
from tests.utils.employee import create_employee
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


def _make_user(db: Session, role_code: str):
    role = get_role_by_code(session=db, code=role_code)
    assert role is not None
    password = random_lower_string()
    user = create_user(
        session=db, user_create=UserCreate(email=random_email(), password=password)
    )
    user.role_id = role.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, password


def _token(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post(
        f"{API}/login/access-token",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _annex_url(employee_id) -> str:
    return f"{API}/employees/{employee_id}/additional-records"


class TestAdditionalRecordsOwnership:
    def test_low_privilege_user_reads_own_annex(
        self, client: TestClient, db: Session
    ) -> None:
        user, password = _make_user(db, "SUR")
        employee = create_employee(db, user_id=user.id)
        headers = _token(client, user.email, password)

        # create own annex via PATCH
        r = client.patch(
            _annex_url(employee.id),
            json={"sss_number": "123-456-789"},
            headers=headers,
        )
        assert r.status_code == 200, r.text

        # read own annex
        r = client.get(_annex_url(employee.id), headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["employee_id"] == str(employee.id)

    def test_low_privilege_user_blocked_from_others_annex(
        self, client: TestClient, db: Session
    ) -> None:
        user, password = _make_user(db, "SUR")
        create_employee(db, user_id=user.id)  # their own record exists
        other = create_employee(db)  # someone else's record (no user link)
        headers = _token(client, user.email, password)

        r = client.get(_annex_url(other.id), headers=headers)
        assert r.status_code == 403, r.text

        r = client.patch(_annex_url(other.id), json={"course": "BSCS"}, headers=headers)
        assert r.status_code == 403, r.text

    def test_elevated_role_reads_any_annex(
        self, client: TestClient, db: Session
    ) -> None:
        hr_user, password = _make_user(db, "HR")
        other = create_employee(db)
        # seed an annex for the other employee
        from app.employee.schemas import EmployeeAdditionalRecordsUpdate
        from app.employee.services import upsert_additional_records

        upsert_additional_records(
            session=db,
            employee_id=other.id,
            data=EmployeeAdditionalRecordsUpdate(tin_number="TIN-999"),
        )

        headers = _token(client, hr_user.email, password)
        r = client.get(_annex_url(other.id), headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["tin_number"] == "TIN-999"

    def test_annex_is_upsert_single_row(
        self, client: TestClient, db: Session, superuser_token_headers
    ) -> None:
        employee = create_employee(db)
        url = _annex_url(employee.id)
        r = client.patch(url, json={"course": "BSCS"}, headers=superuser_token_headers)
        assert r.status_code == 200
        r = client.patch(url, json={"school_graduated": "UP"}, headers=superuser_token_headers)
        assert r.status_code == 200
        # still one row
        from app.employee.selectors import get_additional_records_for_employee

        annex = get_additional_records_for_employee(session=db, employee_id=employee.id)
        assert annex is not None
        assert annex.course == "BSCS"
        assert annex.school_graduated == "UP"
