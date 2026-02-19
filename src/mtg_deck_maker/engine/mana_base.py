"""Mana base builder for Commander deck construction.

Handles land count calculation, basic land distribution based on color pip
ratios, and budget-aware land selection across tiers.
"""

from __future__ import annotations

import re

from mtg_deck_maker.models.card import Card

# Regex to extract colored mana pips from mana cost strings
_COLOR_PIP_RE = re.compile(r"\{([WUBRG/]+)\}")

# Base land counts by number of colors in identity
_BASE_LAND_COUNTS: dict[int, int] = {
    0: 36,  # Colorless
    1: 34,  # Mono
    2: 35,  # 2-color
    3: 36,  # 3-color
    4: 36,  # 4-color
    5: 37,  # 5-color
}

# Budget tier thresholds (USD) and the land quality available at each tier
BUDGET_TIER_TAPLANDS = 50.0
BUDGET_TIER_PAINLANDS = 150.0
BUDGET_TIER_SHOCKLANDS = 300.0
BUDGET_TIER_FETCHLANDS = 300.0  # Fetch lands unlock at $300+


def calculate_land_count(
    color_identity: list[str],
    ramp_count: int = 0,
    avg_cmc: float = 3.0,
) -> int:
    """Calculate the recommended number of lands for a Commander deck.

    Base count is determined by the number of colors. Adjustments are
    made for ramp density and average converted mana cost.

    Args:
        color_identity: List of color characters in the commander's identity.
        ramp_count: Number of ramp cards in the deck.
        avg_cmc: Average converted mana cost of non-land cards.

    Returns:
        Recommended land count (integer).
    """
    num_colors = len(color_identity)
    base = _BASE_LAND_COUNTS.get(num_colors, 36)

    # Ramp adjustment: -1 per 4 ramp cards above 8
    ramp_adjustment = 0
    if ramp_count > 8:
        ramp_adjustment = -((ramp_count - 8) // 4)

    # CMC adjustment
    cmc_adjustment = 0
    if avg_cmc > 3.5:
        cmc_adjustment = 1
    elif avg_cmc < 2.5:
        cmc_adjustment = -1

    result = base + ramp_adjustment + cmc_adjustment

    # Ensure a reasonable minimum and maximum
    return max(28, min(42, result))


def calculate_basic_land_distribution(
    color_pips: dict[str, int], total_basics: int
) -> dict[str, int]:
    """Distribute basic lands proportionally to color pip requirements.

    Args:
        color_pips: Dict mapping color character to pip count
            (e.g., {"W": 10, "U": 6}).
        total_basics: Total number of basic lands to distribute.

    Returns:
        Dict mapping color to number of basic lands of that type.
        If no pip data, distributes evenly.
    """
    if not color_pips or total_basics <= 0:
        return {}

    total_pips = sum(color_pips.values())
    if total_pips == 0:
        # Even distribution
        colors = list(color_pips.keys())
        if not colors:
            return {}
        per_color = total_basics // len(colors)
        remainder = total_basics % len(colors)
        distribution = {c: per_color for c in colors}
        # Distribute remainder to colors with most pips (alphabetically for ties)
        for i, color in enumerate(sorted(colors)):
            if i < remainder:
                distribution[color] += 1
        return distribution

    # Proportional distribution with rounding
    distribution: dict[str, int] = {}
    allocated = 0

    # Sort colors for deterministic behavior
    sorted_colors = sorted(color_pips.keys())

    for color in sorted_colors:
        pips = color_pips[color]
        exact = (pips / total_pips) * total_basics
        count = round(exact)
        distribution[color] = count
        allocated += count

    # Fix rounding errors
    diff = total_basics - allocated
    if diff != 0:
        # Add/remove from the color with the largest fractional remainder
        remainders = []
        for color in sorted_colors:
            pips = color_pips[color]
            exact = (pips / total_pips) * total_basics
            frac = exact - int(exact)
            remainders.append((frac, color))

        if diff > 0:
            # Need more lands - add to colors with largest fractional parts
            remainders.sort(key=lambda x: x[0], reverse=True)
            for i in range(abs(diff)):
                color = remainders[i % len(remainders)][1]
                distribution[color] += 1
        else:
            # Need fewer lands - remove from colors with smallest fractional parts
            remainders.sort(key=lambda x: x[0])
            for i in range(abs(diff)):
                color = remainders[i % len(remainders)][1]
                if distribution[color] > 0:
                    distribution[color] -= 1

    return distribution


def count_color_pips(cards: list[Card]) -> dict[str, int]:
    """Count color pips across all non-land cards' mana costs.

    Args:
        cards: List of cards to analyze.

    Returns:
        Dict mapping color character to total pip count.
    """
    pips: dict[str, int] = {}

    for card in cards:
        if card.is_land or not card.mana_cost:
            continue

        matches = _COLOR_PIP_RE.findall(card.mana_cost)
        for match in matches:
            # Handle hybrid symbols like "W/U"
            parts = match.split("/")
            for part in parts:
                part = part.strip()
                if part in ("W", "U", "B", "R", "G"):
                    pips[part] = pips.get(part, 0) + 1

    return pips


def _is_command_tower(card: Card) -> bool:
    """Check if a card is Command Tower."""
    return card.name == "Command Tower"


def _classify_land_tier(card: Card) -> str:
    """Classify a land into a budget tier category.

    Returns a tier label used for budget-aware selection.
    This is a simplified heuristic based on common land naming patterns.

    Args:
        card: A land card to classify.

    Returns:
        One of: "basic", "tapland", "painland", "checkland",
        "shockland", "filterland", "fetchland", "command_tower", "utility".
    """
    name = card.name.lower()
    oracle = (card.oracle_text or "").lower()

    if card.name == "Command Tower":
        return "command_tower"

    # Basic lands
    basic_names = {"plains", "island", "swamp", "mountain", "forest"}
    if name in basic_names:
        return "basic"
    # Snow basics
    if name.startswith("snow-covered "):
        return "basic"

    # Fetch lands: "search your library for a" in oracle + sacrifice
    if "search your library" in oracle and "sacrifice" in oracle:
        return "fetchland"

    # Shock lands: "enters the battlefield" + "pay 2 life"
    if "pay 2 life" in oracle and "enters the battlefield" in oracle:
        return "shockland"

    # Pain lands: "deals 1 damage to you"
    if "deals 1 damage to you" in oracle:
        return "painland"

    # Check lands: "enters the battlefield tapped unless you control"
    if "unless you control" in oracle:
        return "checkland"

    # Filter lands: "Add two mana in any combination"
    if "any combination" in oracle and "add" in oracle:
        return "filterland"

    # Tap lands: "enters the battlefield tapped"
    if "enters the battlefield tapped" in oracle:
        return "tapland"

    return "utility"


def _budget_allows_tier(budget: float, tier: str) -> bool:
    """Check if the budget allows a given land tier.

    Args:
        budget: Total deck budget in USD.
        tier: Land tier classification.

    Returns:
        True if the tier is allowed at this budget level.
    """
    if tier in ("basic", "command_tower", "utility"):
        return True
    if tier == "tapland":
        return True  # Always available
    if tier in ("painland", "checkland"):
        return budget >= BUDGET_TIER_PAINLANDS
    if tier in ("shockland", "filterland"):
        return budget >= BUDGET_TIER_SHOCKLANDS
    if tier == "fetchland":
        return budget >= BUDGET_TIER_FETCHLANDS
    return True


def build_mana_base(
    color_identity: list[str],
    num_lands: int,
    budget: float,
    available_lands: list[Card],
) -> list[Card]:
    """Build a mana base from available lands, respecting budget constraints.

    Selects lands appropriate for the color identity and budget tier,
    prioritizing untapped sources at higher budgets and filling remaining
    slots with basic lands proportional to color pip requirements.

    Args:
        color_identity: Commander's color identity.
        num_lands: Target number of lands.
        budget: Total deck budget in USD.
        available_lands: Pool of available land cards to select from.

    Returns:
        List of selected land Cards for the mana base.
    """
    selected: list[Card] = []
    is_multicolor = len(color_identity) > 1

    # Step 1: Always include Command Tower for multicolor
    for land in available_lands:
        if _is_command_tower(land) and is_multicolor:
            selected.append(land)
            break

    # Step 2: Select non-basic lands within budget tier
    selected_names: set[str] = {c.name for c in selected}
    nonbasic_candidates: list[Card] = []

    for land in available_lands:
        if land.name in selected_names:
            continue
        # Skip Command Tower for non-multicolor decks
        if _is_command_tower(land) and not is_multicolor:
            continue
        tier = _classify_land_tier(land)
        if tier == "basic":
            continue
        if not _budget_allows_tier(budget, tier):
            continue
        # Ensure the land is relevant to our colors
        if land.color_identity and not set(land.color_identity).issubset(
            set(color_identity)
        ):
            continue
        nonbasic_candidates.append(land)

    # Add nonbasic lands (up to a limit, leaving room for basics)
    max_nonbasics = num_lands // 2  # At most half the mana base as nonbasics
    for land in nonbasic_candidates[:max_nonbasics]:
        if len(selected) >= num_lands:
            break
        if land.name not in selected_names:
            selected.append(land)
            selected_names.add(land.name)

    # Step 3: Fill remaining slots with basic lands
    basics_needed = num_lands - len(selected)

    if basics_needed > 0 and color_identity:
        # Create placeholder basic land cards proportional to color pips
        # In real usage, actual basic land Card objects would be in available_lands
        basic_map = {
            "W": "Plains",
            "U": "Island",
            "B": "Swamp",
            "R": "Mountain",
            "G": "Forest",
        }

        # Look for basic lands in available_lands
        available_basics: dict[str, Card] = {}
        for land in available_lands:
            if land.name in basic_map.values():
                available_basics[land.name] = land

        # If no pip data, distribute evenly by color identity
        pip_counts = {c: 1 for c in color_identity}
        distribution = calculate_basic_land_distribution(pip_counts, basics_needed)

        for color, count in distribution.items():
            basic_name = basic_map.get(color, "")
            if basic_name and basic_name in available_basics:
                for _ in range(count):
                    selected.append(available_basics[basic_name])
            elif basic_name:
                # Create a minimal basic land Card if not in available pool
                for _ in range(count):
                    basic = Card(
                        oracle_id=f"basic-{basic_name.lower()}",
                        name=basic_name,
                        type_line="Basic Land",
                        oracle_text="",
                        mana_cost="",
                        cmc=0.0,
                        colors=[],
                        color_identity=[],
                        keywords=[],
                    )
                    selected.append(basic)
    elif basics_needed > 0:
        # Colorless deck: add Wastes or utility lands
        for _ in range(basics_needed):
            wastes = Card(
                oracle_id="basic-wastes",
                name="Wastes",
                type_line="Basic Land",
                oracle_text="{T}: Add {C}.",
                mana_cost="",
                cmc=0.0,
                colors=[],
                color_identity=[],
                keywords=[],
            )
            selected.append(wastes)

    return selected[:num_lands]
