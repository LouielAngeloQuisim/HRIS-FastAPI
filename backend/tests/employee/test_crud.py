"""Phase 1 test set A — CRUD per resource (design §5).

Uses the superuser token (bypasses RBAC) so the tests exercise CRUD behaviour,
soft-delete isolation and unique-constraint 409s rather than permission checks
(those are covered separately in test_route_protection / test_require_permission).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config.settings import settings

API = settings.API_V1_STR


class TestNoParentCrud:
    """CRUD for resources with no required parent dependency."""

    @pytest.mark.parametrize(
        "prefix,create,code_field",
        [
            ("/divisions", {"name": "Dup Division"}, "code"),
            ("/subdivisions", {"name": "Dup Sub", "location": "Loc"}, "subdivision_code"),
            ("/project-types", {"name": "Dup Type"}, "code"),
            ("/positions", {"title": "Dup Pos"}, "code"),
            ("/model-types", {"name": "Dup MT"}, "code"),
        ],
    )
    def test_crud(
        self,
        client: TestClient,
        superuser_token_headers,
        prefix: str,
        create: dict,
        code_field: str,
    ) -> None:
        code_value = f"{uuid.uuid4().hex[:10]}"
        payload = {**create, code_field: code_value}
        # create -> 201
        r = client.post(f"{API}{prefix}/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        obj_id = r.json()["id"]

        # duplicate unique code -> 409 (DB constraint backstop)
        r = client.post(f"{API}{prefix}/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 409, r.text

        # read by id -> 200
        r = client.get(f"{API}{prefix}/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == obj_id

        # list includes it
        r = client.get(f"{API}{prefix}/", headers=superuser_token_headers)
        assert r.status_code == 200
        assert any(item["id"] == obj_id for item in r.json()["data"])

        # update -> 200, reflected
        update_key = "name" if "name" in create else "title"
        r = client.patch(
            f"{API}{prefix}/{obj_id}",
            json={update_key: "Renamed"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()[update_key] == "Renamed"

        # soft-delete -> Message; gone from list; is_deleted True
        r = client.delete(f"{API}{prefix}/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        r = client.get(f"{API}{prefix}/", headers=superuser_token_headers)
        assert not any(item["id"] == obj_id for item in r.json()["data"])

    def test_read_unknown_returns_404(
        self, client: TestClient, superuser_token_headers
    ) -> None:
        r = client.get(f"{API}/divisions/00000000-0000-0000-0000-000000000000",
                       headers=superuser_token_headers)
        assert r.status_code == 404
