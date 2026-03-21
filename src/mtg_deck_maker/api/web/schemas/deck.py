"""Pydantic schemas for deck-related API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeckBuildRequest(BaseModel):
    """Request body for building a new deck."""

    commander: str
    partner: str | None = None
    budget: float = Field(100.0, gt=0)
    seed: int = 42
    smart: bool = False
    provider: str = "auto"


class DeckCardResponse(BaseModel):
    """A single card entry in a deck response."""

    card_id: int
    quantity: int
    category: str
    is_commander: bool
    card_name: str
    cmc: float
    colors: list[str]
    price: float
    mana_cost: str
    type_line: str
    oracle_text: str
    image_url: str | None = None


class DeckResponse(BaseModel):
    """Response schema for a complete deck."""

    id: int | None
    name: str
    format: str
    budget_target: float | None
    created_at: str
    cards: list[DeckCardResponse]
    total_cards: int
    total_price: float
    average_cmc: float
    color_distribution: dict[str, int]
    commanders: list[DeckCardResponse]


class DeckExportRequest(BaseModel):
    """Request body for exporting a deck."""

    format: str = Field("csv", pattern="^(csv|moxfield|archidekt)$")


class DeckAdviseRequest(BaseModel):
    """Request body for getting deck advice."""

    question: str = "What improvements would you suggest for this deck?"
    provider: str = "auto"
