"""Post-build synergy audit for deck-internal pairwise synergy analysis.

After a deck is built, this module computes pairwise synergy for all selected
nonland cards, identifies low-synergy outliers, and suggests swaps from the
remaining candidate pool to improve overall deck coherence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mtg_deck_maker.engine.synergy import compute_pairwise_synergy
from mtg_deck_maker.models.card import Card


@dataclass(slots=True)
class SynergyAuditResult:
    """Result of a post-build synergy audit."""

    avg_synergy: float
    low_synergy_cards: list[tuple[str, float]]
    suggested_swaps: list[tuple[str, str, float]]
    card_synergy_scores: dict[str, float] = field(default_factory=dict)


def _compute_card_synergy_map(cards: list[Card]) -> dict[str, float]:
    """Compute mean pairwise synergy for each card with all other cards.

    Args:
        cards: List of cards to evaluate.

    Returns:
        Dict mapping card name to its average pairwise synergy with the
        rest of the list.
    """
    n = len(cards)
    if n < 2:
        return {c.name: 0.0 for c in cards}

    # Accumulate pairwise scores per card
    totals: dict[str, float] = {c.name: 0.0 for c in cards}
    for i in range(n):
        for j in range(i + 1, n):
            score = compute_pairwise_synergy(cards[i], cards[j])
            totals[cards[i].name] += score
            totals[cards[j].name] += score

    # Each card has (n-1) pairs
    return {name: total / (n - 1) for name, total in totals.items()}


def _find_swap_candidates(
    outlier: Card,
    remaining_deck: list[Card],
    pool: list[Card],
    current_avg: float,
    max_candidates: int = 100,
) -> list[tuple[str, float]]:
    """Find pool cards that would improve synergy if swapped for the outlier.

    Args:
        outlier: The low-synergy card being considered for removal.
        remaining_deck: The deck minus the outlier.
        pool: Candidate cards not in the current deck.
        current_avg: The outlier's current average synergy with the deck.
        max_candidates: Maximum number of pool cards to evaluate.

    Returns:
        List of (candidate_name, synergy_improvement) tuples sorted by
        improvement descending. Only candidates that improve synergy are
        included.
    """
    if not remaining_deck or not pool:
        return []

    deck_count = len(remaining_deck)
    candidates: list[tuple[str, float]] = []

    for candidate in pool[:max_candidates]:
        total = 0.0
        for deck_card in remaining_deck:
            total += compute_pairwise_synergy(candidate, deck_card)
        candidate_avg = total / deck_count
        improvement = candidate_avg - current_avg
        if improvement > 0.0:
            candidates.append((candidate.name, improvement))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def audit_synergy(
    selected: list[Card],
    pool: list[Card],
    top_swap_count: int = 5,
) -> SynergyAuditResult:
    """Run a post-build synergy audit on a deck.

    Computes pairwise synergy for all cards in ``selected``, identifies
    low-synergy outliers, and suggests swaps from ``pool`` that would
    improve overall deck synergy.

    Args:
        selected: The cards currently in the deck (nonland).
        pool: Remaining candidate cards not in the deck.
        top_swap_count: Maximum number of swap suggestions to return.

    Returns:
        A ``SynergyAuditResult`` with synergy statistics and swap
        suggestions.
    """
    if len(selected) < 2:
        return SynergyAuditResult(
            avg_synergy=0.0,
            low_synergy_cards=[(c.name, 0.0) for c in selected],
            suggested_swaps=[],
            card_synergy_scores={c.name: 0.0 for c in selected},
        )

    # Step 1: compute per-card average synergy
    card_scores = _compute_card_synergy_map(selected)

    # Step 2: overall average synergy
    avg_synergy = sum(card_scores.values()) / len(card_scores)

    # Step 3: sort all cards ascending by synergy (lowest first)
    sorted_cards = sorted(card_scores.items(), key=lambda x: x[1])
    low_synergy_cards = sorted_cards  # all cards sorted ascending

    # Step 4: find swaps for the bottom outliers
    selected_names = {c.name for c in selected}
    filtered_pool = [c for c in pool if c.name not in selected_names]

    card_by_name: dict[str, Card] = {c.name: c for c in selected}
    suggested_swaps: list[tuple[str, str, float]] = []

    # Consider bottom cards as outlier candidates
    outlier_count = min(top_swap_count, len(sorted_cards))
    for outlier_name, outlier_avg in sorted_cards[:outlier_count]:
        outlier_card = card_by_name[outlier_name]
        remaining_deck = [c for c in selected if c.name != outlier_name]

        candidates = _find_swap_candidates(
            outlier_card,
            remaining_deck,
            filtered_pool,
            outlier_avg,
        )
        if candidates:
            best_name, best_improvement = candidates[0]
            suggested_swaps.append((outlier_name, best_name, best_improvement))

    # Sort swaps by improvement descending and limit
    suggested_swaps.sort(key=lambda x: x[2], reverse=True)
    suggested_swaps = suggested_swaps[:top_swap_count]

    return SynergyAuditResult(
        avg_synergy=avg_synergy,
        low_synergy_cards=low_synergy_cards,
        suggested_swaps=suggested_swaps,
        card_synergy_scores=card_scores,
    )
