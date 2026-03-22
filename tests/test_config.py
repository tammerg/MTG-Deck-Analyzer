"""Tests for the configuration loading system."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mtg_deck_maker.config import (
    AppConfig,
    ConstraintsConfig,
    GeneralConfig,
    LLMConfig,
    PricingConfig,
    load_config,
)

_ALL_ENV_VARS = [
    "MTG_DATA_DIR",
    "MTG_CACHE_TTL_HOURS",
    "MTG_OFFLINE_MODE",
    "MTG_PREFERRED_SOURCE",
    "MTG_PREFERRED_CURRENCY",
    "MTG_PREFERRED_FINISH",
    "MTG_MAX_PRICE_PER_CARD",
    "MTG_LLM_PROVIDER",
    "MTG_OPENAI_MODEL",
    "MTG_ANTHROPIC_MODEL",
    "MTG_LLM_TIMEOUT",
    "MTG_LLM_MAX_RETRIES",
]


def _clear_env(monkeypatch) -> None:
    for key in _ALL_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


class TestDefaultConfig:
    """Test representative defaults across all config sections."""

    def test_representative_defaults(self) -> None:
        config = AppConfig()
        # constraints
        assert config.constraints.avoid_reserved_list is True
        assert config.constraints.max_price_per_card == 20.0
        assert config.constraints.exclude_cards == []
        # pricing
        assert config.pricing.preferred_source == "tcgplayer"
        assert config.pricing.preferred_currency == "USD"
        # general
        assert config.general.data_dir == "./data"
        assert config.general.offline_mode is False
        # llm
        assert config.llm.provider == "auto"
        assert config.llm.openai_model == "gpt-4o"
        assert config.llm.anthropic_model == "claude-sonnet-4-20250514"
        assert config.llm.max_tokens == 2048
        assert config.llm.research_enabled is True


class TestLoadConfigDefaults:
    """Test load_config with only defaults (no file, no env, no CLI)."""

    def test_load_defaults(self, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config = load_config(config_path=Path("/nonexistent/config.toml"))
        assert config.constraints.max_price_per_card == 20.0
        assert config.pricing.preferred_source == "tcgplayer"
        assert config.general.cache_ttl_hours == 24


class TestLoadConfigFromToml:
    """Test loading config from a TOML file."""

    def test_load_constraints_from_toml(self, tmp_path, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config_file = tmp_path / ".mtg-deck-maker.toml"
        config_file.write_text(
            """
[constraints]
avoid_reserved_list = false
max_price_per_card = 10.0
exclude_cards = ["Mana Crypt", "Dockside Extortionist"]
force_cards = ["Skullclamp"]
allow_fast_mana = true

[pricing]
preferred_source = "cardmarket"
preferred_currency = "EUR"

[general]
data_dir = "/custom/data"
cache_ttl_hours = 12
offline_mode = true
"""
        )

        config = load_config(config_path=config_file)
        assert config.constraints.avoid_reserved_list is False
        assert config.constraints.max_price_per_card == 10.0
        assert config.constraints.exclude_cards == [
            "Mana Crypt",
            "Dockside Extortionist",
        ]
        assert config.constraints.force_cards == ["Skullclamp"]
        assert config.constraints.allow_fast_mana is True
        assert config.pricing.preferred_source == "cardmarket"
        assert config.pricing.preferred_currency == "EUR"
        assert config.general.data_dir == "/custom/data"
        assert config.general.cache_ttl_hours == 12
        assert config.general.offline_mode is True

    def test_partial_toml_uses_defaults(self, tmp_path, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config_file = tmp_path / ".mtg-deck-maker.toml"
        config_file.write_text(
            """
[constraints]
max_price_per_card = 15.0
"""
        )

        config = load_config(config_path=config_file)
        assert config.constraints.max_price_per_card == 15.0
        # Other values remain default
        assert config.constraints.avoid_reserved_list is True
        assert config.pricing.preferred_source == "tcgplayer"
        assert config.general.cache_ttl_hours == 24


class TestLoadConfigFromEnv:
    """Test environment variable overrides."""

    def test_env_overrides_toml(self, tmp_path, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config_file = tmp_path / ".mtg-deck-maker.toml"
        config_file.write_text(
            """
