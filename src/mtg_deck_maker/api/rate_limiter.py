"""Async token bucket rate limiter for API clients."""

from __future__ import annotations

import asyncio
import time
from types import TracebackType


class RateLimiter:
    """Token bucket rate limiter with async context manager interface.

    Provides configurable rate limiting for HTTP API clients. Uses a token
    bucket algorithm where tokens refill at a constant rate up to a maximum
    burst capacity.

    Usage::

        limiter = RateLimiter(rate=10.0, burst=10)
        async with limiter:
            await make_api_call()

    Args:
        rate: Number of requests allowed per second.
        burst: Maximum number of tokens (burst capacity). Defaults to
            the same value as rate, allowing short bursts up to the limit.
    """

    def __init__(self, rate: float, burst: int | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")

        self._rate = rate
        self._burst = burst if burst is not None else int(rate)
        if self._burst <= 0:
            raise ValueError("burst must be positive")

        self._tokens = float(self._burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def rate(self) -> float:
        """Requests per second."""
        return self._rate

    @property
    def burst(self) -> int:
        """Maximum burst capacity."""
        return self._burst

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (without refilling)."""
        return self._tokens

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self._burst),
            self._tokens + elapsed * self._rate,
        )
        self._last_refill = now

    async def acquire(self) -> None:
        """Acquire a single token, waiting if necessary.

        Blocks until a token is available. Uses asyncio.sleep to yield
        control while waiting for token refill.
        """
        async with self._lock:
            self._refill()

            while self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
                self._refill()

            self._tokens -= 1.0

    async def __aenter__(self) -> RateLimiter:
        """Acquire a token when entering the context."""
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """No-op on exit; token was consumed on entry."""
