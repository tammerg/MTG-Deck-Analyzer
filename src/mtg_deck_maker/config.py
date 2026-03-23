"""Configuration loading with precedence: CLI args > env vars > TOML file > defaults."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


CONFIG_FILE_NAME = ".mtg-deck-maker.toml"


@dataclass(slots=True)
class ConstraintsConfig:
    """Deck-building constraint settings."""

    avoid_reserved_list: bool = True
    avoid_infinite_combos: bool = True
    max_price_per_card: float = 20.0
    allow_tutors: bool = True
    allow_fast_mana: bool = False
    include_staples: bool = True
    prefer_nonfoil: bool = True
    exclude_cards: list[str] = field(default_factory=list)
    force_cards: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PricingConfig:
    """Pricing source and preference settings."""

    preferred_source: str = "tcgplayer"
    preferred_currency: str = "USD"
    preferred_finish: str = "nonfoil"
    price_policy: str = "cheapest_print"


@dataclass(slots=True)
class GeneralConfig:
    """General application settings."""

    data_dir: str = "./data"
    cache_ttl_hours: int = 24
    offline_mode: bool = False


@dataclass(slots=True)
class LLMConfig:
    """LLM provider settings."""

    provider: str = "auto"
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout_s: float = 60.0
    max_retries: int = 3
    research_enabled: bool = True
    priority_bonus: int = 500


@dataclass(slots=True)
class AppConfig:
    """Top-level application configuration."""

    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    pricing: PricingConfig = field(default_factory=PricingConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


def _parse_bool(value: str) -> bool:
    """Parse a boolean from a string environment variable."""
    return value.lower() in ("true", "1", "yes", "on")


def _load_toml_file(config_path: Path | None = None) -> dict:
    """Load configuration from a TOML file if it exists.

    Searches in order:
    1. Explicit path if provided
    2. Current working directory
    3. User home directory
    """
    search_paths: list[Path] = []

    if config_path is not None:
        search_paths.append(config_path)
    else:
        search_paths.append(Path.cwd() / CONFIG_FILE_NAME)
        search_paths.append(Path.home() / CONFIG_FILE_NAME)

    for path in search_paths:
        if path.is_file():
            with open(path, "rb") as f:
                return tomllib.load(f)

    return {}


def _apply_toml_to_constraints(
    config: ConstraintsConfig, toml_data: dict
) -> None:
    """Apply TOML [constraints] section to a ConstraintsConfig."""
    section = toml_data.get("constraints", {})
    if not section:
        return

    bool_fields = [
        "avoid_reserved_list",
        "avoid_infinite_combos",
        "allow_tutors",
        "allow_fast_mana",
        "include_staples",
        "prefer_nonfoil",
    ]
    for field_name in bool_fields:
        if field_name in section:
            setattr(config, field_name, bool(section[field_name]))

    if "max_price_per_card" in section:
        config.max_price_per_card = float(section["max_price_per_card"])

    if "exclude_cards" in section:
        config.exclude_cards = list(section["exclude_cards"])

    if "force_cards" in section:
        config.force_cards = list(section["force_cards"])


def _apply_toml_to_pricing(config: PricingConfig, toml_data: dict) -> None:
    """Apply TOML [pricing] section to a PricingConfig."""
    section = toml_data.get("pricing", {})
    if not section:
        return

    for field_name in (
        "preferred_source",
        "preferred_currency",
        "preferred_finish",
        "price_policy",
    ):
        if field_name in section:
            setattr(config, field_name, str(section[field_name]))


def _apply_toml_to_general(config: GeneralConfig, toml_data: dict) -> None:
    """Apply TOML [general] section to a GeneralConfig."""
    section = toml_data.get("general", {})
    if not section:
        return

    if "data_dir" in section:
        config.data_dir = str(section["data_dir"])

    if "cache_ttl_hours" in section:
        config.cache_ttl_hours = int(section["cache_ttl_hours"])

    if "offline_mode" in section:
        config.offline_mode = bool(section["offline_mode"])


def _apply_toml_to_llm(config: LLMConfig, toml_data: dict) -> None:
    """Apply TOML [llm] section to an LLMConfig."""
    section = toml_data.get("llm", {})
    if not section:
        return

    str_fields = ["provider", "openai_model", "anthropic_model"]
    for field_name in str_fields:
        if field_name in section:
            setattr(config, field_name, str(section[field_name]))

    int_fields = ["max_tokens", "max_retries", "priority_bonus"]
    for field_name in int_fields:
        if field_name in section:
            setattr(config, field_name, int(section[field_name]))

    float_fields = ["temperature", "timeout_s"]
    for field_name in float_fields:
        if field_name in section:
            setattr(config, field_name, float(section[field_name]))

    if "research_enabled" in section:
        config.research_enabled = bool(section["research_enabled"])


def _apply_env_vars(config: AppConfig) -> None:
    """Apply environment variable overrides to config.

    Environment variable mapping:
    - MTG_DATA_DIR -> general.data_dir
    - MTG_CACHE_TTL_HOURS -> general.cache_ttl_hours
    - MTG_OFFLINE_MODE -> general.offline_mode
    - MTG_PREFERRED_SOURCE -> pricing.preferred_source
    - MTG_PREFERRED_CURRENCY -> pricing.preferred_currency
    - MTG_PREFERRED_FINISH -> pricing.preferred_finish
    - MTG_MAX_PRICE_PER_CARD -> constraints.max_price_per_card
    - MTG_LLM_PROVIDER -> llm.provider
    - MTG_OPENAI_MODEL -> llm.openai_model
    - MTG_ANTHROPIC_MODEL -> llm.anthropic_model
    - MTG_LLM_TIMEOUT -> llm.timeout_s
    - MTG_LLM_MAX_RETRIES -> llm.max_retries
    """
    env_map: dict[str, tuple[str, str, type | Callable[[str], object]]] = {
        "MTG_DATA_DIR": ("general", "data_dir", str),
        "MTG_CACHE_TTL_HOURS": ("general", "cache_ttl_hours", int),
        "MTG_OFFLINE_MODE": ("general", "offline_mode", _parse_bool),
        "MTG_PREFERRED_SOURCE": ("pricing", "preferred_source", str),
        "MTG_PREFERRED_CURRENCY": ("pricing", "preferred_currency", str),
        "MTG_PREFERRED_FINISH": ("pricing", "preferred_finish", str),
        "MTG_MAX_PRICE_PER_CARD": (
            "constraints",
            "max_price_per_card",
            float,
        ),
        "MTG_LLM_PROVIDER": ("llm", "provider", str),
        "MTG_OPENAI_MODEL": ("llm", "openai_model", str),
        "MTG_ANTHROPIC_MODEL": ("llm", "anthropic_model", str),
        "MTG_LLM_TIMEOUT": ("llm", "timeout_s", float),
        "MTG_LLM_MAX_RETRIES": ("llm", "max_retries", int),
    }

    for env_key, (section_name, field_name, converter) in env_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            section = getattr(config, section_name)
            setattr(section, field_name, converter(value))


def _apply_cli_overrides(
    config: AppConfig, cli_overrides: dict | None
) -> None:
    """Apply CLI argument overrides to config.

    Expects a flat dict with dotted keys like:
    {"constraints.max_price_per_card": 10.0, "general.offline_mode": True}
    """
    if not cli_overrides:
        return

    for key, value in cli_overrides.items():
        parts = key.split(".", 1)
        if len(parts) != 2:
            continue
        section_name, field_name = parts
        section = getattr(config, section_name, None)
        if section is not None and hasattr(section, field_name):
            setattr(section, field_name, value)


def load_config(
    config_path: Path | None = None,
    cli_overrides: dict | None = None,
) -> AppConfig:
    """Load configuration with full precedence chain.

    Precedence (highest to lowest):
    1. CLI argument overrides
    2. Environment variables
    3. TOML config file
    4. Default values

    Args:
        config_path: Explicit path to a TOML config file.
        cli_overrides: Dict of dotted-key overrides from CLI arguments.

    Returns:
        Fully resolved AppConfig instance.
    """
    config = AppConfig()

    # Layer 1: TOML file (lowest precedence after defaults)
    toml_data = _load_toml_file(config_path)
    if toml_data:
        _apply_toml_to_constraints(config.constraints, toml_data)
        _apply_toml_to_pricing(config.pricing, toml_data)
        _apply_toml_to_general(config.general, toml_data)
        _apply_toml_to_llm(config.llm, toml_data)

    # Layer 2: Environment variables
    _apply_env_vars(config)

    # Layer 3: CLI overrides (highest precedence)
    _apply_cli_overrides(config, cli_overrides)

    return config
