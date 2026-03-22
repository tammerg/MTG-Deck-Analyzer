"""Budget efficiency metric — measures quality per dollar spent."""

from __future__ import annotations

from dataclasses import dataclass, field

from mtg_deck_maker.models.deck import Deck, DeckCard


@dataclass(slots=True)
class BudgetEfficiencyResult:
    """Result of a budget efficiency analysis on a deck."""

    total_spent: float = 0.0
    budget_target: float | None = None
    budget_utilization: float | None = None
    avg_price_per_card: float = 0.0
    quality_per_dollar: float | None = None
    price_distribution: dict[str, int] = field(default_factory=dict)
    most_expensive: list[tuple[str, float]] = field(default_factory=list)


def _mainboard_nonland(deck: Deck) -> list[DeckCard]:
    """Return mainboard cards that are not lands, commanders, or companions."""
    return [
        card
        for card in deck.cards
        if not card.is_commander
        and not card.is_companion
        and card.category != "land"
    ]


def _price_bracket(price: float) -> str:
    """Classify a card price into a bracket name."""
    if price < 0.50:
        return "bulk"
    if price < 2.00:
        return "budget"
    if price < 10.00:
        return "mid"
    if price < 30.00:
        return "premium"
    return "chase"


def _build_price_distribution(cards: list[DeckCard]) -> dict[str, int]:
    """Count cards in each price bracket, respecting quantity."""
    dist: dict[str, int] = {
        "bulk": 0,
        "budget": 0,
        "mid": 0,
        "premium": 0,
        "chase": 0,
    }
    for card in cards:
        bracket = _price_bracket(card.price)
        dist[bracket] += card.quantity
    return dist


def _top_expensive(cards: list[DeckCard], n: int = 5) -> list[tuple[str, float]]:
    """Return up to *n* most expensive cards sorted by price descending."""
    # Expand by quantity so a 4x copy could appear multiple times,
    # but in Commander quantity is almost always 1.  We sort unique entries.
    expanded: list[tuple[str, float]] = []
    for card in cards:
        for _ in range(card.quantity):
            expanded.append((card.card_name, card.price))
    expanded.sort(key=lambda t: t[1], reverse=True)
    return expanded[:n]


def budget_efficiency(
    deck: Deck,
    edhrec_inclusion: dict[str, float] | None = None,
) -> BudgetEfficiencyResult:
    """Compute budget efficiency metrics for a deck.

    Parameters
    ----------
    deck:
        The deck to analyse.
    edhrec_inclusion:
        Optional mapping of card name -> EDHREC inclusion rate (0.0-1.0).
        When provided, ``quality_per_dollar`` is computed.

    Returns
    -------
    BudgetEfficiencyResult
    """
    cards = _mainboard_nonland(deck)

    total_spent = sum(c.price * c.quantity for c in cards)
    total_qty = sum(c.quantity for c in cards)

    avg_price = total_spent / total_qty if total_qty > 0 else 0.0

    # Budget utilization
    budget_target = deck.budget_target
    if budget_target is not None:
        budget_utilization: float | None = total_spent / budget_target if budget_target else 0.0
    else:
        budget_utilization = None

    # Quality per dollar
    quality_per_dollar: float | None = None
    if edhrec_inclusion is not None and total_qty > 0 and avg_price > 0:
        total_inclusion = 0.0
        for card in cards:
            rate = edhrec_inclusion.get(card.card_name, 0.0)
            total_inclusion += rate * card.quantity
        avg_inclusion = total_inclusion / total_qty
        quality_per_dollar = avg_inclusion / avg_price
    elif edhrec_inclusion is not None:
        quality_per_dollar = 0.0

    return BudgetEfficiencyResult(
        total_spent=total_spent,
        budget_target=budget_target,
        budget_utilization=budget_utilization,
        avg_price_per_card=avg_price,
        quality_per_dollar=quality_per_dollar,
        price_distribution=_build_price_distribution(cards),
        most_expensive=_top_expensive(cards),
    )
