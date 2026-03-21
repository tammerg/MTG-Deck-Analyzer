"""Tests for the OpenAI provider."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.advisor.openai_provider import OpenAIProvider


class TestIsAvailable:
    def test_not_available_without_key(self):
        provider = OpenAIProvider(api_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider._api_key = None
            assert provider.is_available() is False

    def test_available_with_key_and_sdk(self):
        provider = OpenAIProvider(api_key="sk-test")
        # If openai is installed, should be available
        try:
            import openai  # noqa: F401
            assert provider.is_available() is True
        except ImportError:
            # openai not installed, that's ok for this test env
            assert provider.is_available() is False

    def test_not_available_without_sdk(self):
        provider = OpenAIProvider(api_key="sk-test")
        # Temporarily make openai unimportable
        saved = sys.modules.get("openai")
        sys.modules["openai"] = None  # type: ignore[assignment]
        try:
            assert provider.is_available() is False
        finally:
            if saved is not None:
                sys.modules["openai"] = saved
            else:
                sys.modules.pop("openai", None)


class TestName:
    def test_name(self):
        provider = OpenAIProvider(api_key="sk-test")
        assert provider.name == "OpenAI ChatGPT"


class TestChat:
    def test_chat_sends_correct_messages(self):
        mock_message = MagicMock()
        mock_message.content = "Great deck advice."

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")

        sys.modules["openai"] = mock_openai
        try:
            result = provider.chat(
                [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Help me."},
                ],
                max_tokens=512,
                temperature=0.5,
            )
        finally:
            sys.modules.pop("openai", None)

        assert result == "Great deck advice."
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["messages"] == [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Help me."},
        ]
        assert call_kwargs.kwargs["max_tokens"] == 512
        assert call_kwargs.kwargs["temperature"] == 0.5

    def test_chat_raises_without_key(self):
        provider = OpenAIProvider(api_key=None)
        provider._api_key = None

        mock_openai = MagicMock()
        sys.modules["openai"] = mock_openai
        try:
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                provider.chat([{"role": "user", "content": "Hello"}])
        finally:
            sys.modules.pop("openai", None)

    def test_chat_raises_without_sdk(self):
        provider = OpenAIProvider(api_key="sk-test")
        saved = sys.modules.get("openai")
        sys.modules["openai"] = None  # type: ignore[assignment]
        try:
            with pytest.raises(RuntimeError, match="openai"):
                provider.chat([{"role": "user", "content": "Hello"}])
        finally:
            if saved is not None:
                sys.modules["openai"] = saved
            else:
                sys.modules.pop("openai", None)

    def test_chat_empty_response(self):
        mock_response = MagicMock()
        mock_response.choices = []

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")

        sys.modules["openai"] = mock_openai
        try:
            result = provider.chat(
                [{"role": "user", "content": "Hello"}],
            )
        finally:
            sys.modules.pop("openai", None)

        assert result == ""

    @patch("mtg_deck_maker.advisor.retry.time.sleep")
    def test_chat_retries_on_429(self, mock_sleep):
        mock_message = MagicMock()
        mock_message.content = "Success"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("Error 429 rate_limit"),
            mock_response,
        ]

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test")

        sys.modules["openai"] = mock_openai
        try:
            result = provider.chat(
                [{"role": "user", "content": "Hello"}],
            )
        finally:
            sys.modules.pop("openai", None)

        assert result == "Success"
        assert mock_client.chat.completions.create.call_count == 2
