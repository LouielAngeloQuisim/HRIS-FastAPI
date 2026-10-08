"""Employer identity setup used by statutory payroll certificates."""

from fastapi.testclient import TestClient

from app.config.settings import settings

API = f"{settings.API_V1_STR}/payroll/employer-profile"


def test_employer_profile_can_be_started_incrementally_and_read_back(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    initial = client.get(API, headers=superuser_token_headers)
    assert initial.status_code == 200
    assert initial.json() == {
        "id": "default",
        "tin_number": None,
        "registered_name": None,
        "registered_address": None,
        "postal_code": None,
        "rdo_code": None,
        "employer_type": None,
        "signatory_name": None,
        "signatory_title": None,
        "source_reference": None,
        "is_verified": False,
        "verified_by": None,
        "verified_at": None,
        "updated_by": None,
        "updated_at": None,
    }
    incomplete_verification = client.post(
        f"{API}/verify", headers=superuser_token_headers
    )
    assert incomplete_verification.status_code == 409
    assert incomplete_verification.json()["detail"] == "Save employer certificate details first"
    partial_profile = client.put(
        API,
        headers=superuser_token_headers,
        json={"registered_name": "Example Company Inc."},
    )
    assert partial_profile.status_code == 200, partial_profile.text
    incomplete_verification = client.post(
        f"{API}/verify", headers=superuser_token_headers
    )
    assert incomplete_verification.status_code == 409
    assert "Missing fields:" in incomplete_verification.json()["detail"]
    assert "tin_number" in incomplete_verification.json()["detail"]

    saved = client.put(
        API,
        headers=superuser_token_headers,
        json={
            "tin_number": "  123-456-789-000  ",
            "registered_name": "  Example Company Inc.  ",
            "registered_address": "  1 Sample Street, Manila  ",
            "postal_code": "1000",
            "rdo_code": "039",
            "employer_type": "main",
            "signatory_name": "Payroll Officer",
            "signatory_title": "HR Manager",
            "source_reference": "Company registration certificate reviewed",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["tin_number"] == "123-456-789-000"
    assert saved.json()["registered_name"] == "Example Company Inc."
    assert saved.json()["employer_type"] == "main"
    assert saved.json()["updated_by"] is not None
    assert saved.json()["is_verified"] is False

    verified = client.post(
        f"{API}/verify", headers=superuser_token_headers
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["is_verified"] is True
    assert verified.json()["verified_by"] is not None
    assert verified.json()["verified_at"] is not None

    partial = client.put(
        API,
        headers=superuser_token_headers,
        json={"signatory_title": "Authorized HR Representative"},
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["is_verified"] is False
    assert partial.json()["verified_by"] is None
    assert partial.json()["tin_number"] == "123-456-789-000"
    assert partial.json()["registered_name"] == "Example Company Inc."
    assert partial.json()["signatory_title"] == "Authorized HR Representative"

    persisted = client.get(API, headers=superuser_token_headers)
    assert persisted.status_code == 200
    assert persisted.json() == partial.json()


def test_employer_profile_rejects_unknown_employer_type(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        API,
        headers=superuser_token_headers,
        json={"employer_type": "unknown"},
    )
    assert response.status_code == 422


def test_employer_profile_verification_requires_approval_permission(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{API}/verify", headers=normal_user_token_headers
    )
    assert response.status_code == 403
