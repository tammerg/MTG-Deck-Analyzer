"""Pydantic schemas for research-related API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Request body for commander research."""

    commander: str
    budget: float | None = None
    provider: str = "auto"


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
