"""Phase 0 required test #3 - rate-limit trigger test.

Covers the sliding-window backend directly and the login / password-recovery /
password-reset endpoints end to end.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.common.rate_limit import (
    InMemorySlidingWindowBackend,
    RateLimiter,
    build_key,
    login_rate_limiter,
)
from app.config.settings import settings
from app.user.models import UserCreate
from app.user.services import create_user
from tests.utils.utils import random_email, random_lower_string

LIMIT = settings.LOGIN_RATE_LIMIT_ATTEMPTS


@pytest.fixture(autouse=True)
def clean_rate_limiter():
    """Rate-limit state is process-wide, so isolate every test."""
    login_rate_limiter.reset()
    yield
    login_rate_limiter.reset()


def _login(client: TestClient, email: str, password: str):
    return client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )


class TestSlidingWindowBackend:
    def test_allows_up_to_the_limit(self) -> None:
        limiter = RateLimiter(InMemorySlidingWindowBackend())
        for _ in range(LIMIT):
            assert limiter.hit("k", limit=LIMIT, window_seconds=900).allowed

    def test_blocks_the_attempt_after_the_limit(self) -> None:
        limiter = RateLimiter(InMemorySlidingWindowBackend())
        for _ in range(LIMIT):
            limiter.hit("k", limit=LIMIT, window_seconds=900)

        result = limiter.hit("k", limit=LIMIT, window_seconds=900)

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    def test_remaining_counts_down(self) -> None:
        limiter = RateLimiter(InMemorySlidingWindowBackend())
        first = limiter.hit("k", limit=LIMIT, window_seconds=900)
        assert first.remaining == LIMIT - 1

    def test_keys_are_isolated(self) -> None:
        limiter = RateLimiter(InMemorySlidingWindowBackend())
        for _ in range(LIMIT + 1):
            limiter.hit("a", limit=LIMIT, window_seconds=900)

        assert limiter.hit("b", limit=LIMIT, window_seconds=900).allowed

    def test_window_expiry_lets_attempts_through_again(self) -> None:
        """A zero-length window means every prior hit is already stale."""
        limiter = RateLimiter(InMemorySlidingWindowBackend())
        for _ in range(LIMIT + 3):
            limiter.hit("k", limit=LIMIT, window_seconds=900)

        assert limiter.hit("k", limit=LIMIT, window_seconds=0).allowed

    def test_clear_resets_a_single_key(self) -> None:
        limiter = RateLimiter(InMemorySlidingWindowBackend())
        for _ in range(LIMIT):
            limiter.hit("k", limit=LIMIT, window_seconds=900)

        limiter.clear("k")

        assert limiter.hit("k", limit=LIMIT, window_seconds=900).allowed

    def test_peek_does_not_consume_an_attempt(self) -> None:
        limiter = RateLimiter(InMemorySlidingWindowBackend())
        for _ in range(10):
            limiter.peek("k", limit=LIMIT, window_seconds=900)

        assert limiter.hit("k", limit=LIMIT, window_seconds=900).allowed


class TestKeyComposition:
    def test_key_combines_scope_ip_and_identifier(self) -> None:
        key = build_key(scope="login", client_ip="10.0.0.1", identifier="a@b.com")
        assert key == "login:10.0.0.1:a@b.com"

    def test_identifier_is_case_insensitive(self) -> None:
        """Otherwise casing variations would multiply the allowance."""
        assert build_key(
            scope="login", client_ip="10.0.0.1", identifier="A@B.com"
        ) == build_key(scope="login", client_ip="10.0.0.1", identifier="a@b.com")

    def test_different_identifiers_do_not_share_a_bucket(self) -> None:
        assert build_key(
            scope="login", client_ip="10.0.0.1", identifier="a@b.com"
        ) != build_key(scope="login", client_ip="10.0.0.1", identifier="c@d.com")


class TestLoginEndpointRateLimit:
    def test_repeated_failures_trigger_429(
        self, client: TestClient, db: Session
    ) -> None:
        user = create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(), password=random_lower_string()
            ),
        )

        for attempt in range(LIMIT):
            r = _login(client, user.email, "wrong-password")
            assert r.status_code == 400, f"attempt {attempt} should still be allowed"

        blocked = _login(client, user.email, "wrong-password")

        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
        assert int(blocked.headers["Retry-After"]) > 0

    def test_lockout_applies_even_with_the_correct_password(
        self, client: TestClient, db: Session
    ) -> None:
        """Once locked, a correct guess must not be accepted either."""
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )

        for _ in range(LIMIT):
            _login(client, user.email, "wrong-password")

        blocked = _login(client, user.email, password)

        assert blocked.status_code == 429

    def test_successful_login_clears_the_counter(
        self, client: TestClient, db: Session
    ) -> None:
        """A legitimate user who mistypes then succeeds is not penalised."""
        password = random_lower_string()
        user = create_user(
            session=db,
            user_create=UserCreate(email=random_email(), password=password),
        )

        for _ in range(LIMIT - 1):
            _login(client, user.email, "wrong-password")

        assert _login(client, user.email, password).status_code == 200

        # Budget is restored, so the next run of failures starts from zero.
        for attempt in range(LIMIT):
            r = _login(client, user.email, "wrong-password")
            assert r.status_code == 400, f"attempt {attempt} should be allowed again"

    def test_one_user_lockout_does_not_affect_another(
        self, client: TestClient, db: Session
    ) -> None:
        """Keying on identifier as well as IP prevents collateral lockout."""
        victim = create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(), password=random_lower_string()
            ),
        )
        bystander_password = random_lower_string()
        bystander = create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(), password=bystander_password
            ),
        )

        for _ in range(LIMIT + 1):
            _login(client, victim.email, "wrong-password")

        r = _login(client, bystander.email, bystander_password)

        assert r.status_code == 200

    def test_unknown_account_is_also_rate_limited(
        self, client: TestClient
    ) -> None:
        """Enumeration attempts must be throttled too."""
        email = random_email()
        for _ in range(LIMIT):
            _login(client, email, "wrong-password")

        assert _login(client, email, "wrong-password").status_code == 429


class TestPasswordResetRateLimit:
    def test_password_recovery_is_rate_limited(self, client: TestClient) -> None:
        email = random_email()
        for _ in range(LIMIT):
            r = client.post(f"{settings.API_V1_STR}/password-recovery/{email}")
            assert r.status_code == 200

        blocked = client.post(f"{settings.API_V1_STR}/password-recovery/{email}")

        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers

    def test_password_recovery_limit_is_per_email(
        self, client: TestClient
    ) -> None:
        first, second = random_email(), random_email()
        for _ in range(LIMIT + 1):
            client.post(f"{settings.API_V1_STR}/password-recovery/{first}")

        r = client.post(f"{settings.API_V1_STR}/password-recovery/{second}")

        assert r.status_code == 200

    def test_reset_password_token_guessing_is_rate_limited(
        self, client: TestClient
    ) -> None:
        payload = {"token": "guessed-token", "new_password": random_lower_string()}
        for _ in range(LIMIT):
            r = client.post(f"{settings.API_V1_STR}/reset-password/", json=payload)
            assert r.status_code == 400

        blocked = client.post(f"{settings.API_V1_STR}/reset-password/", json=payload)

        assert blocked.status_code == 429
