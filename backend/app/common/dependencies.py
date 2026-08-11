from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlmodel import Session

from app.common.schemas import TokenPayload
from app.common.security import TOKEN_TYPE_ACCESS, decode_token
from app.config.settings import settings
from app.user.models import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

CREDENTIALS_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_engine():
    from app.config.database import engine

    return engine


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.config.settings import settings

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

CREDENTIALS_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_engine():
    from app.config.database import engine

    return engine


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(
    request: Request, session: SessionDep, token: TokenDep
) -> User:
    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
        token_data = TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers=CREDENTIALS_HEADERS,
        )
    except (jwt.InvalidTokenError, ValidationError):
        # Covers bad signatures, missing claims, and refresh tokens presented
        # in the Authorization header.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers=CREDENTIALS_HEADERS,
        )

    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    request.state.user_id = str(user.id)
    request.state.user_email = user.email
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
