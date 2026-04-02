"""Pydantic schemas for the research API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from typing import Literal

ResearchProviderLiteral = Literal["auto", "openai", "anthropic", "data"]


class ResearchRequest(BaseModel):
    """Request body for commander research."""

    commander: str = Field(min_length=1, max_length=200)
    budget: float | None = None
    provider: ResearchProviderLiteral = "auto"


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
    source: Literal["llm", "data"] = "llm"
