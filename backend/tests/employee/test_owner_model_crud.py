"""Phase 1 test set — CRUD contract for Owner and Model (design §5).

Closes the blind spot flagged in the session audit: both resources were
listed as CRUD-complete in AGENTS.md §2 but had NO backend test proving
create/read/update/delete actually persists correctly against the DB — only
schema-shape tests existed (test_owner_category_lots.py). A broken POST or
PATCH route on either was invisible to the test suite.

Uses the superuser token (bypasses RBAC) so the tests exercise CRUD behaviour,
soft-delete isolation and field-level persistence rather than permission checks
(those are covered centrally by test_route_protection / test_require_permission).
A dedicated permission-gate test is included for each resource.
"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee import models as m
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


# --- Owner ------------------------------------------------------------------


class TestOwnerCrud:
    """Full CRUD lifecycle for Owner against the real DB."""

    def _owner_payload(self) -> dict:
        return {
            "first_name": "Jane",
            "last_name": "Doe",
            "lot_no": "L-100",
            "block": "B-5",
            "email": random_email(),
            "contact_no": "+639171234567",
        }

    def test_create_returns_201_and_persists(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        payload = self._owner_payload()
        r = client.post(f"{API}/owners/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"]
        assert body["first_name"] == payload["first_name"]
        assert body["last_name"] == payload["last_name"]
        assert body["lot_no"] == payload["lot_no"]
        assert body["block"] == payload["block"]
        assert body["email"] == payload["email"]
        assert body["contact_no"] == payload["contact_no"]
        assert body["is_deleted"] is False

        # Verify it actually hit the DB, not just the response
        db_obj = db.get(m.Owner, uuid.UUID(body["id"]))
        assert db_obj is not None
        assert db_obj.first_name == payload["first_name"]

    def test_read_by_id_existing_and_unknown(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        # Create one
        r = client.post(
            f"{API}/owners/", json=self._owner_payload(), headers=superuser_token_headers
        )
        obj_id = r.json()["id"]

        # Read by id -> 200
        r = client.get(f"{API}/owners/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == obj_id

        # Unknown id -> 404
        r = client.get(
            f"{API}/owners/00000000-0000-0000-0000-000000000000",
            headers=superuser_token_headers,
        )
        assert r.status_code == 404

    def test_list_returns_only_active_rows(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        # Create two owners
        r1 = client.post(
            f"{API}/owners/", json=self._owner_payload(), headers=superuser_token_headers
        )
        r2 = client.post(
            f"{API}/owners/", json=self._owner_payload(), headers=superuser_token_headers
        )
        id1, id2 = r1.json()["id"], r2.json()["id"]

        # List includes both
        r = client.get(f"{API}/owners/", headers=superuser_token_headers)
        assert r.status_code == 200
        ids = [item["id"] for item in r.json()["data"]]
        assert id1 in ids
        assert id2 in ids

        # Soft-delete one
        client.delete(f"{API}/owners/{id1}", headers=superuser_token_headers)

        # List no longer includes the deleted one
        r = client.get(f"{API}/owners/", headers=superuser_token_headers)
        ids = [item["id"] for item in r.json()["data"]]
        assert id1 not in ids
        assert id2 in ids

    def test_update_changes_fields_unrelated_not_nulled(
        self, client: TestClient, superuser_token_headers
    ) -> None:
        r = client.post(
            f"{API}/owners/", json=self._owner_payload(), headers=superuser_token_headers
        )
        obj_id = r.json()["id"]

        # Patch only first_name
        r = client.patch(
            f"{API}/owners/{obj_id}",
            json={"first_name": "Updated"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["first_name"] == "Updated"
        # Unrelated fields preserved
        assert body["last_name"] == "Doe"
        assert body["lot_no"] == "L-100"
        assert body["block"] == "B-5"
        assert body["email"] is not None
        assert body["contact_no"] is not None

    def test_soft_delete_sets_flag_and_disappears(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        r = client.post(
            f"{API}/owners/", json=self._owner_payload(), headers=superuser_token_headers
        )
        obj_id = r.json()["id"]

        # Delete -> 200
        r = client.delete(f"{API}/owners/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text

        # Gone from list
        r = client.get(f"{API}/owners/", headers=superuser_token_headers)
        assert not any(item["id"] == obj_id for item in r.json()["data"])

        # Direct DB check: is_deleted=True, deleted_at set
        db_obj = db.get(m.Owner, uuid.UUID(obj_id))
        assert db_obj is not None
        assert db_obj.is_deleted is True
        assert db_obj.deleted_at is not None

    def test_permission_gate_blocks_low_privilege(
        self, client: TestClient, db: Session
    ) -> None:
        """Token with a role that lacks owner/add gets 403."""
        from app.rbac.models import Role
        from app.user.models import UserCreate
        from app.user.services import create_user

        # Create a role with NO permissions (the empty_role equivalent)
        empty_role = Role(code=f"NONE-{random_lower_string()[:8]}", name="No Access")
        db.add(empty_role)
        db.commit()
        db.refresh(empty_role)

        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(), password=password, is_superuser=False
            ),
        )
        user.role_id = empty_role.id
        db.add(user)
        db.commit()
        db.refresh(user)

        r = client.post(
            f"{API}/login/access-token",
            data={"username": user.email, "password": password},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post(
            f"{API}/owners/", json=self._owner_payload(), headers=headers
        )
        assert r.status_code == 403


# --- Model ------------------------------------------------------------------


class TestModelCrud:
    """Full CRUD lifecycle for Model against the real DB."""

    def _model_payload(self, model_type_id: uuid.UUID | None = None) -> dict:
        payload: dict = {"name": f"Model-{random_lower_string()[:8]}"}
        if model_type_id is not None:
            payload["model_type_id"] = str(model_type_id)
        return payload

    def test_create_returns_201_and_persists(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        payload = self._model_payload()
        r = client.post(f"{API}/models/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"]
        assert body["name"] == payload["name"]
        assert body["is_deleted"] is False

        db_obj = db.get(m.Model, uuid.UUID(body["id"]))
        assert db_obj is not None
        assert db_obj.name == payload["name"]

    def test_create_with_model_type_id(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        """Model.model_type_id is a nullable FK — verify it persists when provided."""
        # Create a model_type to reference
        mt = m.ModelTypes(name="TestMT", code=f"MT-{random_lower_string()[:8]}")
        db.add(mt)
        db.commit()
        db.refresh(mt)

        payload = self._model_payload(model_type_id=mt.id)
        r = client.post(f"{API}/models/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        assert r.json()["model_type_id"] == str(mt.id)

    def test_read_by_id_existing_and_unknown(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        r = client.post(
            f"{API}/models/", json=self._model_payload(), headers=superuser_token_headers
        )
        obj_id = r.json()["id"]

        r = client.get(f"{API}/models/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == obj_id

        r = client.get(
            f"{API}/models/00000000-0000-0000-0000-000000000000",
            headers=superuser_token_headers,
        )
        assert r.status_code == 404

    def test_list_returns_only_active_rows(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        r1 = client.post(
            f"{API}/models/", json=self._model_payload(), headers=superuser_token_headers
        )
        r2 = client.post(
            f"{API}/models/", json=self._model_payload(), headers=superuser_token_headers
        )
        id1, id2 = r1.json()["id"], r2.json()["id"]

        r = client.get(f"{API}/models/", headers=superuser_token_headers)
        ids = [item["id"] for item in r.json()["data"]]
        assert id1 in ids and id2 in ids

        client.delete(f"{API}/models/{id1}", headers=superuser_token_headers)

        r = client.get(f"{API}/models/", headers=superuser_token_headers)
        ids = [item["id"] for item in r.json()["data"]]
        assert id1 not in ids
        assert id2 in ids

    def test_update_changes_fields_unrelated_not_nulled(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        # Create with a model_type_id
        mt = m.ModelTypes(name="TestMT", code=f"MT-{random_lower_string()[:8]}")
        db.add(mt)
        db.commit()
        db.refresh(mt)

        r = client.post(
            f"{API}/models/",
            json=self._model_payload(model_type_id=mt.id),
            headers=superuser_token_headers,
        )
        obj_id = r.json()["id"]

        r = client.patch(
            f"{API}/models/{obj_id}",
            json={"name": "Renamed Model"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "Renamed Model"
        # model_type_id preserved
        assert body["model_type_id"] == str(mt.id)

    def test_soft_delete_sets_flag_and_disappears(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        r = client.post(
            f"{API}/models/", json=self._model_payload(), headers=superuser_token_headers
        )
        obj_id = r.json()["id"]

        r = client.delete(f"{API}/models/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text

        r = client.get(f"{API}/models/", headers=superuser_token_headers)
        assert not any(item["id"] == obj_id for item in r.json()["data"])

        db_obj = db.get(m.Model, uuid.UUID(obj_id))
        assert db_obj is not None
        assert db_obj.is_deleted is True
        assert db_obj.deleted_at is not None

    def test_permission_gate_blocks_low_privilege(
        self, client: TestClient, db: Session
    ) -> None:
        """Token with a role that lacks models/add gets 403."""
        from app.rbac.models import Role
        from app.user.models import UserCreate
        from app.user.services import create_user

        # Create a role with NO permissions (the empty_role equivalent)
        empty_role = Role(code=f"NONE-{random_lower_string()[:8]}", name="No Access")
        db.add(empty_role)
        db.commit()
        db.refresh(empty_role)

        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(), password=password, is_superuser=False
            ),
        )
        user.role_id = empty_role.id
        db.add(user)
        db.commit()
        db.refresh(user)

        r = client.post(
            f"{API}/login/access-token",
            data={"username": user.email, "password": password},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post(
            f"{API}/models/", json=self._model_payload(), headers=headers
        )
        assert r.status_code == 403
