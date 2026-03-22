"""Scored candidate model for deck building engine pipeline.

Replaces untyped dicts that previously threaded card scoring data
through the deck builder and budget optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass

from mtg_deck_maker.models.card import Card


@dataclass(slots=True)
class ScoredCandidate:
    """A card with its computed scores and metadata for deck selection.

    Produced by the deck builder scoring pipeline and consumed by the
    budget optimizer during card selection.

    Attributes:
        card: The underlying Card object.
        card_id: Stable identifier (Card.id or fallback object id).
        score: Final composite score (synergy * power / price_weight + bonuses).
        price: Card price in USD.
        category: Primary functional category assignment.
        synergy: Raw synergy score from the synergy engine.
        power: Power/quality score derived from EDHREC data and confidence.
    """

    card: Card
    card_id: int
    score: float
    price: float
    category: str
    synergy: float = 0.0
    power: float = 0.0
