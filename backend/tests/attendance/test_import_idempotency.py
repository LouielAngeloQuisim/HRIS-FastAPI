"""QA-01 — Attendance import idempotency (lost response must reconcile, retries must not duplicate).

Covers the replay contract (201 first / 200 replay), payload-conflict 409,
blank/deleted-key policies, authorization preservation, keyless creates,
natural-key non-merging, no side effects on rejections, and the race-safe
unique-index settlement with two real PostgreSQL sessions.
"""

import threading
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.attendance.models import DailyTimeRecord, Shift
from app.attendance.schemas import DailyTimeRecordCreate
from app.attendance.services import create_dtr
from app.config.database import engine
from app.config.settings import settings
from app.employee.models import EmployeeRecords
from app.user.models import User

API = settings.API_V1_STR


def _superuser_id(db: Session) -> uuid.UUID:
    """created_by has FK user.id — the seeded superuser is the only guaranteed row."""
    return db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one().id

KEY = "dtr-import-batch1-r0"
LOGIN = "2026-08-04T08:00:00+00:00"
LOGOUT = "2026-08-04T17:00:00+00:00"


@pytest.fixture
def employee(db: Session) -> EmployeeRecords:
    emp = EmployeeRecords(
        employee_code=f"IDP-{uuid.uuid4().hex[:8]}",
        first_name="Rhea", last_name="Okonkwo", birthdate="1990-01-01",
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _payload(employee_code: str, **over: object) -> dict:
    body: dict = {
        "employee_code": employee_code,
        "login_date": LOGIN,
        "logout_date": LOGOUT,
    }
    body.update(over)
    return body


def _active_rows_for_key(db: Session, employee_id: uuid.UUID, key: str) -> list[DailyTimeRecord]:
    return list(
        db.exec(
            select(DailyTimeRecord).where(
                DailyTimeRecord.employee_id == employee_id,
                DailyTimeRecord.source_ref == key,
                DailyTimeRecord.is_deleted == False,  # noqa: E712
            )
        ).all()
    )


class TestReplayContract:
    def test_first_create_201_replay_200_same_row(self, client, superuser_token_headers, employee, db):
        r1 = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY), headers=superuser_token_headers)
        assert r1.status_code == 201, r1.text
        r2 = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY), headers=superuser_token_headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["id"] == r1.json()["id"]
        assert len(_active_rows_for_key(db, employee.id, KEY)) == 1

    def test_replay_preserves_actor_computed_and_source_authority(self, client, superuser_token_headers, employee, db):
        first = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY), headers=superuser_token_headers).json()
        fake = str(uuid.uuid4())
        spoof = _payload(employee.employee_code, source_ref=KEY)
        spoof.update({"created_by": fake, "rendered_minutes": 9999, "source": "csv"})
        r = client.post(f"{API}/daily-time-records/", json=spoof, headers=superuser_token_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == first["id"]
        assert body["created_by"] == first["created_by"] != fake
        assert body["rendered_minutes"] == first["rendered_minutes"] == 480
        assert body["source"] == "manual"

    def test_same_key_changed_payload_is_409_and_original_untouched(self, client, superuser_token_headers, employee, db):
        first = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY), headers=superuser_token_headers).json()
        changed = _payload(employee.employee_code, source_ref=KEY, logout_date="2026-08-04T19:00:00+00:00")
        r = client.post(f"{API}/daily-time-records/", json=changed, headers=superuser_token_headers)
        assert r.status_code == 409
        assert "reconcile manually" in r.json()["detail"].lower() or "changed" in r.json()["detail"].lower()
        rows = _active_rows_for_key(db, employee.id, KEY)
        assert len(rows) == 1 and str(rows[0].id) == first["id"]
        assert rows[0].logout_date == datetime.fromisoformat(LOGOUT)

    def test_same_key_different_shift_payload_is_409(self, client, superuser_token_headers, employee, db, shift):
        client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY, shift_code=shift.code), headers=superuser_token_headers)
        r = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY), headers=superuser_token_headers)
        assert r.status_code == 409
        assert len(_active_rows_for_key(db, employee.id, KEY)) == 1


