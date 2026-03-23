"""Tests for the LLM provider abstraction and factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mtg_deck_maker.advisor.anthropic_provider import AnthropicProvider
from mtg_deck_maker.advisor.llm_provider import LLMProvider, get_provider
from mtg_deck_maker.advisor.openai_provider import OpenAIProvider


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


class TestModelId:
    """model_id must return the underlying API model identifier, not the display name."""

    def test_anthropic_default_model_id(self):
        p = AnthropicProvider(api_key="sk-ant-test")
        assert p.model_id == "claude-sonnet-4-20250514"
        assert p.model_id != p.name  # must differ from display name

    def test_anthropic_custom_model_id(self):
        p = AnthropicProvider(api_key="sk-ant-test", model="claude-opus-4-20250514")
        assert p.model_id == "claude-opus-4-20250514"

    def test_openai_default_model_id(self):
        p = OpenAIProvider(api_key="sk-test")
        assert p.model_id == "gpt-4o"
        assert p.model_id != p.name

    def test_openai_custom_model_id(self):
        p = OpenAIProvider(api_key="sk-test", model="gpt-4-turbo")
        assert p.model_id == "gpt-4-turbo"

    def test_model_id_is_str(self):
        for p in (AnthropicProvider(api_key="x"), OpenAIProvider(api_key="x")):
            assert isinstance(p.model_id, str)
            assert len(p.model_id) > 0
