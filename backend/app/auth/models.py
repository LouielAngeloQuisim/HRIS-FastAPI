import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class RefreshToken(SQLModel, table=True):
    """Server-side record of an issued refresh token.

    The legacy system had no such record: its JWTs were valid until they
    expired and logout was purely client-side (roadmap §1, §5). Persisting a
    row per issued token is what allows genuine revocation, rotation, and
    replay detection.

    Only the digest of the token is stored - never the token itself.
    """

    __tablename__ = "refresh_token"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    jti: uuid.UUID = Field(unique=True, index=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    token_hash: str = Field(unique=True, index=True, max_length=64)
    issued_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        index=True,
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    # Rotation chain. Lets an operator trace a session's history and makes
    # replay of a superseded token attributable.
    replaced_by_jti: uuid.UUID | None = Field(default=None)
    user_agent: str | None = Field(default=None, max_length=512)
    client_ip: str | None = Field(default=None, max_length=64)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        reference = now or get_datetime_utc()
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= reference

    def is_active(self, *, now: datetime | None = None) -> bool:
        return not self.is_revoked and not self.is_expired(now=now)