class TestKeyPolicy:
    def test_blank_source_ref_rejected_422(self, client, superuser_token_headers, employee):
        r = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=""), headers=superuser_token_headers)
        assert r.status_code == 422

    def test_whitespace_only_source_ref_rejected_400(self, client, superuser_token_headers, employee):
        r = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref="   "), headers=superuser_token_headers)
        assert r.status_code == 400
        assert "blank" in r.json()["detail"]

    def test_deleted_key_never_resurrected_retry_is_409_fresh_key_creates_new(self, client, superuser_token_headers, employee, db):
        created = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY), headers=superuser_token_headers).json()
        d = client.delete(f"{API}/daily-time-records/{created['id']}", headers=superuser_token_headers)
        assert d.status_code == 200
        # Automatic retry with the same identity must NOT resurrect the deleted punch.
        r = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY), headers=superuser_token_headers)
        assert r.status_code == 409
        assert "deleted" in r.json()["detail"].lower()
        assert len(_active_rows_for_key(db, employee.id, KEY)) == 0
        # A fresh explicit import identity creates a new row.
        fresh = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=KEY + "-reimport"), headers=superuser_token_headers)
        assert fresh.status_code == 201
        assert fresh.json()["id"] != created["id"]

    def test_natural_key_punches_are_never_merged(self, client, superuser_token_headers, employee, db):
        """Same employee+times with two DIFFERENT opaque keys are two legitimate
        punches (or a deliberate re-import); idempotency never guesses by natural key."""
        r1 = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref="dtr-import-b1-r0"), headers=superuser_token_headers)
        r2 = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref="dtr-import-b2-r0"), headers=superuser_token_headers)
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

    def test_keyless_manual_create_unaffected(self, client, superuser_token_headers, employee):
        r = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code), headers=superuser_token_headers)
        assert r.status_code == 201
        assert r.json()["source_ref"] is None

    def test_rejected_requests_leave_no_rows(self, client, superuser_token_headers, employee, db):
        before = len(db.exec(select(DailyTimeRecord)).all())
        for payload in [
            _payload(employee.employee_code, source_ref="   "),                      # 400 blank
            _payload(employee.employee_code, source_ref=KEY, login_date=LOGOUT),     # 400 login>=logout
            {"employee_code": "DOES-NOT-EXIST", "login_date": LOGIN, "logout_date": LOGOUT, "source_ref": KEY},  # 404
        ]:
            assert client.post(f"{API}/daily-time-records/", json=payload, headers=superuser_token_headers).status_code in (400, 404)
        after = len(db.exec(select(DailyTimeRecord)).all())
        assert after == before


class TestAuthorization:
    def test_unauthorized_keyed_create_is_403_before_any_replay(self, client, superuser_token_headers, normal_user_token_headers, employee):
        """QA-01 requirement 4: the permission gate runs before the idempotency
        lookup — an unauthorized retry cannot read or replay a row at all."""
        key = f"dtr-import-auth-{uuid.uuid4().hex[:8]}"
        # First commit as superuser so a replay row EXISTS.
        committed = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=key), headers=superuser_token_headers)
        assert committed.status_code == 201
        r = client.post(f"{API}/daily-time-records/", json=_payload(employee.employee_code, source_ref=key), headers=normal_user_token_headers)
        assert r.status_code == 403, r.text


