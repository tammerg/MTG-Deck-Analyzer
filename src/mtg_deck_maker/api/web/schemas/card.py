"""Pydantic schemas for card-related API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


def _scryfall_image_url(scryfall_id: str) -> str:
    """Build the Scryfall image URL for a given scryfall_id."""
    return (
        f"https://cards.scryfall.io/normal/front/"
        f"{scryfall_id[0]}/{scryfall_id[1]}/{scryfall_id}.jpg"
    )


class CardResponse(BaseModel):
    """Response schema for a single card."""

    id: int
    oracle_id: str
    name: str
    type_line: str
    oracle_text: str
    mana_cost: str
    cmc: float
    colors: list[str]
    color_identity: list[str]
    keywords: list[str]
    edhrec_rank: int | None
    legal_commander: bool
    legal_brawl: bool
    updated_at: str
    image_url: str | None = None


class CardSearchResponse(BaseModel):
    """Response schema for card search with pagination metadata."""

    results: list[CardResponse]
    total: int


class CardSearchParams(BaseModel):
    """Query parameters for card search."""

    query: str = Field("", alias="q")
    color: str | None = None
    type: str | None = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
