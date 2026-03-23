"""Tests for the Anthropic provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.advisor.anthropic_provider import AnthropicProvider


class TestIsAvailable:
    def test_available_with_key_and_sdk(self):
        provider = AnthropicProvider(api_key="test-key")
        # Stub out the anthropic SDK so is_available() sees it as importable
        # regardless of whether the package is installed in this environment.
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            assert provider.is_available() is True

    def test_not_available_without_key(self):
        provider = AnthropicProvider(api_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider._api_key = None
            assert provider.is_available() is False

    def test_not_available_without_sdk(self):
        provider = AnthropicProvider(api_key="test-key")
        with patch.dict(
            "sys.modules", {"anthropic": None}
        ):
            # Force ImportError on import
            import sys
            saved = sys.modules.get("anthropic")
            sys.modules["anthropic"] = None  # type: ignore[assignment]
            try:
                result = provider.is_available()
                # When module is None in sys.modules, import raises ImportError
            finally:
                if saved is not None:
                    sys.modules["anthropic"] = saved
                else:
                    sys.modules.pop("anthropic", None)


class TestName:
    def test_name(self):
        provider = AnthropicProvider(api_key="test-key")
        assert provider.name == "Anthropic Claude"


class TestChat:
    def test_chat_sends_correct_messages(self):
        mock_content = MagicMock()
        mock_content.text = "Add more removal."

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="test-key")

        with patch(
            "mtg_deck_maker.advisor.anthropic_provider.anthropic",
            mock_anthropic,
            create=True,
        ), patch(
            "mtg_deck_maker.advisor.retry.time.sleep",
        ):
            # Patch the import inside chat()
            import importlib
            import sys

            sys.modules["anthropic"] = mock_anthropic
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
                # Restore real anthropic
                if "anthropic" in sys.modules:
                    importlib.import_module("anthropic")

        assert result == "Add more removal."
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["system"] == "You are helpful."
        assert call_kwargs.kwargs["messages"] == [
            {"role": "user", "content": "Help me."}
        ]

    def test_chat_no_system_message(self):
        mock_content = MagicMock()
        mock_content.text = "Response."

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="test-key")

        import sys
        sys.modules["anthropic"] = mock_anthropic
        try:
            result = provider.chat(
                [{"role": "user", "content": "Hello."}],
            )
        finally:
            import importlib
            importlib.import_module("anthropic")

        assert result == "Response."
        call_kwargs = mock_client.messages.create.call_args
        assert "system" not in call_kwargs.kwargs

    def test_chat_raises_without_key(self):
        provider = AnthropicProvider(api_key=None)
        provider._api_key = None
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            provider.chat([{"role": "user", "content": "Hello"}])
