"""Phase b3 test set D — holiday route tests (design doc §1.9, test_holiday_routes).

Tests for holiday config CRUD, holiday instance creation, and is_holiday behaviour.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.database import engine
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.leave.models import HolidayConfig

API = settings.API_V1_STR


@pytest.fixture
def holiday_config(db: Session) -> HolidayConfig:
    cfg = HolidayConfig(
        code=f"NEWYEAR-{uuid.uuid4().hex[:6]}",
        name="New Year's Day",
        month_day="01-01",
        type="regular",
        is_recurring=True,
        is_active=True,
        is_deleted=False,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


class TestHolidayConfigCrud:
    def test_create_holiday_config(self, client: TestClient, superuser_token_headers) -> None:
        r = client.post(
            f"{API}/holidays/",
            json={
                "code": f"INDEP-{uuid.uuid4().hex[:6]}",
                "name": "Independence Day",
                "month_day": "06-12",
                "type": "regular",
                "multiplier_regular_rest_day": "2.600",
                "multiplier_overtime_rest_day": "3.380",
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "Independence Day"
        assert r.json()["multiplier_regular_rest_day"] == "2.600"
        assert r.json()["multiplier_overtime_rest_day"] == "3.380"

    def test_rest_day_multiplier_must_be_at_least_one(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.post(
            f"{API}/holidays/",
            json={
                "code": f"BADFACTOR-{uuid.uuid4().hex[:6]}",
                "name": "Invalid factor",
                "month_day": "06-12",
                "type": "regular",
                "multiplier_regular_rest_day": "0.9",
            },
            headers=superuser_token_headers,
        )
        assert response.status_code == 422, response.text

    def test_list_holiday_configs(
        self, client: TestClient, superuser_token_headers, holiday_config: HolidayConfig,
    ) -> None:
        r = client.get(f"{API}/holidays/", headers=superuser_token_headers)
        assert r.status_code == 200
        assert any(c["id"] == str(holiday_config.id) for c in r.json()["data"])

    def test_update_holiday_config(
        self, client: TestClient, superuser_token_headers, holiday_config: HolidayConfig,
    ) -> None:
        r = client.patch(
            f"{API}/holidays/{holiday_config.id}",
            json={"name": "Updated Holiday Name"},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Updated Holiday Name"

    def test_soft_delete_holiday_config(
        self, client: TestClient, superuser_token_headers, holiday_config: HolidayConfig,
    ) -> None:
        r = client.patch(
            f"{API}/holidays/{holiday_config.id}",
            json={"is_active": False},
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is False


class TestHolidayInstance:
    def test_create_instance_with_observed_and_raw_date(
        self, client: TestClient, superuser_token_headers, holiday_config: HolidayConfig,
    ) -> None:
        """Creating an instance stores both observed_date and raw_date."""
        r = client.post(
            f"{API}/holidays/instances",
            json={
                "config_id": str(holiday_config.id),
                "observed_date": "2026-01-01",
                "raw_date": "2026-01-01",
                "leave_year": 2026,
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["observed_date"] == "2026-01-01"
        assert body["raw_date"] == "2026-01-01"
        assert body["leave_year"] == 2026

    def test_create_instance_with_weekend_observation(
        self, client: TestClient, superuser_token_headers, db: Session,
    ) -> None:
        """Non-recurring holiday with observe_weekend_as creates correct instance."""
        # Create a holiday that falls on Saturday
        sat_config = HolidayConfig(
            code=f"SAT-{uuid.uuid4().hex[:6]}",
            name="Saturday Holiday",
            month_day="12-26",
            type="special_non_working",
            observe_weekend_as="previous_friday",
            is_recurring=False,
            is_active=True,
            is_deleted=False,
        )
        db.add(sat_config)
        db.commit()
        db.refresh(sat_config)

        r = client.post(
            f"{API}/holidays/instances",
            json={
                "config_id": str(sat_config.id),
                "observed_date": "2037-12-25",  # Friday (observed)
                "raw_date": "2037-12-26",       # Saturday (actual)
                "leave_year": 2037,
            },
            headers=superuser_token_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["observed_date"] == "2037-12-25"
        assert body["raw_date"] == "2037-12-26"

    def test_list_instances(
        self, client: TestClient, superuser_token_headers, holiday_config: HolidayConfig,
    ) -> None:
        # Create an instance
        client.post(
            f"{API}/holidays/instances",
            json={
                "config_id": str(holiday_config.id),
                "observed_date": "2026-01-01",
                "leave_year": 2026,
            },
            headers=superuser_token_headers,
        )

        r = client.get(f"{API}/holidays/instances?leave_year=2026", headers=superuser_token_headers)
        assert r.status_code == 200
        instances = r.json()["data"]
        assert any(i["config_id"] == str(holiday_config.id) for i in instances)


class TestIsHoliday:
    def test_is_holiday_checks_observed_date(
        self, client: TestClient, superuser_token_headers,
        holiday_config: HolidayConfig,
    ) -> None:
        """A date is a holiday if it matches an instance's observed_date, not raw_date."""
        # Create instance with observed != raw
        inst_r = client.post(
            f"{API}/holidays/instances",
            json={
                "config_id": str(holiday_config.id),
                "observed_date": "2026-01-01",
                "raw_date": "2026-01-02",  # different from observed
                "leave_year": 2026,
            },
            headers=superuser_token_headers,
        )
        assert inst_r.status_code == 201, inst_r.text
        created_instance_id = inst_r.json()["id"]

        # Query calendar — only the observed_date should be treated as holiday
        # We test this via the calendar endpoint
        # First we need an employee
        emp = EmployeeRecords(
            employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
            first_name="Test", last_name="User", birthdate="1990-01-01",
        )
        with Session(engine) as sess:
            sess.add(emp)
            sess.commit()
            sess.refresh(emp)
        emp_id = str(emp.id)

        r = client.get(
            f"{API}/employees/{emp_id}/leave-calendar"
            f"?from_date=2026-01-01&to_date=2026-01-02",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200, r.text
        events = r.json()
        holiday_events = [e for e in events if e["type"] == "holiday"]
        # Jan 1 is observed = holiday; Jan 2 is raw but not observed = not holiday
        # Our specific instance should be in the results with observed_date Jan 1
        our_holidays = [e for e in holiday_events if e["id"] == created_instance_id]
        assert len(our_holidays) == 1, f"Expected our holiday instance to be in calendar, got {[e['id'] for e in holiday_events]}"
        assert our_holidays[0]["observed_date"] == "2026-01-01"

    def test_non_recurring_outside_year_returns_none(
        self, client: TestClient, superuser_token_headers, db: Session,
    ) -> None:
        """A non-recurring holiday for a different year should not appear."""
        cfg = HolidayConfig(
            code=f"NONREC-{uuid.uuid4().hex[:6]}",
            name="One-Time Event",
            month_day="03-15",
            type="special_non_working",
            is_recurring=False,
            is_active=True,
            is_deleted=False,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

        # Create instance for 2025 only
        client.post(
            f"{API}/holidays/instances",
            json={
                "config_id": str(cfg.id),
                "observed_date": "2025-03-15",
                "leave_year": 2025,
            },
            headers=superuser_token_headers,
        )

        # Should not appear in 2026 instances
        r = client.get(f"{API}/holidays/instances?leave_year=2026", headers=superuser_token_headers)
        instances = r.json()["data"]
        assert not any(i["config_id"] == str(cfg.id) for i in instances)


def test_delete_holiday_hides_template_and_preserves_instances(
    client, db, superuser_token_headers, holiday_config,
):
    from app.leave.models import HolidayInstance

    instance = HolidayInstance(
        config_id=holiday_config.id, observed_date="2026-01-01",
        raw_date="2026-01-01", leave_year=2026,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    instance_id = instance.id
    config_id = holiday_config.id
    response = client.delete(
        f"{API}/holidays/{config_id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    db.refresh(holiday_config)
    assert holiday_config.is_deleted is True
    assert holiday_config.deleted_at is not None
    assert db.get(HolidayInstance, instance_id) is not None
    listed = client.get(f"{API}/holidays/", headers=superuser_token_headers)
    assert all(row["id"] != str(config_id) for row in listed.json()["data"])
    assert client.delete(
        f"{API}/holidays/{config_id}", headers=superuser_token_headers
    ).status_code == 404


def test_delete_holiday_requires_delete_permission(
    client, normal_user_token_headers, holiday_config, db,
):
    config_id = holiday_config.id
    assert client.delete(f"{API}/holidays/{config_id}").status_code == 401
    assert client.delete(
        f"{API}/holidays/{config_id}", headers=normal_user_token_headers
    ).status_code == 403
    db.refresh(holiday_config)
    assert holiday_config.is_deleted is False


def test_delete_missing_holiday_returns_404(client, superuser_token_headers):
    response = client.delete(
        f"{API}/holidays/{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404
