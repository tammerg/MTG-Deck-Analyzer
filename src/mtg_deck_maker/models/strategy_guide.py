"""Strategy guide data models for post-build deck analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HandSample:
    """A single simulated opening hand."""

    cards: list[str]
    land_count: int
    ramp_count: int
    avg_cmc: float
    has_win_enabler: bool
    keep_recommendation: bool
    reason: str


@dataclass(slots=True)
class HandSimulationResult:
    """Aggregate results from Monte Carlo opening hand simulation."""

    total_simulations: int
    keep_rate: float
    avg_land_count: float
    avg_ramp_count: float
    avg_cmc_in_hand: float
    sample_hands: list[HandSample] = field(default_factory=list)
    mulligan_advice: str = ""


@dataclass(slots=True)
class WinPath:
    """A win condition path the deck can pursue."""

    name: str
    cards: list[str]
    description: str
    combo_id: str | None = None


@dataclass(slots=True)
class GamePhase:
    """Guidance for a phase of the game."""

    phase_name: str
    turn_range: str
    priorities: list[str]
    key_cards: list[str]
    description: str


@dataclass(slots=True)
class KeySynergy:
    """A synergistic card pair in the deck."""

    card_a: str
    card_b: str
    reason: str


@dataclass(slots=True)
class StrategyGuide:
    """Top-level strategy guide container for a deck."""

    archetype: str
    themes: list[str]
    win_paths: list[WinPath] = field(default_factory=list)
    game_phases: list[GamePhase] = field(default_factory=list)
    hand_simulation: HandSimulationResult | None = None
    key_synergies: list[KeySynergy] = field(default_factory=list)
    llm_narrative: str | None = None
