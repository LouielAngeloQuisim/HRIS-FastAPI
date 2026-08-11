"""Phase 1 — Dashboard KPI counts (design §1.6 / Q10).

Each field is verified against an independently-seeded expected count, not just
"endpoint returns 200". dtr_records_daily_count is 0/pending until Phase 2
(no worker_logs table yet).
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from tests.utils.employee import (
    build_construction_chain,
    create_division,
    create_employee,
)

API = settings.API_V1_STR


class TestDashboard:
    def test_counts_match_seeded_data(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        # Tests are not transaction-isolated, so clear prior residue first so the
        # seeded counts are exact and independently verifiable.
        from sqlmodel import text

        for table in [
            "emp_task",
            "employee_projects",
            "category",
            "lots",
            "blocks",
            "phase",
            "model",
            "model_types",
            "owner",
            "project",
            "project_type",
            "position",
            "employee_attachments",
            "employee_additional_records",
            "employee_records",
            "subdivision",
            "department",
            "division",
        ]:
            db.exec(text(f"DELETE FROM {table}"))
        db.commit()

        # Seed known quantities of each countable entity.
        create_division(db)
        create_division(db)  # two divisions
        create_employee(db)
        create_employee(db)
        create_employee(db)  # three employees
        build_construction_chain(db)  # 1 subdivision, 1 project, 1 owner

        # Independent expectations:
        # subdivisions: chain creates 1
        # projects: chain creates 1
        # owners: chain creates 1
        # employee_projects: none seeded
        # departments: none seeded
        # model_count: none seeded

        r = client.get(f"{API}/dashboard/", headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["employee_records"] == 3
        assert body["divisions"] == 2
        assert body["subdivisions"] == 1
        assert body["projects"] == 1
        assert body["owners"] == 1
        assert body["departments"] == 0
        assert body["employee_projects"] == 0
        assert body["model_count"] == 0
        # Pending Phase 2 (no worker_logs table yet) -> 0, not fabricated.
        assert body["dtr_records_daily_count"] == 0

    def test_dashboard_requires_emp_list_view(
        self, client: TestClient, normal_user_token_headers
    ) -> None:
        """A user without emp_list/view (SUR has none) gets 403."""
        r = client.get(f"{API}/dashboard/", headers=normal_user_token_headers)
        assert r.status_code == 403
