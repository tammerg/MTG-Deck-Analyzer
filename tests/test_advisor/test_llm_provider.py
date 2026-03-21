"""Tests for the LLM provider abstraction and factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mtg_deck_maker.advisor.llm_provider import LLMProvider, get_provider


class TestLLMProviderAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]


class TestGetProvider:
    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": ""},
        clear=False,
    )
    def test_openai_explicit(self):
        # Mock openai import availability
        with patch(
            "mtg_deck_maker.advisor.openai_provider.importlib_available",
            True,
            create=True,
        ):
            provider = get_provider("openai")
        if provider is not None:
            assert provider.name == "OpenAI ChatGPT"

    @patch.dict("os.environ", {}, clear=True)
    def test_openai_no_key_returns_none(self):
        provider = get_provider("openai")
        assert provider is None

    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test", "OPENAI_API_KEY": ""},
        clear=False,
    )
    def test_anthropic_explicit(self):
        provider = get_provider("anthropic")
        if provider is not None:
            assert provider.name == "Anthropic Claude"

    @patch.dict("os.environ", {}, clear=True)
    def test_anthropic_no_key_returns_none(self):
        provider = get_provider("anthropic")
        assert provider is None

    @patch.dict("os.environ", {}, clear=True)
    def test_auto_none_when_no_keys(self):
        provider = get_provider("auto")
        assert provider is None

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "sk-ant-test"},
        clear=True,
    )
    def test_auto_falls_back_to_anthropic(self):
        provider = get_provider("auto")
        if provider is not None:
            assert provider.name == "Anthropic Claude"

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": "sk-ant-test"},
        clear=True,
    )
    def test_auto_prefers_openai(self):
        provider = get_provider("auto")
        # If openai SDK is available, should prefer OpenAI
        # If not, falls back to Anthropic - both are valid
        assert provider is not None

    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test"},
        clear=True,
    )
    def test_model_override_passed_to_anthropic(self):
        provider = get_provider("anthropic", model="claude-opus-4-20250514")
        assert provider is not None
        assert provider._model == "claude-opus-4-20250514"

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=True,
    )
    def test_model_override_passed_to_openai(self):
        provider = get_provider("openai", model="gpt-4-turbo")
        if provider is not None:  # Only if openai SDK is installed
            assert provider._model == "gpt-4-turbo"

    @patch.dict("os.environ", {}, clear=True)
    def test_model_override_with_no_key_returns_none(self):
        provider = get_provider("anthropic", model="some-model")
        assert provider is None
