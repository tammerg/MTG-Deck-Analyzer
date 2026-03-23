"""Tests for the async_compat utility module."""

from __future__ import annotations

import asyncio

import pytest

from mtg_deck_maker.utils.async_compat import run_async


async def _coro(value: int) -> int:
    """Simple coroutine that returns its argument."""
    return value


async def _failing_coro() -> None:
    """Coroutine that raises."""
    raise ValueError("coro failed")


class TestRunAsyncNoLoop:
    """Behaviour when no event loop is running (CLI context)."""

    def test_returns_coroutine_result(self):
        result = run_async(_coro(42))
        assert result == 42

    def test_propagates_exception(self):
        with pytest.raises(ValueError, match="coro failed"):
            run_async(_failing_coro())


class TestRunAsyncWithLoop:
    """Behaviour when called from inside a running event loop (FastAPI context)."""

    def test_returns_coroutine_result_from_event_loop(self):
        async def _runner():
            return run_async(_coro(99))

        result = asyncio.run(_runner())
        assert result == 99

    def test_propagates_exception_from_event_loop(self):
        async def _runner():
            return run_async(_failing_coro())

        with pytest.raises(ValueError, match="coro failed"):
            asyncio.run(_runner())

    def test_nested_calls_do_not_deadlock(self):
        """Multiple sequential calls from within an event loop should all complete."""
        async def _runner():
            results = []
            for i in range(3):
                results.append(run_async(_coro(i)))
            return results

        assert asyncio.run(_runner()) == [0, 1, 2]
