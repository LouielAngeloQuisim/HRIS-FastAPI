import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.auth.models import RefreshToken


def get_refresh_token_by_jti(
    *, session: Session, jti: uuid.UUID
) -> RefreshToken | None:
    return session.exec(
        select(RefreshToken).where(RefreshToken.jti == jti)
    ).first()


def get_refresh_token_by_hash(
    *, session: Session, token_hash: str
) -> RefreshToken | None:
    return session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()


def get_active_refresh_tokens_for_user(
    *, session: Session, user_id: uuid.UUID
) -> list[RefreshToken]:
    now = datetime.now(timezone.utc)
    rows = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),  # type: ignore[union-attr]
            RefreshToken.expires_at > now,
        )
    ).all()
    return list(rows)
