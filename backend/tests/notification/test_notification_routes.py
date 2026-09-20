"""Phase B5 — notification route tests."""

from fastapi.testclient import TestClient

from app.config.settings import settings

API = settings.API_V1_STR


def test_create_and_read_notification(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    payload = {
        "type": "leave_approved",
        "title": "Leave approved",
        "body": "Your leave has been approved",
        "data": {"leave_id": "123"},
    }
    r = client.post(f"{API}/notifications/", json=payload, headers=superuser_token_headers)
    assert r.status_code == 201, r.text
    obj_id = r.json()["id"]

    r = client.get(f"{API}/notifications/{obj_id}", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Leave approved"


def test_list_notifications(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.get(f"{API}/notifications/", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    assert "data" in r.json()


def test_mark_notification_read(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    payload = {
        "type": "payroll_run_generated",
        "title": "Payroll generated",
        "body": "Payroll run has been generated",
    }
    r = client.post(f"{API}/notifications/", json=payload, headers=superuser_token_headers)
    assert r.status_code == 201, r.text
    obj_id = r.json()["id"]

    r = client.post(f"{API}/notifications/{obj_id}/read", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    assert r.json()["read_at"] is not None


def test_mark_all_notifications_read(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.post(f"{API}/notifications/mark-all-read", headers=superuser_token_headers)
    assert r.status_code == 200, r.text


def test_get_unread_count(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.get(f"{API}/notifications/unread-count", headers=superuser_token_headers)
    assert r.status_code == 200, r.text
    assert "unread_count" in r.json()


def test_pre_payday_check(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.post(f"{API}/notifications/pre-payday-check", headers=superuser_token_headers)
    assert r.status_code == 202, r.text
    data = r.json()
    assert "status" in data
    assert "checked_date" in data
