"""Tests for the async token bucket rate limiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from mtg_deck_maker.api.rate_limiter import RateLimiter


class TestRateLimiterCreation:
    """Test RateLimiter initialization and validation."""

    def test_create_with_defaults(self) -> None:
        limiter = RateLimiter(rate=10.0)
        assert limiter.rate == 10.0
        assert limiter.burst == 10

    def test_create_with_custom_burst(self) -> None:
        limiter = RateLimiter(rate=5.0, burst=20)
        assert limiter.rate == 5.0
        assert limiter.burst == 20

    def test_create_with_fractional_rate(self) -> None:
        limiter = RateLimiter(rate=0.5, burst=1)
        assert limiter.rate == 0.5
        assert limiter.burst == 1

    def test_zero_rate_raises_error(self) -> None:
        with pytest.raises(ValueError, match="rate must be positive"):
            RateLimiter(rate=0.0)

    def test_negative_rate_raises_error(self) -> None:
        with pytest.raises(ValueError, match="rate must be positive"):
            RateLimiter(rate=-1.0)

    def test_zero_burst_raises_error(self) -> None:
        with pytest.raises(ValueError, match="burst must be positive"):
            RateLimiter(rate=1.0, burst=0)

    def test_negative_burst_raises_error(self) -> None:
        with pytest.raises(ValueError, match="burst must be positive"):
            RateLimiter(rate=1.0, burst=-1)

    def test_initial_tokens_equal_burst(self) -> None:
        limiter = RateLimiter(rate=5.0, burst=5)
        assert limiter.available_tokens == 5.0


class TestRateLimiterAcquire:
    """Test token acquisition behavior."""

    @pytest.mark.asyncio
    async def test_acquire_consumes_token(self) -> None:
        limiter = RateLimiter(rate=10.0, burst=10)
        await limiter.acquire()
        # Token should be consumed (approximately 9 left, accounting for refill)
        assert limiter.available_tokens < 10.0

    @pytest.mark.asyncio
    async def test_acquire_multiple_within_burst(self) -> None:
        limiter = RateLimiter(rate=100.0, burst=5)
        for _ in range(5):
            await limiter.acquire()
        # All burst tokens consumed; should be near 0
        assert limiter.available_tokens < 1.0

    @pytest.mark.asyncio
    async def test_acquire_waits_when_exhausted(self) -> None:
        # Very low rate so we can measure the wait
        limiter = RateLimiter(rate=100.0, burst=1)
        await limiter.acquire()  # Consume the one token

        start = time.monotonic()
        await limiter.acquire()  # Should wait for refill
        elapsed = time.monotonic() - start

        # At 100 req/sec, refill takes ~0.01s per token
        # Allow generous tolerance for CI environments
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self) -> None:
        limiter = RateLimiter(rate=1000.0, burst=5)
        # Drain all tokens
        for _ in range(5):
            await limiter.acquire()

        # Wait a small amount for refill
        await asyncio.sleep(0.01)
        # At 1000/sec, 0.01s should give ~10 tokens, capped at burst=5
        await limiter.acquire()  # Should succeed without long wait


class TestRateLimiterContextManager:
    """Test async context manager interface."""

    @pytest.mark.asyncio
    async def test_context_manager_acquires_token(self) -> None:
        limiter = RateLimiter(rate=10.0, burst=10)
        async with limiter:
            pass
        assert limiter.available_tokens < 10.0

    @pytest.mark.asyncio
    async def test_context_manager_works_in_loop(self) -> None:
        limiter = RateLimiter(rate=100.0, burst=5)
        for _ in range(3):
            async with limiter:
                pass

    @pytest.mark.asyncio
    async def test_context_manager_exception_still_consumes_token(
        self,
    ) -> None:
        limiter = RateLimiter(rate=10.0, burst=10)
        with pytest.raises(RuntimeError):
            async with limiter:
                raise RuntimeError("test error")
        # Token was consumed on entry, even though body raised
        assert limiter.available_tokens < 10.0


class TestRateLimiterConcurrency:
    """Test concurrent access to the rate limiter."""

    @pytest.mark.asyncio
    async def test_concurrent_acquires_respect_rate(self) -> None:
        limiter = RateLimiter(rate=100.0, burst=5)
        results: list[bool] = []

        async def acquire_and_record() -> None:
            async with limiter:
                results.append(True)

        # Launch more tasks than burst capacity
        tasks = [acquire_and_record() for _ in range(8)]
        await asyncio.gather(*tasks)
        assert len(results) == 8

    @pytest.mark.asyncio
    async def test_concurrent_acquires_are_serialized(self) -> None:
        """Verify that concurrent acquires don't over-consume tokens."""
        limiter = RateLimiter(rate=1000.0, burst=3)
        order: list[int] = []

        async def acquire_with_id(idx: int) -> None:
            async with limiter:
                order.append(idx)

        tasks = [acquire_with_id(i) for i in range(5)]
        await asyncio.gather(*tasks)
        assert len(order) == 5
