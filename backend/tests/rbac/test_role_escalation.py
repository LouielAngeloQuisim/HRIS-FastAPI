"""Phase 1 b1 required test #2 - "a user cannot escalate their own role".

Covers design §3 / §5 Test set B. The legacy UsersController::updateUser let a
caller set their own user_type. Here the role is omitted from all user-update
schemas and only settable via the dedicated admin endpoint.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.rbac.selectors import get_role_by_code
from app.user.models import UserCreate
from app.user.services import create_user
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


@pytest.fixture
def low_privilege_user(db: Session) -> Iterator[dict]:
    """A user bound to the low-privilege SUR role, plus a login token."""
    role = get_role_by_code(session=db, code="SUR")
    assert role is not None
    password = random_lower_string()
    user = create_user(
        session=db, user_create=UserCreate(email=random_email(), password=password)
    )
    user.role_id = role.id
    db.add(user)
    db.commit()
    db.refresh(user)

    yield {"user": user, "password": password}

    db.delete(user)
    db.commit()


def _token(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post(
        f"{API}/login/access-token",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestNoRoleEscalation:
    def test_self_update_cannot_change_role(
        self, client: TestClient, db: Session, low_privilege_user: dict
    ) -> None:
        """Sending role_id/role on PATCH /users/me must not change the role."""
        user = low_privilege_user["user"]
        admin_role = get_role_by_code(session=db, code="SADM")
        headers = _token(client, user.email, low_privilege_user["password"])

        r = client.patch(
            f"{API}/users/me",
            json={"role_id": str(admin_role.id)},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        db.refresh(user)
        assert user.role_id == get_role_by_code(session=db, code="SUR").id

    def test_self_update_cannot_set_role_field(
        self, client: TestClient, db: Session, low_privilege_user: dict
    ) -> None:
        """Even a legacy 'user_type' key is ignored (schema omits it)."""
        user = low_privilege_user["user"]
        headers = _token(client, user.email, low_privilege_user["password"])
        r = client.patch(f"{API}/users/me", json={"user_type": "SADM"}, headers=headers)
        assert r.status_code in (200, 422)
        db.refresh(user)
        assert user.role_id == get_role_by_code(session=db, code="SUR").id

    def test_role_change_requires_admin_permission(
        self, client: TestClient, db: Session, low_privilege_user: dict
    ) -> None:
        """POST /users/{id}/role as a non-admin -> 403."""
        user = low_privilege_user["user"]
        headers = _token(client, user.email, low_privilege_user["password"])
        r = client.post(
            f"{API}/users/{user.id}/role",
            json={"role_code": "SADM"},
            headers=headers,
        )
        assert r.status_code == 403, r.text

    def test_non_superuser_cannot_assign_system_role(
        self, client: TestClient, db: Session, low_privilege_user: dict
    ) -> None:
        """Even with admin/edit, a non-superuser cannot assign a system role."""
        from app.rbac.models import RoleCreate
        from app.rbac.services import create_role

        # An admin-ish role with administration/edit but is_system=False.
        adminish = create_role(
            session=db,
            role_in=RoleCreate(code=f"ADM_{uuid.uuid4().hex[:6]}", name="Adminish"),
        )
        user = low_privilege_user["user"]
        user.role_id = adminish.id
        db.add(user)
        db.commit()

        # Give the adminish role administration/edit permission so it passes the gate.
        from app.rbac.models import RolePermission
        from app.rbac.selectors import get_module_by_code

        admin_module = get_module_by_code(session=db, code="administration")
        db.add(
            RolePermission(
                role_id=adminish.id, module_id=admin_module.id,
                can_view=True, can_edit=True,
            )
        )
        db.commit()

        headers = _token(client, user.email, low_privilege_user["password"])
        r = client.post(
            f"{API}/users/{user.id}/role",
            json={"role_code": "SADM"},
            headers=headers,
        )
        assert r.status_code == 403, r.text

    def test_admin_can_assign_role(self, client: TestClient, superuser_token_headers) -> None:
        """A superuser (or admin) can assign a role via the dedicated endpoint."""
        # create a target user to re-role
        password = random_lower_string()
        email = random_email()
        r = client.post(
            f"{API}/users/",
            json={"email": email, "password": password, "full_name": "Target"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        user_id = r.json()["id"]
        r = client.post(
            f"{API}/users/{user_id}/role",
            json={"role_code": "HR"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["role_id"] is not None