class TestConcurrency:
    def test_two_sessions_same_key_settle_to_one_row(self, employee, db):
        """Race-safe proof (QA-01 requirement 1): two INDEPENDENT PostgreSQL
        sessions INSERT the same (employee, key) concurrently. The partial
        unique index serializes them: exactly one row is created; the loser
        reconciles to the winner's row as a replay — no duplicates, even
        though the lookup+insert alone is not atomic."""
        key = f"dtr-import-race-{uuid.uuid4().hex[:8]}"
        login = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
        logout = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)
        actor = _superuser_id(db)
        results: dict[int, tuple[str, bool]] = {}
        barrier = threading.Barrier(2)

        def worker(idx: int) -> None:
            with Session(engine) as s:
                data = DailyTimeRecordCreate(
                    employee_id=employee.id, login_date=login, logout_date=logout, source_ref=key
                )
                barrier.wait()
                row, replayed = create_dtr(session=s, data=data, actor_id=actor)
                results[idx] = (str(row.id), replayed)

        threads = [threading.Thread(target=worker, args=(i,)) for i in (1, 2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not any(t.is_alive() for t in threads)

        assert len(results) == 2, "both sessions must complete"
        (id_a, replay_a), (id_b, replay_b) = results[1], results[2]
        assert id_a == id_b, "both callers reconcile to the same committed row"
        assert replay_a != replay_b, "exactly one session created; the other replayed"

        with Session(engine) as check:
            rows = list(
                check.exec(
                    select(DailyTimeRecord).where(
                        DailyTimeRecord.employee_id == employee.id,
                        DailyTimeRecord.source_ref == key,
                        DailyTimeRecord.is_deleted == False,  # noqa: E712
                    )
                ).all()
            )
        assert len(rows) == 1


@pytest.fixture
def shift(db: Session) -> Shift:
    srow = Shift(
        code=f"DAY-{uuid.uuid4().hex[:8]}", name="Day Shift",
        start_time="08:00", end_time="17:00",
        lunch_break_duration=60, total_hours_minus_lunch=480,
    )
    db.add(srow)
    db.commit()
    db.refresh(srow)
    return srow


def _make_employee_user_with_dtr_add(db: Session, client: TestClient, email: str, linked_employee: EmployeeRecords) -> dict:
    """Non-superuser linked to `linked_employee`, granted daily_time_record:add."""
    from app.rbac.models import Role, RolePermission
    from app.rbac.selectors import get_module_by_code
    from app.user.models import UserCreate
    from app.user.services import create_user
    from tests.utils.user import user_authentication_headers
    from tests.utils.utils import random_lower_string

    password = random_lower_string()
    user = create_user(session=db, user_create=UserCreate(email=email, password=password))
    db.refresh(linked_employee)
    linked_employee.user_id = user.id
    db.add(linked_employee)
    db.commit()

    role = Role(code=f"TEST_RECON_{uuid.uuid4().hex[:6]}", name="Test Reconciler")
    db.add(role)
    db.commit()
    db.refresh(role)
    user.role_id = role.id
    db.add(user)
    db.commit()

    dtr_module = get_module_by_code(session=db, code="daily_time_record")
    db.add(RolePermission(role_id=role.id, module_id=dtr_module.id, can_view=True, can_add=True))
    db.commit()
    return user_authentication_headers(client=client, email=email, password=password)


class TestReconcileEndpoint:
    """QA-01 blockers 2/4: bounded, authorized (employee, key) PAIR verdicts.

    Verdict contract:
      committed  -> exactly one ACTIVE pair match (wizard: success)
      deleted    -> soft-deleted pair match (wizard: retired, never replay)
      not_found  -> absent *within the caller's visible scope* only
      unresolved -> employee unknown/out of scope -> wizard MUST keep UNKNOWN
    """

    RECONCILE = f"{API}/daily-time-records/reconcile-imports"

    def _reconcile(self, client, headers, pairs):
        return client.post(self.RECONCILE, json={"keys": pairs}, headers=headers)

    def test_committed_pair_returns_record_id(self, client, superuser_token_headers, employee):
        created = client.post(
            f"{API}/daily-time-records/",
            json=_payload(employee.employee_code, source_ref=KEY),
            headers=superuser_token_headers,
        ).json()
        r = self._reconcile(client, superuser_token_headers, [{"employee_code": employee.employee_code, "source_ref": KEY}])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["requested"] == 1 and body["unresolved"] == 0
        res = body["results"][0]
        assert res["status"] == "committed" and res["record_id"] == created["id"]

    def test_deleted_pair_reports_deleted_never_committed(self, client, superuser_token_headers, employee, db):
        created = client.post(
            f"{API}/daily-time-records/",
            json=_payload(employee.employee_code, source_ref=KEY),
            headers=superuser_token_headers,
        ).json()
        assert client.delete(f"{API}/daily-time-records/{created['id']}", headers=superuser_token_headers).status_code == 200
        r = self._reconcile(client, superuser_token_headers, [{"employee_code": employee.employee_code, "source_ref": KEY}])
        res = r.json()["results"][0]
        assert res["status"] == "deleted"
        assert len(_active_rows_for_key(db, employee.id, KEY)) == 0

    def test_absent_key_is_not_found(self, client, superuser_token_headers, employee):
        r = self._reconcile(client, superuser_token_headers, [{"employee_code": employee.employee_code, "source_ref": "dtr-import-never-r0"}])
        assert r.status_code == 200
        assert r.json()["results"][0]["status"] == "not_found"

    def test_same_key_other_employee_is_not_found_never_cross_match(self, client, superuser_token_headers, employee, db):
        """Pairing is (employee, key) — a key committed for A must NEVER be
        reported as committed for B (no natural-key/global-key guessing)."""
        other = EmployeeRecords(
            employee_code=f"IDP-{uuid.uuid4().hex[:8]}",
            first_name="Nia", last_name="Vasquez", birthdate="1991-02-02",
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        client.post(
            f"{API}/daily-time-records/",
            json=_payload(employee.employee_code, source_ref=KEY),
            headers=superuser_token_headers,
        )
        r = self._reconcile(client, superuser_token_headers, [{"employee_code": other.employee_code, "source_ref": KEY}])
        assert r.json()["results"][0]["status"] == "not_found"

    def test_unknown_employee_is_unresolved_not_not_found(self, client, superuser_token_headers):
        r = self._reconcile(client, superuser_token_headers, [{"employee_code": "NO-SUCH-EMP", "source_ref": KEY}])
        assert r.status_code == 200
        body = r.json()
        assert body["results"][0]["status"] == "unresolved"
        assert body["unresolved"] == 1

    def test_over_capacity_batch_is_rejected_422(self, client, superuser_token_headers, employee):
        pairs = [{"employee_code": employee.employee_code, "source_ref": f"dtr-import-big-r{i}"} for i in range(201)]
        r = self._reconcile(client, superuser_token_headers, pairs)
        assert r.status_code == 422

    def test_not_found_then_late_commit_retry_is_200_replay_same_row(self, client, superuser_token_headers, employee, db):
        """Blocker 4 race-safe contract: not_found is NOT proof of non-commit.
        Original request commits late -> the retry with the SAME key replays
        the late row (200) instead of duplicating it."""
        key = f"dtr-import-late-{uuid.uuid4().hex[:8]}"
        r = self._reconcile(client, superuser_token_headers, [{"employee_code": employee.employee_code, "source_ref": key}])
        assert r.json()["results"][0]["status"] == "not_found"

        # Simulate the timed-out original request committing AFTER we looked.
        login = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
        logout = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)
        with Session(engine) as late:
            late_row, replayed = create_dtr(
                session=late,
                data=DailyTimeRecordCreate(employee_id=employee.id, login_date=login, logout_date=logout, source_ref=key),
                actor_id=_superuser_id(db),
            )
        assert not replayed

        # Browser retry replays the identical payload + SAME key.
        retry = client.post(
            f"{API}/daily-time-records/",
            json=_payload(employee.employee_code, source_ref=key),
            headers=superuser_token_headers,
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["id"] == str(late_row.id)
        assert len(_active_rows_for_key(db, employee.id, key)) == 1

    def test_non_superuser_settles_own_pair_and_unresolves_other_scope(self, client, superuser_token_headers, db, employee):
        """Row-level visibility mirrors the DTR list route (is_superuser gate):
        own employee reconciles definitely; foreign employees stay unresolved
        — missing visibility is NOT reported as missing data."""
        other = EmployeeRecords(
            employee_code=f"IDP-{uuid.uuid4().hex[:8]}",
            first_name="Lara", last_name="Flores", birthdate="1988-03-03",
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        own_key = f"dtr-import-own-{uuid.uuid4().hex[:8]}"
        foreign_key = f"dtr-import-foreign-{uuid.uuid4().hex[:8]}"
        for emp, k in ((employee, own_key), (other, foreign_key)):
            assert client.post(
                f"{API}/daily-time-records/",
                json=_payload(emp.employee_code, source_ref=k),
                headers=superuser_token_headers,
            ).status_code == 201

        headers = _make_employee_user_with_dtr_add(db, client, f"recon-{uuid.uuid4().hex[:8]}@example.com", employee)
        r = self._reconcile(client, headers, [
            {"employee_code": employee.employee_code, "source_ref": own_key},
            {"employee_code": other.employee_code, "source_ref": foreign_key},
        ])
        assert r.status_code == 200, r.text
        results = {res["employee_code"]: res for res in r.json()["results"]}
        assert results[employee.employee_code]["status"] == "committed"
        assert results[other.employee_code]["status"] == "unresolved"
        assert r.json()["unresolved"] == 1

    def test_reconcile_requires_add_permission(self, client, normal_user_token_headers, employee):
        r = self._reconcile(client, normal_user_token_headers, [{"employee_code": employee.employee_code, "source_ref": KEY}])
        assert r.status_code == 403, r.text
