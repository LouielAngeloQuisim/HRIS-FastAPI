"""Phase 1 test set D — Indexing & Constraints (design §5 Point 4 / §7).

D.1: post-migration catalog check that each §7.1 composite (fk, is_deleted)
index actually exists.
D.2: unique-constraint violation -> mapped 409 (not 500), ErrorBody shape.
D.3: DB constraint is the real backstop (documented manual/load-test item).
"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, text

from app.config.settings import settings
from tests.utils.employee import build_construction_chain

API = settings.API_V1_STR

# Every composite index declared in design §7.1, as (table, [columns]).
EXPECTED_COMPOSITE_INDEXES = {
    "employee_records": [["division_id", "is_deleted"], ["department_id", "is_deleted"], ["employee_status", "is_deleted"]],
    "category": [["project_id", "is_deleted"], ["phase_id", "is_deleted"]],
    "phase": [["subdivision_id", "is_deleted"]],
    "blocks": [["phase_id", "is_deleted"]],
    "lots": [["blocks_id", "is_deleted"]],
    "employee_projects": [["project_id", "is_deleted"], ["employee_id", "is_deleted"]],
    "emp_task": [["emp_project_id", "is_deleted"]],
    "project": [["subdivision_id", "is_deleted"], ["project_type_id", "is_deleted"]],
    "department": [["division_id", "is_deleted"]],
}


class TestIndexesExist:
    def test_composite_indexes_exist(self, db: Session) -> None:
        rows = db.exec(
            text(
                "SELECT tablename, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public'"
            )
        ).all()
        index_by_table: dict[str, list[str]] = {}
        for tablename, indexdef in rows:
            index_by_table.setdefault(tablename, []).append(indexdef)

        for table, combos in EXPECTED_COMPOSITE_INDEXES.items():
            defs = index_by_table.get(table, [])
            for combo in combos:
                # Column order matters; look for "col1, col2" adjacency in the def.
                joined = ", ".join(combo)
                assert any(joined in d for d in defs), (
                    f"{table} missing composite index ({joined})"
                )


class TestUniqueConstraint409:
    def _assert_409(self, r) -> None:
        assert r.status_code == 409, r.text
        body = r.json()
        # ErrorBody shape (design D.2): success=false, detail + structured error.
        # `type` is "conflict" when the DB IntegrityError handler fires, or
        # "http_error" when a route pre-checks the duplicate explicitly.
        assert body["success"] is False
        assert body["detail"]
        assert body["error"]["type"] in ("conflict", "http_error")
        assert body["error"]["message"]

    def test_duplicate_employee_code_returns_409(
        self, client: TestClient, superuser_token_headers
    ) -> None:
        code = f"EMP-{uuid.uuid4().hex[:6]}"
        payload = {
            "employee_code": code,
            "first_name": "A",
            "last_name": "B",
            "birthdate": "1990-01-01",
        }
        r1 = client.post(f"{API}/employees/", json=payload, headers=superuser_token_headers)
        assert r1.status_code == 201, r1.text
        r2 = client.post(f"{API}/employees/", json=payload, headers=superuser_token_headers)
        self._assert_409(r2)

    def test_duplicate_division_code_returns_409(
        self, client: TestClient, superuser_token_headers
    ) -> None:
        code = f"DIV-{uuid.uuid4().hex[:6]}"
        payload = {"code": code, "name": "Div"}
        r1 = client.post(f"{API}/divisions/", json=payload, headers=superuser_token_headers)
        assert r1.status_code == 201, r1.text
        r2 = client.post(f"{API}/divisions/", json=payload, headers=superuser_token_headers)
        self._assert_409(r2)

    def test_duplicate_role_code_returns_409(
        self, client: TestClient, superuser_token_headers
    ) -> None:
        code = f"R-{uuid.uuid4().hex[:6]}"
        payload = {"code": code, "name": "Role"}
        r1 = client.post(f"{API}/rbac/roles", json=payload, headers=superuser_token_headers)
        assert r1.status_code == 201, r1.text
        r2 = client.post(f"{API}/rbac/roles", json=payload, headers=superuser_token_headers)
        self._assert_409(r2)

    def test_duplicate_category_lot_id_returns_409(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        """Two Categories claiming the same Lot -> 409 (uq_lots_category_id)."""
        chain = build_construction_chain(db)
        # build a second category with the same lot_id
        second = {
            "code": f"CAT2-{uuid.uuid4().hex[:6]}",
            "project_id": str(chain["project"].id),
            "phase_id": str(chain["phase"].id),
            "blocks_id": str(chain["block"].id),
            "lot_id": str(chain["lot"].id),
        }
        r = client.post(f"{API}/categories/", json=second, headers=superuser_token_headers)
        assert r.status_code == 409, r.text
