"""Phase 1 — EmployeeAttachments upload/list/delete + ownership.

Files are stored outside the web root; only the path is persisted. Uploading to
another employee's record requires elevated emp_list/add; own uploads are allowed.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from tests.utils.employee import create_employee

API = settings.API_V1_STR


class TestAttachments:
    def test_upload_list_delete_as_superuser(
        self, client: TestClient, superuser_token_headers, db: Session
    ) -> None:
        employee = create_employee(db)
        url = f"{API}/employees/{employee.id}/attachments"

        r = client.post(
            url,
            headers=superuser_token_headers,
            files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"type": "resume", "attachment_name": "My Resume"},
        )
        assert r.status_code == 201, r.text
        att_id = r.json()["id"]
        assert r.json()["file_path"]  # path stored, not the blob
        assert r.json()["attachment_size"] == len(b"%PDF-1.4 fake")

        # list
        r = client.get(url, headers=superuser_token_headers)
        assert r.status_code == 200
        assert any(i["id"] == att_id for i in r.json()["data"])

        # delete (soft)
        r = client.delete(
            f"{url}/{att_id}", headers=superuser_token_headers
        )
        assert r.status_code == 200
        r = client.get(url, headers=superuser_token_headers)
        assert not any(i["id"] == att_id for i in r.json()["data"])

    def test_file_path_is_not_in_web_root(self, db: Session) -> None:
        """Regression guard: stored path must be under the upload dir, never a
        public web-root path."""
        from app.config.settings import settings as s

        assert not s.FILE_UPLOAD_DIR.startswith(("static", "public", "media"))
        assert "/uploads" in s.FILE_UPLOAD_DIR or s.FILE_UPLOAD_DIR.startswith("/tmp")

    def test_low_privilege_user_cannot_upload_to_others(
        self, client: TestClient, db: Session
    ) -> None:
        from tests.employee.test_additional_records import _make_user, _token

        user, password = _make_user(db, "SUR")
        create_employee(db, user_id=user.id)
        other = create_employee(db)
        headers = _token(client, user.email, password)

        r = client.post(
            f"{API}/employees/{other.id}/attachments",
            headers=headers,
            files={"file": ("doc.txt", b"x", "text/plain")},
        )
        assert r.status_code == 403, r.text

    def test_low_privilege_user_uploads_own(
        self, client: TestClient, db: Session
    ) -> None:
        from tests.employee.test_additional_records import _make_user, _token

        user, password = _make_user(db, "SUR")
        employee = create_employee(db, user_id=user.id)
        headers = _token(client, user.email, password)

        r = client.post(
            f"{API}/employees/{employee.id}/attachments",
            headers=headers,
            files={"file": ("own.txt", b"mine", "text/plain")},
        )
        assert r.status_code == 201, r.text
