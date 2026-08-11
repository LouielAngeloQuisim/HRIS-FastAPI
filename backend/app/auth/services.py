import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlmodel import Session, update

from app.auth.models import RefreshToken
from app.auth.schemas import TokenPair
from app.auth.selectors import (
    get_active_refresh_tokens_for_user,
    get_refresh_token_by_jti,
)
from app.common.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from app.config.settings import settings
from app.user.models import User


class RefreshTokenError(Exception):
    """Raised when a refresh token cannot be used to mint a new token pair."""


class RefreshTokenReuseError(RefreshTokenError):
    """A superseded or already-revoked refresh token was presented.

    Treated as a compromise signal: the whole token family for that user is
    revoked, forcing re-authentication.
    """


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_token_pair(
    *,
    session: Session,
    user: User,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> TokenPair:
    """Mint a fresh access/refresh pair and persist the refresh record."""
    access_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(user.id, expires_delta=access_expires)
    refresh_token, jti, expires_at = create_refresh_token(
        user.id, expires_delta=refresh_expires
    )

    session.add(
        RefreshToken(
            jti=jti,
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
            user_agent=(user_agent or None),
            client_ip=(client_ip or None),
        )
    )
    session.commit()

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_expires.total_seconds()),
    )


def revoke_all_for_user(*, session: Session, user_id: uuid.UUID) -> int:
    """Revoke every live refresh token for a user. Returns the count."""
    active = get_active_refresh_tokens_for_user(session=session, user_id=user_id)
    if not active:
        return 0
    now = _now()
    session.exec(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),  # type: ignore[union-attr]
        )
        .values(revoked_at=now)
    )
    session.commit()
    return len(active)


def _resolve_presented_token(
    *, session: Session, refresh_token: str
) -> tuple[RefreshToken, uuid.UUID]:
    try:
        payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    except jwt.ExpiredSignatureError:
        raise RefreshTokenError("Refresh token has expired")
    except jwt.InvalidTokenError:
        raise RefreshTokenError("Invalid refresh token")

    try:
        jti = uuid.UUID(str(payload["jti"]))
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        raise RefreshTokenError("Invalid refresh token")

    record = get_refresh_token_by_jti(session=session, jti=jti)
    if record is None:
        # Correctly signed but unknown to us - it was pruned, or the signing
        # key is being used against a different database.
        raise RefreshTokenError("Invalid refresh token")

    if record.token_hash != hash_token(refresh_token):
        raise RefreshTokenError("Invalid refresh token")

    return record, user_id


def rotate_refresh_token(
    *,
    session: Session,
    refresh_token: str,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> tuple[User, TokenPair]:
    """Exchange a refresh token for a new pair, invalidating the old one."""
    record, user_id = _resolve_presented_token(
        session=session, refresh_token=refresh_token
    )

    if record.is_revoked:
        # Someone is replaying a token we already retired. We cannot tell the
        # legitimate holder from the attacker, so revoke the family.
        revoke_all_for_user(session=session, user_id=record.user_id)
        raise RefreshTokenReuseError(
            "Refresh token has already been used; all sessions revoked"
        )

    if record.is_expired():
        raise RefreshTokenError("Refresh token has expired")

    user = session.get(User, user_id)
    if user is None:
        raise RefreshTokenError("Invalid refresh token")
    if not user.is_active:
        raise RefreshTokenError("Inactive user")

    pair = issue_token_pair(
        session=session, user=user, user_agent=user_agent, client_ip=client_ip
    )

    new_record = get_refresh_token_by_jti(
        session=session,
        jti=uuid.UUID(
            str(decode_token(pair.refresh_token, expected_type=TOKEN_TYPE_REFRESH)["jti"])
        ),
    )
    record.revoked_at = _now()
    record.replaced_by_jti = new_record.jti if new_record else None
    session.add(record)
    session.commit()

    return user, pair


def revoke_refresh_token(
    *, session: Session, refresh_token: str, all_sessions: bool = False
) -> int:
    """Revoke the presented refresh token, or every session for its owner."""
    record, _ = _resolve_presented_token(
        session=session, refresh_token=refresh_token
    )

    if all_sessions:
        return revoke_all_for_user(session=session, user_id=record.user_id)

    if record.is_revoked:
        return 0

    record.revoked_at = _now()
    session.add(record)
    session.commit()
    return 1
