"""Color identity helpers for Magic: The Gathering mana and color operations."""

from __future__ import annotations

import re

# WUBRG: The canonical color order in Magic
WUBRG = ["W", "U", "B", "R", "G"]

# Map of single-letter color codes to full names
COLOR_NAME_MAP: dict[str, str] = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
}

# Reverse map: full name to code
NAME_TO_COLOR: dict[str, str] = {v: k for k, v in COLOR_NAME_MAP.items()}

# Mana symbol pattern: matches {W}, {U}, {B}, {R}, {G} and hybrid symbols
_MANA_SYMBOL_RE = re.compile(r"\{([WUBRGC/]+)\}")


def parse_color_identity(mana_cost_string: str) -> list[str]:
    """Parse color identity from a mana cost string.

    Extracts color characters from mana cost notation like "{2}{W}{U}"
    and returns them in WUBRG order.

    Handles:
    - Standard symbols: {W}, {U}, {B}, {R}, {G}
    - Hybrid symbols: {W/U}, {B/G}, etc.
    - Colorless/generic: {1}, {2}, {C}, {X} (ignored)

    Args:
        mana_cost_string: Mana cost string in {X} notation.

    Returns:
        Sorted list of unique color characters in WUBRG order.
    """
    if not mana_cost_string:
        return []

    colors: set[str] = set()
    matches = _MANA_SYMBOL_RE.findall(mana_cost_string)

    for match in matches:
        # Handle hybrid symbols like "W/U" -> ["W", "U"]
        parts = match.split("/")
        for part in parts:
            part = part.strip()
            if part in WUBRG:
                colors.add(part)

    return _sort_wubrg(list(colors))


def union_color_identities(identities: list[list[str]]) -> list[str]:
    """Compute the union of multiple color identities.

    Args:
        identities: List of color identity lists to merge.

    Returns:
        Sorted union of all colors in WUBRG order.
    """
    result: set[str] = set()
    for identity in identities:
        result.update(identity)
    return _sort_wubrg(list(result))


def is_within_identity(
    card_colors: list[str], commander_identity: list[str]
) -> bool:
    """Check if a card's color identity fits within a commander's identity.

    A card can be included in a deck if every color in the card's color
    identity is present in the commander's color identity.

    Special case: colorless cards (empty identity) fit in any deck.

    Args:
        card_colors: The card's color identity.
        commander_identity: The commander's color identity.

    Returns:
        True if the card is within the commander's color identity.
    """
    if not card_colors:
        return True
    return set(card_colors).issubset(set(commander_identity))


def color_identity_to_name(identity: list[str]) -> str:
    """Convert a color identity to a human-readable name.

    Examples:
        [] -> "Colorless"
        ["W"] -> "White"
        ["W", "U"] -> "Azorius"
        ["W", "U", "B", "R", "G"] -> "Five-Color"

    Args:
        identity: List of color characters.

    Returns:
        Human-readable color combination name.
    """
    sorted_id = _sort_wubrg(identity)
    key = "".join(sorted_id)

    guild_names: dict[str, str] = {
        "": "Colorless",
        "W": "White",
        "U": "Blue",
        "B": "Black",
        "R": "Red",
        "G": "Green",
        "WU": "Azorius",
        "WB": "Orzhov",
        "UB": "Dimir",
        "UR": "Izzet",
        "BR": "Rakdos",
        "BG": "Golgari",
        "RG": "Gruul",
        "WR": "Boros",
        "WG": "Selesnya",
        "UG": "Simic",
        "WUB": "Esper",
        "WUR": "Jeskai",
        "WUG": "Bant",
        "WBR": "Mardu",
        "WBG": "Abzan",
        "WRG": "Naya",
        "UBR": "Grixis",
        "UBG": "Sultai",
        "URG": "Temur",
        "BRG": "Jund",
        "WUBR": "Yore-Tiller",
        "WUBG": "Witch-Maw",
        "WURG": "Ink-Treader",
        "WBRG": "Dune-Brood",
        "UBRG": "Glint-Eye",
        "WUBRG": "Five-Color",
    }

    return guild_names.get(key, f"Custom ({key})")


def _sort_wubrg(colors: list[str]) -> list[str]:
    """Sort a list of color characters in WUBRG order.

    Args:
        colors: List of color characters to sort.

    Returns:
        Sorted list in WUBRG order.
    """
    order = {c: i for i, c in enumerate(WUBRG)}
    return sorted(set(colors), key=lambda c: order.get(c, 99))