[general]
data_dir = "/toml/data"
cache_ttl_hours = 12
"""
        )

        monkeypatch.setenv("MTG_DATA_DIR", "/env/data")
        monkeypatch.setenv("MTG_CACHE_TTL_HOURS", "6")

        config = load_config(config_path=config_file)
        assert config.general.data_dir == "/env/data"
        assert config.general.cache_ttl_hours == 6

    @pytest.mark.parametrize(
        "env_var, env_val, attr_path, expected",
        [
            ("MTG_OFFLINE_MODE", "true", "general.offline_mode", True),
            ("MTG_MAX_PRICE_PER_CARD", "50.0", "constraints.max_price_per_card", 50.0),
            ("MTG_PREFERRED_SOURCE", "scryfall", "pricing.preferred_source", "scryfall"),
        ],
    )
    def test_env_overrides(self, monkeypatch, env_var, env_val, attr_path, expected) -> None:
        _clear_env(monkeypatch)
        monkeypatch.setenv(env_var, env_val)
        config = load_config(config_path=Path("/nonexistent.toml"))
        section, field = attr_path.split(".")
        assert getattr(getattr(config, section), field) == expected


class TestLoadConfigFromCli:
    """Test CLI override precedence."""

    @pytest.mark.parametrize(
        "description, env_vars, toml_content, cli_overrides, attr_path, expected",
        [
            (
                "cli_overrides_env",
                {"MTG_MAX_PRICE_PER_CARD": "50.0"},
                None,
                {"constraints.max_price_per_card": 5.0},
                "constraints.max_price_per_card",
                5.0,
            ),
            (
                "cli_overrides_toml_and_env",
                {"MTG_DATA_DIR": "/env/data"},
                '[general]\ndata_dir = "/toml/data"',
                {"general.data_dir": "/cli/data"},
                "general.data_dir",
                "/cli/data",
            ),
            (
                "cli_multiple_overrides_price",
                {},
                None,
                {
                    "constraints.max_price_per_card": 100.0,
                    "general.offline_mode": True,
                    "pricing.preferred_source": "justtcg",
                },
                "constraints.max_price_per_card",
                100.0,
            ),
        ],
    )
    def test_cli_precedence(
        self, tmp_path, monkeypatch, description, env_vars, toml_content, cli_overrides, attr_path, expected
    ) -> None:
        _clear_env(monkeypatch)
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)

        if toml_content:
            config_file = tmp_path / ".mtg-deck-maker.toml"
            config_file.write_text(toml_content)
        else:
            config_file = Path("/nonexistent.toml")

        config = load_config(config_path=config_file, cli_overrides=cli_overrides)
        section, field = attr_path.split(".")
        assert getattr(getattr(config, section), field) == expected

    def test_cli_invalid_key_ignored(self, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config = load_config(
            config_path=Path("/nonexistent.toml"),
            cli_overrides={"nonexistent.field": "value", "bad_key": 42},
        )
        assert config.constraints.max_price_per_card == 20.0


class TestLLMConfigFromToml:
    """Test loading LLM config from TOML."""

    def test_load_llm_from_toml(self, tmp_path, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config_file = tmp_path / ".mtg-deck-maker.toml"
        config_file.write_text(
            """
[llm]
provider = "openai"
openai_model = "gpt-4o-mini"
anthropic_model = "claude-haiku-4-5-20251001"
max_tokens = 4096
temperature = 0.5
timeout_s = 30.0
max_retries = 5
research_enabled = false
priority_bonus = 300
"""
        )
        config = load_config(config_path=config_file)
        assert config.llm.provider == "openai"
        assert config.llm.openai_model == "gpt-4o-mini"
        assert config.llm.anthropic_model == "claude-haiku-4-5-20251001"
        assert config.llm.max_tokens == 4096
        assert config.llm.temperature == 0.5
        assert config.llm.timeout_s == 30.0
        assert config.llm.max_retries == 5
        assert config.llm.research_enabled is False
        assert config.llm.priority_bonus == 300

    def test_partial_llm_toml(self, tmp_path, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config_file = tmp_path / ".mtg-deck-maker.toml"
        config_file.write_text(
            """
[llm]
provider = "anthropic"
"""
        )
        config = load_config(config_path=config_file)
        assert config.llm.provider == "anthropic"
        assert config.llm.openai_model == "gpt-4o"
        assert config.llm.max_tokens == 2048


class TestLLMConfigFromEnv:
    """Test LLM environment variable overrides."""

    @pytest.mark.parametrize(
        "env_vars, attr, expected",
        [
            ({"MTG_LLM_PROVIDER": "anthropic"}, "provider", "anthropic"),
            ({"MTG_LLM_TIMEOUT": "120.0"}, "timeout_s", 120.0),
            ({"MTG_LLM_MAX_RETRIES": "5"}, "max_retries", 5),
            (
                {"MTG_OPENAI_MODEL": "gpt-4o-mini", "MTG_ANTHROPIC_MODEL": "claude-haiku-4-5-20251001"},
                "openai_model",
                "gpt-4o-mini",
            ),
        ],
    )
    def test_env_llm_overrides(self, monkeypatch, env_vars, attr, expected) -> None:
        _clear_env(monkeypatch)
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)
        config = load_config(config_path=Path("/nonexistent.toml"))
        assert getattr(config.llm, attr) == expected


class TestLLMConfigFromCli:
    """Test LLM CLI override precedence."""

    def test_cli_llm_override(self, monkeypatch) -> None:
        _clear_env(monkeypatch)
        config = load_config(
            config_path=Path("/nonexistent.toml"),
            cli_overrides={"llm.provider": "openai", "llm.priority_bonus": 1000},
        )
        assert config.llm.provider == "openai"
        assert config.llm.priority_bonus == 1000
