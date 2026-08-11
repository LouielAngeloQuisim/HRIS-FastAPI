"""Phase 1 test set A — CRUD for parent-dependent resources (design §5).

These resources require a parent chain before they can be created (Department,
Project, Phase, Blocks, Lots, Category, EmployeeProjects, EmpTask, Employee).
The superuser token bypasses RBAC so the tests focus on CRUD + soft-delete
isolation + unique-constraint 409.
"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from tests.utils.employee import (
    build_construction_chain,
    create_division,
    create_employee,
    create_position,
    create_project_type,
    create_subdivision,
)

API = settings.API_V1_STR


class TestParentCrud:
    def test_department_crud(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        division = create_division(db)
        payload = {"code": f"DEP-{uuid.uuid4().hex[:6]}", "name": "Ops", "division_id": str(division.id)}
        r = client.post(f"{API}/departments/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        obj_id = r.json()["id"]

        r = client.post(f"{API}/departments/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 409, r.text

        r = client.patch(
            f"{API}/departments/{obj_id}", json={"name": "Ops Renamed"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200 and r.json()["name"] == "Ops Renamed"

        r = client.delete(f"{API}/departments/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200
        r = client.get(f"{API}/departments/", headers=superuser_token_headers)
        assert not any(i["id"] == obj_id for i in r.json()["data"])

    def test_project_crud(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        subdivision = create_subdivision(db)
        project_type = create_project_type(db)
        payload = {
            "code": f"PROJ-{uuid.uuid4().hex[:6]}",
            "name": "Tower",
            "subdivision_id": str(subdivision.id),
            "project_type_id": str(project_type.id),
        }
        r = client.post(f"{API}/projects/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        obj_id = r.json()["id"]

        r = client.post(f"{API}/projects/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 409, r.text

        r = client.patch(
            f"{API}/projects/{obj_id}", json={"name": "Tower Renamed"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200 and r.json()["name"] == "Tower Renamed"

    def test_phase_blocks_lots_crud(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        chain = build_construction_chain(db)

        # Phase CRUD
        phase = chain["phase"]
        r = client.get(f"{API}/phases/{phase.id}", headers=superuser_token_headers)
        assert r.status_code == 200

        # Block create via API
        block_payload = {"block_name": "Block B", "phase_id": str(chain["phase"].id)}
        r = client.post(f"{API}/blocks/", json=block_payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text

        # Lot create via API
        lot_payload = {"lot_name": "Lot 9", "blocks_id": str(chain["block"].id)}
        r = client.post(f"{API}/lots/", json=lot_payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        lot_id = r.json()["id"]

        # Lot soft-delete (unreferenced by any active category after chain category is gone)
        r = client.delete(f"{API}/lots/{lot_id}", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        r = client.get(f"{API}/lots/", headers=superuser_token_headers)
        assert not any(i["id"] == lot_id for i in r.json()["data"])

    def test_category_crud(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        chain = build_construction_chain(db)
        from tests.utils.employee import create_lot

        fresh_lot = create_lot(db, chain["block"].id)
        payload = {
            "code": f"CAT-{uuid.uuid4().hex[:6]}",
            "project_id": str(chain["project"].id),
            "phase_id": str(chain["phase"].id),
            "blocks_id": str(chain["block"].id),
            "owner_id": str(chain["owner"].id),
            "lot_id": str(fresh_lot.id),
        }
        r = client.post(f"{API}/categories/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text

        r = client.post(f"{API}/categories/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 409, r.text

    def test_employee_project_task_crud(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        chain = build_construction_chain(db)
        employee = create_employee(db)

        ep_payload = {
            "employee_id": str(employee.id),
            "project_id": str(chain["project"].id),
        }
        r = client.post(
            f"{API}/employee-projects/", json=ep_payload, headers=superuser_token_headers
        )
        assert r.status_code == 201, r.text
        ep_id = r.json()["id"]

        task_payload = {"emp_project_id": ep_id, "task_desc": "Build", "assigned_hours": "4.5"}
        r = client.post(f"{API}/emp-tasks/", json=task_payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        task_id = r.json()["id"]

        # approve / deny (gated emp_project/edit, superuser bypasses)
        r = client.post(f"{API}/emp-tasks/{task_id}/approve", headers=superuser_token_headers)
        assert r.status_code == 200
        r = client.post(f"{API}/emp-tasks/{task_id}/deny", headers=superuser_token_headers)
        assert r.status_code == 200

    def test_employee_records_crud(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        position = create_position(db)
        payload = {
            "employee_code": f"EMP-{uuid.uuid4().hex[:6]}",
            "first_name": "Anna",
            "last_name": "Santos",
            "birthdate": "1992-05-05",
            "position_id": str(position.id),
        }
        r = client.post(f"{API}/employees/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 201, r.text
        obj_id = r.json()["id"]

        r = client.post(f"{API}/employees/", json=payload, headers=superuser_token_headers)
        assert r.status_code == 409, r.text

        r = client.patch(
            f"{API}/employees/{obj_id}", json={"employee_status": "On Leave"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200 and r.json()["employee_status"] == "On Leave"

        r = client.delete(f"{API}/employees/{obj_id}", headers=superuser_token_headers)
        assert r.status_code == 200
        r = client.get(f"{API}/employees/", headers=superuser_token_headers)
        assert not any(i["id"] == obj_id for i in r.json()["data"])

    def test_division_delete_guard(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        """Q4: deleting a Division with an active Department child -> 409."""
        division = create_division(db)
        from tests.utils.employee import create_department

        create_department(db, division.id)
        r = client.delete(f"{API}/divisions/{division.id}", headers=superuser_token_headers)
        assert r.status_code == 409, r.text
