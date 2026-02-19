"""Deck analysis engine for evaluating Commander deck composition.

Identifies weaknesses, generates mana curve analysis, color distribution,
and produces actionable text recommendations for deck improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mtg_deck_maker.engine.categories import Category, categorize_card
from mtg_deck_maker.engine.power_level import (
    analyze_deck_composition,
    estimate_power_level,
)
from mtg_deck_maker.models.card import Card

# Minimum thresholds for a healthy Commander deck
_MIN_RAMP = 8
_MIN_CARD_DRAW = 8
_MIN_REMOVAL = 5
_MIN_BOARD_WIPES = 2
_IDEAL_AVG_CMC_LOW = 2.0
_IDEAL_AVG_CMC_HIGH = 3.5


@dataclass(slots=True)
class DeckAnalysis:
    """Complete analysis of a Commander deck's composition and health."""

    category_breakdown: dict[str, int] = field(default_factory=dict)
    mana_curve: dict[int, int] = field(default_factory=dict)
    color_distribution: dict[str, int] = field(default_factory=dict)
    avg_cmc: float = 0.0
    weak_categories: list[str] = field(default_factory=list)
    strong_categories: list[str] = field(default_factory=list)
    total_price: float = 0.0
    power_level: int = 1
    recommendations: list[str] = field(default_factory=list)


def _compute_color_distribution(cards: list[Card]) -> dict[str, int]:
    """Count cards per color across the deck.

    Each card contributes to all its colors. Colorless cards are counted
    under the "Colorless" key.

    Args:
        cards: List of cards to analyze.

    Returns:
        Dict mapping color name to card count.
    """
    distribution: dict[str, int] = {}
    for card in cards:
        if not card.colors:
            distribution["Colorless"] = distribution.get("Colorless", 0) + 1
        else:
            for color in card.colors:
                distribution[color] = distribution.get(color, 0) + 1
    return distribution


def _identify_weak_categories(category_counts: dict[str, int]) -> list[str]:
    """Identify categories that fall below recommended minimums.

    Args:
        category_counts: Dict mapping category name to card count.

    Returns:
        List of category names that are below minimum thresholds.
    """
    weak: list[str] = []

    ramp_count = category_counts.get(Category.RAMP.value, 0)
    if ramp_count < _MIN_RAMP:
        weak.append(Category.RAMP.value)

    draw_count = category_counts.get(Category.CARD_DRAW.value, 0)
    if draw_count < _MIN_CARD_DRAW:
        weak.append(Category.CARD_DRAW.value)

    removal_count = category_counts.get(Category.REMOVAL.value, 0)
    if removal_count < _MIN_REMOVAL:
        weak.append(Category.REMOVAL.value)

    wipe_count = category_counts.get(Category.BOARD_WIPE.value, 0)
    if wipe_count < _MIN_BOARD_WIPES:
        weak.append(Category.BOARD_WIPE.value)

    return weak


def _identify_strong_categories(category_counts: dict[str, int]) -> list[str]:
    """Identify categories that are well above recommended minimums.

    A category is considered strong if it has at least 150% of the minimum
    threshold.

    Args:
        category_counts: Dict mapping category name to card count.

    Returns:
        List of category names that are strong.
    """
    strong: list[str] = []
    thresholds = {
        Category.RAMP.value: _MIN_RAMP,
        Category.CARD_DRAW.value: _MIN_CARD_DRAW,
        Category.REMOVAL.value: _MIN_REMOVAL,
        Category.BOARD_WIPE.value: _MIN_BOARD_WIPES,
    }

    for cat, minimum in thresholds.items():
        count = category_counts.get(cat, 0)
        if count >= minimum * 1.5:
            strong.append(cat)

    return strong


