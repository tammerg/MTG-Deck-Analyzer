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


# ---------------------------------------------------------------------------
# Strategy Guide schemas
# ---------------------------------------------------------------------------


class StrategyGuideRequest(BaseModel):
    """Request body for generating a strategy guide."""

    provider: str = "auto"
    num_simulations: int = 1000
    seed: int = 42


class HandSampleResponse(BaseModel):
    """A single simulated opening hand."""

    cards: list[str]
    land_count: int
    ramp_count: int
    avg_cmc: float
    has_win_enabler: bool
    keep_recommendation: bool
    reason: str


class HandSimulationResponse(BaseModel):
    """Aggregate opening hand simulation results."""

    total_simulations: int
    keep_rate: float
    avg_land_count: float
    avg_ramp_count: float
    avg_cmc_in_hand: float
    sample_hands: list[HandSampleResponse]
    mulligan_advice: str


class WinPathResponse(BaseModel):
    """A win condition path."""

    name: str
    cards: list[str]
    description: str
    combo_id: str | None = None


class GamePhaseResponse(BaseModel):
    """Guidance for a game phase."""

    phase_name: str
    turn_range: str
    priorities: list[str]
    key_cards: list[str]
    description: str


class KeySynergyResponse(BaseModel):
    """A synergistic card pair."""

    card_a: str
    card_b: str
    reason: str


class StrategyGuideResponse(BaseModel):
    """Complete strategy guide response."""

    archetype: str
    themes: list[str]
    win_paths: list[WinPathResponse]
    game_phases: list[GamePhaseResponse]
    hand_simulation: HandSimulationResponse | None = None
    key_synergies: list[KeySynergyResponse]
    llm_narrative: str | None = None
