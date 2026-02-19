"""Power level estimation for Commander decks.

Analyzes deck composition and assigns a power level on a 1-10 scale
based on factors like mana curve, interaction density, ramp, tutors,
and overall card quality.
"""

from __future__ import annotations

import re

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.engine.categories import Category

# Fast mana card names (partial list of the most impactful)
FAST_MANA_CARDS: set[str] = {
    "Sol Ring",
    "Mana Crypt",
    "Mana Vault",
    "Mox Diamond",
    "Chrome Mox",
    "Lotus Petal",
    "Jeweled Lotus",
    "Lion's Eye Diamond",
    "Grim Monolith",
    "Dark Ritual",
    "Cabal Ritual",
    "Simian Spirit Guide",
    "Elvish Spirit Guide",
}

# Mana pip regex for color pip distribution
_COLOR_PIP_RE = re.compile(r"\{([WUBRG])\}")


def analyze_deck_composition(
    cards: list[Card],
    categories: dict[int, list[tuple[str, float]]],
) -> dict:
    """Analyze a deck's composition and return detailed statistics.

    Args:
        cards: List of all cards in the deck.
        categories: Dict mapping card ID to list of (category, confidence)
            tuples, as returned by bulk_categorize.

    Returns:
        Dict with keys:
            - category_counts: dict[str, int] count of cards per category
            - average_cmc: float average CMC of non-land cards
            - mana_curve: dict[int, int] histogram of CMC values (0-7+)
            - color_pip_distribution: dict[str, int] pip counts by color
            - interaction_ratio: float (removal + counterspells) / total non-lands
            - ramp_ratio: float ramp cards / total non-lands
            - fast_mana_count: int number of fast mana cards
            - tutor_count: int number of tutor cards
            - total_cards: int
    """
    category_counts: dict[str, int] = {}
    mana_curve: dict[int, int] = {i: 0 for i in range(8)}  # 0 through 7+
    color_pips: dict[str, int] = {}
    non_land_count = 0
    total_cmc = 0.0
    fast_mana = 0
    tutor_count = 0
    interaction_count = 0
    ramp_count = 0

    for card in cards:
        card_key = card.id if card.id is not None else id(card)
        card_cats = categories.get(card_key, [])

        # Count categories
        for cat_name, _conf in card_cats:
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

        # Mana curve (non-land only)
        if not card.is_land:
            non_land_count += 1
            total_cmc += card.cmc
            cmc_bucket = min(7, int(card.cmc))
            mana_curve[cmc_bucket] = mana_curve.get(cmc_bucket, 0) + 1

        # Color pip distribution
        if card.mana_cost:
            for pip_match in _COLOR_PIP_RE.findall(card.mana_cost):
                color_pips[pip_match] = color_pips.get(pip_match, 0) + 1

        # Fast mana check
        if card.name in FAST_MANA_CARDS:
            fast_mana += 1

        # Tutor count
        cat_names = {c for c, _ in card_cats}
        if Category.TUTOR.value in cat_names:
            tutor_count += 1

        # Interaction count (removal + counterspells)
        if Category.REMOVAL.value in cat_names or Category.COUNTERSPELL.value in cat_names:
            interaction_count += 1

        # Ramp count
        if Category.RAMP.value in cat_names:
            ramp_count += 1

    average_cmc = total_cmc / non_land_count if non_land_count > 0 else 0.0
    interaction_ratio = interaction_count / non_land_count if non_land_count > 0 else 0.0
    ramp_ratio = ramp_count / non_land_count if non_land_count > 0 else 0.0

    return {
        "category_counts": category_counts,
        "average_cmc": round(average_cmc, 2),
        "mana_curve": mana_curve,
        "color_pip_distribution": color_pips,
        "interaction_ratio": round(interaction_ratio, 3),
        "ramp_ratio": round(ramp_ratio, 3),
        "fast_mana_count": fast_mana,
        "tutor_count": tutor_count,
        "total_cards": len(cards),
    }


def estimate_power_level(deck_analysis: dict) -> int:
    """Estimate a Commander deck's power level on a 1-10 scale.

    Higher scores indicate more competitive/optimized decks.

    Factors considered:
        - Average CMC (lower = higher power)
        - Interaction density (removal + counterspells)
        - Ramp density
        - Card draw density
        - Tutor count
        - Fast mana count
        - Total deck price (correlates with power)

    Args:
        deck_analysis: Dict as returned by analyze_deck_composition, with
            optional additional key "total_price" (float, USD).

    Returns:
        Integer power level from 1 to 10.
    """
    score = 0.0

    avg_cmc = deck_analysis.get("average_cmc", 3.5)
    interaction_ratio = deck_analysis.get("interaction_ratio", 0.0)
    ramp_ratio = deck_analysis.get("ramp_ratio", 0.0)
    fast_mana = deck_analysis.get("fast_mana_count", 0)
    tutor_count = deck_analysis.get("tutor_count", 0)
    total_price = deck_analysis.get("total_price", 0.0)
    category_counts = deck_analysis.get("category_counts", {})
    total_cards = deck_analysis.get("total_cards", 100)

    # CMC scoring (0-2 points): lower avg CMC = higher power
    if avg_cmc <= 2.0:
        score += 2.0
    elif avg_cmc <= 2.5:
        score += 1.5
    elif avg_cmc <= 3.0:
        score += 1.0
    elif avg_cmc <= 3.5:
        score += 0.5

    # Interaction density (0-1.5 points)
    if interaction_ratio >= 0.15:
        score += 1.5
    elif interaction_ratio >= 0.10:
        score += 1.0
    elif interaction_ratio >= 0.05:
        score += 0.5

    # Ramp density (0-1 point)
    if ramp_ratio >= 0.12:
        score += 1.0
    elif ramp_ratio >= 0.08:
        score += 0.5

    # Card draw density (0-1 point)
    draw_count = category_counts.get(Category.CARD_DRAW.value, 0)
    non_land = total_cards - category_counts.get(Category.LAND.value, 0)
    draw_ratio = draw_count / non_land if non_land > 0 else 0.0
    if draw_ratio >= 0.12:
        score += 1.0
    elif draw_ratio >= 0.08:
        score += 0.5

    # Tutor count (0-1.5 points)
    if tutor_count >= 5:
        score += 1.5
    elif tutor_count >= 3:
        score += 1.0
    elif tutor_count >= 1:
        score += 0.5

    # Fast mana (0-1.5 points)
    if fast_mana >= 4:
        score += 1.5
    elif fast_mana >= 2:
        score += 1.0
    elif fast_mana >= 1:
        score += 0.5

    # Total price correlation (0-1 point)
    if total_price >= 1000:
        score += 1.0
    elif total_price >= 500:
        score += 0.75
    elif total_price >= 250:
        score += 0.5
    elif total_price >= 100:
        score += 0.25

    # Convert raw score (0-9.5 max) to 1-10 scale
    power_level = max(1, min(10, round(score) + 1))
    return power_level
