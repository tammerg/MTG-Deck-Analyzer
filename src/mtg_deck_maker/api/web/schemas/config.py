"""Pydantic schemas for configuration API endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class ConstraintsConfigResponse(BaseModel):
    """Response schema for constraint configuration."""

    avoid_reserved_list: bool
    avoid_infinite_combos: bool
    max_price_per_card: float
    allow_tutors: bool
    allow_fast_mana: bool
    include_staples: bool
    prefer_nonfoil: bool
    exclude_cards: list[str]
    force_cards: list[str]


class PricingConfigResponse(BaseModel):
    """Response schema for pricing configuration."""

    preferred_source: str
    preferred_currency: str
    preferred_finish: str
    price_policy: str


class GeneralConfigResponse(BaseModel):
    """Response schema for general configuration."""

    data_dir: str
    cache_ttl_hours: int
    offline_mode: bool


class LLMConfigResponse(BaseModel):
    """Response schema for LLM configuration."""

    provider: str
    openai_model: str
    anthropic_model: str
    max_tokens: int
    temperature: float
    timeout_s: float
    max_retries: int
    research_enabled: bool
    priority_bonus: int


class ConfigResponse(BaseModel):
    """Response schema for the full application configuration."""

    constraints: ConstraintsConfigResponse
    pricing: PricingConfigResponse
    general: GeneralConfigResponse
    llm: LLMConfigResponse


class ConstraintsConfigUpdate(BaseModel):
    """Partial update schema for constraint configuration."""

    avoid_reserved_list: bool | None = None
    avoid_infinite_combos: bool | None = None
    max_price_per_card: float | None = None
    allow_tutors: bool | None = None
    allow_fast_mana: bool | None = None
    include_staples: bool | None = None
    prefer_nonfoil: bool | None = None
    exclude_cards: list[str] | None = None
    force_cards: list[str] | None = None


class PricingConfigUpdate(BaseModel):
    """Partial update schema for pricing configuration."""

    preferred_source: str | None = None
    preferred_currency: str | None = None
    preferred_finish: str | None = None
    price_policy: str | None = None


class GeneralConfigUpdate(BaseModel):
    """Partial update schema for general configuration."""

    data_dir: str | None = None
    cache_ttl_hours: int | None = None
    offline_mode: bool | None = None


class LLMConfigUpdate(BaseModel):
    """Partial update schema for LLM configuration."""

    provider: str | None = None
    openai_model: str | None = None
    anthropic_model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    timeout_s: float | None = None
    max_retries: int | None = None
    research_enabled: bool | None = None
    priority_bonus: int | None = None


class ConfigUpdateRequest(BaseModel):
    """Partial update schema for the full application configuration."""

    constraints: ConstraintsConfigUpdate | None = None
    pricing: PricingConfigUpdate | None = None
    general: GeneralConfigUpdate | None = None
    llm: LLMConfigUpdate | None = None
