"""Upgrade recommender for Commander decks.

Evaluates potential card swaps and ranks them by an upgrade score that
accounts for synergy improvement, power delta, and price efficiency.
"""

from __future__ import annotations

from dataclasses import dataclass

from mtg_deck_maker.engine.categories import Category, categorize_card
from mtg_deck_maker.engine.synergy import compute_synergy
from mtg_deck_maker.models.card import Card


@dataclass(slots=True)
class UpgradeRecommendation:
    """A single recommended card swap for a deck upgrade."""

    card_out: Card
    card_in: Card
    price_delta: float
    reason: str
    upgrade_score: float


def _compute_upgrade_score(
    old_synergy: float,
    new_synergy: float,
    old_cmc: float,
    new_cmc: float,
    new_price: float,
) -> float:
    """Compute the upgrade value score for a card swap.

    Formula: upgrade_value = (new_synergy - old_synergy) * power_delta / new_price

    The power_delta is approximated as a CMC efficiency bonus: cards with
    lower CMC for the same effect are considered more powerful.

    Args:
        old_synergy: Synergy score of the card being removed.
        new_synergy: Synergy score of the replacement card.
        old_cmc: CMC of the card being removed.
        new_cmc: CMC of the replacement card.
        new_price: Price of the replacement card in USD.

    Returns:
        Upgrade score (higher is better). Can be negative if downgrade.
    """
    synergy_delta = new_synergy - old_synergy

    # Power delta: favor cards that cost less mana or have higher synergy
    # Use a simple ratio: higher CMC reduction = more power
    power_delta = max(0.1, 1.0 + (old_cmc - new_cmc) * 0.1)

    # Avoid division by zero for free cards
    price_factor = max(0.01, new_price)

    return synergy_delta * power_delta / price_factor


def _build_swap_reason(
    card_out: Card,
    card_in: Card,
    out_cats: list[tuple[str, float]],
    in_cats: list[tuple[str, float]],
    focus: str | None,
) -> str:
    """Build a human-readable reason for a card swap.

    Args:
        card_out: The card being removed.
        card_in: The card being added.
        out_cats: Categories of the outgoing card.
        in_cats: Categories of the incoming card.
        focus: Optional focus area for upgrades.

    Returns:
        Explanation string for the swap.
    """
    in_cat_names = {c for c, _ in in_cats}
    out_cat_names = {c for c, _ in out_cats}

    new_roles = in_cat_names - out_cat_names
    if focus and focus in in_cat_names:
        return (
            f"Upgrades {focus}: {card_in.name} replaces {card_out.name} "
            f"for better {focus} support."
        )
    if new_roles:
        roles_str = ", ".join(sorted(new_roles))
        return (
            f"{card_in.name} adds {roles_str} role(s) that "
            f"{card_out.name} did not provide."
        )
    if card_in.cmc < card_out.cmc:
        return (
            f"{card_in.name} (CMC {card_in.cmc:g}) is more mana-efficient "
            f"than {card_out.name} (CMC {card_out.cmc:g})."
        )
    return (
        f"{card_in.name} has higher synergy with your commander "
        f"than {card_out.name}."
    )


def recommend_upgrades(
    deck_cards: list[Card],
    budget: float,
    card_pool: list[Card],
    categories: dict[int, list[tuple[str, float]]],
    prices: dict[str, float],
    commander: Card | None = None,
    focus: str | None = None,
) -> list[UpgradeRecommendation]:
    """Recommend card upgrades for a Commander deck.

    Evaluates each card in the deck against candidates from the card pool,
    scoring potential swaps by synergy improvement, power efficiency, and
    price. Supports an optional focus mode to prioritize specific categories.

    Args:
        deck_cards: List of Card objects currently in the deck.
        budget: Total budget available for upgrades in USD.
        card_pool: List of Card objects available as replacements.
        categories: Dict mapping card key to (category, confidence) tuples
            for deck cards (from bulk_categorize).
        prices: Dict mapping card name to price in USD.
        commander: Optional commander card for synergy computation.
            If None, synergy scoring is skipped.
        focus: Optional category to prioritize (e.g., "card_draw").

    Returns:
        List of UpgradeRecommendation sorted by upgrade_score descending,
        filtered to stay within the specified budget.
    """
    if not deck_cards or not card_pool:
        return []

    deck_names = {card.name for card in deck_cards}
    recommendations: list[UpgradeRecommendation] = []

    # Pre-categorize pool cards
    pool_categories: dict[str, list[tuple[str, float]]] = {}
    for card in card_pool:
        if card.name not in deck_names:
            pool_categories[card.name] = categorize_card(card)

    for deck_card in deck_cards:
        card_key = deck_card.id if deck_card.id is not None else id(deck_card)
        deck_card_cats = categories.get(card_key, categorize_card(deck_card))
        deck_cat_names = {c for c, _ in deck_card_cats}

        old_synergy = 0.0
        if commander is not None:
            old_synergy = compute_synergy(commander, deck_card)

        old_price = prices.get(deck_card.name, 0.0)

        for pool_card in card_pool:
            if pool_card.name in deck_names:
                continue

            pool_card_cats = pool_categories.get(
                pool_card.name, categorize_card(pool_card)
            )
            pool_cat_names = {c for c, _ in pool_card_cats}

            # If focus mode, only consider cards that serve the focus category
            if focus and focus not in pool_cat_names:
                continue

            new_price = prices.get(pool_card.name, 0.0)
            price_delta = new_price - old_price

            # Skip if this single swap exceeds budget
            if price_delta > budget:
                continue

            new_synergy = 0.0
            if commander is not None:
                new_synergy = compute_synergy(commander, pool_card)

            score = _compute_upgrade_score(
                old_synergy=old_synergy,
                new_synergy=new_synergy,
                old_cmc=deck_card.cmc,
                new_cmc=pool_card.cmc,
                new_price=max(0.01, new_price),
            )

            # Only recommend positive upgrades
            if score <= 0:
                continue

            reason = _build_swap_reason(
                deck_card, pool_card, deck_card_cats, pool_card_cats, focus
            )

            recommendations.append(
                UpgradeRecommendation(
                    card_out=deck_card,
                    card_in=pool_card,
                    price_delta=price_delta,
                    reason=reason,
                    upgrade_score=score,
                )
            )

    # Sort by upgrade_score descending
    recommendations.sort(key=lambda r: r.upgrade_score, reverse=True)

    # Filter to budget: greedily select upgrades that fit
    filtered: list[UpgradeRecommendation] = []
    remaining_budget = budget
    used_out: set[str] = set()
    used_in: set[str] = set()

    for rec in recommendations:
        if rec.card_out.name in used_out:
            continue
        if rec.card_in.name in used_in:
            continue
        if rec.price_delta > remaining_budget:
            continue

        filtered.append(rec)
        remaining_budget -= max(0, rec.price_delta)
        used_out.add(rec.card_out.name)
        used_in.add(rec.card_in.name)

    return filtered
