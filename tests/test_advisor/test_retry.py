"""Tests for the retry module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.advisor.retry import RetryError, _is_retryable, with_retries


class TestIsRetryable:
    def test_429_is_retryable(self):
        assert _is_retryable(Exception("Error code: 429")) is True

    def test_rate_limit_is_retryable(self):
        assert _is_retryable(Exception("rate_limit_exceeded")) is True

    def test_rate_limit_space_is_retryable(self):
        assert _is_retryable(Exception("rate limit hit")) is True

    def test_500_is_retryable(self):
        assert _is_retryable(Exception("Internal server error 500")) is True

    def test_502_is_retryable(self):
        assert _is_retryable(Exception("502 Bad Gateway")) is True

    def test_503_is_retryable(self):
        assert _is_retryable(Exception("503 Service Unavailable")) is True

    def test_504_is_retryable(self):
        assert _is_retryable(Exception("504 Gateway Timeout")) is True

    def test_400_not_retryable(self):
        assert _is_retryable(Exception("400 Bad Request")) is False

    def test_auth_error_not_retryable(self):
        assert _is_retryable(Exception("Authentication failed")) is False

    def test_generic_error_not_retryable(self):
        assert _is_retryable(ValueError("some error")) is False


class TestWithRetries:
    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_success_first_attempt(self, mock_sleep):
        fn = MagicMock(return_value="ok")
        result = with_retries(fn, max_retries=3)
        assert result == "ok"
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_success_after_retries(self, mock_sleep):
        fn = MagicMock(
            side_effect=[Exception("429 rate limit"), Exception("502"), "ok"]
        )
        result = with_retries(fn, max_retries=3)
        assert result == "ok"
        assert fn.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_all_retries_exhausted(self, mock_sleep):
        fn = MagicMock(side_effect=Exception("429 rate limit"))
        with pytest.raises(RetryError) as exc_info:
            with_retries(fn, max_retries=2)
        assert exc_info.value.attempts == 3
        assert "429" in str(exc_info.value.last_error)

    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_non_retryable_raises_immediately(self, mock_sleep):
        fn = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError, match="bad input"):
            with_retries(fn, max_retries=3)
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        fn = MagicMock(
            side_effect=[
                Exception("429"),
                Exception("429"),
                Exception("429"),
                "ok",
            ]
        )
        result = with_retries(fn, max_retries=3, backoff_base=2.0)
        assert result == "ok"
        # Backoff: 2^0=1, 2^1=2, 2^2=4
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)

    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_custom_retryable(self, mock_sleep):
        fn = MagicMock(
            side_effect=[ValueError("retry me"), "ok"]
        )
        result = with_retries(
            fn,
            max_retries=3,
            retryable=lambda exc: isinstance(exc, ValueError),
        )
        assert result == "ok"
        assert fn.call_count == 2

    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_retry_error_attributes(self, mock_sleep):
        original = Exception("503 server error")
        fn = MagicMock(side_effect=original)
        with pytest.raises(RetryError) as exc_info:
            with_retries(fn, max_retries=1)
        assert exc_info.value.last_error is original
        assert exc_info.value.attempts == 2
