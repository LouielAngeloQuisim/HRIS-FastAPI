"""Phase 0 required test #1 - "Auth flow: login / refresh / logout / expired-token rejection".

Also covers the two failure modes the legacy system had no answer for
(roadmap §1, §5): tokens that cannot be revoked, and refresh tokens being
accepted wherever an access token is.
"""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.models import RefreshToken
from app.auth.services import issue_token_pair
from app.common.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from app.config.settings import settings
from app.user.models import User, UserCreate
from app.user.services import create_user
from tests.utils.utils import random_email, random_lower_string


@pytest.fixture
def auth_user(db: Session) -> User:
    """A dedicated active user so these tests never race the shared fixtures."""
    user = create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password=random_lower_string(), is_superuser=False
        ),
    )
    return user


def _login(client: TestClient, email: str, password: str):
    return client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


class TestLogin:
    def test_login_returns_access_and_refresh_tokens(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )

        r = _login(client, user.email, password)

        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    def test_access_token_is_accepted_on_protected_route(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        tokens = _login(client, user.email, password).json()

        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=_auth_headers(tokens["access_token"]),
        )

        assert r.status_code == 200
        assert r.json()["email"] == user.email

    def test_login_persists_a_revocable_refresh_record(
        self, client: TestClient, db: Session
    ) -> None:
        """Revocation is only real if the server has a row to revoke."""
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        tokens = _login(client, user.email, password).json()

        record = db.exec(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(tokens["refresh_token"])
            )
        ).first()

        assert record is not None
        assert record.user_id == user.id
        assert record.revoked_at is None

    def test_raw_refresh_token_is_never_stored(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        tokens = _login(client, user.email, password).json()

        stored = db.exec(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        ).first()

        assert stored is not None
        assert stored.token_hash != tokens["refresh_token"]
        assert stored.token_hash == hash_token(tokens["refresh_token"])

    def test_login_with_wrong_password_issues_nothing(
        self, client: TestClient, db: Session
    ) -> None:
        user = create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(), password=random_lower_string()
            ),
        )

        r = _login(client, user.email, "not-the-password")

        assert r.status_code == 400
        assert "access_token" not in r.json()


class TestRefresh:
    def test_refresh_returns_a_new_usable_pair(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        original = _login(client, user.email, password).json()

        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": original["refresh_token"]},
        )

        assert r.status_code == 200
        refreshed = r.json()
        assert refreshed["refresh_token"] != original["refresh_token"]

        # The newly minted access token must actually work.
        me = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=_auth_headers(refreshed["access_token"]),
        )
        assert me.status_code == 200
        assert me.json()["email"] == user.email

    def test_refresh_token_is_single_use(
        self, client: TestClient, db: Session
    ) -> None:
        """Rotation: the spent token must not be redeemable a second time."""
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        original = _login(client, user.email, password).json()

        first = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": original["refresh_token"]},
        )
        assert first.status_code == 200

        replay = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": original["refresh_token"]},
        )
        assert replay.status_code == 401

    def test_replaying_a_spent_token_revokes_the_whole_family(
        self, client: TestClient, db: Session
    ) -> None:
        """A replayed token means one of the two holders is an attacker."""
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        original = _login(client, user.email, password).json()
        rotated = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": original["refresh_token"]},
        ).json()

        # Attacker replays the superseded token.
        client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": original["refresh_token"]},
        )

        # The legitimate holder's current token is now dead too.
        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": rotated["refresh_token"]},
        )
        assert r.status_code == 401

    def test_rotation_is_recorded_in_the_chain(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        original = _login(client, user.email, password).json()
        old_jti = uuid.UUID(
            decode_token(original["refresh_token"], expected_type=TOKEN_TYPE_REFRESH)[
                "jti"
            ]
        )

        client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": original["refresh_token"]},
        )

        db.expire_all()
        old = db.exec(
            select(RefreshToken).where(RefreshToken.jti == old_jti)
        ).first()
        assert old is not None
        assert old.revoked_at is not None
        assert old.replaced_by_jti is not None

    def test_garbage_refresh_token_is_rejected(self, client: TestClient) -> None:
        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": "not-a-jwt"},
        )
        assert r.status_code == 401

    def test_unknown_but_well_signed_refresh_token_is_rejected(
        self, client: TestClient, auth_user: User
    ) -> None:
        """Signed by us, but no server-side record - must not be honoured."""
        orphan, _, _ = create_refresh_token(
            auth_user.id, expires_delta=timedelta(days=1)
        )

        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": orphan},
        )
        assert r.status_code == 401


