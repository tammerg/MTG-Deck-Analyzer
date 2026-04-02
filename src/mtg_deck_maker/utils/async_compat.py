"""Async compatibility helpers for running coroutines from sync code.

Handles both standalone contexts (CLI, scripts) where no event loop is
running, and contexts where a loop is already active (e.g. FastAPI route
handlers).  Using plain ``asyncio.run()`` in the latter case raises
``RuntimeError: This event loop is already running``.
"""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
from collections.abc import Coroutine
from typing import TypeVar

_T = TypeVar("_T")

__all__ = ["run_async"]

# Module-level singleton — avoids creating a new thread pool on every call.
_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)
atexit.register(_THREAD_POOL.shutdown, wait=False)


def run_async(coro: Coroutine[object, object, _T]) -> _T:
    """Run a coroutine from synchronous code, handling both contexts.

    When called from a script or CLI (no running event loop), delegates to
    ``asyncio.run``.  When called from within an already-running event loop
    (e.g. a FastAPI route handler), offloads the coroutine to a fresh thread
    with its own event loop so the caller's loop is not blocked.

    Args:
        coro: An awaitable coroutine object to execute.

    Returns:
        The value returned by the coroutine.

    Raises:
        Exception: Any exception raised by the coroutine is re-raised.

    Example::

        # Works in both CLI and FastAPI contexts:
        result = run_async(fetch_commander_data(name))
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running — safe to use asyncio.run directly.
        return asyncio.run(coro)

    # Already inside a running event loop (e.g. FastAPI).  Offload to the
    # module-level singleton pool so we don't create a new thread per call.
    future = _THREAD_POOL.submit(asyncio.run, coro)
    return future.result()
