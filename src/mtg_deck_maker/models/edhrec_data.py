"""EDHREC per-commander card inclusion data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EdhrecCommanderData:
    """Per-commander card inclusion data from EDHREC.

    Represents how frequently a specific card appears in decks built
    around a particular commander on EDHREC.

    Attributes:
        commander_name: The commander this data is associated with.
        card_name: The card name this inclusion data is for.
        inclusion_rate: Fraction of decks running this card (0.0 to 1.0).
        num_decks: Number of decks running this card.
        potential_decks: Total decks for this commander on EDHREC.
        synergy_score: EDHREC's own synergy metric (default 0.0).
    """

    commander_name: str
    card_name: str
    inclusion_rate: float
    num_decks: int
    potential_decks: int
    synergy_score: float = 0.0
