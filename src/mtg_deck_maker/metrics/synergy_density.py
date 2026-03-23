"""Synergy density metric — average pairwise synergy for a deck."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from mtg_deck_maker.engine.categories import Category
from mtg_deck_maker.engine.synergy import compute_pairwise_synergy
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.deck import Deck

_LOW_SYNERGY_THRESHOLD = 0.1


@dataclass(slots=True)
class SynergyDensityResult:
    """Result of computing synergy density for a deck."""

    avg_synergy: float  # Mean pairwise synergy across all nonland pairs
    min_synergy: float  # Minimum pairwise synergy score found
    max_synergy: float  # Maximum pairwise synergy score found
    low_synergy_count: int  # Number of pairs with synergy below 0.1
    pair_count: int  # Total number of pairs evaluated
    card_count: int  # Number of nonland cards evaluated


def _zeroed_result(card_count: int = 0) -> SynergyDensityResult:
    """Return a zeroed result for edge cases with fewer than 2 cards."""
    return SynergyDensityResult(
        avg_synergy=0.0,
        min_synergy=0.0,
        max_synergy=0.0,
        low_synergy_count=0,
        pair_count=0,
        card_count=card_count,
    )


def synergy_density(
    deck: Deck,
    card_lookup: dict[str, Card],
) -> SynergyDensityResult:
    """Compute synergy density for a deck.

    Evaluates all pairwise synergy scores between nonland cards in the deck
    using compute_pairwise_synergy() from the synergy engine.

    Args:
        deck: The deck to analyze.
        card_lookup: Mapping of card name -> Card object for resolving
            DeckCard entries to full Card objects with oracle text.

    Returns:
        SynergyDensityResult with density statistics.
    """
    # Filter to nonland, non-commander, non-companion cards that exist in lookup
    cards: list[Card] = []
    for deck_card in deck.cards:
        if deck_card.is_commander or deck_card.is_companion:
            continue
        if deck_card.category == Category.LAND.value:
            continue
        full_card = card_lookup.get(deck_card.card_name)
        if full_card is not None:
            cards.append(full_card)

    if len(cards) < 2:
        return _zeroed_result(card_count=len(cards))

    total_synergy = 0.0
    min_synergy = float("inf")
    max_synergy = float("-inf")
    low_synergy_count = 0
    pair_count = 0

    for card_a, card_b in combinations(cards, 2):
        score = compute_pairwise_synergy(card_a, card_b)
        total_synergy += score
        pair_count += 1
        if score < min_synergy:
            min_synergy = score
        if score > max_synergy:
            max_synergy = score
        if score < _LOW_SYNERGY_THRESHOLD:
            low_synergy_count += 1

    avg_synergy = total_synergy / pair_count

    return SynergyDensityResult(
        avg_synergy=avg_synergy,
        min_synergy=min_synergy,
        max_synergy=max_synergy,
        low_synergy_count=low_synergy_count,
        pair_count=pair_count,
        card_count=len(cards),
    )
