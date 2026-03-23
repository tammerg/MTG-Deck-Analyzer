"""Pydantic schemas for research-related API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mtg_deck_maker.api.web.schemas.deck import ProviderLiteral


class ResearchRequest(BaseModel):
    """Request body for commander research."""

    commander: str = Field(min_length=1, max_length=200)
    budget: float | None = None
    provider: ProviderLiteral = "auto"


class ResearchResponse(BaseModel):
    """Response schema for commander research."""

    commander_name: str
    strategy_overview: str
    key_cards: list[str]
    budget_staples: list[str]
    combos: list[str]
    win_conditions: list[str]
    cards_to_avoid: list[str]
    parse_success: bool
