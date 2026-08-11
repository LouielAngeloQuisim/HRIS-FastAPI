"""Sliding-window rate limiting for authentication endpoints.

The legacy system had no rate limiting anywhere (roadmap §5), leaving login and
password reset open to credential stuffing and token brute-forcing.

Phase 0 decision: 5 attempts per 15 minutes, keyed on client IP *and* the
submitted identifier. Keying on both matters - IP alone lets one NAT'd office
lock itself out, while identifier alone lets an attacker deliberately lock a
known user out of their own account from anywhere.

Only *consecutive failures* count. A successful login clears the counter, so a
legitimate user who signs in repeatedly is never penalised.

The backend is pluggable. The in-memory implementation below is correct for a
single process; a multi-worker deployment needs a shared store (Redis), which
is why the backend is an interface rather than a module-level dict.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


class RateLimitBackend(ABC):
    """Storage strategy for the sliding window."""

    @abstractmethod
    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        """Record an attempt and report whether it is allowed."""

    @abstractmethod
    def peek(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        """Report status without recording an attempt."""

    @abstractmethod
    def clear(self, key: str) -> None:
        """Forget a key, e.g. after a successful authentication."""

    @abstractmethod
    def reset(self) -> None:
        """Drop all state. Intended for tests and process restart."""


class InMemorySlidingWindowBackend(RateLimitBackend):
    """Precise sliding window backed by per-key timestamp deques.

    Chosen over a fixed window because a fixed window lets an attacker make
    2x the limit across a boundary (5 at 14:59, 5 more at 15:01).
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, *, window_seconds: int, now: float) -> deque[float]:
        bucket = self._hits[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        return bucket

    def _result(
        self,
        bucket: deque[float],
        *,
        limit: int,
        window_seconds: int,
        now: float,
        allowed: bool,
    ) -> RateLimitResult:
        remaining = max(0, limit - len(bucket))
        # Time until the oldest hit ages out of the window, which is the
        # earliest moment the caller could succeed.
        retry_after = 0 if allowed or not bucket else max(
            1, int(bucket[0] + window_seconds - now) + 1
        )
        return RateLimitResult(
            allowed=allowed, remaining=remaining, retry_after=retry_after
        )

    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        with self._lock:
            bucket = self._prune(key, window_seconds=window_seconds, now=now)
            bucket.append(now)
            # This attempt counts, so the limit is breached at limit + 1.
            return self._result(
                bucket,
                limit=limit,
                window_seconds=window_seconds,
                now=now,
                allowed=len(bucket) <= limit,
            )

    def peek(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        with self._lock:
            bucket = self._prune(key, window_seconds=window_seconds, now=now)
            # Nothing recorded, so ask whether a further attempt would fit.
            return self._result(
                bucket,
                limit=limit,
                window_seconds=window_seconds,
                now=now,
                allowed=len(bucket) < limit,
            )

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RateLimiter:
    """Thin policy wrapper around a backend."""

    def __init__(self, backend: RateLimitBackend) -> None:
        self.backend = backend

    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        return self.backend.hit(key, limit=limit, window_seconds=window_seconds)

    def peek(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        return self.backend.peek(key, limit=limit, window_seconds=window_seconds)

    def clear(self, key: str) -> None:
        self.backend.clear(key)

    def reset(self) -> None:
        self.backend.reset()


# Process-wide limiter. Swap the backend here to move to Redis.
login_rate_limiter = RateLimiter(InMemorySlidingWindowBackend())


def build_key(*, scope: str, client_ip: str | None, identifier: str | None) -> str:
    """Compose the composite key.

    The identifier is lower-cased so `User@x.com` and `user@x.com` share a
    bucket and cannot be used to double the effective allowance.
    """
    ip_part = (client_ip or "unknown").strip()
    id_part = (identifier or "unknown").strip().lower()
    return f"{scope}:{ip_part}:{id_part}"