class TestLogout:
    def test_logout_prevents_further_refresh(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        tokens = _login(client, user.email, password).json()

        out = client.post(
            f"{settings.API_V1_STR}/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert out.status_code == 200

        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert r.status_code == 401

    def test_logout_marks_the_record_revoked(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        tokens = _login(client, user.email, password).json()

        client.post(
            f"{settings.API_V1_STR}/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )

        db.expire_all()
        record = db.exec(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(tokens["refresh_token"])
            )
        ).first()
        assert record is not None
        assert record.revoked_at is not None

    def test_logout_one_session_leaves_others_alive(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        session_a = _login(client, user.email, password).json()
        session_b = _login(client, user.email, password).json()

        client.post(
            f"{settings.API_V1_STR}/logout",
            json={"refresh_token": session_a["refresh_token"]},
        )

        still_valid = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": session_b["refresh_token"]},
        )
        assert still_valid.status_code == 200

    def test_logout_all_sessions_revokes_every_device(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        session_a = _login(client, user.email, password).json()
        session_b = _login(client, user.email, password).json()

        client.post(
            f"{settings.API_V1_STR}/logout",
            json={"refresh_token": session_a["refresh_token"], "all_sessions": True},
        )

        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": session_b["refresh_token"]},
        )
        assert r.status_code == 401


class TestExpiredTokenRejection:
    def test_expired_access_token_is_rejected(
        self, client: TestClient, auth_user: User
    ) -> None:
        expired = create_access_token(
            auth_user.id, expires_delta=timedelta(minutes=-1)
        )

        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=_auth_headers(expired),
        )

        assert r.status_code == 401
        assert r.json()["detail"] == "Token has expired"

    def test_expired_refresh_token_is_rejected(
        self, client: TestClient, db: Session, auth_user: User
    ) -> None:
        expired, jti, expires_at = create_refresh_token(
            auth_user.id, expires_delta=timedelta(days=-1)
        )
        # Persist a matching record so the rejection is provably about expiry
        # rather than the record simply being absent.
        db.add(
            RefreshToken(
                jti=jti,
                user_id=auth_user.id,
                token_hash=hash_token(expired),
                expires_at=expires_at,
            )
        )
        db.commit()

        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": expired},
        )
        assert r.status_code == 401

    def test_valid_access_token_is_not_expired(
        self, client: TestClient, auth_user: User
    ) -> None:
        """Guards the expiry test above against a false positive."""
        valid = create_access_token(auth_user.id, expires_delta=timedelta(minutes=5))

        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=_auth_headers(valid),
        )
        assert r.status_code == 200

    def test_tampered_token_is_rejected(
        self, client: TestClient, auth_user: User
    ) -> None:
        token = create_access_token(auth_user.id, expires_delta=timedelta(minutes=5))
        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")

        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=_auth_headers(tampered),
        )
        assert r.status_code == 401


class TestTokenTypeConfusion:
    def test_refresh_token_cannot_be_used_as_access_token(
        self, client: TestClient, db: Session
    ) -> None:
        """The long-lived credential must not unlock the API directly."""
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        tokens = _login(client, user.email, password).json()

        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=_auth_headers(tokens["refresh_token"]),
        )

        assert r.status_code == 401
        assert r.json()["detail"] == "Could not validate credentials"

    def test_access_token_cannot_be_used_as_refresh_token(
        self, client: TestClient, db: Session
    ) -> None:
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )
        tokens = _login(client, user.email, password).json()

        r = client.post(
            f"{settings.API_V1_STR}/login/refresh-token",
            json={"refresh_token": tokens["access_token"]},
        )
        assert r.status_code == 401

    def test_tokens_carry_an_explicit_type_claim(self, auth_user: User) -> None:
        access = create_access_token(auth_user.id, expires_delta=timedelta(minutes=5))
        refresh, _, _ = create_refresh_token(
            auth_user.id, expires_delta=timedelta(days=1)
        )

        assert (
            decode_token(access, expected_type=TOKEN_TYPE_ACCESS)["type"]
            == TOKEN_TYPE_ACCESS
        )
        assert (
            decode_token(refresh, expected_type=TOKEN_TYPE_REFRESH)["type"]
            == TOKEN_TYPE_REFRESH
        )


class TestRevocationService:
    def test_issue_then_revoke_all_kills_every_token(
        self, db: Session, auth_user: User
    ) -> None:
        from app.auth.services import revoke_all_for_user

        issue_token_pair(session=db, user=auth_user)
        issue_token_pair(session=db, user=auth_user)

        revoked = revoke_all_for_user(session=db, user_id=auth_user.id)

        assert revoked == 2
        db.expire_all()
        remaining = db.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == auth_user.id,
                RefreshToken.revoked_at.is_(None),  # type: ignore[union-attr]
            )
        ).all()
        assert list(remaining) == []