def _generate_recommendations(
    category_counts: dict[str, int],
    avg_cmc: float,
    mana_curve: dict[int, int],
    weak_categories: list[str],
) -> list[str]:
    """Generate actionable text recommendations based on deck weaknesses.

    Args:
        category_counts: Dict mapping category name to card count.
        avg_cmc: Average converted mana cost of non-land cards.
        mana_curve: Histogram of CMC values.
        weak_categories: List of weak category names.

    Returns:
        List of recommendation strings.
    """
    recommendations: list[str] = []

    ramp_count = category_counts.get(Category.RAMP.value, 0)
    if Category.RAMP.value in weak_categories:
        deficit = _MIN_RAMP - ramp_count
        recommendations.append(
            f"Add {deficit} more ramp source(s). "
            f"You have {ramp_count}, aim for at least {_MIN_RAMP}. "
            "Consider Sol Ring, Arcane Signet, or Cultivate."
        )

    draw_count = category_counts.get(Category.CARD_DRAW.value, 0)
    if Category.CARD_DRAW.value in weak_categories:
        deficit = _MIN_CARD_DRAW - draw_count
        recommendations.append(
            f"Add {deficit} more card draw source(s). "
            f"You have {draw_count}, aim for at least {_MIN_CARD_DRAW}. "
            "Consider Rhystic Study, Beast Whisperer, or Night's Whisper."
        )

    removal_count = category_counts.get(Category.REMOVAL.value, 0)
    if Category.REMOVAL.value in weak_categories:
        deficit = _MIN_REMOVAL - removal_count
        recommendations.append(
            f"Add {deficit} more targeted removal spell(s). "
            f"You have {removal_count}, aim for at least {_MIN_REMOVAL}. "
            "Consider Swords to Plowshares, Beast Within, or Generous Gift."
        )

    wipe_count = category_counts.get(Category.BOARD_WIPE.value, 0)
    if Category.BOARD_WIPE.value in weak_categories:
        deficit = _MIN_BOARD_WIPES - wipe_count
        if wipe_count == 0:
            recommendations.append(
                "Your deck has no board wipes. "
                f"Add at least {_MIN_BOARD_WIPES}. "
                "Consider Wrath of God, Blasphemous Act, or Cyclonic Rift."
            )
        else:
            recommendations.append(
                f"Add {deficit} more board wipe(s). "
                f"You have {wipe_count}, aim for at least {_MIN_BOARD_WIPES}."
            )

    if avg_cmc > _IDEAL_AVG_CMC_HIGH:
        recommendations.append(
            f"Your average CMC is {avg_cmc:.2f}, which is high. "
            f"Consider lowering it to {_IDEAL_AVG_CMC_HIGH} or below "
            "by replacing expensive spells with cheaper alternatives."
        )
    elif avg_cmc < _IDEAL_AVG_CMC_LOW:
        recommendations.append(
            f"Your average CMC is {avg_cmc:.2f}, which is very low. "
            "Make sure you have enough impactful spells for the late game."
        )

    # Check mana curve distribution for heavy top-end
    high_cmc_count = sum(
        count for cmc_val, count in mana_curve.items() if cmc_val >= 6
    )
    total_nonland = sum(mana_curve.values())
    if total_nonland > 0 and high_cmc_count / total_nonland > 0.20:
        recommendations.append(
            "Over 20% of your non-land cards cost 6+ mana. "
            "Consider trimming some high-cost cards for a smoother curve."
        )

    return recommendations


def analyze_deck(
    cards: list[Card],
    categories: dict[int, list[tuple[str, float]]],
) -> DeckAnalysis:
    """Perform a comprehensive analysis of a Commander deck.

    Combines category breakdown, mana curve, color distribution, and
    weakness detection into a single DeckAnalysis result.

    Args:
        cards: List of all Card objects in the deck.
        categories: Dict mapping card key (card.id or negative index) to
            list of (category, confidence) tuples, as returned by
            bulk_categorize.

    Returns:
        DeckAnalysis with all computed metrics and recommendations.
    """
    composition = analyze_deck_composition(cards, categories)

    category_counts = composition["category_counts"]
    mana_curve = composition["mana_curve"]
    avg_cmc = composition["average_cmc"]

    color_dist = _compute_color_distribution(cards)
    weak_cats = _identify_weak_categories(category_counts)
    strong_cats = _identify_strong_categories(category_counts)

    # Compute total price from card data (DeckCard prices not available here,
    # so we default to 0.0; callers can set total_price after construction)
    total_price = 0.0

    power_data = dict(composition)
    power_data["total_price"] = total_price
    power_level = estimate_power_level(power_data)

    recommendations = _generate_recommendations(
        category_counts, avg_cmc, mana_curve, weak_cats
    )

    return DeckAnalysis(
        category_breakdown=category_counts,
        mana_curve=mana_curve,
        color_distribution=color_dist,
        avg_cmc=avg_cmc,
        weak_categories=weak_cats,
        strong_categories=strong_cats,
        total_price=total_price,
        power_level=power_level,
        recommendations=recommendations,
    )
