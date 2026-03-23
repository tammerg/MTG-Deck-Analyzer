"""Shared retry logic with exponential backoff for LLM providers."""

from __future__ import annotations

import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore[assignment]

try:
    import openai as _openai
except ImportError:
    _openai = None  # type: ignore[assignment]


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, last_error: Exception, attempts: int) -> None:
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(f"Failed after {attempts} attempts: {last_error}")


def with_retries(
    fn: Callable[[], str],
    max_retries: int = 3,
    backoff_base: float = 2.0,
    retryable: Callable[[Exception], bool] | None = None,
) -> str:
    """Execute fn() with exponential backoff on retryable errors.

    Args:
        fn: Callable that returns a string response.
        max_retries: Maximum number of retry attempts.
        backoff_base: Base for exponential backoff (seconds).
        retryable: Optional callable that returns True if the exception is
            retryable.  Defaults to retrying on rate limit (429) and server
            errors (5xx).

    Returns:
        The string result from fn().

    Raises:
        RetryError: If all retries are exhausted.
        Exception: If the error is not retryable.
    """
    if retryable is None:
        retryable = _is_retryable

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if not retryable(exc):
                raise
            if attempt < max_retries:
                wait = backoff_base ** attempt
                logger.warning(
                    "Attempt %d/%d failed (%s), retrying in %.1fs...",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)

    assert last_error is not None
    raise RetryError(last_error, max_retries + 1)


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is retryable (429 rate limit or 5xx server error)."""
    # Check SDK-specific exception types first
    if _anthropic is not None:
        if isinstance(exc, _anthropic.RateLimitError):
            return True
        if isinstance(exc, _anthropic.InternalServerError):
            return True
    if _openai is not None:
        if isinstance(exc, _openai.RateLimitError):
            return True
        if isinstance(exc, _openai.InternalServerError):
            return True
    # Fall back to string parsing for unknown exception types
    error_str = str(exc).lower()
    if "429" in error_str or "rate_limit" in error_str or "rate limit" in error_str:
        return True
    for code in ("500", "502", "503", "504"):
        if code in error_str:
            return True
    return False
