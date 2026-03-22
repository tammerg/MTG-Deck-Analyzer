"""Tests for the retry module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.advisor.retry import RetryError, _is_retryable, with_retries


class TestIsRetryable:
    @pytest.mark.parametrize(
        "exc, expected",
        [
            (Exception("Error code: 429"), True),
            (Exception("rate_limit_exceeded"), True),
            (Exception("rate limit hit"), True),
            (Exception("Internal server error 500"), True),
            (Exception("502 Bad Gateway"), True),
            (Exception("503 Service Unavailable"), True),
            (Exception("504 Gateway Timeout"), True),
            (Exception("400 Bad Request"), False),
            (Exception("Authentication failed"), False),
            (ValueError("some error"), False),
        ],
        ids=[
            "429", "rate_limit", "rate_limit_space",
            "500", "502", "503", "504",
            "400_not_retryable", "auth_not_retryable", "generic_not_retryable",
        ],
    )
    def test_is_retryable(self, exc, expected):
        assert _is_retryable(exc) is expected


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
