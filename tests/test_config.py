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


class TestDefaultConfig:
    """Test default configuration values."""

    def test_default_constraints(self) -> None:
        config = AppConfig()
        assert config.constraints.avoid_reserved_list is True
        assert config.constraints.avoid_infinite_combos is True
        assert config.constraints.max_price_per_card == 20.0
        assert config.constraints.allow_tutors is True
        assert config.constraints.allow_fast_mana is False
        assert config.constraints.include_staples is True
        assert config.constraints.prefer_nonfoil is True
        assert config.constraints.exclude_cards == []
        assert config.constraints.force_cards == []

    def test_default_pricing(self) -> None:
        config = AppConfig()
        assert config.pricing.preferred_source == "tcgplayer"
        assert config.pricing.preferred_currency == "USD"
        assert config.pricing.preferred_finish == "nonfoil"
        assert config.pricing.price_policy == "cheapest_print"

    def test_default_general(self) -> None:
        config = AppConfig()
        assert config.general.data_dir == "./data"
        assert config.general.cache_ttl_hours == 24
        assert config.general.offline_mode is False

    def test_default_llm(self) -> None:
        config = AppConfig()
        assert config.llm.provider == "auto"
        assert config.llm.openai_model == "gpt-4o"
        assert config.llm.anthropic_model == "claude-sonnet-4-20250514"
        assert config.llm.max_tokens == 2048
        assert config.llm.temperature == 0.7
        assert config.llm.timeout_s == 60.0
        assert config.llm.max_retries == 3
        assert config.llm.research_enabled is True
        assert config.llm.priority_bonus == 500


class TestLoadConfigDefaults:
    """Test load_config with only defaults (no file, no env, no CLI)."""

    def test_load_defaults(self, monkeypatch) -> None:
        # Clear any env vars that might interfere
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = load_config(config_path=Path("/nonexistent/config.toml"))
        assert config.constraints.max_price_per_card == 20.0
        assert config.pricing.preferred_source == "tcgplayer"
        assert config.general.cache_ttl_hours == 24


class TestLoadConfigFromToml:
    """Test loading config from a TOML file."""

    def test_load_constraints_from_toml(self, tmp_path, monkeypatch) -> None:
        # Clear env vars
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

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
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

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

    def test_nonexistent_toml_uses_defaults(self, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = load_config(config_path=Path("/does/not/exist.toml"))
        assert config.constraints.max_price_per_card == 20.0


class TestLoadConfigFromEnv:
    """Test environment variable overrides."""

    def test_env_overrides_toml(self, tmp_path, monkeypatch) -> None:
        # Clear all env vars first
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

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
        # Env should override TOML
        assert config.general.data_dir == "/env/data"
        assert config.general.cache_ttl_hours == 6

    def test_env_offline_mode(self, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("MTG_OFFLINE_MODE", "true")

        config = load_config(config_path=Path("/nonexistent.toml"))
        assert config.general.offline_mode is True

    def test_env_max_price_per_card(self, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("MTG_MAX_PRICE_PER_CARD", "50.0")

        config = load_config(config_path=Path("/nonexistent.toml"))
        assert config.constraints.max_price_per_card == 50.0

    def test_env_preferred_source(self, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("MTG_PREFERRED_SOURCE", "scryfall")

        config = load_config(config_path=Path("/nonexistent.toml"))
        assert config.pricing.preferred_source == "scryfall"


class TestLoadConfigFromCli:
    """Test CLI override precedence."""

    def test_cli_overrides_env(self, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("MTG_MAX_PRICE_PER_CARD", "50.0")

        config = load_config(
            config_path=Path("/nonexistent.toml"),
            cli_overrides={"constraints.max_price_per_card": 5.0},
        )
        # CLI should override env
        assert config.constraints.max_price_per_card == 5.0

    def test_cli_overrides_toml_and_env(self, tmp_path, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        config_file = tmp_path / ".mtg-deck-maker.toml"
        config_file.write_text(
            """
[general]
data_dir = "/toml/data"
"""
        )
        monkeypatch.setenv("MTG_DATA_DIR", "/env/data")

        config = load_config(
            config_path=config_file,
            cli_overrides={"general.data_dir": "/cli/data"},
        )
        assert config.general.data_dir == "/cli/data"

    def test_cli_multiple_overrides(self, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = load_config(
            config_path=Path("/nonexistent.toml"),
            cli_overrides={
                "constraints.max_price_per_card": 100.0,
                "general.offline_mode": True,
                "pricing.preferred_source": "justtcg",
            },
        )
        assert config.constraints.max_price_per_card == 100.0
        assert config.general.offline_mode is True
        assert config.pricing.preferred_source == "justtcg"

    def test_cli_invalid_key_ignored(self, monkeypatch) -> None:
        for key in [
            "MTG_DATA_DIR",
            "MTG_CACHE_TTL_HOURS",
            "MTG_OFFLINE_MODE",
            "MTG_PREFERRED_SOURCE",
            "MTG_PREFERRED_CURRENCY",
            "MTG_PREFERRED_FINISH",
            "MTG_MAX_PRICE_PER_CARD",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = load_config(
            config_path=Path("/nonexistent.toml"),
            cli_overrides={"nonexistent.field": "value", "bad_key": 42},
        )
        # Should not crash; defaults should remain
        assert config.constraints.max_price_per_card == 20.0


class TestDataclassSlots:
    """Test that dataclasses use slots for memory efficiency."""

    def test_constraints_has_slots(self) -> None:
        assert hasattr(ConstraintsConfig, "__slots__")

    def test_pricing_has_slots(self) -> None:
        assert hasattr(PricingConfig, "__slots__")

    def test_general_has_slots(self) -> None:
        assert hasattr(GeneralConfig, "__slots__")

    def test_app_config_has_slots(self) -> None:
        assert hasattr(AppConfig, "__slots__")

    def test_llm_config_has_slots(self) -> None:
        assert hasattr(LLMConfig, "__slots__")


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
        # Other values remain default
        assert config.llm.openai_model == "gpt-4o"
        assert config.llm.max_tokens == 2048


class TestLLMConfigFromEnv:
    """Test LLM environment variable overrides."""

    def test_env_llm_provider(self, monkeypatch) -> None:
        _clear_env(monkeypatch)
        monkeypatch.setenv("MTG_LLM_PROVIDER", "anthropic")
        config = load_config(config_path=Path("/nonexistent.toml"))
        assert config.llm.provider == "anthropic"

    def test_env_llm_timeout(self, monkeypatch) -> None:
        _clear_env(monkeypatch)
        monkeypatch.setenv("MTG_LLM_TIMEOUT", "120.0")
        config = load_config(config_path=Path("/nonexistent.toml"))
        assert config.llm.timeout_s == 120.0

    def test_env_llm_model_overrides(self, monkeypatch) -> None:
        _clear_env(monkeypatch)
        monkeypatch.setenv("MTG_OPENAI_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("MTG_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        config = load_config(config_path=Path("/nonexistent.toml"))
        assert config.llm.openai_model == "gpt-4o-mini"
        assert config.llm.anthropic_model == "claude-haiku-4-5-20251001"

    def test_env_llm_max_retries(self, monkeypatch) -> None:
        _clear_env(monkeypatch)
        monkeypatch.setenv("MTG_LLM_MAX_RETRIES", "5")
        config = load_config(config_path=Path("/nonexistent.toml"))
        assert config.llm.max_retries == 5


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
