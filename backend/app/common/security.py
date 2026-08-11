import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config.settings import settings

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)

ALGORITHM = "HS256"

# Tokens carry an explicit type claim. Without it a refresh token - which is
# long-lived by design - would be accepted anywhere an access token is, which
# would defeat the point of keeping access tokens short-lived.
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenTypeError(jwt.InvalidTokenError):
    """Raised when a token is structurally valid but of the wrong type."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(
    *,
    subject: str | Any,
    expires_delta: timedelta,
    token_type: str,
    jti: uuid.UUID,
) -> str:
    issued_at = _now()
    payload = {
        "sub": str(subject),
        "exp": issued_at + expires_delta,
        "iat": issued_at,
        "jti": str(jti),
        "type": token_type,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta,
    jti: uuid.UUID | None = None,
) -> str:
    return _encode(
        subject=subject,
        expires_delta=expires_delta,
        token_type=TOKEN_TYPE_ACCESS,
        jti=jti or uuid.uuid4(),
    )


def create_refresh_token(
    subject: str | Any,
    expires_delta: timedelta,
    jti: uuid.UUID | None = None,
) -> tuple[str, uuid.UUID, datetime]:
    """Return (token, jti, expires_at).

    The jti is returned so the caller can persist a server-side record, which
    is what makes revocation real rather than advisory.
    """
    token_jti = jti or uuid.uuid4()
    expires_at = _now() + expires_delta
    token = _encode(
        subject=subject,
        expires_delta=expires_delta,
        token_type=TOKEN_TYPE_REFRESH,
        jti=token_jti,
    )
    return token, token_jti, expires_at


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    """Decode and validate a token, enforcing its type claim.

    Raises jwt.ExpiredSignatureError for expired tokens and TokenTypeError when
    the type claim does not match, so callers can distinguish the two.
    """
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub", "jti", "type"]},
    )
    if payload.get("type") != expected_type:
        raise TokenTypeError(
            f"Expected a {expected_type} token, got {payload.get('type')!r}"
        )
    return payload


def hash_token(token: str) -> str:
    """Hash a refresh token for storage.

    Refresh tokens are bearer credentials, so the database stores only a digest;
    a leaked database dump then cannot be replayed against the API.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


# ---------------------------------------------------------------------------
# Request identity (used by audit logging and the structured error format).
# The id is generated once per request and stored on the ASGI scope so it
# survives the whole pipeline; callers fall back to generating a throwaway id
# when no request is in scope.
# ---------------------------------------------------------------------------

REQUEST_ID_HEADER = "x-request-id"


def get_request_id(request: Any | None = None) -> str:
    if request is not None:
        rid = getattr(request.state, "request_id", None)
        if rid:
            return rid
    return str(uuid.uuid4())
