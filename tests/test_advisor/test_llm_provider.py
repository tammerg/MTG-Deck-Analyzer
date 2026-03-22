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
    @pytest.mark.parametrize(
        "provider_name, env, expected_name",
        [
            ("openai", {"OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": ""}, "OpenAI ChatGPT"),
            ("anthropic", {"ANTHROPIC_API_KEY": "sk-ant-test", "OPENAI_API_KEY": ""}, "Anthropic Claude"),
        ],
        ids=["openai_explicit", "anthropic_explicit"],
    )
    def test_explicit_provider(self, provider_name, env, expected_name):
        with patch.dict("os.environ", env, clear=False):
            provider = get_provider(provider_name)
        if provider is not None:
            assert provider.name == expected_name

    @pytest.mark.parametrize(
        "provider_name, env",
        [
            ("openai", {}),
            ("anthropic", {}),
            ("anthropic", {}),
        ],
        ids=["openai_no_key", "anthropic_no_key", "model_override_no_key"],
    )
    def test_no_key_returns_none(self, provider_name, env):
        with patch.dict("os.environ", env, clear=True):
            provider = get_provider(provider_name)
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

    @pytest.mark.parametrize(
        "provider_name, env, model, attr_expected",
        [
            ("anthropic", {"ANTHROPIC_API_KEY": "sk-ant-test"}, "claude-opus-4-20250514", "claude-opus-4-20250514"),
            ("openai", {"OPENAI_API_KEY": "sk-test"}, "gpt-4-turbo", "gpt-4-turbo"),
        ],
        ids=["anthropic_model_override", "openai_model_override"],
    )
    def test_model_override(self, provider_name, env, model, attr_expected):
        with patch.dict("os.environ", env, clear=True):
            provider = get_provider(provider_name, model=model)
        if provider is not None:
            assert provider._model == attr_expected
