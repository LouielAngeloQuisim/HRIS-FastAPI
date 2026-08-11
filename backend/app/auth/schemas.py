from sqlmodel import SQLModel


class TokenPair(SQLModel):
    """Issued on login and on every refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(SQLModel):
    refresh_token: str


class LogoutRequest(SQLModel):
    refresh_token: str
    # Opt-in "sign out everywhere". Defaults to revoking just this session so
    # logging out on one device does not disrupt the others.
    all_sessions: bool = False
