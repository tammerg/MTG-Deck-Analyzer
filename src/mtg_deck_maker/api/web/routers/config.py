"""Config router - get and update application configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from mtg_deck_maker.api.web.dependencies import get_config
from mtg_deck_maker.api.web.schemas.config import (
    ConfigResponse,
    ConfigUpdateRequest,
    ConstraintsConfigResponse,
    GeneralConfigResponse,
    LLMConfigResponse,
    PricingConfigResponse,
)
from mtg_deck_maker.config import AppConfig

router = APIRouter(tags=["config"])


def _config_to_response(config: AppConfig) -> ConfigResponse:
    """Convert an AppConfig instance to a ConfigResponse."""
    return ConfigResponse(
        constraints=ConstraintsConfigResponse(
            avoid_reserved_list=config.constraints.avoid_reserved_list,
            avoid_infinite_combos=config.constraints.avoid_infinite_combos,
            max_price_per_card=config.constraints.max_price_per_card,
            allow_tutors=config.constraints.allow_tutors,
            allow_fast_mana=config.constraints.allow_fast_mana,
            include_staples=config.constraints.include_staples,
            prefer_nonfoil=config.constraints.prefer_nonfoil,
            exclude_cards=config.constraints.exclude_cards,
            force_cards=config.constraints.force_cards,
        ),
        pricing=PricingConfigResponse(
            preferred_source=config.pricing.preferred_source,
            preferred_currency=config.pricing.preferred_currency,
            preferred_finish=config.pricing.preferred_finish,
            price_policy=config.pricing.price_policy,
        ),
        general=GeneralConfigResponse(
            data_dir=config.general.data_dir,
            cache_ttl_hours=config.general.cache_ttl_hours,
            offline_mode=config.general.offline_mode,
        ),
        llm=LLMConfigResponse(
            provider=config.llm.provider,
            openai_model=config.llm.openai_model,
            anthropic_model=config.llm.anthropic_model,
            max_tokens=config.llm.max_tokens,
            temperature=config.llm.temperature,
            timeout_s=config.llm.timeout_s,
            max_retries=config.llm.max_retries,
            research_enabled=config.llm.research_enabled,
            priority_bonus=config.llm.priority_bonus,
        ),
    )


@router.get("/config", response_model=ConfigResponse)
def get_config_endpoint(
    config: AppConfig = Depends(get_config),
) -> ConfigResponse:
    """Return the current application configuration.

    Returns:
        ConfigResponse reflecting all current settings.
    """
    return _config_to_response(config)


@router.put("/config", response_model=ConfigResponse)
def update_config(
    update: ConfigUpdateRequest,
    config: AppConfig = Depends(get_config),
) -> ConfigResponse:
    """Apply a partial update to the application configuration.

    Changes are applied to the in-memory config for the duration of
    this request. They are not persisted to disk automatically; users
    should manage the TOML file directly for permanent changes.

    Args:
        update: Partial config update with optional section overrides.

    Returns:
        ConfigResponse reflecting the updated configuration.
    """
    if update.constraints is not None:
        for field_name, value in update.constraints.model_dump(exclude_none=True).items():
            setattr(config.constraints, field_name, value)

    if update.pricing is not None:
        for field_name, value in update.pricing.model_dump(exclude_none=True).items():
            setattr(config.pricing, field_name, value)

    if update.general is not None:
        for field_name, value in update.general.model_dump(exclude_none=True).items():
            setattr(config.general, field_name, value)

    if update.llm is not None:
        for field_name, value in update.llm.model_dump(exclude_none=True).items():
            setattr(config.llm, field_name, value)

    return _config_to_response(config)
