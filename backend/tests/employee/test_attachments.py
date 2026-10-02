"""Phase 1 — EmployeeAttachments upload/list/delete + ownership.

Files are stored outside the web root; only the path is persisted. Uploading to
another employee's record requires elevated emp_list/add; own uploads are allowed.
"""

import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config.settings import settings
from app.employee.services import store_attachment_file
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
        r = client.delete(f"{url}/{att_id}", headers=superuser_token_headers)
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


# --- Roadmap #95: upload size + filename limits ------------------------------


def _stored_name_len(basename: str) -> int:
    # uuid4().hex is always 32 chars, plus the joining "-".
    return 33 + len(basename)


class TestUploadSizeLimit:
    def test_service_rejects_oversized_content_before_writing(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "FILE_UPLOAD_MAX_BYTES", 100)
        employee_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            store_attachment_file(
                employee_id=employee_id, filename="big.bin", content=b"x" * 101
            )
        assert exc_info.value.status_code == 413
        assert "maximum upload size" in exc_info.value.detail
        # Nothing was written and the per-employee dir was never created.
        assert list(tmp_path.iterdir()) == []
        assert not (tmp_path / str(employee_id)).exists()

    def test_service_accepts_content_exactly_at_limit(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "FILE_UPLOAD_MAX_BYTES", 100)
        employee_id = uuid.uuid4()

        stored = store_attachment_file(
            employee_id=employee_id, filename="edge.bin", content=b"x" * 100
        )
        target = Path(stored)
        assert target.exists()
        assert target.read_bytes() == b"x" * 100  # no truncation

    def test_route_rejects_oversized_upload_with_413(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers,
        tmp_path,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "FILE_UPLOAD_MAX_BYTES", 100)
        employee = create_employee(db)

        r = client.post(
            f"{API}/employees/{employee.id}/attachments",
            headers=superuser_token_headers,
            files={"file": ("big.pdf", b"x" * 101, "application/pdf")},
        )
        assert r.status_code == 413, r.text
        body = r.json()
        assert body["success"] is False
        assert body["error"]["type"] == "http_error"
        assert "maximum upload size" in body["detail"]
        assert list(tmp_path.iterdir()) == []  # no partial file on disk

    def test_route_still_accepts_valid_upload_under_limit(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers,
        tmp_path,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "FILE_UPLOAD_MAX_BYTES", 100)
        employee = create_employee(db)

        r = client.post(
            f"{API}/employees/{employee.id}/attachments",
            headers=superuser_token_headers,
            files={"file": ("ok.pdf", b"x" * 50, "application/pdf")},
        )
        assert r.status_code == 201, r.text
        assert r.json()["attachment_size"] == 50
        files = list((tmp_path / str(employee.id)).iterdir())
        assert len(files) == 1
        assert files[0].read_bytes() == b"x" * 50


class TestUploadFilenameLimit:
    def test_service_rejects_overlong_stored_name_before_writing(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        employee_id = uuid.uuid4()
        # Default cap: stored name must stay within FILE_UPLOAD_MAX_FILENAME_LENGTH.
        # 33 + len(basename) exceeds the 255-char cap by one.
        long_name = "a" * (settings.FILE_UPLOAD_MAX_FILENAME_LENGTH - 33 + 1)
        assert _stored_name_len(long_name) > settings.FILE_UPLOAD_MAX_FILENAME_LENGTH

        with pytest.raises(HTTPException) as exc_info:
            store_attachment_file(
                employee_id=employee_id, filename=long_name, content=b"x"
            )
        assert exc_info.value.status_code == 400
        assert "filename is too long" in exc_info.value.detail
        assert list(tmp_path.iterdir()) == []
        assert not (tmp_path / str(employee_id)).exists()

    def test_service_accepts_stored_name_exactly_at_limit(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        employee_id = uuid.uuid4()
        edge_name = "a" * (settings.FILE_UPLOAD_MAX_FILENAME_LENGTH - 33)
        assert _stored_name_len(edge_name) == settings.FILE_UPLOAD_MAX_FILENAME_LENGTH

        stored = store_attachment_file(
            employee_id=employee_id, filename=edge_name, content=b"data"
        )
        target = Path(stored)
        assert target.exists()
        assert target.read_bytes() == b"data"

    def test_service_accepts_normal_filename(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        employee_id = uuid.uuid4()

        stored = store_attachment_file(
            employee_id=employee_id, filename="resume.pdf", content=b"%PDF"
        )
        target = Path(stored)
        assert target.exists()
        assert target.name.endswith("-resume.pdf")
        assert target.parent == tmp_path / str(employee_id)

    def test_service_still_strips_path_components(self, tmp_path, monkeypatch) -> None:
        """Path-traversal guard stays intact after the roadmap #95 checks."""
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        employee_id = uuid.uuid4()

        stored = store_attachment_file(
            employee_id=employee_id, filename="../../etc/passwd", content=b"x"
        )
        target = Path(stored)
        assert target.parent == tmp_path / str(employee_id)
        assert target.name.endswith("-passwd")
        assert "etc" not in target.name.split("-", 1)[1]

    def test_route_rejects_overlong_filename_with_400(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers,
        tmp_path,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "FILE_UPLOAD_MAX_FILENAME_LENGTH", 40)
        employee = create_employee(db)
        # 33 + 10 = 43 > 40, rejected before any write.
        r = client.post(
            f"{API}/employees/{employee.id}/attachments",
            headers=superuser_token_headers,
            files={"file": ("abcdefghij.txt", b"x", "text/plain")},
        )
        assert r.status_code == 400, r.text
        body = r.json()
        assert body["success"] is False
        assert body["error"]["type"] == "http_error"
        assert "filename is too long" in body["detail"]
        assert not (tmp_path / str(employee.id)).exists()

    def test_route_accepts_filename_at_new_limit(
        self,
        client: TestClient,
        db: Session,
        superuser_token_headers,
        tmp_path,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "FILE_UPLOAD_MAX_FILENAME_LENGTH", 40)
        employee = create_employee(db)
        # 33 + 7 = 40 == limit, accepted.
        r = client.post(
            f"{API}/employees/{employee.id}/attachments",
            headers=superuser_token_headers,
            files={"file": ("own.txt", b"mine", "text/plain")},
        )
        assert r.status_code == 201, r.text

    def test_service_rejects_unicode_name_exceeding_byte_limit(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "FILE_UPLOAD_MAX_FILENAME_LENGTH", 255)
        filename = chr(233) * 112
        assert 33 + len(filename) < 255
        assert 33 + len(filename.encode()) > 255
        with pytest.raises(HTTPException) as exc_info:
            store_attachment_file(
                employee_id=uuid.uuid4(), filename=filename, content=b"x"
            )
        assert exc_info.value.status_code == 400
        assert list(tmp_path.iterdir()) == []
