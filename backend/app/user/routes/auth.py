from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.schemas import LogoutRequest, RefreshRequest, TokenPair
from app.auth.services import (
    RefreshTokenError,
    RefreshTokenReuseError,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.common.audit.sink import SecurityEventType, log_security_event
from app.common.dependencies import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.common.rate_limit_deps import (
    RateLimitTicket,
    login_rate_limit,
    password_recovery_rate_limit,
    password_reset_rate_limit,
)
from app.user.schemas import Message, NewPassword, UserPublic, UserUpdate
from app.user.selectors import get_user_by_email
from app.user.services import authenticate, update_user
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


def _client_context(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None
    return user_agent, client_ip


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    rate_limit: Annotated[RateLimitTicket, Depends(login_rate_limit)],
) -> TokenPair:
    user_agent, client_ip = _client_context(request)
    request_id = getattr(request.state, "request_id", None)

    user = authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        log_security_event(
            security_event=SecurityEventType.LOGIN_FAILED,
            user_email=form_data.username,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            reason="incorrect_credentials",
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        log_security_event(
            security_event=SecurityEventType.LOGIN_FAILED,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            reason="inactive_account",
        )
        raise HTTPException(status_code=400, detail="Inactive user")

    # Only consecutive failures should count towards the limit.
    rate_limit.clear()

    log_security_event(
        security_event=SecurityEventType.LOGIN_SUCCESS,
        user_id=str(user.id),
        user_email=user.email,
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return issue_token_pair(
        session=session, user=user, user_agent=user_agent, client_ip=client_ip
    )


@router.post("/login/refresh-token")
def refresh_access_token(
    request: Request, session: SessionDep, body: RefreshRequest
) -> TokenPair:
    """Exchange a refresh token for a new pair.

    The presented token is rotated out, so each refresh token is single-use.
    Replaying a spent token revokes every session for that user.
    """
    user_agent, client_ip = _client_context(request)
    request_id = getattr(request.state, "request_id", None)
    try:
        _, pair = rotate_refresh_token(
            session=session,
            refresh_token=body.refresh_token,
            user_agent=user_agent,
            client_ip=client_ip,
        )
        log_security_event(
            security_event=SecurityEventType.TOKEN_REFRESH,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
        )
    except RefreshTokenReuseError as exc:
        log_security_event(
            security_event=SecurityEventType.TOKEN_REUSE_DETECTED,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except RefreshTokenError as exc:
        log_security_event(
            security_event=SecurityEventType.TOKEN_REFRESH,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return pair


@router.post("/logout")
def logout(
    request: Request,
    session: SessionDep,
    body: LogoutRequest,
) -> Message:
    """Revoke a refresh token server-side.

    The legacy system had no logout at all - its JWTs stayed valid until they
    expired (roadmap §1). Here the refresh record is marked revoked, so it can
    never be exchanged again.

    The refresh token presented in the body is the actor's proof of session:
    no separate Bearer access token is required (clients calling logout
    typically do so because the access token just expired, or because they
    want to discard all credentials at once). For ``all_sessions=True`` the
    call still records the requesting IP/UA but no user_id is attributed,
    because the actor authenticates via the refresh token, not a user record.
    """
    user_agent, client_ip = _client_context(request)
    request_id = getattr(request.state, "request_id", None)
    try:
        revoked = revoke_refresh_token(
            session=session,
            refresh_token=body.refresh_token,
            all_sessions=body.all_sessions,
        )
        log_security_event(
            security_event=SecurityEventType.LOGOUT,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            sessions_revoked=revoked,
            all_sessions=body.all_sessions,
        )
    except RefreshTokenError as exc:
        log_security_event(
            security_event=SecurityEventType.LOGOUT,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Message(message=f"Logged out; {revoked} session(s) revoked")


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(
    request: Request,
    email: str,
    session: SessionDep,
    _rate_limit: Annotated[RateLimitTicket, Depends(password_recovery_rate_limit)],
) -> Message:
    user_agent, client_ip = _client_context(request)
    request_id = getattr(request.state, "request_id", None)

    user = get_user_by_email(session=session, email=email)
    if user:
        log_security_event(
            security_event=SecurityEventType.PASSWORD_RESET_REQUEST,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=client_ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    # Deliberately uniform response: revealing whether the address exists would
    # turn this endpoint into a user-enumeration oracle.
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(
    request: Request,
    session: SessionDep,
    body: NewPassword,
    rate_limit: Annotated[RateLimitTicket, Depends(password_reset_rate_limit)],
) -> Message:
    user_agent, client_ip = _client_context(request)
    request_id = getattr(request.state, "request_id", None)

    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    log_security_event(
        security_event=SecurityEventType.PASSWORD_CHANGE,
        user_id=str(user.id),
        user_email=user.email,
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    user_in_update = UserUpdate(password=body.new_password)
    update_user(
        session=session,
        db_user=user,
        user_in=user_in_update,
    )
    rate_limit.clear()
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    user = get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
